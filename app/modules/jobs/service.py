import hashlib
import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import (
    Job,
    JobEvent,
    now,
)
from app.modules.errors import ApplicationError
from app.modules.jobs.lookup import load_job
from app.modules.jobs.policies import ACTIVE_STATUSES, cancellation_state
from app.quality.recorder import begin, finish
from app.schemas import (
    JobCreate,
    JobStatus,
)


def create_job(payload: JobCreate, idempotency_key: str | None = None, *, session):
    data = payload.package.model_dump(mode="json")
    # Preserve replay fingerprints for manual/URL requests created before research fields existed.
    fingerprint_data = {
        k: v for k, v in data.items() if k not in {"research", "discovery"} or v is not None
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()

    def existing_job():
        existing = session.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing and existing.deleted_at is not None:
            raise ApplicationError(409, "Nội dung đã xóa. Khôi phục hoặc gửi với mã yêu cầu mới.")
        if existing and existing.request_hash != fingerprint:
            raise ApplicationError(409, "Idempotency key already used for a different package")
        return existing

    if idempotency_key and (existing := existing_job()):
        return existing
    job = Job(package=data, request_hash=fingerprint, idempotency_key=idempotency_key)
    session.add(job)
    try:
        session.flush()
        run = begin(session, job, "initialize", config={"schema": "content-package-v1"})
        finish(session, run, {"branch": data["branch"], "language": data["language"]})
        session.add(JobEvent(job_id=job.id, status="queued", message="Content package submitted"))
        session.commit()
    except IntegrityError:
        session.rollback()
        if idempotency_key and (existing := existing_job()):
            return existing
        raise
    return job


def list_jobs(status: JobStatus | None = None, limit: int = 50, offset: int = 0, *, session):
    query = select(Job).where(Job.deleted_at.is_(None)).order_by(Job.created_at.desc(), Job.id)
    if status:
        query = query.where(Job.status == status)
    return session.scalars(query.limit(limit).offset(offset)).all()


def get_job(job_id: UUID, *, session):
    return load_job(session, job_id)


def workspace_jobs(*, session):
    active = ACTIVE_STATUSES
    jobs = list(
        session.scalars(
            select(Job)
            .where(Job.deleted_at.is_(None), Job.status.in_(active))
            .order_by(Job.created_at)
        )
    )
    jobs += list(
        session.scalars(
            select(Job)
            .where(Job.deleted_at.is_(None), Job.status.not_in(active))
            .order_by(Job.updated_at.desc())
            .limit(20)
        )
    )
    latest_ids = (
        select(JobEvent.job_id, func.max(JobEvent.id).label("event_id"))
        .where(JobEvent.job_id.in_([job.id for job in jobs]))
        .group_by(JobEvent.job_id)
        .subquery()
    )
    latest_events = (
        {
            event.job_id: event
            for event in session.scalars(
                select(JobEvent).join(latest_ids, JobEvent.id == latest_ids.c.event_id)
            )
        }
        if jobs
        else {}
    )
    rows = []
    for job in jobs:
        latest = latest_events.get(job.id)
        rows.append(
            {
                "id": job.id,
                "title": job.package["title"],
                "branch": job.package["branch"],
                "status": job.status,
                "stage": latest.message if latest else "",
                "error": job.error,
                "phase": "video_review"
                if job.status in ("awaiting_video_review", "video_approved", "video_rejected")
                else "production"
                if job.render_config
                else "content",
            }
        )
    return rows


def delete_job(job_id: UUID, *, session):
    job = load_job(session, job_id)
    if job.status in ACTIVE_STATUSES:
        raise ApplicationError(409, "Hãy dừng tác vụ trước khi xóa.")
    job.deleted_at = now()
    session.add(JobEvent(job_id=job.id, status=job.status, message="Moved to workspace trash"))
    session.commit()
    return {"id": job.id, "deleted": True}


def restore_job(job_id: UUID, *, session):
    job = session.get(Job, str(job_id))
    if job is None:
        raise ApplicationError(404, "Job not found")
    job.deleted_at = None
    session.add(JobEvent(job_id=job.id, status=job.status, message="Restored from workspace trash"))
    session.commit()
    return job


def cancel_job(job_id: UUID, *, session):
    job = load_job(session, job_id)
    if job.status in ("cancelled", "cancelling"):
        return job
    if cancellation_state(job.status) is None:
        raise ApplicationError(409, "Tác vụ này đã kết thúc xử lý, không còn tiến trình để dừng.")
    job.status = cancellation_state(job.status)
    session.add(
        JobEvent(
            job_id=job.id,
            status=job.status,
            message="Cancelled before execution"
            if job.status == "cancelled"
            else "Cancellation requested; stopping job process",
        )
    )
    session.commit()
    return job


def events(job_id: UUID, *, session):
    load_job(session, job_id)
    return session.scalars(
        select(JobEvent).where(JobEvent.job_id == str(job_id)).order_by(JobEvent.id)
    ).all()


def retry(job_id: UUID, *, session):
    job = load_job(session, job_id)
    if job.status != "failed":
        raise ApplicationError(409, "Only failed jobs can be retried")
    if job.attempts >= 3:
        raise ApplicationError(409, "Maximum of three attempts reached")
    job.status, job.error, job.result = ("queued", None, None)
    session.add(JobEvent(job_id=job.id, status="queued", message="Manual retry requested"))
    session.commit()
    return job
