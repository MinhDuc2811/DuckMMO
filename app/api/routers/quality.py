from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import authenticate, get_session
from app.modules.quality.service import (
    activate,
    experiments,
    export_dataset,
    quality,
    rerun_benchmark,
    rollback,
)

router = APIRouter()
protected = [Depends(authenticate)]


@router.get("/api/jobs/{job_id}/quality", dependencies=protected, name="quality")
def endpoint_quality(job_id: UUID, session=Depends(get_session)):
    return quality(job_id=job_id, session=session)


@router.get("/api/learning/experiments", dependencies=protected, name="experiments")
def endpoint_experiments(session=Depends(get_session)):
    return experiments(session=session)


@router.post(
    "/api/learning/experiments/{experiment_id}/promote", dependencies=protected, name="activate"
)
def endpoint_activate(experiment_id: UUID, session=Depends(get_session)):
    return activate(experiment_id=experiment_id, session=session)


@router.post(
    "/api/learning/experiments/{experiment_id}/benchmark",
    dependencies=protected,
    name="rerun_benchmark",
)
def endpoint_rerun_benchmark(experiment_id: UUID, session=Depends(get_session)):
    return rerun_benchmark(experiment_id=experiment_id, session=session)


@router.post("/api/learning/configs/{config_id}/rollback", dependencies=protected, name="rollback")
def endpoint_rollback(config_id: UUID, session=Depends(get_session)):
    return rollback(config_id=config_id, session=session)


@router.get("/api/learning/dataset", dependencies=protected, name="export_dataset")
def endpoint_export_dataset(session=Depends(get_session)):
    return export_dataset(session=session)
