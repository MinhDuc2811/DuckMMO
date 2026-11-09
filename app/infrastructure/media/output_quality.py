"""Full-file FFmpeg quality analysis of the actual delivered MP4, without rewriting it."""

import json
import math
import re
import shutil

import imageio_ffmpeg

from app.config import Settings
from app.contracts.errors import VideoFailure
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.storage import file_digest
from app.quality.evaluators import check, has_blocker

VERSION = "ffmpeg-output-v1"
NUMBER = r"-?\d+(?:\.\d+)?"


def measurement(value):
    """Non-finite loudnorm values (including silence) are represented by JSON null."""
    number = float(value)
    return number if math.isfinite(number) else None


def signal_checks(log, duration):
    loudness = re.findall(r'\{\s*"input_i".*?\}', log, re.S)
    if not loudness:
        raise ValueError("Missing final loudness measurements")
    values = json.loads(loudness[-1])
    integrated, peak = measurement(values["input_i"]), measurement(values["input_tp"])
    black = [
        {"start": float(start), "end": float(end)}
        for start, end in re.findall(
            rf"black_start:({NUMBER}) black_end:({NUMBER}) black_duration:{NUMBER}", log
        )
    ]
    starts = [float(t) for t in re.findall(rf"silence_start: ({NUMBER})", log)]
    ends = [float(t) for t in re.findall(rf"silence_end: ({NUMBER})", log)]
    silence = [
        {"start": start, "end": ends[i] if i < len(ends) else duration}
        for i, start in enumerate(starts)
    ]
    black_fraction = sum(max(0, b["end"] - b["start"]) for b in black) / duration
    return [
        check(
            "output_audio_signal",
            "fail" if peak is None or peak < -50 else "pass",
            {"true_peak_dbtp": peak, "silence_threshold_db": -50},
        ),
        check(
            "output_loudness",
            "warn" if integrated is None or not -24 <= integrated <= -12 else "pass",
            {
                "integrated_lufs": integrated,
                "review_range_lufs": [-24, -12],
                "limitation": "Editorial review range, not a YouTube requirement",
            },
        ),
        check(
            "output_audio_peak",
            "warn" if peak is not None and peak > -1 else "pass",
            {
                "true_peak_dbtp": peak,
                "review_above_dbtp": -1,
                "limitation": "Peak headroom warning, not proof of clipping or distortion",
            },
        ),
        check(
            "output_silence",
            "warn" if silence else "pass",
            {"spans": silence, "minimum_seconds": 1, "threshold_db": -50},
        ),
        check(
            "black_frames",
            "fail" if black_fraction >= 0.95 else "warn" if black else "pass",
            {
                "spans": black,
                "fraction": round(black_fraction, 4),
                "minimum_seconds": 0.5,
                "pixel_threshold": 0.1,
                "picture_threshold": 0.98,
                "limitation": (
                    "Checks near-black full frames; cannot detect black footage behind a white card"
                ),
            },
        ),
    ]


def inspect_output(directory, elapsed, width, height, *, run_command=run_command):
    """Always return a fail-closed report; the renderer records it before enforcing the gate."""
    settings = Settings()
    path = directory / "video.mp4"
    evaluations = []
    try:
        probe = shutil.which("ffprobe")
        if not probe:
            raise VideoFailure("Cần cài FFprobe để kiểm tra video thành phẩm.")
        result = run_command(
            [
                probe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_entries",
                "format=duration:stream=codec_type,width,height,duration",
                "-of",
                "json",
                "video.mp4",
            ],
            cwd=directory,
            timeout=30,
        )
        info = json.loads(result.stdout)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
        durations = [
            float(info["format"]["duration"]),
            float(video["duration"]),
            float(audio["duration"]),
        ]
        valid = all(math.isfinite(d) and d > 0 and abs(d - elapsed) <= 0.3 for d in durations)
        evaluations.append(
            check(
                "output_streams",
                "pass"
                if valid and (video["width"], video["height"]) == (width, height)
                else "fail",
                {
                    "expected_seconds": elapsed,
                    "durations_seconds": durations,
                    "width": video["width"],
                    "height": video["height"],
                    "expected_size": [width, height],
                    "tolerance_seconds": 0.3,
                },
            )
        )
        # Do not decode unbounded or wrongly sized output after a structural failure.
        if not has_blocker(evaluations):
            result = run_command(
                [
                    imageio_ffmpeg.get_ffmpeg_exe(),
                    "-hide_banner",
                    "-nostdin",
                    "-nostats",
                    "-xerror",
                    "-err_detect",
                    "explode",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-threads",
                    str(settings.ffmpeg_threads),
                    "-i",
                    "video.mp4",
                    "-filter_threads",
                    str(settings.ffmpeg_threads),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0",
                    "-vf",
                    "blackdetect=d=0.5:pix_th=0.1:pic_th=0.98",
                    "-af",
                    "silencedetect=n=-50dB:d=1,loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                    "-threads",
                    str(settings.ffmpeg_threads),
                    "-f",
                    "null",
                    "-",
                ],
                cwd=directory,
                timeout=max(60, int(elapsed * 3)),
            )
            evaluations.extend(signal_checks(result.stderr.decode(errors="replace"), elapsed))
            evaluations.append(
                check("output_full_decode", "pass", {"scope": "All audio and video frames"})
            )
    except (VideoFailure, OSError, ValueError, KeyError, StopIteration, TypeError) as exc:
        evaluations.append(
            check(
                "output_full_decode",
                "fail",
                {
                    "reason": "Không hoàn tất kiểm tra file/hình/tiếng; xem engine-error.log.",
                    "error_type": type(exc).__name__,
                },
            )
        )
    report = {
        "version": VERSION,
        "engine": "FFmpeg/FFprobe",
        "status": "fail"
        if has_blocker(evaluations)
        else "warn"
        if any(e["outcome"] == "warn" for e in evaluations)
        else "pass",
        "sha256": file_digest(path) if path.is_file() else None,
        "evaluations": evaluations,
        "limitations": [
            "Chưa xác minh phát âm Anh–Anh, tính đúng của bài học hoặc độ khớp từng từ.",
            "Không đánh giá độ hấp dẫn, độ nét chữ, mức nhạc lấn giọng hoặc dự đoán lượt xem.",
            "Nền ảnh tĩnh hợp lệ; không dùng phát hiện đứng hình để chặn video.",
        ],
    }
    (directory / "output-quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
