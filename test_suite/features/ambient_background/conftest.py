import imageio_ffmpeg
import pytest

from app.infrastructure.media.commands import run_command


@pytest.fixture
def gradient_clip(tmp_path):
    path = tmp_path / "gradient.mp4"
    run_command(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "nullsrc=s=240x426:r=30:d=4,geq=lum='16+210*N/119':cb=128:cr=128",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        cwd=tmp_path,
    )
    return path
