import imageio_ffmpeg

from app.contracts.errors import VideoFailure
from app.infrastructure.media.commands import run_command


def encode_video(directory, config, style, width, height, elapsed, *, run_command=run_command):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    filters = "fps=24"
    if config["image_files"] and style["motion"] == "slow_zoom":
        filters += (
            f",zoompan=z='min(1+on*0.000015,1.06)':"
            f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=24"
        )
    filters += ",ass=subtitles.ass"
    run_command(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            "frames.ffconcat",
            "-i",
            "narration.wav",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            filters,
            "-c:v",
            "libx264",
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
