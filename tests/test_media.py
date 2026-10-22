import io
import math
import os
import struct
import subprocess
import time
import wave
from functools import partial
from uuid import uuid4

import imageio_ffmpeg
import pytest
from PIL import Image
from sqlalchemy import select

from app.config import Settings
from app.db import Job, MediaAsset
from app.infrastructure.local_lock import LocalBusy, exclusive_lock
from app.infrastructure.media.cleanup import cleanup
from app.infrastructure.media.storage import LocalMediaStorage
from app.modules.production.render import MediaAdapters
from app.services.video import artifact_directory
from app.worker import process_one
from tests.test_pipeline import client, submit  # noqa: F401
from tests.test_video import approved_script


def png():
    output = io.BytesIO()
    Image.new("RGB", (64, 48), "orange").save(output, format="PNG")
    return output.getvalue()


def upload(api_client, job_id, body, kind="image"):
    return api_client.post(
        f"/api/jobs/{job_id}/assets?kind={kind}",
        content=body,
        headers={"Content-Type": "application/octet-stream"},
    )


def test_stream_upload_metadata_dedup_and_job_scope(client):  # noqa: F811
    job_id, content_hash = approved_script(client)
    response = upload(client, job_id, iter([png()[:20], png()[20:]]))
    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset["width"] == 64 and asset["size"] == len(png())
    assert upload(client, job_id, png()).json()["id"] == asset["id"]
    with client.app.state.sessions() as session:
        row = session.get(MediaAsset, asset["id"])
        assert row.details == {"width": 64, "height": 48, "format": "PNG"}
        assert LocalMediaStorage(Settings()).asset_path(row.id).read_bytes() == png()
    other_id, other_hash = approved_script(client)
    rejected = client.post(
        f"/api/jobs/{other_id}/render",
        json={
            "expected_content_hash": other_hash,
            "image_asset_ids": [asset["id"]],
        },
    )
    assert rejected.status_code == 422
    assert client.get(f"/api/jobs/{other_id}/assets").json() == []
    assert client.delete(f"/api/jobs/{other_id}/assets/{asset['id']}").status_code == 404
    assert (
        client.post(
            f"/api/jobs/{job_id}/render",
            json={
                "expected_content_hash": content_hash,
                "image_asset_ids": [asset["id"]],
            },
        ).status_code
        == 200
    )
    job = client.get(f"/api/jobs/{job_id}").json()
    assert "images" not in job["render_config"]
    directory = artifact_directory(job_id, job["render_config"]["run_id"])
    assert (directory / "asset-00.png").exists()
    assert client.delete(f"/api/jobs/{job_id}/assets/{asset['id']}").status_code == 200
    assert (directory / "asset-00.png").exists()


def test_invalid_oversized_and_quota_uploads_leave_no_files(client):  # noqa: F811
    job_id = submit(client).json()["id"]
    root = Settings().artifact_dir
    assert upload(client, job_id, b"not an image").status_code == 422
    assert upload(client, job_id, b"").status_code == 422
    assert upload(client, job_id, iter([b"x" * 1_500_001, b"x" * 1_500_001])).status_code == 413
    assert list((root / "assets").iterdir()) == []
    client.app.state.engine.dispose()
    # The app's Settings instance is intentionally immutable from runtime env changes;
    # exercise capacity at the backend boundary with an explicit tiny budget.
    from app.infrastructure.media.probe import MediaFailure

    storage = LocalMediaStorage(Settings(media_storage_max_bytes=1))
    with pytest.raises(MediaFailure):
        storage.ensure_capacity(2)
    assert client.get(f"/api/jobs/{job_id}/assets").json() == []


def test_upload_lock_fails_fast(client):  # noqa: F811
    job_id = submit(client).json()["id"]
    storage = LocalMediaStorage(Settings())
    with exclusive_lock(storage.root / ".media.lock"):
        assert upload(client, job_id, png()).status_code == 429
        with pytest.raises(LocalBusy):
            with exclusive_lock(storage.root / ".media.lock"):
                pytest.fail("Second lock must not be acquired")
    assert upload(client, job_id, png()).status_code == 201


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "source.mp4"
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=22050",
            "-t",
            "0.75",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return path


def audio_fixture(text, voice, directory, index):
    path = directory / f"voice-{index:04}.wav"
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        output.writeframes(
            b"".join(
                struct.pack("<h", int(4000 * math.sin(i * 2 * math.pi * 220 / 22050)))
                for i in range(22050 * 3)
            )
        )
    return path.name, 3.0


@pytest.mark.parametrize("fit", ["pad", "crop"])
def test_actual_clip_render_loops_mutes_and_survives_source_delete(client, clip, monkeypatch, fit):  # noqa: F811
    monkeypatch.setattr(
        "app.modules.production.render.MediaAdapters",
        partial(MediaAdapters, synthesize=audio_fixture),
    )
    job_id, content_hash = approved_script(client)
    uploaded = upload(client, job_id, clip.read_bytes(), "video")
    assert uploaded.status_code == 201, uploaded.text
    asset_id = uploaded.json()["id"]
    response = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": content_hash,
            "video_asset_id": asset_id,
            "video_fit": fit,
        },
    )
    assert response.status_code == 200, response.text
    assert client.delete(f"/api/jobs/{job_id}/assets/{asset_id}").status_code == 200
    assert process_one(client.app.state.sessions)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "awaiting_video_review", job["error"]
    assert job["video"]["visuals"] == "uploaded_video"
    assert abs(job["video"]["duration"] - 3) < 0.3
    assert (job["video"]["width"], job["video"]["height"]) == (720, 1280)
    directory = artifact_directory(job_id, job["video"]["run_id"])
    assert not list(directory.glob("frame-*.png"))
    assert client.get(f"/api/jobs/{job_id}/artifacts/video").content[4:8] == b"ftyp"
    # Decode final audio and verify its 220 Hz fixture dominates the original 880 Hz track.
    decoded = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-v",
            "error",
            "-i",
            str(directory / "video.mp4"),
            "-vn",
            "-ar",
            "22050",
            "-ac",
            "1",
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout
    import numpy as np

    samples = np.frombuffer(decoded, dtype="<i2")
    spectrum = np.abs(np.fft.rfft(samples))
    frequency = np.fft.rfftfreq(len(samples), 1 / 22050)[spectrum.argmax()]
    assert abs(frequency - 220) < 3
    reviewed = client.post(
        f"/api/jobs/{job_id}/video-review",
        json={
            "decision": "approve",
            "reviewer": "Tester",
            "note": "Clip fixture",
            "expected_video_hash": job["video"]["sha256"],
        },
    )
    assert reviewed.status_code == 200, reviewed.text


def test_clip_limits_and_media_modes(client, clip):  # noqa: F811
    job_id, content_hash = approved_script(client)
    assert upload(client, job_id, png(), "video").status_code == 422
    asset_id = upload(client, job_id, clip.read_bytes(), "video").json()["id"]
    assert (
        client.post(
            f"/api/jobs/{job_id}/render",
            json={
                "expected_content_hash": content_hash,
                "video_asset_id": asset_id,
                "image_asset_ids": [asset_id],
            },
        ).status_code
        == 422
    )
    from app.infrastructure.media.probe import MediaFailure, inspect_video

    with pytest.raises(MediaFailure, match="Clip phải dài"):
        inspect_video(clip, Settings(media_max_duration=0.1))


def test_cleanup_preserves_current_runs_and_sources(client):  # noqa: F811
    job_id, content_hash = approved_script(client)
    asset = upload(client, job_id, png()).json()
    client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": content_hash,
            "image_asset_ids": [asset["id"]],
        },
    ).raise_for_status()
    with client.app.state.sessions() as session:
        current = session.get(Job, job_id).render_config["run_id"]
    storage = LocalMediaStorage(Settings())
    stale = storage.root / job_id / str(uuid4())
    stale.mkdir()
    (stale / "temporary.png").write_bytes(b"old data")
    old = time.time() - 10 * 86400
    os.utime(stale, (old, old))
    current_dir = storage.root / job_id / current
    os.utime(current_dir, (old, old))
    paths = cleanup(storage, client.app.state.sessions)
    assert paths == [stale] and stale.exists()
    cleanup(storage, client.app.state.sessions, apply=True)
    assert not stale.exists() and current_dir.exists()
    assert storage.asset_path(asset["id"]).exists()
    with client.app.state.sessions() as session:
        assert len(list(session.scalars(select(MediaAsset)))) == 1


def test_actual_image_asset_render_stays_supported(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(
        "app.modules.production.render.MediaAdapters",
        partial(MediaAdapters, synthesize=audio_fixture),
    )
    job_id, content_hash = approved_script(client)
    asset = upload(client, job_id, png()).json()
    response = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": content_hash,
            "image_asset_ids": [asset["id"]],
            "layout": "landscape",
        },
    )
    assert response.status_code == 200
    process_one(client.app.state.sessions)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "awaiting_video_review", job["error"]
    assert job["video"]["visuals"] == "uploaded_images"
    assert (job["video"]["width"], job["video"]["height"]) == (1280, 720)


def test_duplicate_supervisor_cannot_recover_running_jobs(client):  # noqa: F811
    import sys

    job_id = submit(client).json()["id"]
    with client.app.state.sessions() as session:
        session.get(Job, job_id).status = "running"
        session.commit()
    storage = LocalMediaStorage(Settings())
    with exclusive_lock(storage.root / ".worker.lock"):
        result = subprocess.run(
            [sys.executable, "-m", "app.worker", "--once"], capture_output=True, timeout=10
        )
    assert result.returncode != 0
    assert b"LocalBusy" in result.stderr
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "running"


def test_configured_upload_limits_and_auth(client):  # noqa: F811
    from fastapi.testclient import TestClient

    from app.main import create_app

    job_id = submit(client).json()["id"]
    with TestClient(
        create_app(Settings(api_key="local-test", media_upload_max_bytes=20))
    ) as protected:
        assert upload(protected, job_id, png()).status_code == 401
        rejected = protected.post(
            f"/api/jobs/{job_id}/assets?kind=image",
            content=png(),
            headers={"X-API-Key": "local-test"},
        )
        assert rejected.status_code == 413
    with TestClient(create_app(Settings(media_storage_max_bytes=2))) as limited:
        assert upload(limited, job_id, png()).status_code == 422
    assert client.get(f"/api/jobs/{job_id}/assets").json() == []
