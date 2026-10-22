from fastapi import APIRouter, Depends

from app.api.dependencies import authenticate, get_engine
from app.api.system import capabilities, health

router = APIRouter()
protected = [Depends(authenticate)]


@router.get("/health", name="health")
def endpoint_health(engine=Depends(get_engine)):
    return health(engine=engine)


@router.get("/api/capabilities", dependencies=protected, name="capabilities")
def endpoint_capabilities():
    return capabilities()
