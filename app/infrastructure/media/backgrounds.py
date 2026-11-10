"""Measured shot selection and bounded-memory ambient looping; no source downloads."""

import json
import math
import re
import subprocess

import imageio_ffmpeg
from PIL import Image

from app.config import Settings
from app.contracts.errors import VideoFailure
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.probe import inspect_video
from app.infrastructure.media.storage import file_digest
from app.infrastructure.processes import stop_process


def select_background(path, options, fps, threads):
    info = inspect_video(path, Settings())
    start = options["start_seconds"]
    duration = min(options["duration_seconds"], info["duration"] - start)
    if duration < 3:
        raise VideoFailure("Đoạn nền cần ít nhất 3 giây trong phạm vi clip.")
    cuts = []
    if options["auto_scene"]:
        result = run_command(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-hide_banner",
                "-nostdin",
                "-nostats",
                "-ss",
                str(start),
                "-t",
                str(duration),
                "-protocol_whitelist",
                "file,pipe",
                "-threads",
                str(threads),
                "-i",
                str(path),
                "-an",
                "-vf",
                "scale=320:-2,fps=4,select='gt(scene,0.3)',showinfo",
                "-filter_threads",
                str(threads),
                "-f",
                "null",
                "-",
            ],
            cwd=path.parent,
            timeout=60,
        )
        cuts = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", result.stderr.decode())]
        points = [0, *sorted({t for t in cuts if 0 < t < duration}), duration]
        first, last = max(zip(points, points[1:]), key=lambda pair: pair[1] - pair[0])
        start, duration = start + first, last - first
        if duration < 3:
            raise VideoFailure("Clip đổi cảnh quá nhanh. Chọn đoạn khác hoặc tắt tự chọn cảnh.")
    count = math.floor(duration * fps)
    frame_bytes = info["width"] * info["height"] * 3
    fade = (
        min(round(0.35 * fps), count // 4, 64_000_000 // frame_bytes)
        if options["smooth_loop"]
        else 0
    )
    report = {
        "version": 1,
        "source_sha256": file_digest(path),
        "start_seconds": start,
        "duration_seconds": count / fps,
        "source_size": [info["width"], info["height"]],
        "fps": fps,
        "scene_sample_fps": 4 if options["auto_scene"] else None,
        "detected_cuts_seconds": cuts,
        "crossfade_frames": fade,
        "period_frames": count - fade,
        "head_buffer_max_bytes": fade * frame_bytes,
        "limitation": "Shot/crossfade checks do not establish relevance or hide every seam.",
    }
    (path.parent / "background-analysis.json").write_text(json.dumps(report, indent=2))
    return info, report


def segment_frames(path, info, report, threads):
    width, height = info["width"], info["height"]
    count = round(report["duration_seconds"] * report["fps"])
    with (path.parent / "background-decoder.log").open("ab") as log:
        process = subprocess.Popen(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-v",
                "error",
                "-nostdin",
                "-ss",
                str(report["start_seconds"]),
                "-protocol_whitelist",
                "file,pipe",
                "-threads",
                str(threads),
                "-i",
                str(path),
                "-an",
                "-vf",
                f"fps={report['fps']}",
                "-filter_threads",
                str(threads),
                "-frames:v",
                str(count),
                "-pix_fmt",
                "rgb24",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=log,
        )
        try:
            for _ in range(count):
                raw = process.stdout.read(width * height * 3)
                if len(raw) != width * height * 3:
                    raise VideoFailure("Không giải mã đủ đoạn nền; xem background-decoder.log.")
                yield Image.frombytes("RGB", (width, height), raw)
            if process.wait(timeout=15):
                raise VideoFailure("Bộ giải mã background báo lỗi.")
        finally:
            process.stdout.close()
            stop_process(process)
            process.wait()


def ambient_frames(path, options, fps, threads):
    info, report = select_background(path, options, fps, threads)
    count = round(report["duration_seconds"] * fps)
    fade, head = report["crossfade_frames"], []
    first_cycle = True
    while True:
        reader = segment_frames(path, info, report, threads)
        try:
            for index, frame in enumerate(reader):
                if first_cycle and index < fade:
                    head.append(frame)
                if not first_cycle and index < fade:
                    continue
                if fade and index >= count - fade:
                    offset = index - (count - fade)
                    frame = Image.blend(frame, head[offset], (offset + 1) / fade)
                yield frame
            first_cycle = False
        finally:
            reader.close()
