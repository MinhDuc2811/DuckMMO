"""Separate Stickman workspace contracts, not IELTS jobs or render presets."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StickmanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    style: Literal["B1", "B2", "B3", "B4"] = "B1"
    ratio: Literal["9:16", "16:9"] = "9:16"


class StickmanEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    project: dict


class StickmanAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    seconds: float = Field(default=20, gt=0, le=60, allow_inf_nan=False)
    note: str = Field(default="", max_length=1000)
    preview_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class StickmanStarter(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    audio_path: str = Field(max_length=100)
    caption: str = Field(min_length=1, max_length=58)


class DirectorBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source: str = Field(min_length=1, max_length=20000)
    style: Literal["A1", "A2", "A3", "A4", "A5", "A6"]
    ratio: Literal["9:16", "16:9"]
    seconds: int = Field(default=60, ge=10, le=300, multiple_of=10)
