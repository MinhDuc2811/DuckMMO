from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STUDIO_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/studio.db"
    api_url: str = "http://127.0.0.1:8000"
    api_key: SecretStr = SecretStr("")
    analysis_base_url: str = ""
    analysis_api_key: SecretStr = SecretStr("")
    analysis_model: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: SecretStr = SecretStr("")
    youtube_refresh_token: SecretStr = SecretStr("")
    style_catalog_url: str = ""
    artifact_dir: Path = Path("data/artifacts")

    def prepare_database_directory(self) -> None:
        url = make_url(self.database_url)
        if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
