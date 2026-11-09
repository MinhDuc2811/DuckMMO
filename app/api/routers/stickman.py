"""Authenticated, independent Stickman Studio endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response

from app.api.dependencies import authenticate, get_settings
from app.contracts.stickman import (
    DirectorBrief,
    StickmanAction,
    StickmanCreate,
    StickmanEdit,
    StickmanStarter,
)
from app.modules.stickman import service

router = APIRouter(prefix="/api/stickman", dependencies=[Depends(authenticate)])


@router.get("/doctor")
def doctor(settings=Depends(get_settings)):
    return service.doctor(settings)


@router.get("/projects")
def projects(settings=Depends(get_settings)):
    return service.projects(settings)


@router.post("/projects", status_code=201)
def create(payload: StickmanCreate, settings=Depends(get_settings)):
    return service.create(payload, settings)


@router.get("/projects/{project_id}")
def project(project_id: UUID, settings=Depends(get_settings)):
    return service.get(project_id, settings)


@router.put("/projects/{project_id}")
def edit(project_id: UUID, payload: StickmanEdit, settings=Depends(get_settings)):
    return service.edit(project_id, payload, settings)


@router.post("/projects/{project_id}/assets", status_code=201)
async def upload(
    project_id: UUID,
    request: Request,
    filename: str = Query(min_length=1, max_length=120),
    rights_note: str = Query(min_length=1, max_length=1000),
    settings=Depends(get_settings),
):
    return await service.upload(project_id, filename, rights_note, request.stream(), settings)


@router.post("/projects/{project_id}/starter")
def starter(project_id: UUID, payload: StickmanStarter, settings=Depends(get_settings)):
    return service.starter(project_id, payload, settings)


@router.post("/projects/{project_id}/actions/{command}")
def action(
    project_id: UUID,
    command: Literal["validate", "preview", "approve", "render"],
    payload: StickmanAction,
    settings=Depends(get_settings),
):
    return service.action(project_id, command, payload, settings)


@router.get("/projects/{project_id}/artifacts/{kind}")
def artifact(
    project_id: UUID,
    kind: Literal["preview", "film", "preview-srt", "film-srt", "contact"],
    settings=Depends(get_settings),
):
    path = service.artifact(project_id, kind, settings)
    return FileResponse(path, filename=path.name)


@router.post("/director-kit")
def kit(payload: DirectorBrief):
    return Response(
        service.director_kit(payload),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="stickman-director-kit.zip"'},
    )
