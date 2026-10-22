"""Browser-to-disk clip upload; encoding is exercised separately with real FFmpeg."""

import subprocess

import httpx
import imageio_ffmpeg
from playwright.sync_api import expect

from e2e.conftest import stop_tree


def test_browser_upload_clip_and_queue(page, studio, tmp_path):
    job = studio.create_job("Clip upload fixture")
    studio.start_worker()
    studio.wait_status(job["id"], "awaiting_review")
    stop_tree(studio.worker)
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={
            "decision": "approve",
            "reviewer": "E2E",
            "note": "Self-authored clip",
        },
    ).raise_for_status()
    clip = tmp_path / "clip.mp4"
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x120:rate=24",
            "-t",
            "0.5",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            str(clip),
        ],
        capture_output=True,
        check=True,
        timeout=20,
    )
    page.goto(studio.ui_url)
    page.get_by_role("button", name="Clip upload fixture", exact=True).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    page.get_by_text("Clip", exact=True).click()
    uploader = page.get_by_test_id("stFileUploader")
    expect(uploader).to_contain_text("Clip cho video")
    uploader.locator("input[type=file]").set_input_files(clip)
    expect(page.get_by_text("clip.mp4", exact=True)).to_be_visible()
    page.get_by_role("button", name="Dựng video", exact=True).click()
    studio.wait_status(job["id"], "queued")
    current = studio.job(job["id"])
    assert current["render_config"]["video_file"] == "input-clip"
    assert current["render_config"]["image_files"] == []
    assets = httpx.get(studio.api_url + f"/api/jobs/{job['id']}/assets").json()
    assert len(assets) == 1 and assets[0]["kind"] == "video"
