from app.modules.errors import ApplicationError
from app.modules.settings.schemas import AIConnectionUpdate
from app.services.ai_connection import load_connection, save_connection


def public_connection(connection):
    return connection.model_dump(mode="json", exclude={"api_key"}) if connection else None


def read_ai_connection(settings):
    try:
        return public_connection(load_connection(settings))
    except (ValueError, OSError):
        return None


def update_ai_connection(payload: AIConnectionUpdate, settings):
    try:
        try:
            existing = load_connection(settings)
        except (ValueError, OSError):
            existing = None
        secret = payload.api_key.get_secret_value() or (
            existing.api_key.get_secret_value() if existing else ""
        )
        connection = save_connection(
            payload.base_url,
            payload.model,
            secret,
            settings=settings,
            structured_output=payload.structured_output,
            timeout_seconds=payload.timeout_seconds,
        )
    except (ValueError, OSError):
        raise ApplicationError(422, "Chưa lưu được. Kiểm tra URL HTTP/HTTPS, tên model và API key.")
    return public_connection(connection)
