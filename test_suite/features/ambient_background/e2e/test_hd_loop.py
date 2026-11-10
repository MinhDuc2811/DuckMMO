"""Real browser/API/worker/FFmpeg. Speech is a declared fixture tone, not a voice audition."""

import httpx
from playwright.sync_api import expect


def settled(page):
    expect(page.get_by_test_id("stApp")).to_have_attribute("data-test-script-state", "notRunning")


def test_choose_hd_and_ambient_background_then_download(page, studio, gradient_clip):
    studio.env["IELTS_E2E_ISOLATED_DIRECTORY"] = str(studio.directory.resolve())
    studio.worker = studio.spawn("worker", ["-m", "test_suite.support.ielts_fixture_worker"])
    response = httpx.post(
        studio.api_url + "/api/jobs",
        json={
            "package": {
                "branch": "novel",
                "language": "en",
                "title": "Ambient HD fixture",
                "sources": [{"label": "Original fixture", "rights_note": "Original test only"}],
                "scenes": [
                    {
                        "narration": "Green space is an area with grass and trees.",
                        "source_indices": [0],
                    }
                ],
            }
        },
    )
    response.raise_for_status()
    job = response.json()
    studio.wait_status(job["id"], "awaiting_review")
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "Fixture", "note": "Original fixture"},
    ).raise_for_status()
    page.goto(studio.ui_url)
    page.get_by_role("button", name="Ambient HD fixture", exact=True).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    settled(page)
    page.get_by_role("button", name="Dùng Khung trắng", exact=True).click()
    settled(page)
    page.get_by_text("Clip", exact=True).click()
    settled(page)
    uploader = page.get_by_test_id("stFileUploader")
    expect(uploader).to_have_count(1)
    expect(uploader).to_contain_text("Clip cho video")
    uploader.locator("input[type=file]").set_input_files(gradient_clip)
    expect(page.get_by_text("gradient.mp4", exact=True)).to_be_visible()
    voice = page.get_by_role("combobox", name="Giọng đọc", exact=True)
    voice.fill("Aria")
    voice.press("ArrowDown")
    voice.press("Enter")
    quality = page.get_by_role("combobox", name="Chất lượng xuất", exact=True)
    quality.fill("Final HD")
    quality.press("ArrowDown")
    quality.press("Enter")
    page.get_by_text("Tối ưu clip nền cho Khung trắng", exact=True).click()
    expect(
        page.get_by_role("checkbox", name="Tối ưu clip nền cho Khung trắng", exact=True)
    ).to_be_checked()
    page.get_by_role("button", name="Dựng video", exact=True).click()
    studio.wait_status(job["id"], "awaiting_video_review")
    rendered = studio.job(job["id"])
    assert (rendered["video"]["width"], rendered["video"]["height"]) == (1080, 1920)
    assert rendered["video"]["delivery"]["video_encode_passes"] == 1
    assert rendered["video"]["quality"]["background"]["crossfade_frames"] > 0
    page.get_by_role("button", name="Mở video để xem và duyệt", exact=True).click()
    expect(
        page.get_by_role("button", name="Tải báo cáo chất lượng JSON", exact=True)
    ).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("button", name="Tải video MP4", exact=True).click()
    assert download.value.path().stat().st_size > 1000
    assert rendered["status"] == "awaiting_video_review"
