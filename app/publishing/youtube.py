"""YouTube resumable upload and owned-channel analytics; OAuth credentials required."""

import hashlib
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from app.config import Settings
from app.db import Job, OutcomeSnapshot, StepRun
from app.quality.recorder import begin, finish
from app.services.video import artifact_directory, content_hash


class PublishFailure(ValueError):
    pass


def connected():
    s = Settings()
    return all(
        (
            s.youtube_client_id,
            s.youtube_client_secret.get_secret_value(),
            s.youtube_refresh_token.get_secret_value(),
        )
    )


def token(client):
    s = Settings()
    if not connected():
        raise PublishFailure(
            "Cần OAuth YouTube: client ID, secret và refresh token. Key Gemini không dùng để đăng."
        )
    response = client.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": s.youtube_client_id,
            "client_secret": s.youtube_client_secret.get_secret_value(),
            "refresh_token": s.youtube_refresh_token.get_secret_value(),
            "grant_type": "refresh_token",
        },
    )
    if response.status_code != 200:
        raise PublishFailure(
            f"OAuth YouTube trả HTTP {response.status_code}. Kiểm tra quyền tài khoản."
        )
    return response.json()["access_token"]


def media(job, expected_hash):
    if job.status != "video_approved" or not job.video or job.video["sha256"] != expected_hash:
        raise PublishFailure("Chỉ đăng đúng video đã được duyệt.")
    if job.video["content_hash"] != content_hash(job.package):
        raise PublishFailure("Kịch bản đã thay đổi, cần duyệt lại.")
    path = artifact_directory(job.id, job.video["run_id"]) / "video.mp4"
    if not path.is_file():
        raise PublishFailure("File video bị thiếu.")
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != expected_hash:
            raise PublishFailure("File video không trùng bản đã duyệt.")
    return path


def upload(session, attempt, payload):
    job = session.get(Job, attempt.job_id)
    path = media(job, attempt.artifact_hash)
    started = time.monotonic()
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        auth = {"Authorization": "Bearer " + token(client)}
        size = path.stat().st_size
        details = dict(attempt.details)
        url = details.get("session_url")
        if url:
            # Resolve uncertain outcomes before sending more bytes; never create a second upload.
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com":
                raise PublishFailure("Upload session URL không hợp lệ.")
            status = client.put(
                url, headers={**auth, "Content-Length": "0", "Content-Range": f"bytes */{size}"}
            )
            if status.status_code in (200, 201):
                attempt.platform_id = status.json()["id"]
                attempt.state = "uploaded"
                run = session.get(StepRun, details.get("run_id"))
                if run:
                    finish(session, run, {"platform_id": attempt.platform_id, "reconciled": True})
                session.commit()
                return
            if status.status_code != 308:
                raise PublishFailure(
                    "Chưa xác minh được upload cũ. Không tạo upload mới để tránh đăng trùng."
                )
            offset = (
                int(status.headers.get("Range", "bytes=0--1").rsplit("-", 1)[-1]) + 1
                if "Range" in status.headers
                else 0
            )
        else:
            run = begin(
                session,
                job,
                "publish",
                inputs={"artifact_hash": attempt.artifact_hash},
                config={"platform": "youtube", "privacy": payload.privacy},
            )
            session.commit()
            response = client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    **auth,
                    "X-Upload-Content-Length": str(size),
                    "X-Upload-Content-Type": "video/mp4",
                },
                json={
                    "snippet": {"title": payload.title, "description": payload.description},
                    "status": {
                        "privacyStatus": payload.privacy,
                        "selfDeclaredMadeForKids": payload.made_for_kids,
                    },
                },
            )
            if response.status_code not in (200, 201) or not response.headers.get("Location"):
                finish(session, run, {"http_status": response.status_code}, state="failed")
                session.commit()
                raise PublishFailure(f"Khởi tạo upload trả HTTP {response.status_code}.")
            url = response.headers["Location"]
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com":
                raise PublishFailure("Upload session URL không hợp lệ.")
            details.update(session_url=url, run_id=run.id, offset=0)
            attempt.details = details
            session.commit()
            offset = 0

        with path.open("rb") as source:
            source.seek(offset)
            while offset < size and time.monotonic() - started < 40:
                session.refresh(job)
                if (
                    job.status != "video_approved"
                    or not job.video
                    or job.video["sha256"] != attempt.artifact_hash
                ):
                    raise PublishFailure("Video đã đổi trong khi upload. Đã dừng gửi dữ liệu.")
                chunk = source.read(8 * 1024 * 1024)
                response = client.put(
                    url,
                    headers={
                        **auth,
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes {offset}-{offset + len(chunk) - 1}/{size}",
                    },
                    content=chunk,
                )
                if response.status_code in (200, 201):
                    attempt.platform_id = response.json()["id"]
                    attempt.state = "uploaded"
                    run = session.get(StepRun, details.get("run_id"))
                    if run:
                        finish(session, run, {"platform_id": attempt.platform_id})
                    session.commit()
                    return
                if response.status_code != 308:
                    raise PublishFailure(
                        f"Upload HTTP {response.status_code}; cần đối soát session trước."
                    )
                offset += len(chunk)
                details["offset"] = offset
                attempt.details = dict(details)
                session.commit()
        attempt.state = "pending"
        session.commit()


def analytics(session, attempt):
    if attempt.state != "uploaded" or not attempt.platform_id:
        raise PublishFailure("Video chưa được upload thành công.")
    latest = session.scalar(
        select(OutcomeSnapshot)
        .where(OutcomeSnapshot.publish_id == attempt.id)
        .order_by(OutcomeSnapshot.sampled_at.desc())
    )
    if latest:
        sampled = latest.sampled_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - sampled < timedelta(hours=1):
            return latest
    today = datetime.now(UTC).date()
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.get(
            "https://youtubeanalytics.googleapis.com/v2/reports",
            headers={"Authorization": "Bearer " + token(client)},
            params={
                "ids": "channel==MINE",
                "startDate": str((attempt.created_at - timedelta(days=1)).date()),
                "endDate": str(today),
                "metrics": (
                    "views,estimatedMinutesWatched,averageViewDuration,"
                    "averageViewPercentage,likes,comments"
                ),
                "filters": "video==" + attempt.platform_id,
            },
        )
    if response.status_code != 200:
        raise PublishFailure(
            f"YouTube Analytics trả HTTP {response.status_code}; không thay bằng số 0."
        )
    data = response.json()
    rows = data.get("rows", [])
    metrics = (
        {
            header["name"]: value
            for header, value in zip(data.get("columnHeaders", []), rows[0], strict=True)
        }
        if rows
        else {}
    )
    record = OutcomeSnapshot(
        publish_id=attempt.id,
        metrics={
            "values": metrics,
            "data_available": bool(rows),
            "window_end": str(today),
            "platform": "youtube",
            "limitations": "Observational metrics; no causal evidence of style improvement",
        },
    )
    session.add(record)
    job = session.get(Job, attempt.job_id)
    run = begin(session, job, "outcomes", inputs={"platform_id": attempt.platform_id})
    finish(session, run, record.metrics)
    session.commit()
    return record
