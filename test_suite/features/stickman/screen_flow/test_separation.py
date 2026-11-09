import httpx
from streamlit.testing.v1 import AppTest

from test_suite.support.paths import PROJECT_ROOT


def test_switching_to_stickman_does_not_render_or_request_the_ielts_job_workspace(
    client, monkeypatch
):
    calls = []

    def local_request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        calls.append(url)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", local_request)
    app = AppTest.from_file(PROJECT_ROOT / "ui/studio.py", default_timeout=20).run()
    assert not app.exception
    calls.clear()
    next(r for r in app.radio if r.label == "Không gian làm việc").set_value(
        "Stickman Studio"
    ).run()
    assert not app.exception
    assert any(h.value == "Stickman Studio" for h in app.header)
    assert not app.tabs
    assert not any("/api/jobs" in url or "/api/ielts" in url for url in calls)
    assert any("/api/stickman/projects" in url for url in calls)
    assert client.get("/api/jobs").json() == []
