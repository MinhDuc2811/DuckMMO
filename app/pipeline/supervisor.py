import os
import subprocess
import sys
import time

from sqlalchemy import select

from app.db import Job, JobEvent
from app.infrastructure.processes import stop_process
from app.pipeline.lifecycle import finish_cancel
from app.quality.recorder import (
    close_interrupted,
)


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
