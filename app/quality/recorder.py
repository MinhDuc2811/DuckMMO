"""Immutable snapshots and evidence bound to exact pipeline revisions."""

import difflib
import hashlib
import json
from contextlib import contextmanager

from sqlalchemy import select

from app.contracts.content import content_hash as content_digest
from app.db import Evaluation, PipelineRevision, ReviewFeedback, StepRun, now


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def revision(session, job):
    previous = session.scalar(
        select(PipelineRevision)
        .where(PipelineRevision.job_id == job.id)
        .order_by(PipelineRevision.created_at.desc())
    )
    if previous and digest(previous.package) == digest(job.package):
        return previous
    row = PipelineRevision(
        job_id=job.id,
        parent_id=previous.id if previous else None,
        content_hash=content_digest(job.package),
        package=job.package,
    )
    session.add(row)
    session.flush()
    return row


def begin(session, job, step, inputs=None, config=None):
    row = StepRun(
        job_id=job.id,
        revision_id=revision(session, job).id,
        step=step,
        input_hash=digest(inputs if inputs is not None else job.package),
        config=config or {},
    )
    session.add(row)
    session.flush()
    return row


def finish(session, run, output=None, evaluations=(), state="completed"):
    run.state, run.finished_at = state, now()
    run.output = output or {}
    run.output_hash = digest(run.output)
    for item in evaluations:
        session.add(Evaluation(run_id=run.id, evaluator="deterministic-v1", **item))


@contextmanager
def tracked(session, job, step, inputs=None, config=None):
    row = begin(session, job, step, inputs, config)
    session.commit()
    try:
        yield row
    except BaseException as exc:
        # Cancellation checkpoints and supervisor recovery close interrupted runs too.
        finish(
            session,
            row,
            {"error_type": type(exc).__name__},
            state="cancelled" if type(exc).__name__ == "JobCancelled" else "failed",
        )
        session.commit()
        raise
    else:
        if row.state == "running":
            finish(session, row)
        session.commit()


def close_interrupted(session, job_id, state):
    for run in session.scalars(
        select(StepRun).where(StepRun.job_id == job_id, StepRun.state == "running")
    ):
        finish(session, run, {"reason": "worker_interrupted"}, state=state)


def feedback(
    session,
    job,
    scope,
    artifact_hash,
    decision,
    note,
    labels=(),
    timecode=None,
    old_text=None,
    new_text=None,
):
    diff = None
    if old_text is not None:
        diff = "\n".join(
            difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile="before",
                tofile="after",
                lineterm="",
            )
        )
    row = ReviewFeedback(
        job_id=job.id,
        revision_id=revision(session, job).id,
        scope=scope,
        artifact_hash=artifact_hash,
        decision=decision,
        note=note,
        labels=list(labels),
        timecode=timecode,
        edit_diff=diff,
    )
    session.add(row)
    return row


def observe_style(session, job, run, evaluations):
    from app.db import Experiment, LearningConfig

    config_id = (job.render_config or {}).get("style", {}).get("learning_config_id")
    if not config_id:
        return
    config = session.get(LearningConfig, config_id)
    if not config or config.state not in ("active", "canary"):
        return
    if any(
        e["outcome"] == "fail" and e["dimension"] in ("subtitle_layout", "subtitle_timeline")
        for e in evaluations
    ):
        config.state = "rolled_back"
        for exp in session.scalars(select(Experiment).where(Experiment.candidate_id == config.id)):
            exp.state = "rolled_back"
    elif run.step == "qa" and config.state == "canary":
        session.flush()
        jobs = {
            r.job_id
            for r in session.scalars(
                select(StepRun).where(StepRun.step == "qa", StepRun.state == "completed")
            )
            if r.config.get("style", {}).get("learning_config_id") == config.id
        }
        if len(jobs) >= 3:
            config.state = "active"
            for exp in session.scalars(
                select(Experiment).where(
                    Experiment.candidate_id == config.id, Experiment.state == "canary"
                )
            ):
                exp.state = "promoted"
