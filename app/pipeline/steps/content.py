from datetime import datetime

from sqlalchemy import select

from app.db import Job, JobEvent
from app.pipeline.lifecycle import JobCancelled, check_running
from app.quality.evaluators import script_checks, source_checks
from app.quality.recorder import (
    begin,
    content_digest,
    digest,
    finish,
    revision,
)
from app.schemas import ContentPackage
from app.services.web_import import ImportFailure


def ingest_sources(session, job, dependencies):
    job_id = job.id
    package = ContentPackage.model_validate(job.package)
    if package.research and not package.source_urls:

        def checkpoint():
            check_running(session, job)
            session.commit()

        session.add(
            JobEvent(
                job_id=job_id, status="running", message="Discovery started: searching sources"
            )
        )
        checkpoint()
        discovery = dependencies.discover(package.research, checkpoint=checkpoint)
        check_running(session, job)
        data = package.model_dump(mode="json")
        data["source_urls"] = discovery["urls"]
        data["discovery"] = discovery
        data["sources"] = [
            {
                "label": url[:300],
                "url": url,
                "rights_note": "Nguồn tìm tự động; chưa xác minh quyền sử dụng.",
            }
            for url in discovery["urls"]
        ]
        package = ContentPackage.model_validate(data)
        job.package = package.model_dump(mode="json")
        session.add(
            JobEvent(
                job_id=job_id,
                status="running",
                message=f"Discovery completed: {len(discovery['urls'])} sources",
            )
        )
        session.commit()
    source_run = None
    if package.source_urls:
        source_run = begin(
            session,
            job,
            "sources",
            config={
                "extractor": "http-trafilatura-v1",
                "reused": bool(package.source_documents),
            },
        )
        session.commit()
    if package.source_urls and not package.source_documents:
        documents = []
        fetched_sources = []
        crawl_warnings = []
        for source_index, url in enumerate(package.source_urls):
            check_running(session, job)
            session.commit()
            try:
                documents.append(dependencies.import_url(str(url)))
                fetched_sources.append(package.sources[source_index])
            except ImportFailure as exc:
                if not package.research:
                    raise
                crawl_warnings.append({"url": str(url), "error": str(exc)})
            check_running(session, job)
        # Commit raw input before analysis so it remains inspectable if analysis fails.
        if not documents:
            raise ImportFailure(
                "Không đọc được nội dung các nguồn đã tìm. Kiểm tra website/mạng.", "extract"
            )
        data = package.model_dump(mode="json")
        if package.research:
            date_warnings = []
            for document in documents:
                published = document.get("published_at")
                try:
                    published_date = datetime.fromisoformat(published).date() if published else None
                except (ValueError, TypeError):
                    published_date = None
                if published_date != package.research.target_date:
                    date_warnings.append(
                        {
                            "url": document["source_url"],
                            "published_at": published,
                            "reason": "different_date" if published_date else "unknown_date",
                        }
                    )
            data["discovery"] = {
                **(data["discovery"] or {}),
                "crawl_warnings": crawl_warnings,
                "date_warnings": date_warnings,
            }
        data["source_documents"] = documents
        if not package.research:
            data["title"] = documents[0]["title"]
        data["sources"] = [
            {
                **fetched_sources[i].model_dump(mode="json"),
                "label": doc["title"],
                "url": doc["source_url"],
            }
            for i, doc in enumerate(documents)
        ]
        data["video_content"] = "\n\n".join(doc["content"] for doc in documents)
        if len(data["video_content"]) > 200000:
            raise ImportFailure("Tổng nội dung vượt 200.000 ký tự.", "size")
        data["scenes"] = [
            {"narration": doc["content"][start : start + 10000], "source_indices": [i]}
            for i, doc in enumerate(documents)
            for start in range(0, len(doc["content"]), 10000)
        ]
        job.package = ContentPackage.model_validate(data).model_dump(mode="json")
        session.add(
            JobEvent(
                job_id=job_id,
                status="running",
                message=f"Crawl completed: {len(documents)} sources",
            )
        )
        session.commit()
    if source_run:
        finish(
            session,
            source_run,
            {"documents_hash": digest(job.package["source_documents"])},
            source_checks(job.package["source_documents"]),
        )


def analyse_content(session, job, dependencies):
    job_id = job.id
    analysis_run = begin(session, job, "analysis", config={"prompt_version": "analysis-v1"})
    check_running(session, job)
    session.add(JobEvent(job_id=job_id, status="running", message="Analysis started"))
    session.commit()
    if job.package.get("source_documents"):
        analysis = dependencies.analyse(ContentPackage.model_validate(job.package))
        check_running(session, job)
        job.package = {**job.package, "video_content": analysis["video_content"]}
    else:
        analysis = None
    job.result = dependencies.preflight(ContentPackage.model_validate(job.package))
    if analysis:
        job.result = {
            **job.result,
            "analysis": {**analysis, "source_count": len(job.package["sources"])},
        }
    analysis_run.revision_id = revision(session, job).id
    finish(
        session,
        analysis_run,
        {
            "analysis": analysis or {"type": "structural"},
            "content_hash": content_digest(job.package),
        },
        script_checks(job.package),
    )
    # Refresh/check BEFORE assigning result; ORM version checking guards a cancel
    # racing with this final commit as well.
    if session.scalar(select(Job.status).where(Job.id == job_id)) != "running":
        raise JobCancelled()
    job.status = "awaiting_review"
    job.error = None
    session.add(
        JobEvent(
            job_id=job_id,
            status=job.status,
            message="Phase 1 complete; ready for Phase 2 review",
        )
    )
    session.commit()
