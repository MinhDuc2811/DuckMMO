import hashlib
import json
from typing import Literal
from uuid import UUID

from sqlalchemy import select

from app.contracts.artifacts import ArtifactDownload
from app.db import (
    Experiment,
    JobEvent,
    LearningConfig,
)
from app.modules.errors import ApplicationError
from app.modules.jobs.lookup import load_job
from app.modules.jobs.policies import can_render
from app.quality.learning import learn_from_feedback
from app.quality.recorder import begin, feedback, finish
from app.schemas import (
    RenderOptions,
    VideoReview,
)
from app.services.video import (
    VideoFailure,
    artifact_directory,
    content_hash,
    content_text,
    prepare_render,
)


def queue_render(job_id: UUID, payload: RenderOptions, *, session):
    job = load_job(session, job_id)
    if not can_render(job.status, job.render_config):
        raise ApplicationError(409, "Cần duyệt kịch bản trước khi dựng video.")
    if content_hash(job.package) != payload.expected_content_hash:
        raise ApplicationError(409, "Kịch bản đã thay đổi. Hãy tải lại và duyệt phiên bản mới.")
    if len(content_text(job.package)) > 30000:
        raise ApplicationError(
            422, "Mỗi video tối đa 30.000 ký tự; hãy rút gọn hoặc chia kịch bản."
        )
    try:
        job.render_config = prepare_render(job.id, payload, job.package, session=session)
    except VideoFailure as exc:
        raise ApplicationError(422, str(exc))
    job.video, job.status, job.attempts, job.error = (None, "queued", 0, None)
    session.add(JobEvent(job_id=job.id, status="queued", message="Video production queued"))
    session.commit()
    return job


def get_artifact(
    job_id: UUID,
    kind: Literal["video", "audio", "subtitles", "styled_subtitles", "style", "poster", "script"],
    *,
    session,
):
    job = load_job(session, job_id)
    if not job.video or job.video["content_hash"] != content_hash(job.package):
        raise ApplicationError(404, "Video chưa sẵn sàng hoặc kịch bản đã thay đổi.")
    filename, media_type = {
        "video": ("video.mp4", "video/mp4"),
        "audio": ("narration.wav", "audio/wav"),
        "subtitles": ("subtitles.srt", "application/x-subrip"),
        "styled_subtitles": ("subtitles.ass", "text/plain"),
        "style": ("style.json", "application/json"),
        "poster": ("poster.png", "image/png"),
        "script": ("script.txt", "text/plain"),
    }[kind]
    path = artifact_directory(job.id, job.video["run_id"]) / filename
    if not path.is_file():
        raise ApplicationError(404, "Không tìm thấy file kết quả.")
    return ArtifactDownload(
        path,
        media_type=media_type,
        filename=filename,
        inline=kind == "video",
    )


def review_video(job_id: UUID, payload: VideoReview, *, session):
    job = load_job(session, job_id)
    if job.status != "awaiting_video_review" or not job.video:
        raise ApplicationError(409, "Chỉ duyệt video đã dựng và kiểm tra xong.")
    if job.video["sha256"] != payload.expected_video_hash or job.video[
        "content_hash"
    ] != content_hash(job.package):
        raise ApplicationError(409, "Video hoặc kịch bản đã thay đổi. Hãy mở lại bản mới.")
    media_path = artifact_directory(job.id, job.video["run_id"]) / "video.mp4"
    if (
        not media_path.is_file()
        or hashlib.sha256(media_path.read_bytes()).hexdigest() != job.video["sha256"]
    ):
        raise ApplicationError(
            409, "File video bị thiếu hoặc đã đổi. Hãy dựng lại trước khi duyệt."
        )
    if payload.timecode is not None and payload.timecode > job.video["duration"]:
        raise ApplicationError(422, "Timecode vượt thời lượng video.")
    feedback(
        session,
        job,
        "video",
        job.video["sha256"],
        payload.decision,
        payload.note,
        payload.labels,
        payload.timecode,
    )
    run = begin(session, job, "video_review", inputs={"sha256": job.video["sha256"]})
    finish(session, run, {"decision": payload.decision})
    if payload.decision == "reject":
        config_id = job.video.get("style", {}).get("learning_config_id")
        if config_id and any(
            (label in payload.labels for label in ("subtitle_overflow", "subtitle_sync"))
        ):
            config = session.get(LearningConfig, config_id)
            if config and config.state in ("active", "canary"):
                config.state = "rolled_back"
                for experiment in session.scalars(
                    select(Experiment).where(Experiment.candidate_id == config.id)
                ):
                    experiment.state = "rolled_back"
        learn_from_feedback(session, job, payload.labels)
    job.status = "video_approved" if payload.decision == "approve" else "video_rejected"
    session.add(
        JobEvent(
            job_id=job.id,
            status=job.status,
            message=json.dumps(payload.model_dump(), ensure_ascii=False),
        )
    )
    session.commit()
    return job
