"""Versioned delivery profiles; old requests keep their existing rendering contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProfileId = Literal["preview", "final"]
PROFILES = {
    "preview": {"short_edge": 720, "fps": 24, "crf": 23, "preset": "veryfast"},
    "final": {"short_edge": 1080, "fps": 30, "crf": 19, "preset": "medium"},
}


def profile(config):
    return PROFILES[config.get("render_quality", "preview")]


def dimensions(config):
    edge = profile(config)["short_edge"]
    wide = edge * 16 // 9
    return (edge, wide) if config["layout"] == "portrait" else (wide, edge)


class BackgroundOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_seconds: float = Field(default=0, ge=0, le=117, allow_inf_nan=False)
    duration_seconds: float = Field(default=8, ge=3, le=20, allow_inf_nan=False)
    smooth_loop: bool = True
    auto_scene: bool = True
