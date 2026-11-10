import json

import imageio_ffmpeg
import pytest

from app.config import Settings
from app.infrastructure.media.commands import run_command
from app.modules.production.render import MediaAdapters, render_video
from tests.test_media import audio_fixture
from tests.test_video import approved_script


@pytest.mark.parametrize(
    "visual",
    [
        {"preset": "lesson-card"},
        {"preset": "auto", "layout": "lesson_card"},
        {"preset": "editorial", "layout": "lesson_card"},
    ],
)
def test_hd_final_remuxes_identical_h264_and_keeps_audio_and_qa(client, visual):
    job_id, digest = approved_script(client)
    queued = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": digest,
            "render_quality": "final",
            "visual": visual,
        },
    )
    assert queued.status_code == 200, queued.text
    job = queued.json()
    result = render_video(
        job_id,
        job["package"],
        job["render_config"],
        lambda _: None,
        adapters=MediaAdapters(synthesize=audio_fixture),
    )
    assert (result["width"], result["height"]) == (1080, 1920)
    assert result["delivery"]["fps"] == 30
    assert result["delivery"]["video_encode_passes"] == 1
    assert result["quality"]["output"]["status"] in ("pass", "warn")
    directory = Settings().artifact_dir / job_id / result["run_id"]
    hashes = []
    for filename in ("motion.mp4", "video.mp4"):
        decoded = run_command(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-v",
                "error",
                "-i",
                filename,
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-f",
                "hash",
                "-hash",
                "sha256",
                "-",
            ],
            cwd=directory,
        )
        hashes.append(decoded.stdout)
    assert hashes[0] == hashes[1], "Final mux must preserve the exact encoded video packets"
    plan = json.loads((directory / "scene-plan.json").read_text())
    assert plan["fps"] == 30
    assert plan["style"]["card_safe_right"] == 0.16
    from PIL import Image

    reader = imageio_ffmpeg.read_frames(str(directory / "video.mp4"))
    try:
        meta = next(reader)
        frame = Image.frombytes("RGB", meta["size"], next(reader))
        assert meta["fps"] == 30
    finally:
        reader.close()
    assert min(frame.getpixel((86, 384))) > 230
    assert max(frame.getpixel((972, 384))) < 230  # right-side control region remains background
