import logging
from dataclasses import dataclass
from typing import Callable

from app.db import Job, JobEvent
from app.pipeline.lifecycle import JobCancelled, check_running, finish_cancel
from app.pipeline.steps.content import analyse_content, ingest_sources
from app.quality.recorder import (
    begin,
    close_interrupted,
    finish,
    observe_style,
)
from app.services.analysis import AnalysisFailure
from app.services.discovery import discover_sources
from app.services.video import VideoFailure
from app.services.web_import import ImportFailure

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineDependencies:
    import_url: Callable
    analyse: Callable
    preflight: Callable
    render_video: Callable
    discover: Callable = discover_sources


def execute_job(sessions, job_id, dependencies):
    try:
        with sessions() as session:
            job = session.get(Job, job_id)
            check_running(session, job)
            if job.render_config:
                produce_video(session, job, dependencies)
            else:
                produce_content(session, job, dependencies)
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


def produce_video(session, job, dependencies):
    job_id = job.id

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

    video = dependencies.render_video(job_id, job.package, job.render_config, progress, checkpoint)
    check_running(session, job)
    job.video = video
    job.status = "awaiting_video_review"
    job.error = None
    session.add(JobEvent(job_id=job_id, status=job.status, message="Video ready for final review"))
    session.commit()


def produce_content(session, job, dependencies):
    ingest_sources(session, job, dependencies)
    analyse_content(session, job, dependencies)
