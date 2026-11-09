import shutil
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api.dependencies import authenticate, get_session, get_settings
from app.contracts.moneyprinter import FootageRequest
from app.contracts.presentation import MusicOptions, VisualOptions, presentation_catalog
from app.modules.production.library import library_asset, stock_search
from app.modules.production.previews import audio_preview, style_preview
from app.modules.production.service import get_artifact, queue_render, review_video
from app.modules.production.voices import preview_speech, voice_catalog
from app.schemas import AudioPreview, JobRead, RenderOptions, VideoReview, VoicePreview

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
    kind: Literal[
        "video",
        "audio",
        "soundtrack",
        "subtitles",
        "styled_subtitles",
        "style",
        "poster",
        "script",
        "quality_report",
    ],
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


@router.get("/api/voices", dependencies=protected)
def endpoint_voices(settings=Depends(get_settings)):
    return voice_catalog(settings)


@router.post("/api/voices/preview", dependencies=protected)
def endpoint_voice_preview(payload: VoicePreview, settings=Depends(get_settings)):
    path = preview_speech(payload, settings)
    return FileResponse(
        path,
        media_type="audio/wav",
        filename="voice-preview.wav",
        background=BackgroundTask(shutil.rmtree, path.parent),
    )


@router.get("/api/production/catalog", dependencies=protected)
def endpoint_presentation_catalog():
    return presentation_catalog()


@router.get("/api/production/library/{kind}/{asset_id}", dependencies=protected)
def endpoint_library_asset(kind: Literal["background", "music"], asset_id: str):
    asset = library_asset(kind, asset_id)
    return FileResponse(asset.path, media_type=asset.media_type, filename=asset.filename)


@router.post("/api/production/style-preview", dependencies=protected)
def endpoint_style_preview(payload: VisualOptions, settings=Depends(get_settings)):
    if payload.preset == "auto":
        from app.modules.errors import ApplicationError

        raise ApplicationError(422, "Chọn một preset để xem mẫu chuyển động.")
    path = style_preview(payload, settings)
    return FileResponse(
        path, media_type="image/gif", background=BackgroundTask(shutil.rmtree, path.parent)
    )


@router.post("/api/jobs/{job_id}/audio-preview", dependencies=protected)
def endpoint_audio_preview(
    job_id: UUID,
    payload: AudioPreview,
    settings=Depends(get_settings),
    session=Depends(get_session),
):
    path = audio_preview(job_id, payload, settings, session=session)
    return FileResponse(
        path, media_type="audio/wav", background=BackgroundTask(shutil.rmtree, path.parent)
    )


@router.post("/api/jobs/{job_id}/music-preview", dependencies=protected)
def endpoint_music_preview(
    job_id: UUID,
    payload: MusicOptions,
    settings=Depends(get_settings),
    session=Depends(get_session),
):
    path = audio_preview(job_id, payload, settings, session=session, music_only=True)
    return FileResponse(
        path, media_type="audio/wav", background=BackgroundTask(shutil.rmtree, path.parent)
    )


@router.get("/api/production/stock/search", dependencies=protected)
def endpoint_stock_search(
    provider: Literal["pexels", "openverse"],
    q: str = Query(min_length=2, max_length=160),
    kind: Literal["image", "video", "audio"] = "image",
    page: int = Query(default=1, ge=1, le=20),
    settings=Depends(get_settings),
):
    return stock_search(provider, kind, q, page, settings)


@router.get("/api/production/moneyprinter", dependencies=protected)
def moneyprinter_status(settings=Depends(get_settings)):
    from app.modules.production.footage import runtime_status

    return runtime_status(settings)


@router.post("/api/jobs/{job_id}/moneyprinter/footage", dependencies=protected, status_code=201)
async def moneyprinter_footage(
    job_id: UUID,
    payload: FootageRequest,
    settings=Depends(get_settings),
    session=Depends(get_session),
):
    from app.modules.production.footage import prepare_footage

    return await prepare_footage(job_id, payload, settings=settings, session=session)
