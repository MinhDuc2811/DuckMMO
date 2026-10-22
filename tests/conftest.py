import pytest


@pytest.fixture(autouse=True)
def isolate_local_settings(tmp_path, monkeypatch):
    # Never read/write the real workspace provider credentials from unit tests.
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
