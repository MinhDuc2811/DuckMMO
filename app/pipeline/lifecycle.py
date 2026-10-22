from sqlalchemy import select, update

from app.db import Job, JobEvent, now
from app.quality.recorder import (
    close_interrupted,
)


class JobCancelled(Exception):
    pass


def check_running(session, job):
    session.refresh(job)
    if job.status != "running":
        raise JobCancelled()


def finish_cancel(sessions, job_id):
    with sessions() as session:
        job = session.get(Job, job_id)
        if job and job.status == "cancelling":
            job.status = "cancelled"
            close_interrupted(session, job_id, "cancelled")
            session.add(JobEvent(job_id=job_id, status="cancelled", message="Job process stopped"))
            session.commit()


def claim_one(sessions) -> str | None:
    with sessions() as session:
        job_id = session.scalar(
            select(Job.id)
            .where(Job.deleted_at.is_(None), Job.status == "queued")
            .order_by(Job.created_at)
            .limit(1)
        )
        if job_id is None:
            return None
        claimed = session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "queued")
            .values(
                status="running",
                attempts=Job.attempts + 1,
                version=Job.version + 1,
                updated_at=now(),
            )
        )
        if claimed.rowcount != 1:
            session.rollback()
            return None
        claimed_job = session.get(Job, job_id)
        session.add(
            JobEvent(
                job_id=job_id,
                status="running",
                message=(
                    "Video production started" if claimed_job.render_config else "Phase 1 started"
                ),
            )
        )
        session.commit()
        return job_id
