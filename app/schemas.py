from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.contracts.presentation import MusicOptions, VisualOptions
from app.contracts.research import ResearchRequest
from app.contracts.voices import get_voice


class Branch(StrEnum):
    COMIC = "comic"
    NOVEL = "novel"
    RESEARCH = "research"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    AWAITING_VIDEO_REVIEW = "awaiting_video_review"
    VIDEO_APPROVED = "video_approved"
    VIDEO_REJECTED = "video_rejected"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    label: str = Field(min_length=1, max_length=300)
    url: HttpUrl | None = None
    rights_note: str = Field(min_length=1, max_length=2000)


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    narration: str = Field(min_length=1, max_length=10000)
    visual_note: str = Field(default="", max_length=2000)
    source_indices: list[int] = Field(default_factory=list, max_length=50)


class ContentPackage(BaseModel):
    """Provisional v1 contract; reconcile with the original Master Plan DOCX."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal["1.0"] = "1.0"
    branch: Branch
    title: str = Field(min_length=1, max_length=200)
    language: Literal["vi", "en", "zh", "ja", "ko"] = "vi"
    sources: list[Source] = Field(min_length=1, max_length=50)
    scenes: list[Scene] = Field(default_factory=list, max_length=200)
    research: ResearchRequest | None = None
    discovery: dict | None = None
    source_urls: list[HttpUrl] = Field(default_factory=list, max_length=10)
    source_documents: list[dict] = Field(default_factory=list, max_length=10)
    video_content: str | None = Field(default=None, min_length=1, max_length=200000)

    @model_validator(mode="after")
    def validate_references(self):
        if not self.scenes and not self.source_urls and self.research is None:
            raise ValueError("Content requires scenes or source URLs to fetch in Phase 1")
        for scene in self.scenes:
            if any(i < 0 or i >= len(self.sources) for i in scene.source_indices):
                raise ValueError("Scene references an unknown source index")
            if self.branch == Branch.RESEARCH and not scene.source_indices:
                raise ValueError("Research narration must reference at least one source")
        return self


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package: ContentPackage


class ContentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=200000)
    expected_content_hash: str


class WebImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl | None = None
    urls: list[HttpUrl] = Field(default_factory=list, max_length=10)
    branch: Branch = Branch.NOVEL
    language: Literal["vi", "en", "zh", "ja", "ko"] = "vi"

    @model_validator(mode="after")
    def require_urls(self):
        if not self.urls and self.url is None:
            raise ValueError("At least one source URL is required")
        if len(self.urls) + int(self.url is not None) > 10:
            raise ValueError("At most 10 source URLs per content")
        return self


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=4000)
    labels: list[
        Literal[
            "incorrect_fact",
            "missing_content",
            "wording",
            "pronunciation",
            "subtitle_overflow",
            "subtitle_pacing",
            "subtitle_sync",
            "visual_relevance",
            "editing_pace",
            "other",
        ]
    ] = Field(default_factory=list, max_length=10)
    timecode: float | None = Field(default=None, ge=0, le=86400)
    expected_content_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class SpeechOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice: str = Field(default="vi-VN-HoaiMyNeural", min_length=1, max_length=80)
    speech_rate: int = Field(default=0, ge=-30, le=30)

    @field_validator("voice")
    @classmethod
    def supported_voice(cls, value):
        get_voice(value)
        return value


class VoicePreview(SpeechOptions):
    text: str = Field(min_length=1, max_length=300)

    @field_validator("text")
    @classmethod
    def nonempty_text(cls, value):
        if not value.strip():
            raise ValueError("Đoạn nghe thử không được để trống.")
        return value


class AudioPreview(VoicePreview):
    music: MusicOptions = Field(default_factory=MusicOptions)


class RenderOptions(SpeechOptions):
    visual: VisualOptions = Field(default_factory=VisualOptions)
    music: MusicOptions = Field(default_factory=MusicOptions)
    layout: Literal["portrait", "landscape"] = "portrait"
    images: list[str] = Field(default_factory=list, max_length=10)
    image_asset_ids: list[UUID] = Field(default_factory=list, max_length=10)
    video_asset_id: UUID | None = None
    video_fit: Literal["pad", "crop"] = "pad"
    expected_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def bound_images(self):
        if self.video_asset_id and (self.images or self.image_asset_ids):
            raise ValueError("Chọn ảnh hoặc clip, không chọn cả hai.")
        if len(self.images) + len(self.image_asset_ids) > 10:
            raise ValueError("Tối đa 10 ảnh")
        if any(len(image) > 4_000_000 for image in self.images):
            raise ValueError("Mỗi ảnh tối đa 3 MB")
        return self


class VideoReview(Review):
    expected_video_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: JobStatus
    package: ContentPackage
    result: dict | None
    error: str | None
    attempts: int
    created_at: datetime
    updated_at: datetime
    render_config: dict | None = None
    video: dict | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    message: str
    created_at: datetime


class YouTubePublish(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    privacy: Literal["private", "unlisted", "public"] = "private"
    made_for_kids: bool
    expected_video_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class KeywordImport(ResearchRequest):
    branch: Branch = Branch.RESEARCH
    language: Literal["vi", "en", "zh", "ja", "ko"] = "vi"
