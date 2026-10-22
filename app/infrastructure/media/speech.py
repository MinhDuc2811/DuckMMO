"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import asyncio
import hashlib
import json
import os
import shutil
import wave
from importlib.metadata import version
from pathlib import Path
from urllib.request import getproxies, proxy_bypass
from uuid import uuid4

import edge_tts
import imageio_ffmpeg

from app.config import Settings
from app.contracts.errors import VideoFailure
from app.contracts.voices import get_voice
from app.infrastructure.media.audio import validate_pcm
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.storage import LocalMediaStorage


def edge_proxy():
    """Route WSS through the supplied HTTPS proxy while respecting NO_PROXY."""
    if proxy_bypass("speech.platform.bing.com"):
        return None
    proxies = getproxies()
    return proxies.get("wss") or proxies.get("https")


def _synthesize(text, voice, directory, index, rate=0, *, settings=None):
    settings = settings or Settings()
    destination = directory / f"voice-{index:04}.wav"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    definition = get_voice(voice)
    if definition.provider == "windows":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if os.name != "nt" or not shell:
            raise VideoFailure("Giọng trên máy cần Windows. Hãy chọn giọng Edge TTS.")
        text_path = directory / f"voice-{index:04}.txt"
        text_path.write_text(text, encoding="utf-8")
        language = "vi-VN" if voice == "local-vi" else "en-US"
        run_command(
            [
                shell,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str((Path(__file__).resolve().parents[2] / "services" / "sapi_tts.ps1").resolve()),
                "-TextPath",
                str(text_path),
                "-OutputPath",
                str(destination),
                "-Language",
                language,
                "-Rate",
                str(round(rate / 10)),
            ],
            cwd=directory,
            timeout=60,
        )
    else:
        mp3 = directory / f"voice-{index:04}.mp3"
        try:
            asyncio.run(
                asyncio.wait_for(
                    edge_tts.Communicate(text, voice, rate=f"{rate:+d}%", proxy=edge_proxy()).save(
                        str(mp3)
                    ),
                    90,
                )
            )
        except Exception as exc:
            raise VideoFailure(
                "Không tạo được giọng Edge TTS. Kiểm tra mạng hoặc chọn giọng Windows local."
            ) from exc
        run_command(
            [ffmpeg, "-y", "-i", str(mp3), "-ar", "22050", "-ac", "1", str(destination)],
            cwd=directory,
        )
    with wave.open(str(destination)) as audio:
        duration = audio.getnframes() / audio.getframerate()
    if duration <= 0:
        raise VideoFailure("Giọng đọc tạo ra không có thời lượng.")
    return destination.name, duration


def synthesize(text, voice, directory, index, rate=0, *, settings=None):
    """Cache raw, untrimmed audio so layout-only renders do not call TTS again."""
    settings = settings or Settings()
    definition = get_voice(voice)
    # Local installed voices can change outside this application; do not cache them.
    if not settings.speech_cache_enabled or definition.provider == "windows":
        return _synthesize(text, voice, directory, index, rate, settings=settings)
    key = hashlib.sha256(
        json.dumps(
            {
                "text": text,
                "voice": voice,
                "rate": rate,
                "format": "pcm-s16-mono-22050",
                "version": 1,
                "edge_tts": version("edge-tts"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    cache = settings.artifact_dir.resolve() / "speech-cache"
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / f"{key}.wav"
    destination = directory / f"voice-{index:04}.wav"
    if cached.is_file():
        try:
            duration = validate_pcm(cached)
        except (wave.Error, EOFError, ValueError):
            cached.unlink(missing_ok=True)
        else:
            try:
                LocalMediaStorage(settings).ensure_capacity(cached.stat().st_size)
            except MediaFailure as exc:
                raise VideoFailure(str(exc)) from exc
            shutil.copyfile(cached, destination)
            return destination.name, duration
    filename, duration = _synthesize(text, voice, directory, index, rate, settings=settings)
    validate_pcm(destination)
    try:
        LocalMediaStorage(settings).ensure_capacity(destination.stat().st_size)
    except MediaFailure:
        # Caching is optional: preserve the usable render audio when cache budget is tight.
        return filename, duration
    temporary = cache / f"{key}.{uuid4()}.part"
    try:
        shutil.copyfile(destination, temporary)
        temporary.replace(cached)
    finally:
        temporary.unlink(missing_ok=True)
    return filename, duration
