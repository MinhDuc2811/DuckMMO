import wave
from datetime import timedelta
from functools import partial

import pytest

from app.db import Job
from app.infrastructure.persistence.database import AutomationRun
from app.modules.automation.runner import tick
from app.modules.automation.service import utc
from app.modules.production.render import MediaAdapters, render_video
from app.worker import process_one
from tests.test_media import audio_fixture


@pytest.mark.parametrize("seconds,manual_review", [(6, False), (3, False), (3, True)])
def test_autonomous_reviewed_lesson_to_real_mp4_and_scheduled_upload(
    client, monkeypatch, plan_payload, google_http, seconds, manual_review
):
    made = client.post("/api/automation/plans", json=plan_payload).json()
    enabled = client.put(
        f"/api/automation/plans/{made['id']}",
        json={"enabled": True, "authorize_auto_publish": True},
    )
    assert enabled.status_code == 200, enabled.text
    sessions, settings = client.app.state.sessions, client.app.state.settings
    with sessions() as session:
        from sqlalchemy import select

        run = session.scalar(select(AutomationRun))
        clock = utc(run.publish_at) - timedelta(minutes=25)

    def speech(text, voice, directory, index):
        filename, duration = audio_fixture(text, voice, directory, index)
        path = directory / filename
        with wave.open(str(path), "rb") as source:
            params, frames = source.getparams(), source.readframes(source.getnframes())
        with wave.open(str(path), "wb") as target:
            target.setparams(params)
            target.writeframes(frames * (seconds // 3))
        return filename, duration * (seconds // 3)

    monkeypatch.setattr(
        "app.worker.render_video",
        partial(render_video, adapters=MediaAdapters(synthesize=speech)),
    )
    tick(sessions, settings, clock)
    assert process_one(sessions)  # structural preflight of already-reviewed original lesson
    tick(sessions, settings, clock)
    assert process_one(sessions)  # actual scene rendering, FFmpeg and final quality gate
    if manual_review:
        from sqlalchemy import select

        with sessions() as session:
            run = session.scalar(select(AutomationRun))
            job = session.get(Job, run.job_id)
            job_id, digest = job.id, job.video["sha256"]
        approved = client.post(
            f"/api/jobs/{job_id}/video-review",
            json={
                "decision": "approve",
                "reviewer": "Fixture",
                "note": "Manual review must not bypass strict schedule policy",
                "expected_video_hash": digest,
            },
        )
        assert approved.status_code == 200
    tick(sessions, settings, clock)
    result = client.get("/api/automation/plans").json()[0]["runs"][0]
    if seconds == 3:
        assert result["state"] == "error", result
        assert "cảnh báo" in result["error"]
        assert not any(r.url.path == "/upload/youtube/v3/videos" for r in google_http)
        return
    assert result["state"] == "scheduled", result
    with sessions() as session:
        job = session.get(Job, result["job_id"])
        assert job.video["voice"] == "en-GB-SoniaNeural"
        assert job.video["quality"]["output"]["status"] == "pass"
        assert job.status == "video_approved"
    tick(sessions, settings, clock + timedelta(days=1))
    assert client.get("/api/automation/plans").json()[0]["runs"][0]["state"] == "published"
    assert sum(r.url.path == "/upload/youtube/v3/videos" for r in google_http) == 1
