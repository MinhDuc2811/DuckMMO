import io
from uuid import uuid4

from PIL import Image

from app.infrastructure.media.music import original_track
from tests.test_video import approved_script


def test_catalog_and_actual_animated_preview(client):
    catalog = client.get("/api/production/catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()["presets"]) == 6
    response = client.post("/api/production/style-preview", json={"preset": "comic"})
    assert response.status_code == 200
    image = Image.open(io.BytesIO(response.content))
    assert image.n_frames > 1
    assert image.size == (240, 426)
    assert client.post("/api/production/style-preview", json={"preset": "auto"}).status_code == 422


def test_audio_upload_pin_queue_delete_and_isolation(client, tmp_path):
    job_id, digest = approved_script(client)
    path = tmp_path / "music.wav"
    original_track(path, "ambient")
    asset = client.post(f"/api/jobs/{job_id}/assets?kind=audio", content=path.read_bytes())
    assert asset.status_code == 201, asset.text
    asset = asset.json()
    assert asset["kind"] == "audio" and abs(asset["duration"] - 8) < 0.05
    duplicate = client.post(f"/api/jobs/{job_id}/assets?kind=audio", content=path.read_bytes())
    assert duplicate.json()["id"] == asset["id"]
    other, other_hash = approved_script(client)
    rejected = client.post(
        f"/api/jobs/{other}/render",
        json={"expected_content_hash": other_hash, "music": {"asset_id": asset["id"]}},
    )
    assert rejected.status_code == 422
    result = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": digest,
            "visual": {"preset": "comic", "layout": "mix", "seed": 7},
            "music": {"asset_id": asset["id"], "volume": 0.12},
        },
    )
    assert result.status_code == 200, result.text
    config = result.json()["render_config"]
    assert config["visual"]["preset"] == "comic"
    assert config["style"]["id"] == "comic"
    from app.infrastructure.media.artifacts import artifact_directory

    directory = artifact_directory(job_id, config["run_id"])
    pinned = (directory / "input-music").read_bytes()
    assert pinned == path.read_bytes()
    assert client.delete(f"/api/jobs/{job_id}/assets/{asset['id']}").status_code == 200
    assert (directory / "input-music").read_bytes() == pinned


def test_invalid_music_is_rejected_before_queue(client):
    job_id, digest = approved_script(client)
    assert (
        client.post(f"/api/jobs/{job_id}/assets?kind=audio", content=b"not music").status_code
        == 422
    )
    assert (
        client.post(
            f"/api/jobs/{job_id}/render",
            json={"expected_content_hash": digest, "music": {"asset_id": str(uuid4())}},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/jobs/{job_id}/render",
            json={
                "expected_content_hash": digest,
                "music": {"track": "ambient", "start_seconds": 8},
            },
        ).status_code
        == 422
    )


def test_mixed_preview_uses_real_mixer_with_fixture_speech(client, monkeypatch, narration):
    def speech(text, voice, directory, index, **kwargs):
        narration(directory / "speech.wav", 2)
        return "speech.wav", 2

    monkeypatch.setattr("app.infrastructure.media.speech.synthesize", speech)
    job_id, _ = approved_script(client)
    response = client.post(
        f"/api/jobs/{job_id}/audio-preview",
        json={"text": "Giọng đọc thử", "music": {"track": "ambient"}},
    )
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"RIFF")
    assert len(response.content) > 22050 * 2 * 1.9


def test_music_preview_does_not_call_tts_and_cleans_files(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Music-only preview must not call speech provider")

    monkeypatch.setattr("app.modules.production.previews.preview_speech", forbidden)
    job_id, _ = approved_script(client)
    response = client.post(f"/api/jobs/{job_id}/music-preview", json={"track": "ambient"})
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"RIFF")
    import array
    import wave

    with wave.open(io.BytesIO(response.content), "rb") as source:
        pcm = array.array("h", source.readframes(source.getnframes()))
    assert max(abs(v) for v in pcm) > 100
    from app.config import Settings

    assert not list(Settings().artifact_dir.glob("tmp*"))
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "approved"


def test_disk_full_rejects_music_queue_and_removes_incomplete_run(client, monkeypatch):
    from app.config import Settings
    from app.infrastructure.media.probe import MediaFailure
    from app.infrastructure.media.storage import LocalMediaStorage

    job_id, digest = approved_script(client)

    def no_space(self, additional=0):
        raise MediaFailure("Ổ đĩa sắp đầy.")

    monkeypatch.setattr(LocalMediaStorage, "ensure_capacity", no_space)
    response = client.post(
        f"/api/jobs/{job_id}/render",
        json={"expected_content_hash": digest, "music": {"track": "ambient"}},
    )
    assert response.status_code == 422
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "approved"
    assert not list((Settings().artifact_dir / job_id).iterdir())


def test_audio_upload_size_limit(client):
    job_id, _ = approved_script(client)
    response = client.post(
        f"/api/jobs/{job_id}/assets?kind=audio",
        content=b"x",
        headers={"Content-Length": "20000001"},
    )
    assert response.status_code == 413
