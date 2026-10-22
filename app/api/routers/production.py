from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.dependencies import authenticate, get_session
from app.modules.production.service import get_artifact, queue_render, review_video
from app.schemas import JobRead, RenderOptions, VideoReview

router = APIRouter()
protected = [Depends(authenticate)]


@router.post(
    "/api/jobs/{job_id}/render", response_model=JobRead, dependencies=protected, name="queue_render"
)
def endpoint_queue_render(job_id: UUID, payload: RenderOptions, session=Depends(get_session)):
    return queue_render(job_id=job_id, payload=payload, session=session)


@router.get("/api/jobs/{job_id}/artifacts/{kind}", dependencies=protected, name="get_artifact")
def endpoint_get_artifact(
    job_id: UUID,
    kind: Literal["video", "audio", "subtitles", "styled_subtitles", "style", "poster", "script"],
    session=Depends(get_session),
):
    artifact = get_artifact(job_id=job_id, kind=kind, session=session)
    return FileResponse(
        artifact.path,
        media_type=artifact.media_type,
        filename=artifact.filename,
        content_disposition_type="inline" if artifact.inline else "attachment",
    )


@router.post(
    "/api/jobs/{job_id}/video-review",
    response_model=JobRead,
    dependencies=protected,
    name="review_video",
)
def endpoint_review_video(job_id: UUID, payload: VideoReview, session=Depends(get_session)):
    return review_video(job_id=job_id, payload=payload, session=session)
