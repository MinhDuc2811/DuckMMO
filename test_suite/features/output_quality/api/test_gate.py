"""Real API/worker/FFmpeg; only TTS is a declared PCM fixture."""

from functools import partial

from pydantic import SecretStr

from app.modules.production.render import MediaAdapters, render_video
from app.worker import process_one
from tests.test_media import audio_fixture
from tests.test_video import approved_script


def test_worker_persists_hash_bound_report_and_protects_download(client, monkeypatch):
    job_id, digest = approved_script(client)
    queued = client.post(f"/api/jobs/{job_id}/render", json={"expected_content_hash": digest})
    assert queued.status_code == 200
    monkeypatch.setattr(
        "app.worker.render_video",
        partial(render_video, adapters=MediaAdapters(synthesize=audio_fixture)),
    )
    assert process_one(client.app.state.sessions)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "awaiting_video_review", job["error"]
    report = client.get(f"/api/jobs/{job_id}/artifacts/quality_report")
    assert report.status_code == 200
    assert report.json() == job["video"]["quality"]["output"]
    assert report.json()["sha256"] == job["video"]["sha256"]
    assert report.json()["status"] in ("pass", "warn")
    evaluations = client.get(f"/api/jobs/{job_id}/quality").json()["evaluations"]
    assert any(
        e["dimension"] == "output_full_decode" and e["outcome"] == "pass" and e["current"]
        for e in evaluations
    )
    client.app.state.settings.api_key = SecretStr("test-protection")
    assert client.get(f"/api/jobs/{job_id}/artifacts/quality_report").status_code == 401


def test_real_final_output_failure_blocks_review_and_keeps_evidence(
    client, monkeypatch, output_clip
):
    # Substitute a genuinely encoded silent MP4 at the encoder boundary, not a fake QA verdict.
    import shutil

    defective = output_clip(sound="anullsrc=r=22050:cl=mono", seconds=3, size="720x1280")
    job_id, digest = approved_script(client)
    queued = client.post(f"/api/jobs/{job_id}/render", json={"expected_content_hash": digest})
    assert queued.status_code == 200

    def encoder(directory, *args, **kwargs):
        shutil.copyfile(defective, directory / "video.mp4")

    monkeypatch.setattr("app.modules.production.render.encode_video", encoder)
    monkeypatch.setattr(
        "app.worker.render_video",
        partial(render_video, adapters=MediaAdapters(synthesize=audio_fixture)),
    )
    assert process_one(client.app.state.sessions)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "failed" and job["video"] is None
    quality = client.get(f"/api/jobs/{job_id}/quality").json()
    assert any(
        e["current"] and e["dimension"] == "output_audio_signal" and e["outcome"] == "fail"
        for e in quality["evaluations"]
    )
    rejected = client.post(
        f"/api/jobs/{job_id}/video-review",
        json={
            "decision": "approve",
            "reviewer": "Fixture",
            "note": "Must reject",
            "expected_video_hash": "0" * 64,
        },
    )
    assert rejected.status_code == 409
