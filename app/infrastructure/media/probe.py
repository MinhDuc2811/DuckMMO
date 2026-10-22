"""Validate local image/clip content independently of upload and rendering."""

import json
import math
import shutil
import subprocess

import imageio_ffmpeg
from PIL import Image


class MediaFailure(ValueError):
    pass


def inspect_image(path):
    try:
        with Image.open(path) as image:
            if image.format not in ("PNG", "JPEG") or image.width * image.height > 20_000_000:
                raise MediaFailure("Chỉ nhận PNG/JPEG, tối đa 20 megapixel.")
            metadata = {"width": image.width, "height": image.height, "format": image.format}
            image.verify()
        return metadata
    except (OSError, Image.DecompressionBombError, ValueError) as exc:
        raise MediaFailure("Ảnh không hợp lệ; cần PNG/JPEG tối đa 20 megapixel.") from exc


def inspect_audio(path, settings):
    probe = shutil.which("ffprobe")
    if not probe:
        raise MediaFailure("Cần FFprobe để kiểm tra nhạc tải lên.")
    try:
        result = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "wav,mp3,flac,ogg,mov",
                "-show_entries",
                "format=duration:stream=codec_type",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )
        info = json.loads(result.stdout)
        duration = float(info["format"]["duration"])
        if not math.isfinite(duration) or not 0.5 <= duration <= 600:
            raise MediaFailure("Nhạc phải dài từ 0,5 đến 600 giây.")
        if not any(s["codec_type"] == "audio" for s in info["streams"]):
            raise MediaFailure("File không có âm thanh.")
        subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-v",
                "error",
                "-nostdin",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "wav,mp3,flac,ogg,mov",
                "-threads",
                str(settings.ffmpeg_threads),
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-t",
                "1",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )
        return {"duration": duration}
    except MediaFailure:
        raise
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise MediaFailure("Nhạc không hợp lệ; cần WAV/MP3/FLAC/OGG/M4A đọc được.") from exc


def inspect_video(path, settings):
    probe = shutil.which("ffprobe")
    if not probe:
        raise MediaFailure("Cần cài FFprobe (gói FFmpeg) để kiểm tra clip tải lên.")
    try:
        result = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,webm",
                "-show_entries",
                "format=duration,format_name:stream=codec_type,width,height,avg_frame_rate",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )
        info = json.loads(result.stdout)
        stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        duration = float(info["format"]["duration"])
        width, height = int(stream["width"]), int(stream["height"])
        numerator, denominator = stream["avg_frame_rate"].split("/")
        fps = float(numerator) / float(denominator)
        if not math.isfinite(duration) or not 0 < duration <= settings.media_max_duration:
            raise MediaFailure(f"Clip phải dài từ trên 0 đến {settings.media_max_duration:g} giây.")
        if not (0 < min(width, height) <= 1080 and max(width, height) <= 1920 and 0 < fps <= 60):
            raise MediaFailure("Clip tối đa 1920×1080 (hoặc dọc tương đương), 60 fps.")
        # Decode a real frame, rather than trusting extension or container metadata alone.
        subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-v",
                "error",
                "-nostdin",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,webm",
                "-threads",
                str(settings.ffmpeg_threads),
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )
        return {"width": width, "height": height, "duration": duration, "fps": fps}
    except MediaFailure:
        raise
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        StopIteration,
        ZeroDivisionError,
    ) as exc:
        raise MediaFailure("Clip không hợp lệ; cần video MP4/MOV/WebM đọc được.") from exc
