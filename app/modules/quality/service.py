from uuid import UUID

from sqlalchemy import select

from app.db import (
    Evaluation,
    Experiment,
    Job,
    LearningConfig,
    PipelineRevision,
    ReviewFeedback,
    StepRun,
)
from app.modules.errors import ApplicationError
from app.modules.jobs.lookup import load_job
from app.quality.learning import create_experiment, promote
from app.quality.recorder import content_digest, digest


def quality(job_id: UUID, *, session):
    job = load_job(session, job_id)
    runs = list(
        session.scalars(
            select(StepRun).where(StepRun.job_id == job.id).order_by(StepRun.started_at)
        )
    )
    evaluations = list(
        session.scalars(select(Evaluation).join(StepRun).where(StepRun.job_id == job.id))
    )
    current_hash = content_digest(job.package)
    revisions = {
        r.id: r
        for r in session.scalars(select(PipelineRevision).where(PipelineRevision.job_id == job.id))
    }
    current_runs = {
        r.id
        for r in runs
        if revisions[r.revision_id].content_hash == current_hash
        and (
            not job.render_config
            or r.step in ("initialize", "sources", "analysis", "content_edit", "content_review")
            or r.config.get("run_id") == job.render_config["run_id"]
            or (
                r.step == "video_review"
                and job.video
                and (r.input_hash == digest({"sha256": job.video["sha256"]}))
            )
        )
    }
    return {
        "job_id": job.id,
        "content_hash": current_hash,
        "runs": [
            {
                "id": r.id,
                "step": r.step,
                "state": r.state,
                "revision_id": r.revision_id,
                "current": r.id in current_runs,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "input_hash": r.input_hash,
                "output_hash": r.output_hash,
                "output": r.output,
            }
            for r in runs
        ],
        "evaluations": [
            {
                "run_id": e.run_id,
                "dimension": e.dimension,
                "outcome": e.outcome,
                "evidence": e.evidence,
                "evaluator": e.evaluator,
                "current": e.run_id in current_runs,
            }
            for e in evaluations
        ],
        "feedback": [
            {
                "id": f.id,
                "scope": f.scope,
                "decision": f.decision,
                "labels": f.labels,
                "note": f.note,
                "timecode": f.timecode,
                "artifact_hash": f.artifact_hash,
                "edit_diff": f.edit_diff,
            }
            for f in session.scalars(
                select(ReviewFeedback)
                .where(ReviewFeedback.job_id == job.id)
                .order_by(ReviewFeedback.created_at)
            )
        ],
        "limitations": [
            "Factual accuracy, pronunciation and word alignment need human review",
            "Old jobs are not retrospectively given quality scores",
        ],
    }


def experiments(*, session):
    return [
        {
            "id": e.id,
            "candidate_id": e.candidate_id,
            "state": e.state,
            "dataset": e.dataset,
            "report": e.report,
        }
        for e in session.scalars(
            select(Experiment).order_by(Experiment.created_at.desc()).limit(30)
        )
    ]


def activate(experiment_id: UUID, *, session):
    row = session.get(Experiment, str(experiment_id))
    if row is None:
        raise ApplicationError(404, "Experiment not found")
    try:
        candidate = promote(session, row)
    except ValueError as exc:
        raise ApplicationError(409, str(exc))
    session.commit()
    return {"id": candidate.id, "state": candidate.state}


def rerun_benchmark(experiment_id: UUID, *, session):
    row = session.get(Experiment, str(experiment_id))
    if row is None:
        raise ApplicationError(404, "Experiment not found")
    new = create_experiment(session, session.get(LearningConfig, row.candidate_id))
    session.commit()
    return {"id": new.id, "state": new.state, "report": new.report}


def rollback(config_id: UUID, *, session):
    row = session.get(LearningConfig, str(config_id))
    if row is None:
        raise ApplicationError(404, "Config not found")
    if row.state not in ("active", "canary"):
        raise ApplicationError(409, "Chỉ rollback cấu hình đang dùng.")
    row.state = "rolled_back"
    for exp in session.scalars(select(Experiment).where(Experiment.candidate_id == row.id)):
        exp.state = "rolled_back"
    session.commit()
    return {"id": row.id, "state": row.state}


def export_dataset(*, session):
    rows = []
    for item in session.scalars(
        select(ReviewFeedback).where(
            ReviewFeedback.scope == "content", ReviewFeedback.decision == "approve"
        )
    ):
        rev = session.get(PipelineRevision, item.revision_id)
        job = session.get(Job, item.job_id)
        if job.deleted_at is not None:
            continue
        rows.append(
            {
                "revision_id": rev.id,
                "source_hash": digest(rev.package.get("source_documents", [])),
                "content": rev.package.get("video_content")
                or "\n\n".join((s["narration"] for s in rev.package.get("scenes", []))),
                "branch": rev.package["branch"],
                "feedback_id": item.id,
                "eligibility": "reviewed_only_rights_and_training_eligibility_unverified",
            }
        )
    return {
        "version": digest(rows),
        "examples": rows,
        "training_ready": False,
        "reason": "Requires provenance/rights review and held-out evaluation",
    }
