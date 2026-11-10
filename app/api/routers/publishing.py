from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, SecretStr

from app.api.dependencies import authenticate, get_session, get_settings
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
def endpoint_youtube_status(settings=Depends(get_settings)):
    return youtube_status(settings)


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


class OAuthConfig(BaseModel):
    client_id: str = Field(min_length=1, max_length=1000)
    client_secret: SecretStr = SecretStr("")


@router.put("/api/youtube/connection", dependencies=protected)
def configure_youtube(payload: OAuthConfig, settings=Depends(get_settings)):
    from app.modules.publishing.oauth import configure

    return configure(payload.client_id, payload.client_secret.get_secret_value(), settings)


@router.post("/api/youtube/oauth/start", dependencies=protected)
def start_youtube(settings=Depends(get_settings)):
    from app.modules.publishing.oauth import start

    return start(settings)


@router.get("/api/youtube/oauth/callback", response_class=HTMLResponse)
def finish_youtube(
    code: str = Query(default="", max_length=4096),
    state: str = Query(default="", max_length=256),
    settings=Depends(get_settings),
):
    # Public redirect endpoint; one-use expiring state + PKCE authenticates this exchange.
    from app.modules.publishing.oauth import complete

    complete(code, state, settings)
    return (
        "<h2>Đã kết nối YouTube.</h2><p>Đóng tab này và quay lại tool để tải trạng thái kênh.</p>"
    )


@router.post("/api/youtube/connection/verify", dependencies=protected)
def verify_youtube(settings=Depends(get_settings)):
    from app.modules.publishing.oauth import verify

    return verify(settings)
