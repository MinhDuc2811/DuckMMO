"""HTTP adapters for local media assets."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import authenticate, get_session, get_settings
from app.modules.production import assets

router = APIRouter(prefix="/api/jobs", dependencies=[Depends(authenticate)])


@router.get("/{job_id}/assets")
def list_assets(job_id: UUID, session=Depends(get_session)):
    return assets.list_assets(job_id, session=session)


@router.post("/{job_id}/assets", status_code=201)
async def upload_asset(
    job_id: UUID,
    kind: Literal["image", "video"],
    request: Request,
    settings=Depends(get_settings),
    session=Depends(get_session),
):
    return await assets.upload_asset(
        job_id,
        kind,
        request.stream(),
        request.headers.get("content-length"),
        settings=settings,
        session=session,
    )


@router.delete("/{job_id}/assets/{asset_id}")
def delete_asset(
    job_id: UUID, asset_id: UUID, settings=Depends(get_settings), session=Depends(get_session)
):
    return assets.delete_asset(job_id, asset_id, settings=settings, session=session)
