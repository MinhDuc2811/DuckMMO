from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import authenticate, get_session, get_settings
from app.contracts.automation import PlanInput, PlanToggle
from app.modules.automation import service

router = APIRouter(prefix="/api/automation", dependencies=[Depends(authenticate)])


@router.get("/plans")
def plans(session=Depends(get_session)):
    return service.list_plans(session=session)


@router.post("/plans", status_code=201)
def create(payload: PlanInput, settings=Depends(get_settings), session=Depends(get_session)):
    return service.create_plan(payload, settings=settings, session=session)


@router.put("/plans/{plan_id}")
def toggle(
    plan_id: UUID, payload: PlanToggle, settings=Depends(get_settings), session=Depends(get_session)
):
    return service.toggle(plan_id, payload, settings=settings, session=session)
