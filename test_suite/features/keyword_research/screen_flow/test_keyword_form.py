import httpx
from streamlit.testing.v1 import AppTest

from test_suite.support.paths import PROJECT_ROOT


def test_keyword_form_queues_job_without_pasting_url(client, monkeypatch):
    def local_request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", local_request)
    app = AppTest.from_file(PROJECT_ROOT / "ui/studio.py", default_timeout=20).run()
    assert not app.exception
    keyword = next(
        widget for widget in app.text_area if widget.label == "Keyword / nội dung muốn làm"
    )
    keyword.set_value("FC Online bản cập nhật mới")
    next(button for button in app.button if button.label == "Tìm nguồn và tổng hợp").click().run()
    assert not app.exception and not app.error
    jobs = client.get("/api/jobs").json()
    assert len(jobs) == 1
    assert jobs[0]["package"]["research"]["keyword"] == "FC Online bản cập nhật mới"
    assert jobs[0]["package"]["source_urls"] == []
