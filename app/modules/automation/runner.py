"""Small durable coordinator; existing supervised worker owns content/render processes."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select

from app.contracts.content import content_hash
from app.contracts.ielts import BriefInput
from app.contracts.study_pack import BACKGROUNDS
from app.db import Evaluation, Job, PublishAttempt, StepRun
from app.infrastructure.local_lock import exclusive_lock
from app.infrastructure.persistence.database import AutomationPlan, AutomationRun
from app.modules.automation.service import utc
from app.modules.content.service import review
from app.modules.errors import ApplicationError
from app.modules.ielts.library import prepare_brief
from app.modules.jobs.service import create_job
from app.modules.production.service import queue_render, review_video
from app.modules.publishing.service import publish_youtube
from app.publishing.connection import status
from app.publishing.youtube import PublishFailure, remote_status
from app.schemas import JobCreate, RenderOptions, Review, VideoReview, YouTubePublish


def advance(run, plan, *, settings, session, clock):
    connection = status(settings)
    if (
        not connection["connected"]
        or (connection.get("channel") or {}).get("id") != plan.channel_id
    ):
        raise ApplicationError(
            409, "Kênh YouTube chưa kết nối hoặc đã thay đổi. Kết nối lại trước khi chạy lịch."
        )
    due = utc(run.publish_at)
    if due <= clock + timedelta(minutes=2):
        raise ApplicationError(
            409, "Lỡ thời điểm chuẩn bị/đăng. Không đăng dồn video cũ; tạo lịch mới."
        )
    if not run.job_id:
        snapshot = run.snapshot
        current = prepare_brief(
            snapshot["library_item_id"],
            BriefInput(
                expected_version=snapshot["library_version"],
                focus_text=snapshot["package"]["scenes"][0]["narration"],
            ),
            session=session,
        )
        if current != snapshot:
            raise ApplicationError(409, "Bài học đã đổi; cần tạo lại lịch.")
        job = create_job(
            JobCreate(package=snapshot["package"]), "automation-" + run.id, session=session
        )
        run.job_id, run.state = job.id, "working"
        session.commit()
        return
    job = session.get(Job, run.job_id)
    if (
        not job
        or job.deleted_at
        or job.status in ("failed", "cancelled", "cancelling", "rejected", "video_rejected")
    ):
        raise ApplicationError(409, "Tác vụ bị dừng, xóa hoặc lỗi; kiểm tra Workspace.")
    if content_hash(job.package) != content_hash(run.snapshot["package"]):
        raise ApplicationError(409, "Kịch bản tự động đã bị sửa; dừng để tránh đăng nhầm.")
    if job.status == "awaiting_review":
        review(
            UUID(job.id),
            Review(
                decision="approve",
                reviewer="Automation policy",
                note=f"Lịch {plan.id}: thư viện đã duyệt; cho phép tự động.",
                expected_content_hash=content_hash(job.package),
            ),
            session=session,
        )
    if job.status == "approved":
        queue_render(
            UUID(job.id),
            RenderOptions(
                voice=plan.options["voice"],
                background_id=plan.options["background_id"],
                visual={"preset": "lesson-card"},
                expected_content_hash=content_hash(job.package),
            ),
            session=session,
        )
    if job.status in ("awaiting_video_review", "video_approved"):
        quality = job.video.get("quality", {}).get("output", {}) if job.video else {}
        acceptable = ("pass", "warn") if plan.options["allow_quality_warnings"] else ("pass",)
        if quality.get("status") not in acceptable or quality.get("sha256") != job.video["sha256"]:
            raise ApplicationError(
                409, "Video chưa đạt chính sách chất lượng của lịch. Kiểm tra báo cáo và cảnh báo."
            )
        invalid = ("fail",) if plan.options["allow_quality_warnings"] else ("fail", "warn")
        blockers = session.scalar(
            select(Evaluation.id)
            .join(StepRun)
            .where(
                StepRun.job_id == job.id,
                StepRun.config["run_id"].as_string() == job.render_config["run_id"],
                Evaluation.outcome.in_(invalid),
            )
            .limit(1)
        )
        if blockers:
            raise ApplicationError(
                409, "Có lỗi/cảnh báo ở giọng đọc, phụ đề hoặc bản dựng; xem tab Chất lượng."
            )
        if job.video["duration"] > 60 or job.video["width"] >= job.video["height"]:
            raise ApplicationError(409, "Lịch này chỉ đăng video dọc tối đa 60 giây.")
        if job.status == "awaiting_video_review":
            review_video(
                UUID(job.id),
                VideoReview(
                    decision="approve",
                    reviewer="Automation policy",
                    note=f"Lịch {plan.id}: đạt kiểm tra kỹ thuật, không phải người duyệt.",
                    expected_video_hash=job.video["sha256"],
                ),
                session=session,
            )
    if job.status == "video_approved":
        session.refresh(plan)
        if not plan.enabled:
            return
        # Reconcile an already-created upload even after a crash/restart; never create a duplicate.
        run.state = "uploading"
        session.commit()
        result = publish_youtube(
            UUID(job.id),
            YouTubePublish(
                title=job.package["title"][:100],
                description="English lesson #Shorts\n"
                + job.package["sources"][0]["rights_note"]
                + "\n"
                + job.package["sources"][0]["label"]
                + "\n"
                + (job.package["sources"][0].get("url") or "")
                + "\nBackground: "
                + BACKGROUNDS[plan.options["background_id"]]["credit"],
                privacy="private",
                made_for_kids=plan.options["made_for_kids"],
                expected_channel_id=plan.channel_id,
                publish_at=due,
                expected_video_hash=job.video["sha256"],
            ),
            settings=settings,
            session=session,
        )
        run.publish_id = result["id"]
        if result["state"] == "uploaded":
            run.state, run.error, run.retry_at = "scheduled", None, None
        session.commit()


def tick(sessions, settings, clock=None):
    """One bounded step under a process-shared lock; never auto-authorize manual jobs."""
    clock = clock or datetime.now(UTC)
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(settings.artifact_dir / ".automation.lock"):
        with sessions() as session:
            runs = session.scalars(
                select(AutomationRun)
                .join(AutomationPlan)
                .where(
                    AutomationPlan.enabled.is_(True),
                    AutomationRun.state.in_(
                        ("pending", "working", "uploading", "retry", "scheduled")
                    ),
                    AutomationRun.publish_at <= clock + timedelta(minutes=30),
                    or_(AutomationRun.retry_at.is_(None), AutomationRun.retry_at <= clock),
                )
                .order_by(AutomationRun.publish_at)
                .limit(10)
            ).all()
            for run in runs:
                if run.retry_at and utc(run.retry_at) > clock:
                    continue
                plan = session.get(AutomationPlan, run.plan_id)
                try:
                    if run.state == "scheduled":
                        attempt = session.get(PublishAttempt, run.publish_id)
                        remote = remote_status(attempt.platform_id, settings)
                        platform_status = remote.get("status", {})
                        processing = remote.get("processingDetails", {}).get("processingStatus")
                        if platform_status.get("uploadStatus") in (
                            "failed",
                            "rejected",
                            "deleted",
                        ) or processing in ("failed", "terminated"):
                            raise ApplicationError(
                                409, "YouTube báo xử lý video thất bại; kiểm tra YouTube Studio."
                            )
                        if platform_status.get("privacyStatus") == "public":
                            run.state, run.error = "published", None
                        elif not platform_status.get("publishAt") and utc(run.publish_at) > clock:
                            raise ApplicationError(
                                409,
                                "YouTube chưa giữ lịch công khai; kiểm tra quyền API.",
                            )
                        elif clock > utc(run.publish_at) + timedelta(minutes=15):
                            raise ApplicationError(
                                409,
                                "YouTube chưa công khai đúng lịch; kiểm tra xử lý/quyền API.",
                            )
                        run.retry_at = clock + timedelta(minutes=5)
                        session.commit()
                        continue
                    # Reconcile completion before checking deadlines after a restart.
                    uploaded = (
                        session.get(PublishAttempt, run.publish_id)
                        if run.publish_id
                        else session.scalar(
                            select(PublishAttempt).where(PublishAttempt.job_id == run.job_id)
                        )
                        if run.job_id
                        else None
                    )
                    if uploaded and uploaded.state == "uploaded":
                        metadata = uploaded.details.get("metadata", {})
                        if (
                            metadata.get("expected_channel_id") != plan.channel_id
                            or not metadata.get("publish_at")
                            or utc(datetime.fromisoformat(metadata["publish_at"]))
                            != utc(run.publish_at)
                        ):
                            raise ApplicationError(
                                409, "Upload hiện có không khớp kênh/lịch đã ủy quyền."
                            )
                        run.publish_id = uploaded.id
                        run.state = "scheduled"
                        run.retry_at = clock + timedelta(minutes=5)
                        session.commit()
                        continue
                    advance(run, plan, settings=settings, session=session, clock=clock)
                except ApplicationError as exc:
                    session.rollback()
                    run = session.get(AutomationRun, run.id)
                    run.failures += 1
                    run.error = exc.detail
                    run.state = "retry" if exc.status_code >= 500 and run.failures < 3 else "error"
                    run.retry_at = (
                        clock + timedelta(minutes=2**run.failures) if run.state == "retry" else None
                    )
                    session.commit()
                except PublishFailure as exc:
                    session.rollback()
                    run = session.get(AutomationRun, run.id)
                    run.error = str(exc)
                    run.retry_at = clock + timedelta(minutes=5)
                    session.commit()
                except Exception:
                    logging.getLogger(__name__).exception("Automation run %s failed", run.id)
                    session.rollback()
                    run = session.get(AutomationRun, run.id)
                    run.state = "error"
                    run.error = (
                        "Lỗi điều phối tự động. Kiểm tra worker log; không tạo lượt đăng mới."
                    )
                    run.failures += 1
                    session.commit()
