"""Explicit finite publishing authorization for reviewed English lessons."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.ielts import BriefInput
from app.contracts.study_pack import BackgroundId


class Episode(BriefInput):
    item_id: UUID


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    first_publish_at: datetime
    interval_hours: int = Field(default=24, ge=6, le=168)
    episodes: list[Episode] = Field(min_length=1, max_length=60)
    background_id: BackgroundId = "misty-lake"
    made_for_kids: bool
    allow_quality_warnings: bool = False

    @model_validator(mode="after")
    def timezone_required(self):
        if self.first_publish_at.tzinfo is None:
            raise ValueError("Lịch cần múi giờ cụ thể.")
        return self


class PlanToggle(BaseModel):
    enabled: bool
    authorize_auto_publish: bool = False
