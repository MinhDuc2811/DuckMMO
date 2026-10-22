"""Declarative auto styles, pinned per render; no downloaded executable templates."""

import hashlib
import json
import time
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import Settings
from app.infrastructure.persistence.styles import learned_style
from app.services.web_import import PublicWebTransport


class VideoStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9-]{1,40}$")
    name: str = Field(min_length=1, max_length=80)
    branch: Literal["novel", "comic", "research"]
    accent: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    background: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    font_size: int = Field(ge=32, le=56)
    outline: int = Field(ge=1, le=5)
    motion: Literal["slow_zoom", "static"]
    fade_ms: int = Field(ge=0, le=300)
    caption_chars: int = Field(ge=24, le=60)


class StyleCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    styles: list[VideoStyle] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def require_all_branches(self):
        if len({s.id for s in self.styles}) != len(self.styles):
            raise ValueError("Duplicate style IDs")
        if {s.branch for s in self.styles} != {"novel", "comic", "research"}:
            raise ValueError("Catalog must cover all three content branches")
        return self


def load_catalog():
    settings = Settings()
    builtin = Path(__file__).with_name("styles.json").read_bytes()
    if not settings.style_catalog_url:
        return builtin, "builtin"
    source = settings.style_catalog_url
    cache = settings.artifact_dir.resolve() / "style-catalog-cache"
    cache.mkdir(parents=True, exist_ok=True)
    cache_file = cache / (hashlib.sha256(source.encode()).hexdigest() + ".json")
    try:
        started = time.monotonic()
        with httpx.Client(
            transport=PublicWebTransport(), timeout=5, follow_redirects=True, max_redirects=3
        ) as client:
            with client.stream("GET", source) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 128_000 or time.monotonic() - started > 10:
                        raise ValueError("Catalog exceeds limits")
                    chunks.append(chunk)
        raw = b"".join(chunks)
        StyleCatalog.model_validate_json(raw)
        # A failed update never destroys the last validated catalog.
        temporary = cache_file.with_suffix(".tmp")
        temporary.write_bytes(raw)
        temporary.replace(cache_file)
        return raw, "synced"
    except (httpx.HTTPError, ValueError, OSError):
        try:
            raw = cache_file.read_bytes()
            StyleCatalog.model_validate_json(raw)
            return raw, "cached_after_sync_failure"
        except (ValueError, OSError):
            return builtin, "builtin_after_sync_failure"


def choose_style(package, use_learned=True, *, session=None):
    # Return a snapshot, so updates never change queued or running jobs.
    raw, sync_status = load_catalog()
    catalog = StyleCatalog.model_validate_json(raw)
    branch = package.get("branch", "novel")
    style = next(s for s in catalog.styles if s.branch == branch)
    selected = {
        **style.model_dump(),
        "catalog_version": catalog.version,
        "catalog_sha256": hashlib.sha256(raw).hexdigest(),
        "selection_reason": f"Tự chọn theo loại nội dung: {branch}",
        "engine": "ffmpeg-libass",
        "sync_status": sync_status,
    }
    if use_learned:
        learned = learned_style(branch, session)
        if learned:
            selected = learned
    return selected


def ass_time(seconds):
    centis = round(seconds * 100)
    return (
        f"{centis // 360000:01}:{centis // 6000 % 60:02}:{centis // 100 % 60:02}.{centis % 100:02}"
    )


def ass_escape(text):
    # User text cannot inject ASS override tags or line-break commands.
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N")


def write_ass(directory, cues, style, width, height):
    accent = "&H00" + style["accent"][5:7] + style["accent"][3:5] + style["accent"][1:3]
    size = style["font_size"] if width == 720 else int(style["font_size"] * 0.85)
    margin = int(height * 0.16)
    fields = (
        "Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    values = (
        f"Auto,Arial,{size},&H00FFFFFF,{accent},&H00101010,&H80000000,-1,0,0,0,100,100,"
        f"0,0,1,{style['outline']},1,2,54,54,{margin},1"
    )
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: {fields}
Style: {values}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for start, end, text in cues:
        fade = min(style["fade_ms"], int((end - start) * 1000 / 4))
        effect = r"{\fad(" + f"{fade},{fade}" + ")}"
        lines.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Auto,,0,0,0,,{effect}{ass_escape(text)}"
        )
    (directory / "subtitles.ass").write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    (directory / "style.json").write_text(
        json.dumps(style, ensure_ascii=False, indent=2), encoding="utf-8"
    )
