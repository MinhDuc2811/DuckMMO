"""Local AI connection settings shared by the UI and worker."""

import json
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.config import Settings


class AIConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    base_url: str = Field(min_length=1, max_length=2000)
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr
    structured_output: bool = False
    timeout_seconds: int = Field(default=120, ge=30, le=600)

    @model_validator(mode="after")
    def valid_connection(self):
        url = urlsplit(self.base_url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError("URL AI phải là HTTP/HTTPS và không chứa thông tin đăng nhập.")
        if not self.api_key.get_secret_value().strip():
            raise ValueError("Cần API key của nhà cung cấp AI.")
        return self


def connection_path(settings=None):
    return (settings or Settings()).artifact_dir.resolve().parent / "settings" / "analysis.json"


def load_connection(settings=None):
    settings = settings or Settings()
    path = connection_path(settings)
    if path.exists():
        return AIConnection.model_validate_json(path.read_text(encoding="utf-8"))
    if all(
        (
            settings.analysis_base_url,
            settings.analysis_model,
            settings.analysis_api_key.get_secret_value(),
        )
    ):
        return AIConnection(
            base_url=settings.analysis_base_url,
            model=settings.analysis_model,
            api_key=settings.analysis_api_key,
        )
    return None


def save_connection(base_url, model, api_key, *, settings=None, **options):
    connection = AIConnection(base_url=base_url, model=model, api_key=api_key, **options)
    path = connection_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "base_url": connection.base_url,
                "model": connection.model,
                "api_key": connection.api_key.get_secret_value(),
                "structured_output": connection.structured_output,
                "timeout_seconds": connection.timeout_seconds,
            }
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
    return connection
