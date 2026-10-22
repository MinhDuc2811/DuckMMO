from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routers import content, jobs, production, publishing, quality, system
from app.api.routers import settings as settings_routes
from app.config import Settings
from app.db import make_engine, make_sessions
from app.modules.errors import ApplicationError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.prepare_database_directory()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        engine.dispose()

    api = FastAPI(title="AI Content Studio", version="0.1.0", lifespan=lifespan)
    api.state.settings = settings
    api.state.engine = engine
    api.state.sessions = make_sessions(engine)

    @api.exception_handler(ApplicationError)
    async def application_error(_request: Request, exc: ApplicationError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    for module in (content, system, jobs, production, quality, publishing, settings_routes):
        api.include_router(module.router)
    return api
