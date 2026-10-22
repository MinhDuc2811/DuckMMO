import time
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db import (
    OutcomeSnapshot,
    PublishAttempt,
)
from app.modules.errors import ApplicationError
from app.modules.jobs.lookup import load_job
from app.publishing import youtube
from app.schemas import (
    YouTubePublish,
)


def youtube_status():
    return {
        "connected": youtube.connected(),
        "platform": "youtube",
        "requires": [
            "STUDIO_YOUTUBE_CLIENT_ID",
            "STUDIO_YOUTUBE_CLIENT_SECRET",
            "STUDIO_YOUTUBE_REFRESH_TOKEN",
        ],
        "scopes": ["youtube.upload", "yt-analytics.readonly"],
    }


def public_attempt(row):
    return {
        "id": row.id,
        "state": row.state,
        "platform_id": row.platform_id,
        "artifact_hash": row.artifact_hash,
        "offset": row.details.get("offset", 0),
    }


def youtube_attempts(job_id: UUID, *, session):
    load_job(session, job_id)
    return [
        public_attempt(row)
        for row in session.scalars(
            select(PublishAttempt)
            .where(PublishAttempt.job_id == str(job_id))
            .order_by(PublishAttempt.created_at)
        )
    ]


def publish_youtube(job_id: UUID, payload: YouTubePublish, *, session):
    job = load_job(session, job_id)
    try:
        youtube.media(job, payload.expected_video_hash)
    except youtube.PublishFailure as exc:
        raise ApplicationError(409, str(exc))
    if not youtube.connected():
        raise ApplicationError(
            409, "Chưa kết nối OAuth YouTube. Cần tài khoản có quyền upload và analytics."
        )
    row = session.scalar(
        select(PublishAttempt).where(
            PublishAttempt.job_id == job.id,
            PublishAttempt.artifact_hash == payload.expected_video_hash,
        )
    )
    metadata = payload.model_dump(exclude={"expected_video_hash"})
    if row is None:
        row = PublishAttempt(
            job_id=job.id, artifact_hash=payload.expected_video_hash, details={"metadata": metadata}
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise ApplicationError(
                409, "Upload đã được khởi tạo bởi yêu cầu khác. Làm mới để tiếp tục."
            )
    if row.state == "uploaded":
        return public_attempt(row)
    if row.details.get("metadata") != metadata:
        raise ApplicationError(409, "Giữ nguyên metadata để tiếp tục upload đang có.")
    if row.state == "uploading" and row.details.get("lease_until", 0) > time.time():
        raise ApplicationError(409, "Upload đang được xử lý. Chờ hoàn tất trước khi thử tiếp.")
    previous_state = row.state
    details = {**row.details, "lease_until": time.time() + 120}
    claimed = session.execute(
        update(PublishAttempt)
        .where(PublishAttempt.id == row.id, PublishAttempt.state == previous_state)
        .values(state="uploading", details=details)
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise ApplicationError(409, "Upload đã thay đổi; làm mới trạng thái.")
    session.commit()
    session.refresh(row)
    try:
        youtube.upload(session, row, payload)
    except (youtube.PublishFailure, httpx.RequestError) as exc:
        row.state = "uncertain"
        session.commit()
        detail = (
            str(exc)
            if isinstance(exc, youtube.PublishFailure)
            else "Upload bị ngắt. Lần sau sẽ đối soát session cũ, không đăng mới."
        )
        raise ApplicationError(502, detail)
    return public_attempt(row)


def youtube_analytics(attempt_id: UUID, *, session):
    row = session.get(PublishAttempt, str(attempt_id))
    if row is None:
        raise ApplicationError(404, "Upload not found")
    load_job(session, UUID(row.job_id))
    try:
        snapshot = youtube.analytics(session, row)
    except (youtube.PublishFailure, httpx.RequestError) as exc:
        detail = (
            str(exc)
            if isinstance(exc, youtube.PublishFailure)
            else "Chưa lấy được Analytics. Dữ liệu vẫn là unknown."
        )
        raise ApplicationError(502, detail)
    return {"sampled_at": snapshot.sampled_at, "metrics": snapshot.metrics}


def youtube_analytics_history(attempt_id: UUID, *, session):
    row = session.get(PublishAttempt, str(attempt_id))
    if row is None:
        raise ApplicationError(404, "Upload not found")
    load_job(session, UUID(row.job_id))
    return [
        {"sampled_at": s.sampled_at, "metrics": s.metrics}
        for s in session.scalars(
            select(OutcomeSnapshot)
            .where(OutcomeSnapshot.publish_id == str(attempt_id))
            .order_by(OutcomeSnapshot.sampled_at.desc())
        )
    ]
