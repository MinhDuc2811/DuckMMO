from pathlib import Path

import imageio_ffmpeg
import pytest

from app.infrastructure.media.commands import run_command


@pytest.fixture
def output_clip(tmp_path):
    def make(
        *,
        color="#559988",
        sound="sine=frequency=440:sample_rate=22050",
        audio=True,
        seconds=2,
        size="240x426",
        video_filter=None,
    ):
        path = tmp_path / "video.mp4"
        args = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={size}:r=25",
        ]
        if audio:
            args += ["-f", "lavfi", "-i", sound]
        args += ["-t", str(seconds), "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p"]
        if video_filter:
            args += ["-vf", video_filter]
        if audio:
            args += ["-c:a", "aac"]
        run_command([*args, str(path)], cwd=tmp_path)
        return Path(path)

    return make
