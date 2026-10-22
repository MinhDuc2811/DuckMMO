from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AIConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str = Field(min_length=1, max_length=2000)
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr = SecretStr("")
    structured_output: bool = False
    timeout_seconds: int = Field(default=120, ge=30, le=600)
