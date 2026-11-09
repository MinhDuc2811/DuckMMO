import shutil
from pathlib import Path

import pytest

from app.infrastructure.media import moneyprinter
from tests.test_media import clip  # noqa: F401


@pytest.fixture
def mpt_http(tmp_path, monkeypatch, clip):  # noqa: F811
    monkeypatch.setenv("MPT_FIXTURE_ROOT", str(tmp_path))
    monkeypatch.setenv("STUDIO_PEXELS_API_KEY", "fixture-only")
    monkeypatch.setenv("STUDIO_MPT_DIR", str(tmp_path / "moneyprinter"))
    monkeypatch.setattr(
        moneyprinter, "BRIDGE", Path(__file__).resolve().parents[2] / "support/mpt_http_fixture.py"
    )
    shutil.copyfile(clip, tmp_path / "provider.mp4")
