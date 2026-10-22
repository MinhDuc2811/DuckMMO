from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import authenticate, get_session
from app.modules.jobs.service import (
    cancel_job,
    create_job,
    delete_job,
    events,
    get_job,
    list_jobs,
    restore_job,
    retry,
    workspace_jobs,
)
from app.schemas import EventRead, JobCreate, JobRead, JobStatus

router = APIRouter()
protected = [Depends(authenticate)]


@router.post(
    "/api/jobs", response_model=JobRead, status_code=201, dependencies=protected, name="create_job"
)
def endpoint_create_job(
    payload: JobCreate,
    session=Depends(get_session),
    idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128)] = None,
):
    return create_job(payload=payload, session=session, idempotency_key=idempotency_key)


@router.get("/api/jobs", response_model=list[JobRead], dependencies=protected, name="list_jobs")
def endpoint_list_jobs(
    status: JobStatus | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session=Depends(get_session),
):
    return list_jobs(status=status, limit=limit, offset=offset, session=session)


@router.get("/api/jobs/{job_id}", response_model=JobRead, dependencies=protected, name="get_job")
def endpoint_get_job(job_id: UUID, session=Depends(get_session)):
    return get_job(job_id=job_id, session=session)


@router.get("/api/workspace/jobs", dependencies=protected, name="workspace_jobs")
def endpoint_workspace_jobs(session=Depends(get_session)):
    return workspace_jobs(session=session)


@router.delete("/api/jobs/{job_id}", dependencies=protected, name="delete_job")
def endpoint_delete_job(job_id: UUID, session=Depends(get_session)):
    return delete_job(job_id=job_id, session=session)


@router.post(
    "/api/jobs/{job_id}/restore", response_model=JobRead, dependencies=protected, name="restore_job"
)
def endpoint_restore_job(job_id: UUID, session=Depends(get_session)):
    return restore_job(job_id=job_id, session=session)


@router.post(
    "/api/jobs/{job_id}/cancel", response_model=JobRead, dependencies=protected, name="cancel_job"
)
def endpoint_cancel_job(job_id: UUID, session=Depends(get_session)):
    return cancel_job(job_id=job_id, session=session)


@router.get(
    "/api/jobs/{job_id}/events",
    response_model=list[EventRead],
    dependencies=protected,
    name="events",
)
def endpoint_events(job_id: UUID, session=Depends(get_session)):
    return events(job_id=job_id, session=session)


@router.post(
    "/api/jobs/{job_id}/retry", response_model=JobRead, dependencies=protected, name="retry"
)
def endpoint_retry(job_id: UUID, session=Depends(get_session)):
    return retry(job_id=job_id, session=session)
