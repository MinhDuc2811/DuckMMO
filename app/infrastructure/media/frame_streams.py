"""Raw frame pipes with explicit ownership, bounded memory and child reaping."""

import subprocess

import imageio_ffmpeg
from PIL import Image

from app.config import Settings
from app.contracts.errors import VideoFailure
from app.infrastructure.media.probe import inspect_video
from app.infrastructure.processes import stop_process


def clip_frames(path, threads):
    metadata = inspect_video(path, Settings())
    size = (metadata["width"], metadata["height"])
    frame_bytes = size[0] * size[1] * 3
    with (path.parent / "scene-decoder.log").open("wb") as log:
        process = subprocess.Popen(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-v",
                "error",
                "-nostdin",
                "-stream_loop",
                "-1",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,webm",
                "-threads",
                str(threads),
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-an",
                "-vf",
                "fps=24",
                "-filter_threads",
                str(threads),
                "-threads",
                str(threads),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=log,
        )
        try:
            while True:
                raw = process.stdout.read(frame_bytes)
                if len(raw) != frame_bytes:
                    raise VideoFailure("Không đọc được frame của clip; xem scene-decoder.log.")
                yield Image.frombytes("RGB", size, raw)
        finally:
            process.stdout.close()
            stop_process(process)
            process.wait()


def encode_frames(images, path, size, fps, threads):
    with (path.parent / "scene-encoder.log").open("wb") as log:
        process = subprocess.Popen(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                "-v",
                "error",
                "-f",
                "rawvideo",
                "-pixel_format",
                "rgb24",
                "-video_size",
                f"{size[0]}x{size[1]}",
                "-framerate",
                str(fps),
                "-i",
                "pipe:0",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-threads",
                str(threads),
                "-preset",
                "veryfast",
                "-crf",
                "23",
                str(path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=log,
            bufsize=0,
        )
        try:
            for image in images:
                raw = memoryview(image.tobytes())
                while raw:
                    written = process.stdin.write(raw)
                    if not written:
                        raise VideoFailure("FFmpeg đã đóng pipe frame.")
                    raw = raw[written:]
            process.stdin.close()
            if process.wait(timeout=30):
                raise VideoFailure("Không xuất được scene; xem scene-encoder.log.")
        except BaseException:
            process.stdin.close()
            stop_process(process)
            raise
        finally:
            images.close()
            process.stdin.close()
            process.wait()
