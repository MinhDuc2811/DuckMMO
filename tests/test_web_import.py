import socket

import httpx
import pytest

from app.services import web_import
from app.services.web_import import ImportFailure, extract_page, public_addresses, validate_url
from app.worker import process_one
from tests.test_pipeline import client  # noqa: F401


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://[::1]",
        "http://169.254.169.254",
        "file:///tmp/x",
        "https://user:pass@any-site.test/a",
        "https://localhost/a",
        "https://example.com:999/a",
    ],
)
def test_rejects_private_or_invalid_urls(url):
    with pytest.raises(ImportFailure):
        validate_url(url)


@pytest.mark.parametrize(
    "url",
    ["https://example.com/article", "https://another-site.org/a", "http://news.example.net/story"],
)
def test_no_domain_allowlist(url):
    validate_url(url)


def test_dns_private_address_rejected(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))],
    )
    with pytest.raises(ImportFailure, match="nội bộ"):
        public_addresses("public-looking.example", 443)


def fixture_html():
    paragraphs = [
        "Đoạn truyện tự viết cho kiểm thử nhiều cấu trúc trang web. " * 5,
        "Đoạn cuối nói về hành trình và các nhân vật trong câu chuyện. " * 5,
    ]
    return (
        "<html><head><title>Chương mẫu</title></head><body><nav>MENU</nav><article>"
        + "".join(f"<p>{p}</p>" for p in paragraphs)
        + "</article><footer>FOOTER</footer></body></html>"
    )


def test_extract_generic_article():
    title, content = extract_page(fixture_html())
    assert title == "Chương mẫu"
    assert "Đoạn cuối" in content
    assert "MENU" not in content
    assert "FOOTER" not in content


def test_fetch_follows_redirect_and_preserves_headers(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "https://second.example/story"})
        return httpx.Response(200, text=fixture_html(), headers={"content-type": "text/html"})

    monkeypatch.setattr(web_import, "PublicWebTransport", lambda: httpx.MockTransport(handle))
    result = web_import.import_url("https://first.example/start")
    assert result["source_url"] == "https://second.example/story"
    assert "Đoạn cuối" in result["content"]
    assert len(requests) == 2
    assert "Mozilla" in requests[0].headers["User-Agent"]


def test_redirect_to_private_network_blocked(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    monkeypatch.setattr(web_import, "PublicWebTransport", lambda: httpx.MockTransport(handle))
    with pytest.raises(ImportFailure):
        web_import.import_url("https://first.example/start")
    assert len(requests) == 1


@pytest.mark.parametrize(
    "status,content_type,body,stage",
    [
        (403, "text/html", "forbidden", "http_status"),
        (200, "application/pdf", "pdf", "content_type"),
        (200, "text/html", "<html><body>Loading...</body></html>", "extract"),
    ],
)
def test_failure_stage_is_not_hidden(monkeypatch, status, content_type, body, stage):
    monkeypatch.setattr(
        web_import,
        "PublicWebTransport",
        lambda: httpx.MockTransport(
            lambda _: httpx.Response(status, text=body, headers={"content-type": content_type})
        ),
    )
    with pytest.raises(ImportFailure) as error:
        web_import.import_url("https://any-site.example/a")
    assert error.value.stage == stage


def test_multisource_phase1_then_review(client, monkeypatch):  # noqa: F811
    calls = []

    def imported(url):
        calls.append(url)
        return {"title": "Chương mẫu", "content": "Nội dung từ nguồn " + url, "source_url": url}

    monkeypatch.setattr("app.worker.import_url", imported)
    monkeypatch.setattr(
        "app.worker.analyse",
        lambda _: {
            "type": "ai",
            "ai_generated": True,
            "video_content": "Kịch bản sau phân tích",
            "summary": "Tóm tắt",
            "key_points": ["Ý chính"],
        },
    )
    response = client.post(
        "/api/import/web",
        json={
            "urls": ["https://first.example/story", "https://second.example/article"],
            "branch": "research",
        },
    )
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "queued"
    assert job["package"]["scenes"] == []
    assert calls == []  # HTTP endpoint queues; only Phase 1 worker fetches sources.
    review = {"decision": "approve", "reviewer": "User", "note": "Checked"}
    assert client.post(f"/api/jobs/{job['id']}/review", json=review).status_code == 409
    process_one(client.app.state.sessions)
    ready = client.get(f"/api/jobs/{job['id']}").json()
    assert ready["status"] == "awaiting_review"
    assert len(calls) == 2
    assert len(ready["package"]["source_documents"]) == 2
    assert ready["result"]["analysis"]["source_count"] == 2
    assert client.post(f"/api/jobs/{job['id']}/review", json=review).status_code == 200


def test_crawl_failure_blocks_phase2_and_retry_really_fetches(client, monkeypatch):  # noqa: F811
    def failed(_):
        raise ImportFailure("Website trả HTTP 403", "http_status")

    monkeypatch.setattr("app.worker.import_url", failed)
    job = client.post("/api/import/web", json={"url": "https://any-site.example/a"}).json()
    process_one(client.app.state.sessions)
    failed_job = client.get(f"/api/jobs/{job['id']}").json()
    assert failed_job["status"] == "failed"
    assert "http_status" in failed_job["error"]
    assert failed_job["package"]["source_documents"] == []
    monkeypatch.setattr(
        "app.worker.import_url",
        lambda url: {"title": "Recovered", "content": "Text now available", "source_url": url},
    )
    monkeypatch.setattr(
        "app.worker.analyse",
        lambda _: {"type": "ai", "ai_generated": True, "video_content": "Kịch bản sau phân tích"},
    )
    client.post(f"/api/jobs/{job['id']}/retry")
    process_one(client.app.state.sessions)
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "awaiting_review"
