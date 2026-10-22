from app.db import Job
from app.modules.errors import ApplicationError


def load_job(session, job_id):
    job = session.get(Job, str(job_id))
    if job is None or job.deleted_at is not None:
        raise ApplicationError(404, "Job not found")
    return job
