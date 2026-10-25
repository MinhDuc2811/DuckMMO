import json

import httpx
import pytest

from app.pipeline.lifecycle import claim_one
from app.pipeline.runner import PipelineDependencies, execute_job
from app.services.analysis import AnalysisFailure, analyse
from app.services.preflight import preflight
from app.services.web_import import ImportFailure

REQUEST = {"keyword": "FC Online update", "target_date": "2026-10-23", "topic_path": ["news"]}


def test_discovery_crawl_analysis_retry_reuses_saved_sources(client):
    calls = []

    def discovery(request, **kwargs):
        kwargs["checkpoint"]()
        calls.append("discovery")
        return {"urls": ["https://source.example/a", "https://source.example/b"], "warnings": []}

    def crawl(url):
        calls.append(url)
        if url.endswith("/a"):
            raise ImportFailure("Unavailable", "http_status")
        return {"title": "Patch details", "source_url": url, "content": "Confirmed update details."}

    def unavailable(package):
        raise AnalysisFailure("AI unavailable")

    job = client.post("/api/import/keyword", json=REQUEST).json()
    sessions = client.app.state.sessions
    deps = PipelineDependencies(crawl, unavailable, preflight, lambda *args: None, discovery)
    execute_job(sessions, claim_one(sessions), deps)
    failed = client.get(f"/api/jobs/{job['id']}").json()
    assert failed["status"] == "failed"
    assert failed["package"]["sources"][0]["url"] == "https://source.example/b"
    assert failed["package"]["source_documents"][0]["content"] == "Confirmed update details."
    assert len(failed["package"]["discovery"]["crawl_warnings"]) == 1
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 200
    deps = PipelineDependencies(
        crawl, lambda p: {"video_content": "Update [1]"}, preflight, lambda *args: None, discovery
    )
    execute_job(sessions, claim_one(sessions), deps)
    result = client.get(f"/api/jobs/{job['id']}").json()
    assert result["status"] == "awaiting_review"
    assert result["package"]["title"] == "FC Online update — 23/10/2026"
    assert calls == ["discovery", "https://source.example/a", "https://source.example/b"]


@pytest.mark.parametrize(
    "narration,valid",
    [("Update [1]", True), ("Update [2]", False), ("Update without source", False)],
)
def test_ai_receives_research_context_and_validates_citation_indices(
    client, monkeypatch, narration, valid
):
    from app.schemas import ContentPackage

    monkeypatch.setenv("STUDIO_ANALYSIS_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("STUDIO_ANALYSIS_MODEL", "test")
    monkeypatch.setenv("STUDIO_ANALYSIS_API_KEY", "fixture-key")
    captured = []

    def post(self, url, **kwargs):
        captured.append(kwargs["json"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Summary",
                                    "key_points": ["Point"],
                                    "video_content": narration,
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    package = ContentPackage(
        branch="research",
        title="Test",
        research=REQUEST,
        sources=[{"label": "Patch", "rights_note": "Fixture"}],
        source_documents=[
            {"title": "Patch", "source_url": "https://site.example/a", "content": "Confirmed patch"}
        ],
    )
    if valid:
        result = analyse(package)
        assert result["references"][0]["url"] == "https://site.example/a"
    else:
        with pytest.raises(AnalysisFailure, match="dẫn nguồn"):
            analyse(package)
    context = json.loads(captured[0]["messages"][1]["content"])
    assert context["research"]["keyword"] == REQUEST["keyword"]
    assert context["research"]["target_date"] == "2026-10-23"


@pytest.mark.parametrize(
    "published,reason",
    [
        ("2026-10-23T09:00:00+07:00", None),
        ("2026-10-22T09:00:00+07:00", "different_date"),
        (None, "unknown_date"),
    ],
)
def test_source_date_warnings_are_snapshotted_before_analysis(client, published, reason):
    captured = []

    def discovery(request, **kwargs):
        return {"urls": ["https://source.example/article"], "warnings": []}

    def crawl(url):
        return {
            "title": "Patch",
            "source_url": url,
            "content": "Patch details",
            "published_at": published,
            "retrieved_at": "2026-10-25T01:00:00+00:00",
        }

    def analysis(package):
        captured.append(package)
        return {"video_content": "Confirmed patch [1]"}

    response = client.post("/api/import/keyword", json=REQUEST)
    assert response.status_code == 201
    job_id = response.json()["id"]
    sessions = client.app.state.sessions
    execute_job(
        sessions,
        claim_one(sessions),
        PipelineDependencies(
            crawl,
            analysis,
            preflight,
            lambda *args: None,
            discovery,
        ),
    )
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "awaiting_review"
    warnings = job["package"]["discovery"]["date_warnings"]
    assert [item["reason"] for item in warnings] == ([reason] if reason else [])
    assert captured[0].discovery["date_warnings"] == warnings
    assert job["package"]["source_documents"][0]["retrieved_at"] == "2026-10-25T01:00:00+00:00"
