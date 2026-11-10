"""Translate provider failures without returning credentials or authorization codes."""

import httpx

from app.infrastructure.local_lock import LocalBusy
from app.modules.errors import ApplicationError
from app.publishing import connection


def call(operation, *args):
    try:
        return operation(*args)
    except (connection.ConnectionFailure, LocalBusy) as exc:
        raise ApplicationError(409, str(exc)) from exc
    except (httpx.HTTPError, OSError, ValueError, KeyError):
        raise ApplicationError(
            502, "Chưa kết nối được Google/YouTube. Kiểm tra mạng và cấu hình OAuth."
        )


def configure(client_id, secret, settings):
    call(connection.configure, client_id.strip(), secret, settings)
    return connection.status(settings)


def start(settings):
    return call(connection.begin, settings)


def complete(code, state, settings):
    return call(connection.complete, code, state, settings)


def verify(settings):
    return call(connection.verify, settings)
