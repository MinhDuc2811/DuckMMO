from fastapi import APIRouter, Depends

from app.api.dependencies import authenticate, get_settings
from app.modules.settings.schemas import AIConnectionUpdate
from app.modules.settings.service import read_ai_connection, update_ai_connection

router = APIRouter(dependencies=[Depends(authenticate)])


@router.get("/api/settings/ai")
def read_connection(settings=Depends(get_settings)):
    return read_ai_connection(settings)


@router.put("/api/settings/ai")
def update_connection(payload: AIConnectionUpdate, settings=Depends(get_settings)):
    return update_ai_connection(payload, settings)
