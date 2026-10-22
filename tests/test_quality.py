import wave

import pytest

from app.db import Job, LearningConfig, ReviewFeedback
from app.quality.evaluators import audio_checks, subtitle_checks
from app.quality.learning import create_experiment, promote
from app.quality.recorder import begin, close_interrupted
from app.services.styles import choose_style
from app.worker import process_one
from tests.test_pipeline import client, submit  # noqa: F401


def test_quality_revisions_feedback_and_stale_review(client):  # noqa: F811
    job = submit(client).json()
    process_one(client.app.state.sessions)
    before = client.get(f"/api/jobs/{job['id']}/quality").json()
    assert any(r["step"] == "analysis" and r["current"] for r in before["runs"])
    assert any(
        e["dimension"] == "factual_accuracy" and e["outcome"] == "unknown"
        for e in before["evaluations"]
    )
    content_hash = before["content_hash"]
    edited = client.put(
        f"/api/jobs/{job['id']}/content",
        json={"content": "Nội dung sửa đã được kiểm chứng.", "expected_content_hash": content_hash},
    )
    assert edited.status_code == 200
    stale = client.post(
        f"/api/jobs/{job['id']}/review",
        json={
            "decision": "approve",
            "reviewer": "Test",
            "note": "Stale review",
            "expected_content_hash": content_hash,
        },
    )
    assert stale.status_code == 409
    after = client.get(f"/api/jobs/{job['id']}/quality").json()
    assert not next(r for r in after["runs"] if r["step"] == "analysis")["current"]
    assert after["feedback"][0]["decision"] == "edit"
    assert "Nội dung sửa" in after["feedback"][0]["edit_diff"]
    client.post(
        f"/api/jobs/{job['id']}/review",
        json={
            "decision": "approve",
            "reviewer": "Test",
            "note": "Confirmed",
            "expected_content_hash": after["content_hash"],
        },
    )
    dataset = client.get("/api/learning/dataset").json()
    assert len(dataset["examples"]) == 1
    assert not dataset["training_ready"]


def test_interrupted_run_is_closed(client):  # noqa: F811
    item = submit(client).json()
    with client.app.state.sessions() as session:
        job = session.get(Job, item["id"])
        run = begin(session, job, "sources")
        close_interrupted(session, job.id, "cancelled")
        session.commit()
        assert run.state == "cancelled"


def test_subtitle_gate_detects_overflow_and_invalid_timing(monkeypatch):
    monkeypatch.setenv("STUDIO_STYLE_CATALOG_URL", "")
    style = choose_style({"branch": "novel"}, use_learned=False)
    checks = subtitle_checks(
        [(0, 2, "Tiếng Việt " * 40), (1, 3, "Sai thời gian")], 2, style, 720, 1280
    )
    assert next(e for e in checks if e["dimension"] == "subtitle_layout")["outcome"] == "fail"
    assert next(e for e in checks if e["dimension"] == "subtitle_timeline")["outcome"] == "fail"
    assert next(e for e in checks if e["dimension"] == "word_alignment")["outcome"] == "unknown"


def test_audio_gate_detects_silence(tmp_path):
    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(22050)
        output.writeframes(bytes(44100))
    checks = audio_checks(path)
    assert checks[0]["outcome"] == "fail"


def test_bad_candidate_cannot_be_promoted(client):  # noqa: F811
    style = choose_style({"branch": "novel"}, use_learned=False)
    with client.app.state.sessions() as session:
        candidate = LearningConfig(
            family="style",
            branch="novel",
            config={**style, "font_size": 56, "caption_chars": 60},
            provenance={"reason": "test"},
        )
        session.add(candidate)
        session.flush()
        experiment = create_experiment(session, candidate)
        assert experiment.state == "blocked"
        with pytest.raises(ValueError):
            promote(session, experiment)
        session.commit()
        exp_id = experiment.id
    assert client.post(f"/api/learning/experiments/{exp_id}/promote").status_code == 409


def test_measured_candidate_canary_and_rollback(client):  # noqa: F811
    original = choose_style({"branch": "novel"}, use_learned=False)
    # Controlled weak baseline proves that the harness measures improvement, not a constant score.
    with client.app.state.sessions() as session:
        baseline = LearningConfig(
            family="style",
            branch="novel",
            state="active",
            config={**original, "font_size": 56, "caption_chars": 60},
            provenance={"test": True},
        )
        session.add(baseline)
        for i in range(3):
            job = Job(package={"branch": "novel"}, request_hash=str(i))
            session.add(job)
            session.flush()
            from app.quality.recorder import revision

            session.add(
                ReviewFeedback(
                    job_id=job.id,
                    revision_id=revision(session, job).id,
                    scope="video",
                    artifact_hash="0" * 64,
                    decision="reject",
                    note="Overflow",
                    labels=["subtitle_overflow"],
                )
            )
        candidate = LearningConfig(
            family="style",
            branch="novel",
            config={**original, "font_size": 40, "caption_chars": 48},
            provenance={"test": True},
        )
        session.add(candidate)
        session.flush()
        experiment = create_experiment(session, candidate)
        assert experiment.report["candidate"]["score"] > experiment.report["baseline"]["score"]
        assert experiment.state == "eligible", experiment.report
        session.commit()
        exp_id, candidate_id = experiment.id, candidate.id
    promoted = client.post(f"/api/learning/experiments/{exp_id}/promote")
    assert promoted.status_code == 200
    assert promoted.json()["state"] == "canary"
    assert choose_style({"branch": "novel"})["learning_config_id"] == candidate_id
    assert client.post(f"/api/learning/configs/{candidate_id}/rollback").status_code == 200
    assert "learning_config_id" not in choose_style({"branch": "novel"})


def test_migration_preserves_existing_job(client):  # noqa: F811
    from alembic import command
    from alembic.config import Config
    job = submit(client).json()
    command.downgrade(Config("alembic.ini"), "0003")
    command.upgrade(Config("alembic.ini"), "head")
    saved = client.get(f"/api/jobs/{job['id']}").json()
    assert saved["package"] == job["package"]
    assert client.get(f"/api/jobs/{job['id']}/quality").json()["runs"] == []
