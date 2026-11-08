import httpx
from streamlit.testing.v1 import AppTest

from app.worker import process_one
from test_suite.support.paths import PROJECT_ROOT
from tests.test_pipeline import PACKAGE, submit


def test_english_defaults_to_uk_voice_and_music_stays_off_until_selected(client, monkeypatch):
    package = {
        **PACKAGE,
        "language": "en",
        "title": "English lesson",
        "scenes": [{"narration": "Learn at your own pace.", "source_indices": [0]}],
    }
    job = submit(client, package).json()
    assert process_one(client.app.state.sessions)
    client.post(
        f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "Test", "note": "Original UI fixture"},
    ).raise_for_status()

    def local_request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", local_request)
    app = AppTest.from_file(PROJECT_ROOT / "ui/studio.py", default_timeout=20).run()
    next(b for b in app.button if b.label == "Tiếp tục dựng video").click().run()
    voice = next(s for s in app.selectbox if s.label == "Giọng đọc")
    assert voice.value == "en-GB-SoniaNeural"
    next(b for b in app.button if b.label == "Dùng Khung trắng").click().run()
    assert not app.exception
    assert next(r for r in app.radio if r.label == "Nguồn nhạc nền").value == "off"
    assert not any(s.label == "Bản nhạc" for s in app.selectbox)
    next(r for r in app.radio if r.label == "Nguồn nhạc nền").set_value("library").run()
    assert next(s for s in app.selectbox if s.label == "Bản nhạc").value == "ambient"
    assert next(s for s in app.slider if s.label == "Âm lượng nhạc (%)").value == 10
    assert next(c for c in app.checkbox if c.label == "Tự giảm nhạc khi có lời").value
    next(r for r in app.radio if r.label == "Nguồn nhạc nền").set_value("off").run()
    app.run()
    assert not app.exception
    assert next(r for r in app.radio if r.label == "Nguồn nhạc nền").value == "off"
