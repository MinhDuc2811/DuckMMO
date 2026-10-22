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
        for url in package.source_urls:
            check_running(session, job)
            session.commit()
            documents.append(dependencies.import_url(str(url)))
            check_running(session, job)
        # Commit raw input before analysis so it remains inspectable if analysis fails.
        data = package.model_dump(mode="json")
        data["source_documents"] = documents
        data["title"] = documents[0]["title"]
        data["sources"] = [
            {**data["sources"][i], "label": doc["title"], "url": doc["source_url"]}
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
