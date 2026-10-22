"""Streaming upload and asset lifecycle, separate from the content/job API."""

import asyncio
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.db import MediaAsset
from app.services.local_lock import LocalBusy, exclusive_lock
from app.services.media_probe import MediaFailure, inspect_image, inspect_video
from app.services.media_storage import LocalMediaStorage, file_digest


def asset_info(asset):
    return {
        "id": asset.id,
        "kind": asset.kind,
        "size": asset.size,
        "sha256": asset.sha256,
        **asset.details,
    }


def media_router(settings, authenticate, get_session, load_job):
    router = APIRouter(prefix="/api/jobs", dependencies=[Depends(authenticate)])

    @router.get("/{job_id}/assets")
    def list_assets(job_id: UUID, session=Depends(get_session)):
        load_job(session, job_id)
        return [
            asset_info(a)
            for a in session.scalars(
                select(MediaAsset)
                .where(MediaAsset.job_id == str(job_id))
                .order_by(MediaAsset.created_at)
            )
        ]

    @router.post("/{job_id}/assets", status_code=201)
    async def upload_asset(
        job_id: UUID,
        kind: Literal["image", "video"],
        request: Request,
        session=Depends(get_session),
    ):
        load_job(session, job_id)
        storage = LocalMediaStorage(settings)
        path = storage.asset_path(uuid4())
        temporary = path.with_suffix(".part")
        limit = (
            min(settings.media_upload_max_bytes, 3_000_000)
            if kind == "image"
            else (settings.media_upload_max_bytes)
        )
        try:
            # One upload across API processes. Fail fast instead of buffering waiting requests.
            with exclusive_lock(storage.root / ".media.lock"):
                count = session.scalar(
                    select(func.count())
                    .select_from(MediaAsset)
                    .where(MediaAsset.job_id == str(job_id))
                )
                if count >= 20:
                    raise HTTPException(409, "Mỗi nội dung tối đa 20 file; xóa file không dùng.")
                declared = request.headers.get("content-length")
                try:
                    expected = int(declared) if declared is not None else limit
                except ValueError as exc:
                    raise HTTPException(400, "Content-Length không hợp lệ.") from exc
                if expected < 0 or expected > limit:
                    raise HTTPException(413, "File vượt giới hạn dung lượng.")
                await run_in_threadpool(storage.ensure_capacity, expected)
                size = 0
                with temporary.open("xb") as target:
                    async with asyncio.timeout(120):
                        async for chunk in request.stream():
                            size += len(chunk)
                            if size > limit or (declared is not None and size > expected):
                                raise HTTPException(413, "File vượt giới hạn dung lượng.")
                            await run_in_threadpool(target.write, chunk)
                if size == 0:
                    raise HTTPException(422, "File trống.")
                if declared is not None and size != expected:
                    raise HTTPException(400, "Dung lượng nhận được không khớp Content-Length.")
                sha256 = await run_in_threadpool(file_digest, temporary)
                existing = session.scalar(
                    select(MediaAsset).where(
                        MediaAsset.job_id == str(job_id),
                        MediaAsset.kind == kind,
                        MediaAsset.sha256 == sha256,
                    )
                )
                if existing:
                    await run_in_threadpool(storage.verify, existing)
                    return asset_info(existing)
                details = (
                    await run_in_threadpool(inspect_image, temporary)
                    if kind == "image"
                    else await run_in_threadpool(inspect_video, temporary, settings)
                )
                # Recheck deletion after receiving a potentially slow request.
                session.expire_all()
                load_job(session, job_id)
                temporary.replace(path)
                asset = MediaAsset(
                    id=path.name,
                    job_id=str(job_id),
                    kind=kind,
                    size=size,
                    sha256=sha256,
                    details=details,
                )
                try:
                    session.add(asset)
                    session.commit()
                except BaseException:
                    path.unlink(missing_ok=True)
                    raise
                return asset_info(asset)
        except LocalBusy as exc:
            raise HTTPException(429, str(exc), headers={"Retry-After": "3"}) from exc
        except MediaFailure as exc:
            raise HTTPException(422, str(exc)) from exc
        except TimeoutError as exc:
            raise HTTPException(408, "Tải file quá 120 giây. Hãy thử clip nhỏ hơn.") from exc
        except OSError as exc:
            raise HTTPException(
                507, "Không ghi được file local. Kiểm tra ổ đĩa/quyền ghi."
            ) from exc
        finally:
            temporary.unlink(missing_ok=True)

    @router.delete("/{job_id}/assets/{asset_id}")
    def delete_asset(job_id: UUID, asset_id: UUID, session=Depends(get_session)):
        load_job(session, job_id)
        storage = LocalMediaStorage(settings)
        try:
            with exclusive_lock(storage.root / ".media.lock"):
                asset = session.get(MediaAsset, str(asset_id))
                if asset is None or asset.job_id != str(job_id):
                    raise HTTPException(404, "Không tìm thấy file.")
                # Runs have their own pinned local copy/link, so removing this asset cannot
                # invalidate an already queued render or a reviewed result.
                session.delete(asset)
                session.commit()
                storage.asset_path(asset_id).unlink(missing_ok=True)
                return {"deleted": True}
        except LocalBusy as exc:
            raise HTTPException(429, str(exc)) from exc

    return router
