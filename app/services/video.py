"""Compatibility facade; media adapters and production orchestration have separate owners."""

from app.contracts.captions import split_captions, timestamp
from app.contracts.content import content_hash, content_text
from app.contracts.errors import VideoFailure
from app.infrastructure.media.artifacts import artifact_directory, prepare_render
from app.modules.production.render import render_video

__all__ = [
    "content_hash",
    "content_text",
    "split_captions",
    "timestamp",
    "VideoFailure",
    "artifact_directory",
    "prepare_render",
    "render_video",
]
