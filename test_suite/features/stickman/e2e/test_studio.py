"""Real browser -> separate workspace -> actual upstream renderer; PCM tone, no TTS."""

import hashlib

import httpx
from playwright.sync_api import expect

from test_suite.support.stickman import pcm


def settled(page):
    expect(page.get_by_test_id("stApp")).to_have_attribute("data-test-script-state", "notRunning")


def test_separate_stickman_workspace_upload_preview_approve_render_download(page, studio, tmp_path):
    audio = tmp_path / "original-fixture.wav"
    audio.write_bytes(pcm())
    page.goto(studio.ui_url)
    page.get_by_text("Stickman Studio", exact=True).click()
    expect(page.get_by_role("heading", name="Stickman Studio", exact=True)).to_be_visible()
    settled(page)
    assert httpx.get(studio.api_url + "/api/jobs").json() == []
    page.get_by_role("textbox", name="Tên dự án Stickman", exact=True).fill(
        "Separate Stickman fixture"
    )
    page.get_by_role("button", name="Tạo dự án riêng", exact=True).click()
    settled(page)
    page.locator('input[type="file"]').set_input_files(audio)
    page.get_by_role("textbox", name="Nguồn và quyền dùng file", exact=True).fill(
        "Original PCM fixture, not a speech recording"
    )
    page.get_by_role("button", name="Lưu file vào dự án", exact=True).click()
    settled(page)
    page.get_by_text("Tạo timeline B1 minh họa nhanh", exact=True).click()
    page.get_by_role("textbox", name="Caption ngắn cho đoạn minh họa", exact=True).fill(
        "Learn one idea at a time."
    )
    page.get_by_role("button", name="Tạo timeline B1", exact=True).click()
    settled(page)
    expect(page.get_by_role("button", name="Render MP4 Stickman", exact=True)).to_be_disabled()
    page.get_by_role("button", name="Dựng preview Stickman", exact=True).click()
    expect(page.get_by_role("button", name="Tải preview Stickman", exact=True)).to_be_visible(
        timeout=90000
    )
    settled(page)
    preview = page.locator("video")
    expect(preview).to_have_count(1)
    page.wait_for_function("document.querySelector('video').readyState >= 2")
    page.get_by_role("textbox", name="Nhận xét sau khi xem và nghe preview", exact=True).fill(
        "Automated technical fixture only; not actual human speech/aesthetic approval"
    )
    page.get_by_role("button", name="Duyệt preview Stickman", exact=True).click()
    settled(page)
    page.get_by_role("button", name="Render MP4 Stickman", exact=True).click()
    expect(page.get_by_role("button", name="Tải MP4 Stickman", exact=True)).to_be_visible(
        timeout=90000
    )
    with page.expect_download() as download:
        page.get_by_role("button", name="Tải MP4 Stickman", exact=True).click()
    downloaded = download.value.path()
    items = httpx.get(studio.api_url + "/api/stickman/projects").json()
    assert len(items) == 1 and items[0]["state"] == "rendered"
    with downloaded.open("rb") as file:
        assert hashlib.file_digest(file, "sha256").hexdigest() == items[0]["film_sha256"]
    with page.expect_download() as subtitles:
        page.get_by_role("button", name="Tải phụ đề Stickman", exact=True).click()
    assert "Learn one idea at a time." in subtitles.value.path().read_text()
    assert httpx.get(studio.api_url + "/api/jobs").json() == []
    assert studio.provider_requests == []
