"""Local asset lifecycle independent of HTTP and UI adapters."""

import asyncio
from asyncio import to_thread
from uuid import uuid4

from sqlalchemy import func, select

from app.db import MediaAsset
from app.infrastructure.local_lock import LocalBusy, exclusive_lock
from app.infrastructure.media.probe import MediaFailure, inspect_audio, inspect_image, inspect_video
from app.infrastructure.media.storage import LocalMediaStorage, file_digest
from app.modules.errors import ApplicationError
from app.modules.jobs.lookup import load_job


def asset_info(asset):
    return {
        "id": asset.id,
        "kind": asset.kind,
        "size": asset.size,
        "sha256": asset.sha256,
        **asset.details,
    }


def list_assets(job_id, *, session):
    load_job(session, job_id)
    return [
        asset_info(a)
        for a in session.scalars(
            select(MediaAsset)
            .where(MediaAsset.job_id == str(job_id))
            .order_by(MediaAsset.created_at)
        )
    ]


async def upload_asset(job_id, kind, chunks, content_length, *, settings, session):
    load_job(session, job_id)
    storage = LocalMediaStorage(settings)
    path = storage.asset_path(uuid4())
    temporary = path.with_suffix(".part")
    limit = (
        min(settings.media_upload_max_bytes, 3_000_000)
        if kind == "image"
        else min(settings.media_upload_max_bytes, 20_000_000)
        if kind == "audio"
        else settings.media_upload_max_bytes
    )
    try:
        # One upload across API processes. Fail fast instead of buffering waiting requests.
        with exclusive_lock(storage.root / ".media.lock"):
            count = session.scalar(
                select(func.count()).select_from(MediaAsset).where(MediaAsset.job_id == str(job_id))
            )
            if count >= 20:
                raise ApplicationError(409, "Mỗi nội dung tối đa 20 file; xóa file không dùng.")
            declared = content_length
            try:
                expected = int(declared) if declared is not None else limit
            except ValueError as exc:
                raise ApplicationError(400, "Content-Length không hợp lệ.") from exc
            if expected < 0 or expected > limit:
                raise ApplicationError(413, "File vượt giới hạn dung lượng.")
            await to_thread(storage.ensure_capacity, expected)
            size = 0
            with temporary.open("xb") as target:
                async with asyncio.timeout(120):
                    async for chunk in chunks:
                        size += len(chunk)
                        if size > limit or (declared is not None and size > expected):
                            raise ApplicationError(413, "File vượt giới hạn dung lượng.")
                        await to_thread(target.write, chunk)
            if size == 0:
                raise ApplicationError(422, "File trống.")
            if declared is not None and size != expected:
                raise ApplicationError(400, "Dung lượng nhận được không khớp Content-Length.")
            sha256 = await to_thread(file_digest, temporary)
            existing = session.scalar(
                select(MediaAsset).where(
                    MediaAsset.job_id == str(job_id),
                    MediaAsset.kind == kind,
                    MediaAsset.sha256 == sha256,
                )
            )
            if existing:
                await to_thread(storage.verify, existing)
                return asset_info(existing)
            details = (
                await to_thread(inspect_image, temporary)
                if kind == "image"
                else await to_thread(inspect_audio, temporary, settings)
                if kind == "audio"
                else await to_thread(inspect_video, temporary, settings)
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
        raise ApplicationError(429, str(exc), headers={"Retry-After": "3"}) from exc
    except MediaFailure as exc:
        raise ApplicationError(422, str(exc)) from exc
    except TimeoutError as exc:
        raise ApplicationError(408, "Tải file quá 120 giây. Hãy thử clip nhỏ hơn.") from exc
    except OSError as exc:
        raise ApplicationError(507, "Không ghi được file local. Kiểm tra ổ đĩa/quyền ghi.") from exc
    finally:
        temporary.unlink(missing_ok=True)


def delete_asset(job_id, asset_id, *, settings, session):
    load_job(session, job_id)
    storage = LocalMediaStorage(settings)
    try:
        with exclusive_lock(storage.root / ".media.lock"):
            asset = session.get(MediaAsset, str(asset_id))
            if asset is None or asset.job_id != str(job_id):
                raise ApplicationError(404, "Không tìm thấy file.")
            # Runs have their own pinned local copy/link, so removing this asset cannot
            # invalidate an already queued render or a reviewed result.
            session.delete(asset)
            session.commit()
            storage.asset_path(asset_id).unlink(missing_ok=True)
            return {"deleted": True}
    except LocalBusy as exc:
        raise ApplicationError(429, str(exc)) from exc
