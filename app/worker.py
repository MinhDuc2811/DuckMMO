"""Phase 1: fetch sources, persist raw inputs, analyse, then release to human review."""

import argparse
import logging
import os
import subprocess
import sys
import time

import psutil
from sqlalchemy import select, update

from app.config import Settings
from app.db import Job, JobEvent, make_engine, make_sessions, now
from app.quality.evaluators import script_checks, source_checks
from app.quality.recorder import (
    begin,
    close_interrupted,
    content_digest,
    digest,
    finish,
    observe_style,
    revision,
)
from app.schemas import ContentPackage
from app.services.analysis import AnalysisFailure, analyse
from app.services.local_lock import LocalBusy, exclusive_lock
from app.services.media_cleanup import cleanup
from app.services.media_storage import LocalMediaStorage
from app.services.preflight import preflight
from app.services.video import VideoFailure, render_video
from app.services.web_import import ImportFailure, import_url

logger = logging.getLogger(__name__)


class JobCancelled(Exception):
    pass


def check_running(session, job):
    session.refresh(job)
    if job.status != "running":
        raise JobCancelled()


def finish_cancel(sessions, job_id):
    with sessions() as session:
        job = session.get(Job, job_id)
        if job and job.status == "cancelling":
            job.status = "cancelled"
            close_interrupted(session, job_id, "cancelled")
            session.add(JobEvent(job_id=job_id, status="cancelled", message="Job process stopped"))
            session.commit()


def claim_one(sessions) -> str | None:
    with sessions() as session:
        job_id = session.scalar(
            select(Job.id)
            .where(Job.deleted_at.is_(None), Job.status == "queued")
            .order_by(Job.created_at)
            .limit(1)
        )
        if job_id is None:
            return None
        claimed = session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "queued")
            .values(
                status="running",
                attempts=Job.attempts + 1,
                version=Job.version + 1,
                updated_at=now(),
            )
        )
        if claimed.rowcount != 1:
            session.rollback()
            return None
        claimed_job = session.get(Job, job_id)
        session.add(
            JobEvent(
                job_id=job_id,
                status="running",
                message=(
                    "Video production started" if claimed_job.render_config else "Phase 1 started"
                ),
            )
        )
        session.commit()
        return job_id


def execute_job(sessions, job_id):
    try:
        with sessions() as session:
            job = session.get(Job, job_id)
            check_running(session, job)
            if job.render_config:

                def progress(message):
                    check_running(session, job)
                    session.add(JobEvent(job_id=job_id, status="running", message=message))
                    session.commit()

                active_runs = {}

                def checkpoint(step, state, output=None, evaluations=()):
                    check_running(session, job)
                    if state == "start":
                        active_runs[step] = begin(session, job, step, config=job.render_config)
                    else:
                        run = active_runs.pop(step)
                        finish(session, run, output, evaluations)
                        observe_style(session, job, run, evaluations)
                    session.commit()

                video = render_video(job_id, job.package, job.render_config, progress, checkpoint)
                check_running(session, job)
                job.video = video
                job.status = "awaiting_video_review"
                job.error = None
                session.add(
                    JobEvent(
                        job_id=job_id, status=job.status, message="Video ready for final review"
                    )
                )
                session.commit()
                return
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
                    documents.append(import_url(str(url)))
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
            analysis_run = begin(session, job, "analysis", config={"prompt_version": "analysis-v1"})
            check_running(session, job)
            session.add(JobEvent(job_id=job_id, status="running", message="Analysis started"))
            session.commit()
            if job.package.get("source_documents"):
                analysis = analyse(ContentPackage.model_validate(job.package))
                check_running(session, job)
                job.package = {**job.package, "video_content": analysis["video_content"]}
            else:
                analysis = None
            job.result = preflight(ContentPackage.model_validate(job.package))
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
    except JobCancelled:
        finish_cancel(sessions, job_id)
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        with sessions() as session:
            job = session.get(Job, job_id)
            if job is None or job.status != "running":
                finish_cancel(sessions, job_id)
                return
            close_interrupted(session, job_id, "failed")
            job.status = "failed"
            job.error = (
                f"Crawl [{exc.stage}]: {exc}"
                if isinstance(exc, ImportFailure)
                else str(exc)
                if isinstance(exc, (AnalysisFailure, VideoFailure))
                else "Analysis failed; inspect worker logs and retry."
            )
            session.add(JobEvent(job_id=job_id, status="failed", message=job.error))
            session.commit()


def process_one(sessions) -> bool:
    """In-process entry point for deterministic tests; production uses isolated children."""
    job_id = claim_one(sessions)
    if job_id is None:
        return False
    execute_job(sessions, job_id)
    return True


def stop_process(process):
    if process.poll() is None:
        try:
            children = psutil.Process(process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        # Windows venv python.exe can be a launcher for another python.exe.
        # Stop its descendants as well; killing the launcher alone leaves the job alive.
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        _, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        _, survivors = psutil.wait_procs(alive, timeout=3)
        if survivors:
            raise RuntimeError("Unable to stop job descendants")


def supervise_job(sessions, job_id, process):
    """Monitor only the child handle we own; never kill an arbitrary PID from the database."""
    try:
        while process.poll() is None:
            with sessions() as session:
                job = session.get(Job, job_id)
                cancelling = job is None or job.status in ("cancelling", "cancelled")
            if cancelling:
                stop_process(process)
                finish_cancel(sessions, job_id)
                return
            time.sleep(0.2)
    except BaseException:
        stop_process(process)
        raise
    finally:
        with sessions() as session:
            job = session.get(Job, job_id)
            if job and job.status == "running":
                close_interrupted(session, job_id, "failed")
                job.status = "failed"
                job.error = "Tiến trình xử lý đã dừng đột ngột. Có thể thử lại tác vụ."
                session.add(JobEvent(job_id=job_id, status="failed", message=job.error))
                session.commit()
        finish_cancel(sessions, job_id)


def recover_interrupted(sessions):
    # Called once on supervisor startup (single local supervisor supported).
    with sessions() as session:
        for job in session.scalars(select(Job).where(Job.status.in_(("running", "cancelling")))):
            close_interrupted(
                session, job.id, "cancelled" if job.status == "cancelling" else "failed"
            )
            job.status = "cancelled" if job.status == "cancelling" else "failed"
            job.error = "Worker trước đã ngắt. Có thể thử lại." if job.status == "failed" else None
            session.add(
                JobEvent(
                    job_id=job.id,
                    status=job.status,
                    message="Recovered interrupted worker execution",
                )
            )
        session.commit()


def run_isolated(sessions, job_id):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [sys.executable, "-m", "app.worker", "--job-id", job_id], creationflags=flags
    )
    supervise_job(sessions, job_id, process)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    parser.add_argument("--job-id", help=argparse.SUPPRESS)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    settings.prepare_database_directory()
    engine = make_engine(settings.database_url)
    sessions = make_sessions(engine)
    try:
        if args.job_id:
            execute_job(sessions, args.job_id)
            return
        storage = LocalMediaStorage(settings)
        with exclusive_lock(storage.root / ".worker.lock"):
            try:
                cleanup(storage, sessions, apply=True)
            except LocalBusy:
                logger.info("Skipping retention cleanup while an upload is active")
            recover_interrupted(sessions)
            while True:
                job_id = claim_one(sessions)
                handled = job_id is not None
                if job_id:
                    run_isolated(sessions, job_id)
                if args.once:
                    break
                if not handled:
                    time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
