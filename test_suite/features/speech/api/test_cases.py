import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas import RenderOptions
from tests.test_media import audio_fixture


def test_voice_catalog_preview_and_schema(client, monkeypatch):  # noqa: F811
    voices = client.get("/api/voices").json()["voices"]
    assert {v["provider"] for v in voices} == {"edge", "windows"}
    assert any(v["id"] == "vi-VN-NamMinhNeural" and v["available"] for v in voices)
    assert "api_key" not in client.get("/api/voices").text
    assert client.post("/api/voices/preview", json={"text": " "}).status_code == 422
    assert client.post("/api/voices/preview", json={"text": "a" * 301}).status_code == 422
    monkeypatch.setattr(
        "app.infrastructure.media.speech.synthesize",
        lambda text, voice, directory, index, **kwargs: audio_fixture(
            text, voice, directory, index
        ),
    )
    response = client.post("/api/voices/preview", json={"text": "Xin chào"})
    assert response.status_code == 200 and response.content.startswith(b"RIFF")
    assert list((Settings().artifact_dir / "voice-previews").iterdir()) == []
    assert RenderOptions(expected_content_hash="0" * 64).voice == "vi-VN-HoaiMyNeural"
    with pytest.raises(ValidationError):
        RenderOptions(expected_content_hash="0" * 64, voice="invented-voice")
    with pytest.raises(ValidationError):
        RenderOptions(expected_content_hash="0" * 64, speech_rate=100)


def test_preview_uses_application_credentials_and_is_protected(client, tmp_path, monkeypatch):  # noqa: F811
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings = Settings(
        database_url=str(client.app.state.engine.url),
        api_key="protect-preview",
        artifact_dir=tmp_path / "other-artifacts",
    )
    observed = []

    def provider(text, voice, directory, index, **kwargs):
        observed.append((voice, kwargs["settings"].artifact_dir))
        return audio_fixture(text, voice, directory, index)

    monkeypatch.setattr("app.infrastructure.media.speech.synthesize", provider)
    with TestClient(create_app(settings)) as other:
        assert other.get("/api/voices").status_code == 401
        assert other.post("/api/voices/preview", json={"text": "Xin chào"}).status_code == 401
        headers = {"X-API-Key": "protect-preview"}
        catalog = other.get("/api/voices", headers=headers)
        assert "api_key" not in catalog.text
        response = other.post(
            "/api/voices/preview",
            headers=headers,
            json={"text": "Xin chào", "voice": "vi-VN-NamMinhNeural"},
        )
        assert response.status_code == 200 and response.content.startswith(b"RIFF")
    assert observed == [("vi-VN-NamMinhNeural", settings.artifact_dir)]
