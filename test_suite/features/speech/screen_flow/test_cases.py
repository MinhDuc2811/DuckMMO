import httpx

from tests.test_media import audio_fixture


def test_ui_voice_preview_does_not_queue_video(client, monkeypatch):  # noqa: F811

    from streamlit.testing.v1 import AppTest

    from app.worker import process_one
    from tests.test_pipeline import submit

    job = submit(client).json()
    process_one(client.app.state.sessions)
    client.post(
        f"/api/jobs/{job['id']}/review",
        json={
            "decision": "approve",
            "reviewer": "Tester",
            "note": "Voice preview fixture",
        },
    ).raise_for_status()
    calls = []

    def local_request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        if url.endswith("/api/voices/preview"):
            calls.append(kwargs["json"])
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", local_request)
    monkeypatch.setattr(
        "app.infrastructure.media.speech.synthesize",
        lambda text, voice, directory, index, **kwargs: audio_fixture(
            text, voice, directory, index
        ),
    )
    from test_suite.support.paths import PROJECT_ROOT

    app = AppTest.from_file(PROJECT_ROOT / "ui/studio.py", default_timeout=20).run()
    next(b for b in app.button if b.label == "Tiếp tục dựng video").click().run()
    next(b for b in app.button if b.label == "Nghe thử giọng").click().run()
    assert not app.exception and not app.error
    assert len(calls) == 1 and calls[0]["voice"] == "vi-VN-HoaiMyNeural"
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "approved"
