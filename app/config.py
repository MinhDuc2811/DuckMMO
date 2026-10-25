from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STUDIO_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/studio.db"
    api_url: str = "http://127.0.0.1:8000"
    api_key: SecretStr = SecretStr("")
    search_provider: str = "duckduckgo"
    google_search_api_key: SecretStr = SecretStr("")
    google_search_engine_id: str = ""
    analysis_base_url: str = ""
    analysis_api_key: SecretStr = SecretStr("")
    analysis_model: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: SecretStr = SecretStr("")
    youtube_refresh_token: SecretStr = SecretStr("")
    speech_cache_enabled: bool = True
    style_catalog_url: str = ""
    artifact_dir: Path = Path("data/artifacts")
    media_upload_max_bytes: int = Field(default=100_000_000, ge=1)
    media_storage_max_bytes: int = Field(default=10_000_000_000, ge=1)
    media_min_free_bytes: int = Field(default=500_000_000, ge=0)
    media_max_duration: float = Field(default=120, gt=0)
    render_max_duration: float = Field(default=600, gt=0)
    ffmpeg_threads: int = Field(default=2, ge=1, le=16)

    def prepare_database_directory(self) -> None:
        url = make_url(self.database_url)
        if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
