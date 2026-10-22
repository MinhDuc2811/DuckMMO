from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from app.worker import process_one
from tests.test_pipeline import client  # noqa: F401


def test_ui_submit_and_review(client, monkeypatch):  # noqa: F811
    def local_request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", local_request)
    app = AppTest.from_file(Path(__file__).parents[1] / "ui/studio.py", default_timeout=20).run()
    assert not app.exception
    fields = {field.label: field for field in app.text_input}
    fields["Tiêu đề"].input("Kịch bản UI")
    fields["Tên nguồn"].input("Bản thảo")
    areas = {area.label: area for area in app.text_area}
    areas["Ghi chú quyền sử dụng / giấy phép"].input("Tự sáng tác")
    areas["Lời dẫn (mỗi đoạn cách nhau một dòng trống là một cảnh)"].input("Một câu chuyện mới.")
    next(b for b in app.button if b.label == "Đưa vào hàng đợi").click().run()
    assert not app.exception
    assert app.success
    assert len(client.get("/api/jobs").json()) == 1
    assert not any(a.label == "Nội dung video của bạn" for a in app.text_area)
    process_one(client.app.state.sessions)
    app.run()
    editor = next(a for a in app.text_area if a.label == "Nội dung video của bạn")
    assert editor.value == "Một câu chuyện mới."
    editor.input("Nội dung video đã chỉnh sửa.\n\nĐoạn kết mới.")
    next(b for b in app.button if b.label == "Lưu nội dung").click().run()
    assert not app.exception
    assert any("Đã lưu nội dung" in notice.value for notice in app.success)
    job = client.get("/api/jobs").json()[0]
    assert job["package"]["video_content"] == "Nội dung video đã chỉnh sửa.\n\nĐoạn kết mới."
    assert job["status"] == "awaiting_review"
    # A new browser session loads the saved file content.
    reopened = AppTest.from_file(Path(__file__).parents[1] / "ui/studio.py").run()
    assert (
        next(a for a in reopened.text_area if a.label == "Nội dung video của bạn").value
        == (job["package"]["video_content"])
    )


def test_web_flow_stays_in_phase1_until_analysis_completes(client, monkeypatch):  # noqa: F811
    def local_request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", local_request)
    calls = []

    def imported(url):
        calls.append(url)
        return {"title": "Nguồn mẫu", "source_url": url, "content": "Văn bản nguồn"}

    monkeypatch.setattr("app.worker.import_url", imported)
    monkeypatch.setattr(
        "app.worker.analyse",
        lambda _: {
            "type": "ai",
            "ai_generated": True,
            "video_content": "Kịch bản đã phân tích",
            "summary": "Tóm tắt",
            "key_points": ["Ý chính"],
        },
    )
    app = AppTest.from_file(Path(__file__).parents[1] / "ui/studio.py").run()
    next(a for a in app.text_area if a.label == "Link nguồn (mỗi dòng một URL)").input(
        "https://first.example/story\nhttps://second.example/article"
    )
    next(b for b in app.button if b.label == "Bắt đầu Phase 1").click().run()
    assert calls == []
    assert not any(a.label == "Nội dung video của bạn" for a in app.text_area)
    process_one(client.app.state.sessions)
    app.run()
    assert len(calls) == 2
    assert next(a for a in app.text_area if a.label == "Nội dung video của bạn").value == (
        "Kịch bản đã phân tích"
    )
    next(b for b in app.button if b.label == "Duyệt nội dung").click().run()
    assert client.get("/api/jobs").json()[0]["status"] == "approved"


def test_workspace_shows_existing_task_and_stop_button(client, monkeypatch):  # noqa: F811
    from tests.test_pipeline import submit

    job_id = submit(client).json()["id"]

    def local_request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", local_request)
    app = AppTest.from_file(Path(__file__).parents[1] / "ui/studio.py").run()
    assert any(h.value == "Workspace" for h in app.header)
    assert any(b.label == "Dừng tác vụ" for b in app.button)
    next(b for b in app.button if b.label == "Dừng tác vụ").click().run()
    assert not app.exception
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "cancelled"
    assert any(c.value == "Đã dừng" for c in app.caption)
    assert not any(b.label == "Dừng tác vụ" for b in app.button)
