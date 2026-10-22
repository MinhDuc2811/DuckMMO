import json
from pathlib import Path

import httpx
import pytest

from app.services import styles


@pytest.mark.parametrize(
    "branch,expected",
    [("novel", "story-cinematic"), ("comic", "comic-bold"), ("research", "research-clean")],
)
def test_automatic_style_by_content(branch, expected, monkeypatch):
    monkeypatch.setenv("STUDIO_STYLE_CATALOG_URL", "")
    assert styles.choose_style({"branch": branch})["id"] == expected


def test_sync_update_is_pinned_and_bad_update_keeps_valid_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_STYLE_CATALOG_URL", "https://styles.example/catalog.json")
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path))
    catalog = json.loads(Path(styles.__file__).with_name("styles.json").read_text(encoding="utf-8"))
    catalog["version"] = 2
    payload = json.dumps(catalog).encode()

    def response(request):
        return httpx.Response(200, content=payload)

    monkeypatch.setattr(styles, "PublicWebTransport", lambda: httpx.MockTransport(response))
    first = styles.choose_style({"branch": "novel"})
    assert first["catalog_version"] == 2
    assert first["sync_status"] == "synced"
    catalog["version"] = 3
    catalog["styles"][0]["font_size"] = 48
    payload = json.dumps(catalog).encode()
    second = styles.choose_style({"branch": "novel"})
    assert second["catalog_version"] == 3
    assert first["catalog_version"] == 2
    assert first["font_size"] != second["font_size"]
    payload = b'{"version": 4, "styles": []}'
    cached = styles.choose_style({"branch": "novel"})
    assert cached["catalog_version"] == 3
    assert cached["sync_status"] == "cached_after_sync_failure"


def test_subtitles_escape_overrides_and_keep_vietnamese(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_STYLE_CATALOG_URL", "")
    style = styles.choose_style({"branch": "novel"})
    styles.write_ass(tmp_path, [(0, 2, r"Tiếng Việt {\pos(0,0)}")], style, 720, 1280)
    text = (tmp_path / "subtitles.ass").read_text(encoding="utf-8")
    assert "Tiếng Việt" in text
    assert r"{\pos(0,0)}" not in text
    assert "0:00:02.00" in text
