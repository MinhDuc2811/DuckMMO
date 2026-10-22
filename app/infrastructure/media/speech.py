"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import asyncio
import os
import shutil
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg

from app.contracts.errors import VideoFailure
from app.infrastructure.media.commands import run_command


def synthesize(text, voice, directory, index):
    destination = directory / f"voice-{index:04}.wav"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if voice.startswith("local-"):
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
            ],
            cwd=directory,
            timeout=60,
        )
    else:
        mp3 = directory / f"voice-{index:04}.mp3"
        try:
            asyncio.run(asyncio.wait_for(edge_tts.Communicate(text, voice).save(str(mp3)), 90))
        except Exception as exc:
            raise VideoFailure(
                "Không tạo được giọng Edge TTS. Kiểm tra mạng hoặc chọn giọng trên máy."
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
