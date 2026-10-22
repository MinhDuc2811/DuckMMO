import pytest

from app.services.ai_connection import load_connection, save_connection


def test_saved_connection_reloads_without_exposing_key(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    saved = save_connection("https://provider.example/v1", "model-test", "secret-test")
    assert "secret-test" not in repr(saved)
    loaded = load_connection()
    assert loaded.model == "model-test"
    assert loaded.api_key.get_secret_value() == "secret-test"
    assert "secret-test" not in loaded.model_dump_json()


def test_invalid_connection_is_not_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    with pytest.raises(ValueError):
        save_connection("file:///etc/passwd", "test", "secret")
    assert not (tmp_path / "settings/analysis.json").exists()
