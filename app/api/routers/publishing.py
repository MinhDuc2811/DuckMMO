from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import authenticate, get_session
from app.modules.publishing.service import (
    publish_youtube,
    youtube_analytics,
    youtube_analytics_history,
    youtube_attempts,
    youtube_status,
)
from app.schemas import YouTubePublish

router = APIRouter()
protected = [Depends(authenticate)]


@router.get("/api/youtube/status", dependencies=protected, name="youtube_status")
def endpoint_youtube_status():
    return youtube_status()


@router.get("/api/jobs/{job_id}/youtube", dependencies=protected, name="youtube_attempts")
def endpoint_youtube_attempts(job_id: UUID, session=Depends(get_session)):
    return youtube_attempts(job_id=job_id, session=session)


@router.post("/api/jobs/{job_id}/youtube", dependencies=protected, name="publish_youtube")
def endpoint_publish_youtube(job_id: UUID, payload: YouTubePublish, session=Depends(get_session)):
    return publish_youtube(job_id=job_id, payload=payload, session=session)


@router.post(
    "/api/youtube/{attempt_id}/analytics", dependencies=protected, name="youtube_analytics"
)
def endpoint_youtube_analytics(attempt_id: UUID, session=Depends(get_session)):
    return youtube_analytics(attempt_id=attempt_id, session=session)


@router.get(
    "/api/youtube/{attempt_id}/analytics", dependencies=protected, name="youtube_analytics_history"
)
def endpoint_youtube_analytics_history(attempt_id: UUID, session=Depends(get_session)):
    return youtube_analytics_history(attempt_id=attempt_id, session=session)
