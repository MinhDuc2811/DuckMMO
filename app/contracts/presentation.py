"""Versioned, data-only presentation contracts shared by API and renderer."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

PresetId = Literal["auto", "editorial", "comic", "minimal", "kinetic", "scrapbook", "gallery"]


class VisualOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: PresetId = "auto"
    layout: Literal["preset", "full", "collage", "panels", "quote", "mix"] = "preset"
    intensity: Literal["gentle", "medium", "strong"] = "medium"
    transition: Literal["cut", "fade", "slide"] = "fade"
    accent: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    seed: int = Field(default=0, ge=0, le=2147483647)


class MusicOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: UUID | None = None
    track: Literal["ambient", "pulse"] | None = None
    volume: float = Field(default=0.16, ge=0, le=0.5, allow_inf_nan=False)
    ducking: bool = True
    start_seconds: float = Field(default=0, ge=0, le=600, allow_inf_nan=False)

    @model_validator(mode="after")
    def one_source(self):
        if self.asset_id and self.track:
            raise ValueError("Chỉ chọn một nguồn nhạc nền.")
        return self


PRESETS = {
    "editorial": dict(name="Editorial", layout="collage", background="#171c32", accent="#ffb454"),
    "comic": dict(name="Comic", layout="panels", background="#f0dfb7", accent="#e24845"),
    "minimal": dict(name="Minimal", layout="quote", background="#152b2b", accent="#9de4c1"),
    "kinetic": dict(name="Kinetic", layout="full", background="#24153d", accent="#d4f36b"),
    "scrapbook": dict(name="Scrapbook", layout="collage", background="#42332f", accent="#f4caa4"),
    "gallery": dict(name="Gallery", layout="panels", background="#142437", accent="#92c9ff"),
}


def presentation_catalog():
    return {
        "version": 1,
        "presets": [{"id": key, **value} for key, value in PRESETS.items()],
        "tracks": [
            {"id": "ambient", "name": "Nền êm", "license": "Original synthesized audio"},
            {"id": "pulse", "name": "Nhịp nhẹ", "license": "Original synthesized audio"},
        ],
    }


def apply_presentation(style, options):
    if options.preset == "auto":
        return style
    preset = PRESETS[options.preset]
    return {
        **style,
        "id": options.preset,
        "name": preset["name"],
        "background": preset["background"],
        "accent": options.accent or preset["accent"],
        "selection_reason": "Người dùng chọn; không giới hạn loại nội dung",
        "engine": "pillow-scenes-v1+ffmpeg-libass",
    }
