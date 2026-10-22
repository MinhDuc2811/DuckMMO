import secrets
from typing import Annotated

from fastapi import Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError


def authenticate(request: Request, x_api_key: Annotated[str | None, Header()] = None):
    expected = request.app.state.settings.api_key.get_secret_value()
    if expected and not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(401, "Invalid API key")


def get_engine(request: Request):
    return request.app.state.engine


def get_session(request: Request):
    with request.app.state.sessions() as session:
        try:
            yield session
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, "Thao tác bị xung đột. Làm mới rồi thử lại.")
        except StaleDataError:
            session.rollback()
            raise HTTPException(409, "Job changed concurrently; refresh and try again")


def get_settings(request: Request):
    return request.app.state.settings
