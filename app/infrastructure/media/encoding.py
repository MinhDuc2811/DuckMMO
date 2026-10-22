import imageio_ffmpeg

from app.config import Settings
from app.contracts.errors import VideoFailure
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.storage import LocalMediaStorage
from app.infrastructure.media.visuals import input_arguments, visual_filters


def encode_video(directory, config, style, width, height, elapsed, *, run_command=run_command):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    settings = Settings()
    try:
        LocalMediaStorage(settings).ensure_capacity(int(elapsed * 4_000_000))
        visual_input = input_arguments(config, directory, settings.ffmpeg_threads)
    except MediaFailure as exc:
        raise VideoFailure(str(exc)) from exc
    filters = visual_filters(config, style, width, height)
    run_command(
        [
            ffmpeg,
            "-y",
            "-nostdin",
            "-filter_threads",
            str(settings.ffmpeg_threads),
            *visual_input,
            "-i",
            config.get("audio_file", "narration.wav"),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            filters,
            "-c:v",
            "libx264",
            "-threads",
            str(settings.ffmpeg_threads),
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-t",
            str(elapsed),
            "-fs",
            str(max(1_000_000, int(elapsed * 4_000_000))),
            "-movflags",
            "+faststart",
            "video.mp4",
        ],
        cwd=directory,
        timeout=max(300, int(elapsed * 3)),
    )


def inspect_video(directory, elapsed, *, run_command=run_command):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    sample_times = sorted({0.0, max(0, elapsed / 2), max(0, elapsed - 0.25)})
    for sample_time in sample_times:
        run_command(
            [
                ffmpeg,
                "-v",
                "error",
                "-ss",
                str(sample_time),
                "-i",
                "video.mp4",
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-t",
                "0.2",
                "-f",
                "null",
                "-",
            ],
            cwd=directory,
        )
    run_command(
        [ffmpeg, "-y", "-ss", "0.5", "-i", "video.mp4", "-frames:v", "1", "poster.png"],
        cwd=directory,
    )
    reader = imageio_ffmpeg.read_frames(str(directory / "video.mp4"))
    try:
        metadata = next(reader)
    finally:
        reader.close()
    if abs(metadata["duration"] - elapsed) > 0.3:
        raise VideoFailure("Thời lượng video lệch giọng đọc. Không chuyển sang bước duyệt.")
    return metadata, sample_times
