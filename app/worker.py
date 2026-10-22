"""Worker CLI and provider composition; process control and pipeline are independent."""

import argparse
import logging
import time

from app.config import Settings
from app.db import make_engine, make_sessions
from app.pipeline.lifecycle import claim_one
from app.pipeline.runner import PipelineDependencies
from app.pipeline.runner import execute_job as run_pipeline
from app.pipeline.supervisor import recover_interrupted, run_isolated, supervise_job
from app.services.analysis import analyse
from app.services.preflight import preflight
from app.services.video import render_video
from app.services.web_import import import_url

__all__ = ["claim_one", "process_one", "recover_interrupted", "run_isolated", "supervise_job"]


def execute_job(sessions, job_id):
    dependencies = PipelineDependencies(import_url, analyse, preflight, render_video)
    return run_pipeline(sessions, job_id, dependencies)


def process_one(sessions) -> bool:
    """In-process entry point for deterministic tests; production uses isolated children."""
    job_id = claim_one(sessions)
    if job_id is None:
        return False
    execute_job(sessions, job_id)
    return True


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
