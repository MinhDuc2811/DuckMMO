import json
from uuid import UUID

from app.contracts.content import content_hash, content_text
from app.db import (
    JobEvent,
)
from app.modules.errors import ApplicationError
from app.modules.jobs.lookup import load_job
from app.modules.jobs.policies import EDITABLE_STATUSES
from app.modules.jobs.service import create_job
from app.quality.evaluators import script_checks
from app.quality.recorder import begin, content_digest, feedback, finish, revision
from app.schemas import (
    ContentEdit,
    JobCreate,
    Review,
    WebImport,
)
from app.services.web_import import ImportFailure, validate_url


def import_web(payload: WebImport, *, session):
    urls = list(
        dict.fromkeys((str(u) for u in ([payload.url] if payload.url else []) + payload.urls))
    )
    try:
        for url in urls:
            validate_url(url)
    except ImportFailure as exc:
        raise ApplicationError(422, str(exc))
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


def edit_content(job_id: UUID, payload: ContentEdit, *, session):
    job = load_job(session, job_id)
    if job.status not in EDITABLE_STATUSES:
        raise ApplicationError(409, "Chỉ sửa nội dung sau khi Phase 1 hoàn tất.")
    current_content = content_text(job.package)
    if content_hash(job.package) != payload.expected_content_hash:
        raise ApplicationError(409, "Nội dung đã thay đổi. Hãy tải lại trang trước khi sửa tiếp.")
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
        session, edit_run, {"content_hash": content_digest(job.package)}, script_checks(job.package)
    )
    job.video, job.render_config = (None, None)
    job.status = "awaiting_review"
    job.result = {**(job.result or {}), "edited_after_analysis": True}
    session.add(
        JobEvent(
            job_id=job.id, status="awaiting_review", message="Video content edited; review required"
        )
    )
    session.commit()
    return job


def review(job_id: UUID, payload: Review, *, session):
    job = load_job(session, job_id)
    if job.status != "awaiting_review":
        raise ApplicationError(409, "Only packages awaiting review can be reviewed")
    if payload.expected_content_hash and payload.expected_content_hash != content_digest(
        job.package
    ):
        raise ApplicationError(409, "Nội dung đã đổi. Mở lại phiên bản mới trước khi duyệt.")
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


def import_keyword(payload, *, session, settings):
    from app.services.research_preferences import load_preferences

    research = payload.model_dump(mode="json", exclude={"branch", "language"})
    try:
        preferences = load_preferences(settings)
    except (ValueError, OSError):
        raise ApplicationError(422, "Cấu hình chủ đề bị lỗi; lưu lại trong Nguồn nghiên cứu.")
    if not research["preferred_url"]:
        for profile in preferences.profiles:
            if profile.branch == payload.branch and profile.topic_path == payload.topic_path:
                research["preferred_url"] = (
                    str(profile.preferred_url) if profile.preferred_url else None
                )
                break
    if not research["preferred_url"] and not research["search_web"]:
        raise ApplicationError(422, "Cần website ưu tiên hoặc bật tìm thêm trên web.")
    package = {
        "branch": payload.branch,
        "language": payload.language,
        "title": f"{payload.keyword} — {payload.target_date.strftime('%d/%m/%Y')}"[:200],
        "research": research,
        "sources": [{"label": "Đang tìm nguồn", "rights_note": "Chưa xác minh quyền sử dụng."}],
    }
    return create_job(JobCreate(package=package), session=session)
