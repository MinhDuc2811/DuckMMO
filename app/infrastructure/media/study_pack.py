"""Allowlisted, digest-verified bundled assets; no arbitrary URL/path input."""

import json
from pathlib import Path

from app.contracts.study_pack import BACKGROUNDS, STUDY_TRACKS
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.storage import file_digest

ROOT = Path(__file__).resolve().parents[2] / "assets" / "study-pack"


def bundled_asset(kind, asset_id):
    allowed = BACKGROUNDS if kind == "background" else STUDY_TRACKS if kind == "music" else {}
    if asset_id not in allowed:
        raise MediaFailure("Không tìm thấy tài sản có sẵn.")
    try:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        item = manifest["assets"][f"{kind}/{asset_id}"]
    except (OSError, ValueError, KeyError) as exc:
        raise MediaFailure("Bộ tài sản có sẵn bị thiếu hoặc không hợp lệ.") from exc
    path = (ROOT / item["file"]).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise MediaFailure("File thư viện bị thiếu hoặc không hợp lệ.")
    if file_digest(path) != item["sha256"]:
        raise MediaFailure("File thư viện đã thay đổi. Hãy khôi phục bộ tài sản.")
    return path
