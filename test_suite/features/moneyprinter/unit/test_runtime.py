from pathlib import Path

from app.config import Settings
from app.modules.production.footage import runtime_status


def test_uninstalled_runtime_is_reported_without_fake_success(tmp_path):
    status = runtime_status(
        Settings(mpt_python=Path(tmp_path / "missing-python"), mpt_dir=tmp_path)
    )
    assert status["ready"] is False
    assert "Chưa cài MPT runtime" in status["detail"]
    assert all(type(value) is bool for value in status["providers"].values())
