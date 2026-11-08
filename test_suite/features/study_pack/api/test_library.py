from app.infrastructure.media.storage import file_digest
from app.infrastructure.media.study_pack import bundled_asset
from tests.test_video import approved_script


def test_catalog_downloads_and_pinning(client):
    catalog = client.get("/api/production/catalog").json()
    assert {item["id"] for item in catalog["backgrounds"]} == {
        "study-morning",
        "quiet-work",
        "misty-lake",
    }
    assert {"quiet-pages", "soft-focus", "morning-air"} <= {
        item["id"] for item in catalog["tracks"]
    }
    for item in catalog["backgrounds"]:
        response = client.get(item["url"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")
    assert client.get("/api/production/library/music/quiet-pages").content.startswith(b"RIFF")
    assert client.get("/api/production/library/background/unknown").status_code == 404
    job_id, digest = approved_script(client)
    queued = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": digest,
            "background_id": "study-morning",
            "visual": {"preset": "lesson-card"},
            "music": {"track": "quiet-pages", "volume": 0.10, "ducking": True},
        },
    )
    assert queued.status_code == 200, queued.text
    config = queued.json()["render_config"]
    assert config["image_files"] == ["library-background.png"]
    assert config["background_sha256"] == file_digest(bundled_asset("background", "study-morning"))
    assert config["music_duration"] == 32
    assert config["music_sha256"] == file_digest(bundled_asset("music", "quiet-pages"))


def test_library_downloads_require_existing_api_auth(client, tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    with TestClient(
        create_app(
            Settings(
                database_url=str(client.app.state.engine.url),
                api_key="test-only-key",
                artifact_dir=tmp_path / "protected",
            )
        )
    ) as protected:
        assert protected.get("/api/production/library/music/quiet-pages").status_code == 401
