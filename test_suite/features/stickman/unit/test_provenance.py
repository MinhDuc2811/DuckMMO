import json

from app.infrastructure.media.storage import file_digest
from app.infrastructure.stickman import VENDOR


def test_pinned_upstream_files_and_separate_license_are_present():
    manifest = json.loads((VENDOR / "UPSTREAM.json").read_text())
    assert manifest["commit"] == "eb4bb378c4716a617f9ad7d98a60379b9d1fa54a"
    for file in manifest["files"]:
        assert file_digest(VENDOR / file["local_path"]) == file["sha256"]
    assert "MIT License" in (VENDOR / "LICENSE").read_text()
    assert (VENDOR / "assets/fonts/OFL-Caveat.txt").is_file()
    assert (VENDOR / "assets/fonts/OFL-NotoSans.txt").is_file()
