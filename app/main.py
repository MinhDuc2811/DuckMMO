import hashlib
import json
import secrets
import time
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.config import Settings
from app.db import (
    Evaluation,
    Experiment,
    Job,
    JobEvent,
    LearningConfig,
    OutcomeSnapshot,
    PipelineRevision,
    PublishAttempt,
    ReviewFeedback,
    StepRun,
    make_engine,
    make_sessions,
    now,
)
from app.media_api import media_router
from app.publishing import youtube
from app.quality.evaluators import script_checks
from app.quality.learning import create_experiment, learn_from_feedback, promote
from app.quality.recorder import begin, content_digest, digest, feedback, finish, revision
from app.schemas import (
    ContentEdit,
    EventRead,
    JobCreate,
    JobRead,
    JobStatus,
    RenderOptions,
    Review,
    VideoReview,
    WebImport,
    YouTubePublish,
)
from app.services.media_storage import file_digest
from app.services.video import (
    VideoFailure,
    artifact_directory,
    content_hash,
    content_text,
    prepare_render,
)
from app.services.web_import import ImportFailure, validate_url


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.prepare_database_directory()
    engine = make_engine(settings.database_url)
    sessions = make_sessions(engine)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        engine.dispose()

    api = FastAPI(title="AI Content Studio", version="0.1.0", lifespan=lifespan)
    api.state.engine = engine
    api.state.sessions = sessions

    def authenticate(x_api_key: Annotated[str | None, Header()] = None):
        expected = settings.api_key.get_secret_value()
        if expected and not secrets.compare_digest(x_api_key or "", expected):
            raise HTTPException(401, "Invalid API key")

    def get_session():
        with sessions() as session:
            try:
                yield session
            except IntegrityError:
                session.rollback()
                raise HTTPException(409, "Thao tác bị xung đột. Làm mới rồi thử lại.")
            except StaleDataError:
                session.rollback()
                raise HTTPException(409, "Job changed concurrently; refresh and try again")

    def load_job(session, job_id: UUID):
        job = session.get(Job, str(job_id))
        if job is None or job.deleted_at is not None:
            raise HTTPException(404, "Job not found")
        return job

    protected = [Depends(authenticate)]
    api.include_router(media_router(settings, authenticate, get_session, load_job))

    @api.post("/api/import/web", response_model=JobRead, status_code=201, dependencies=protected)
    def import_web(payload: WebImport, session=Depends(get_session)):
        urls = list(
            dict.fromkeys(str(u) for u in ([payload.url] if payload.url else []) + payload.urls)
        )
        try:
            for url in urls:
                validate_url(url)
        except ImportFailure as exc:
            raise HTTPException(422, str(exc))
        package = {
            "schema_version": "1.0",
            "branch": payload.branch,
            "language": payload.language,
            "title": "Nguồn đang chờ lấy nội dung",
            "source_urls": urls,
            "sources": [
                {
                    "label": url[:300],
                    "url": url,
                    "rights_note": "Nguồn do người dùng nhập; chưa xác minh quyền sử dụng.",
                }
                for url in urls
            ],
            "scenes": [],
        }
        return create_job(JobCreate(package=package), session=session, idempotency_key=None)

    @api.get("/health")
    def health():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM jobs LIMIT 1"))
        except Exception:
            raise HTTPException(503, "Database unavailable or migrations not applied")
        return {"status": "ok", "stage": "foundation"}

    @api.get("/api/capabilities", dependencies=protected)
    def capabilities():
        return {
            "preflight": "ready",
            "human_review": "ready",
            "crawl": "http_html",
            "analysis": "structural",
            "tts": "local_sapi_or_edge",
            "video": "ffmpeg",
            **dict.fromkeys(["ai_gateway", "ocr", "search"], "not_configured"),
        }

    @api.post("/api/jobs", response_model=JobRead, status_code=201, dependencies=protected)
    def create_job(
        payload: JobCreate,
        session=Depends(get_session),
        idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128)] = None,
    ):
        data = payload.package.model_dump(mode="json")
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

        def existing_job():
            existing = session.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if existing and existing.deleted_at is not None:
                raise HTTPException(409, "Nội dung đã xóa. Khôi phục hoặc gửi với mã yêu cầu mới.")
            if existing and existing.request_hash != fingerprint:
                raise HTTPException(409, "Idempotency key already used for a different package")
            return existing

        if idempotency_key and (existing := existing_job()):
            return existing
        job = Job(package=data, request_hash=fingerprint, idempotency_key=idempotency_key)
        session.add(job)
        try:
            session.flush()
            run = begin(session, job, "initialize", config={"schema": "content-package-v1"})
            finish(session, run, {"branch": data["branch"], "language": data["language"]})
            session.add(
                JobEvent(job_id=job.id, status="queued", message="Content package submitted")
            )
            session.commit()
        except IntegrityError:
            session.rollback()
            if idempotency_key and (existing := existing_job()):
                return existing
            raise
        return job

    @api.get("/api/jobs", response_model=list[JobRead], dependencies=protected)
    def list_jobs(
        status: JobStatus | None = None,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        session=Depends(get_session),
    ):
        query = select(Job).where(Job.deleted_at.is_(None)).order_by(Job.created_at.desc(), Job.id)
        if status:
            query = query.where(Job.status == status)
        return session.scalars(query.limit(limit).offset(offset)).all()

    @api.get("/api/jobs/{job_id}", response_model=JobRead, dependencies=protected)
    def get_job(job_id: UUID, session=Depends(get_session)):
        return load_job(session, job_id)

    @api.get("/api/workspace/jobs", dependencies=protected)
    def workspace_jobs(session=Depends(get_session)):
        active = ("queued", "running", "cancelling")
        # Active jobs must remain visible even when more than 50 newer jobs exist.
        jobs = list(
            session.scalars(
                select(Job)
                .where(Job.deleted_at.is_(None), Job.status.in_(active))
                .order_by(Job.created_at)
            )
        )
        jobs += list(
            session.scalars(
                select(Job)
                .where(Job.deleted_at.is_(None), Job.status.not_in(active))
                .order_by(Job.updated_at.desc())
                .limit(20)
            )
        )
        rows = []
        for job in jobs:
            latest = session.scalar(
                select(JobEvent)
                .where(JobEvent.job_id == job.id)
                .order_by(JobEvent.id.desc())
                .limit(1)
            )
            rows.append(
                {
                    "id": job.id,
                    "title": job.package["title"],
                    "branch": job.package["branch"],
                    "status": job.status,
                    "stage": latest.message if latest else "",
                    "error": job.error,
                    "phase": "video_review"
                    if job.status in ("awaiting_video_review", "video_approved", "video_rejected")
                    else "production"
                    if job.render_config
                    else "content",
                }
            )
        return rows

    @api.post("/api/jobs/{job_id}/render", response_model=JobRead, dependencies=protected)
    def queue_render(job_id: UUID, payload: RenderOptions, session=Depends(get_session)):
        job = load_job(session, job_id)
        if job.status not in (
            "approved",
            "awaiting_video_review",
            "video_approved",
            "video_rejected",
        ) and not (job.status in ("failed", "cancelled") and job.render_config):
            raise HTTPException(409, "Cần duyệt kịch bản trước khi dựng video.")
        if content_hash(job.package) != payload.expected_content_hash:
            raise HTTPException(409, "Kịch bản đã thay đổi. Hãy tải lại và duyệt phiên bản mới.")
        if len(content_text(job.package)) > 30000:
            raise HTTPException(
                422, "Mỗi video tối đa 30.000 ký tự; hãy rút gọn hoặc chia kịch bản."
            )
        try:
            job.render_config = prepare_render(job.id, payload, job.package, session=session)
        except VideoFailure as exc:
            raise HTTPException(422, str(exc))
        job.video, job.status, job.attempts, job.error = None, "queued", 0, None
        session.add(JobEvent(job_id=job.id, status="queued", message="Video production queued"))
        session.commit()
        return job

    @api.get("/api/jobs/{job_id}/artifacts/{kind}", dependencies=protected)
    def get_artifact(
        job_id: UUID,
        kind: Literal[
            "video", "audio", "subtitles", "styled_subtitles", "style", "poster", "script"
        ],
        session=Depends(get_session),
    ):
        job = load_job(session, job_id)
        if not job.video or job.video["content_hash"] != content_hash(job.package):
            raise HTTPException(404, "Video chưa sẵn sàng hoặc kịch bản đã thay đổi.")
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
            raise HTTPException(404, "Không tìm thấy file kết quả.")
        return FileResponse(
            path,
            media_type=media_type,
            filename=filename,
            content_disposition_type="inline" if kind == "video" else "attachment",
        )

    @api.post("/api/jobs/{job_id}/video-review", response_model=JobRead, dependencies=protected)
    def review_video(job_id: UUID, payload: VideoReview, session=Depends(get_session)):
        job = load_job(session, job_id)
        if job.status != "awaiting_video_review" or not job.video:
            raise HTTPException(409, "Chỉ duyệt video đã dựng và kiểm tra xong.")
        if job.video["sha256"] != payload.expected_video_hash or job.video[
            "content_hash"
        ] != content_hash(job.package):
            raise HTTPException(409, "Video hoặc kịch bản đã thay đổi. Hãy mở lại bản mới.")
        media_path = artifact_directory(job.id, job.video["run_id"]) / "video.mp4"
        if not media_path.is_file() or file_digest(media_path) != job.video["sha256"]:
            raise HTTPException(
                409, "File video bị thiếu hoặc đã đổi. Hãy dựng lại trước khi duyệt."
            )
        if payload.timecode is not None and payload.timecode > job.video["duration"]:
            raise HTTPException(422, "Timecode vượt thời lượng video.")
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
                label in payload.labels for label in ("subtitle_overflow", "subtitle_sync")
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

    @api.delete("/api/jobs/{job_id}", dependencies=protected)
    def delete_job(job_id: UUID, session=Depends(get_session)):
        job = load_job(session, job_id)
        if job.status in ("queued", "running", "cancelling"):
            raise HTTPException(409, "Hãy dừng tác vụ trước khi xóa.")
        job.deleted_at = now()
        session.add(JobEvent(job_id=job.id, status=job.status, message="Moved to workspace trash"))
        session.commit()
        return {"id": job.id, "deleted": True}

    @api.post("/api/jobs/{job_id}/restore", response_model=JobRead, dependencies=protected)
    def restore_job(job_id: UUID, session=Depends(get_session)):
        job = session.get(Job, str(job_id))
        if job is None:
            raise HTTPException(404, "Job not found")
        job.deleted_at = None
        session.add(
            JobEvent(job_id=job.id, status=job.status, message="Restored from workspace trash")
        )
        session.commit()
        return job

    @api.post("/api/jobs/{job_id}/cancel", response_model=JobRead, dependencies=protected)
    def cancel_job(job_id: UUID, session=Depends(get_session)):
        job = load_job(session, job_id)
        if job.status in ("cancelled", "cancelling"):
            return job
        if job.status not in ("queued", "running"):
            raise HTTPException(409, "Tác vụ này đã kết thúc xử lý, không còn tiến trình để dừng.")
        job.status = "cancelled" if job.status == "queued" else "cancelling"
        session.add(
            JobEvent(
                job_id=job.id,
                status=job.status,
                message="Cancelled before execution"
                if job.status == "cancelled"
                else "Cancellation requested; stopping job process",
            )
        )
        session.commit()
        return job

    @api.put("/api/jobs/{job_id}/content", response_model=JobRead, dependencies=protected)
    def edit_content(job_id: UUID, payload: ContentEdit, session=Depends(get_session)):
        job = load_job(session, job_id)
        if job.status not in (
            "awaiting_review",
            "approved",
            "rejected",
            "awaiting_video_review",
            "video_approved",
            "video_rejected",
        ):
            raise HTTPException(409, "Chỉ sửa nội dung sau khi Phase 1 hoàn tất.")
        current_content = job.package.get("video_content") or "\n\n".join(
            scene["narration"] for scene in job.package["scenes"]
        )
        if hashlib.sha256(current_content.encode()).hexdigest() != payload.expected_content_hash:
            raise HTTPException(409, "Nội dung đã thay đổi. Hãy tải lại trang trước khi sửa tiếp.")
        feedback(
            session,
            job,
            "content",
            content_digest(job.package),
            "edit",
            "Content edited",
            old_text=current_content,
            new_text=payload.content,
        )
        job.package = {**job.package, "video_content": payload.content}
        revision(session, job)
        edit_run = begin(session, job, "content_edit")
        finish(
            session,
            edit_run,
            {"content_hash": content_digest(job.package)},
            script_checks(job.package),
        )
        job.video, job.render_config = None, None
        job.status = "awaiting_review"
        job.result = {**(job.result or {}), "edited_after_analysis": True}
        session.add(
            JobEvent(
                job_id=job.id,
                status="awaiting_review",
                message="Video content edited; review required",
            )
        )
        session.commit()
        return job

    @api.get("/api/jobs/{job_id}/events", response_model=list[EventRead], dependencies=protected)
    def events(job_id: UUID, session=Depends(get_session)):
        load_job(session, job_id)
        return session.scalars(
            select(JobEvent).where(JobEvent.job_id == str(job_id)).order_by(JobEvent.id)
        ).all()

    @api.post("/api/jobs/{job_id}/review", response_model=JobRead, dependencies=protected)
    def review(job_id: UUID, payload: Review, session=Depends(get_session)):
        job = load_job(session, job_id)
        if job.status != "awaiting_review":
            raise HTTPException(409, "Only packages awaiting review can be reviewed")
        if payload.expected_content_hash and payload.expected_content_hash != content_digest(
            job.package
        ):
            raise HTTPException(409, "Nội dung đã đổi. Mở lại phiên bản mới trước khi duyệt.")
        feedback(
            session,
            job,
            "content",
            content_digest(job.package),
            payload.decision,
            payload.note,
            payload.labels,
        )
        run = begin(session, job, "content_review")
        finish(session, run, {"decision": payload.decision})
        job.status = "approved" if payload.decision == "approve" else "rejected"
        session.add(
            JobEvent(
                job_id=job.id,
                status=job.status,
                message=json.dumps(payload.model_dump(), ensure_ascii=False),
            )
        )
        session.commit()
        return job

    @api.post("/api/jobs/{job_id}/retry", response_model=JobRead, dependencies=protected)
    def retry(job_id: UUID, session=Depends(get_session)):
        job = load_job(session, job_id)
        if job.status != "failed":
            raise HTTPException(409, "Only failed jobs can be retried")
        if job.attempts >= 3:
            raise HTTPException(409, "Maximum of three attempts reached")
        job.status, job.error, job.result = "queued", None, None
        session.add(JobEvent(job_id=job.id, status="queued", message="Manual retry requested"))
        session.commit()
        return job

    @api.get("/api/jobs/{job_id}/quality", dependencies=protected)
    def quality(job_id: UUID, session=Depends(get_session)):
        job = load_job(session, job_id)
        runs = list(
            session.scalars(
                select(StepRun).where(StepRun.job_id == job.id).order_by(StepRun.started_at)
            )
        )
        evaluations = list(
            session.scalars(select(Evaluation).join(StepRun).where(StepRun.job_id == job.id))
        )
        # A current report never presents an old revision/render as current evidence.
        current_hash = content_digest(job.package)
        revisions = {
            r.id: r
            for r in session.scalars(
                select(PipelineRevision).where(PipelineRevision.job_id == job.id)
            )
        }
        current_runs = {
            r.id
            for r in runs
            if revisions[r.revision_id].content_hash == current_hash
            and (
                not job.render_config
                or r.step in ("initialize", "sources", "analysis", "content_edit", "content_review")
                or r.config.get("run_id") == job.render_config["run_id"]
                or (
                    r.step == "video_review"
                    and job.video
                    and r.input_hash == digest({"sha256": job.video["sha256"]})
                )
            )
        }
        return {
            "job_id": job.id,
            "content_hash": current_hash,
            "runs": [
                {
                    "id": r.id,
                    "step": r.step,
                    "state": r.state,
                    "revision_id": r.revision_id,
                    "current": r.id in current_runs,
                    "started_at": r.started_at,
                    "finished_at": r.finished_at,
                    "input_hash": r.input_hash,
                    "output_hash": r.output_hash,
                    "output": r.output,
                }
                for r in runs
            ],
            "evaluations": [
                {
                    "run_id": e.run_id,
                    "dimension": e.dimension,
                    "outcome": e.outcome,
                    "evidence": e.evidence,
                    "evaluator": e.evaluator,
                    "current": e.run_id in current_runs,
                }
                for e in evaluations
            ],
            "feedback": [
                {
                    "id": f.id,
                    "scope": f.scope,
                    "decision": f.decision,
                    "labels": f.labels,
                    "note": f.note,
                    "timecode": f.timecode,
                    "artifact_hash": f.artifact_hash,
                    "edit_diff": f.edit_diff,
                }
                for f in session.scalars(
                    select(ReviewFeedback)
                    .where(ReviewFeedback.job_id == job.id)
                    .order_by(ReviewFeedback.created_at)
                )
            ],
            "limitations": [
                "Factual accuracy, pronunciation and word alignment need human review",
                "Old jobs are not retrospectively given quality scores",
            ],
        }

    @api.get("/api/learning/experiments", dependencies=protected)
    def experiments(session=Depends(get_session)):
        return [
            {
                "id": e.id,
                "candidate_id": e.candidate_id,
                "state": e.state,
                "dataset": e.dataset,
                "report": e.report,
            }
            for e in session.scalars(
                select(Experiment).order_by(Experiment.created_at.desc()).limit(30)
            )
        ]

    @api.post("/api/learning/experiments/{experiment_id}/promote", dependencies=protected)
    def activate(experiment_id: UUID, session=Depends(get_session)):
        row = session.get(Experiment, str(experiment_id))
        if row is None:
            raise HTTPException(404, "Experiment not found")
        try:
            candidate = promote(session, row)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        session.commit()
        return {"id": candidate.id, "state": candidate.state}

    @api.post("/api/learning/experiments/{experiment_id}/benchmark", dependencies=protected)
    def rerun_benchmark(experiment_id: UUID, session=Depends(get_session)):
        row = session.get(Experiment, str(experiment_id))
        if row is None:
            raise HTTPException(404, "Experiment not found")
        new = create_experiment(session, session.get(LearningConfig, row.candidate_id))
        session.commit()
        return {"id": new.id, "state": new.state, "report": new.report}

    @api.post("/api/learning/configs/{config_id}/rollback", dependencies=protected)
    def rollback(config_id: UUID, session=Depends(get_session)):
        row = session.get(LearningConfig, str(config_id))
        if row is None:
            raise HTTPException(404, "Config not found")
        if row.state not in ("active", "canary"):
            raise HTTPException(409, "Chỉ rollback cấu hình đang dùng.")
        row.state = "rolled_back"
        for exp in session.scalars(select(Experiment).where(Experiment.candidate_id == row.id)):
            exp.state = "rolled_back"
        # Default returns to the bundled/connected validated style catalog.
        session.commit()
        return {"id": row.id, "state": row.state}

    @api.get("/api/learning/dataset", dependencies=protected)
    def export_dataset(session=Depends(get_session)):
        rows = []
        for item in session.scalars(
            select(ReviewFeedback).where(
                ReviewFeedback.scope == "content", ReviewFeedback.decision == "approve"
            )
        ):
            rev = session.get(PipelineRevision, item.revision_id)
            job = session.get(Job, item.job_id)
            if job.deleted_at is not None:
                continue
            rows.append(
                {
                    "revision_id": rev.id,
                    "source_hash": digest(rev.package.get("source_documents", [])),
                    "content": rev.package.get("video_content")
                    or "\n\n".join(s["narration"] for s in rev.package.get("scenes", [])),
                    "branch": rev.package["branch"],
                    "feedback_id": item.id,
                    "eligibility": "reviewed_only_rights_and_training_eligibility_unverified",
                }
            )
        return {
            "version": digest(rows),
            "examples": rows,
            "training_ready": False,
            "reason": "Requires provenance/rights review and held-out evaluation",
        }

    @api.get("/api/youtube/status", dependencies=protected)
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

    @api.get("/api/jobs/{job_id}/youtube", dependencies=protected)
    def youtube_attempts(job_id: UUID, session=Depends(get_session)):
        load_job(session, job_id)
        return [
            public_attempt(row)
            for row in session.scalars(
                select(PublishAttempt)
                .where(PublishAttempt.job_id == str(job_id))
                .order_by(PublishAttempt.created_at)
            )
        ]

    @api.post("/api/jobs/{job_id}/youtube", dependencies=protected)
    def publish_youtube(job_id: UUID, payload: YouTubePublish, session=Depends(get_session)):
        job = load_job(session, job_id)
        try:
            youtube.media(job, payload.expected_video_hash)
        except youtube.PublishFailure as exc:
            raise HTTPException(409, str(exc))
        if not youtube.connected():
            raise HTTPException(
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
                job_id=job.id,
                artifact_hash=payload.expected_video_hash,
                details={"metadata": metadata},
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise HTTPException(
                    409, "Upload đã được khởi tạo bởi yêu cầu khác. Làm mới để tiếp tục."
                )
        if row.state == "uploaded":
            return public_attempt(row)
        if row.details.get("metadata") != metadata:
            raise HTTPException(409, "Giữ nguyên metadata để tiếp tục upload đang có.")
        if row.state == "uploading" and row.details.get("lease_until", 0) > time.time():
            raise HTTPException(409, "Upload đang được xử lý. Chờ hoàn tất trước khi thử tiếp.")
        previous_state = row.state
        details = {**row.details, "lease_until": time.time() + 120}
        claimed = session.execute(
            update(PublishAttempt)
            .where(PublishAttempt.id == row.id, PublishAttempt.state == previous_state)
            .values(state="uploading", details=details)
        )
        if claimed.rowcount != 1:
            session.rollback()
            raise HTTPException(409, "Upload đã thay đổi; làm mới trạng thái.")
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
                else ("Upload bị ngắt. Lần sau sẽ đối soát session cũ, không đăng mới.")
            )
            raise HTTPException(502, detail)
        return public_attempt(row)

    @api.post("/api/youtube/{attempt_id}/analytics", dependencies=protected)
    def youtube_analytics(attempt_id: UUID, session=Depends(get_session)):
        row = session.get(PublishAttempt, str(attempt_id))
        if row is None:
            raise HTTPException(404, "Upload not found")
        load_job(session, UUID(row.job_id))
        try:
            snapshot = youtube.analytics(session, row)
        except (youtube.PublishFailure, httpx.RequestError) as exc:
            detail = (
                str(exc)
                if isinstance(exc, youtube.PublishFailure)
                else "Chưa lấy được Analytics. Dữ liệu vẫn là unknown."
            )
            raise HTTPException(502, detail)
        return {"sampled_at": snapshot.sampled_at, "metrics": snapshot.metrics}

    @api.get("/api/youtube/{attempt_id}/analytics", dependencies=protected)
    def youtube_analytics_history(attempt_id: UUID, session=Depends(get_session)):
        row = session.get(PublishAttempt, str(attempt_id))
        if row is None:
            raise HTTPException(404, "Upload not found")
        load_job(session, UUID(row.job_id))
        return [
            {"sampled_at": s.sampled_at, "metrics": s.metrics}
            for s in session.scalars(
                select(OutcomeSnapshot)
                .where(OutcomeSnapshot.publish_id == str(attempt_id))
                .order_by(OutcomeSnapshot.sampled_at.desc())
            )
        ]

    return api


app = create_app()
