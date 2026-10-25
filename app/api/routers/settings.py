from fastapi import APIRouter, Depends

from app.api.dependencies import authenticate, get_settings
from app.contracts.research import ResearchPreferences
from app.modules.settings.schemas import AIConnectionUpdate
from app.modules.settings.service import (
    read_ai_connection,
    read_research,
    update_ai_connection,
    update_research,
)

router = APIRouter(dependencies=[Depends(authenticate)])


@router.get("/api/settings/ai")
def read_connection(settings=Depends(get_settings)):
    return read_ai_connection(settings)


@router.put("/api/settings/ai")
def update_connection(payload: AIConnectionUpdate, settings=Depends(get_settings)):
    return update_ai_connection(payload, settings)


@router.get("/api/settings/research")
def read_research_preferences(settings=Depends(get_settings)):
    return read_research(settings)


@router.put("/api/settings/research")
def update_research_preferences(payload: ResearchPreferences, settings=Depends(get_settings)):
    return update_research(payload, settings)
