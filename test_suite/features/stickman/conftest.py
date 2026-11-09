import pytest


@pytest.fixture(autouse=True)
def isolate_stickman(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDIO_STICKMAN_DIR", str(tmp_path / "stickman"))
