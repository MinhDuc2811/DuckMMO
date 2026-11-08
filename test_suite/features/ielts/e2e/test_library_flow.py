"""Real library-to-MP4 flow. Only speech synthesis uses an offline PCM fixture."""

import hashlib

import httpx
from playwright.sync_api import expect


def settled(page):
    expect(page.get_by_test_id("stApp")).to_have_attribute("data-test-script-state", "notRunning")


def test_library_topic_vocabulary_review_one_focus_short_render_download(page, studio, tmp_path):
    studio.env["IELTS_E2E_ISOLATED_DIRECTORY"] = str(studio.directory.resolve())
    studio.env["STUDIO_STYLE_CATALOG_URL"] = ""
    studio.worker = studio.spawn("worker", ["-m", "test_suite.support.ielts_fixture_worker"])
    page.goto(studio.ui_url)
    page.get_by_role("tab", name="Thư viện IELTS", exact=True).click()
    settled(page)
    page.get_by_text("Thêm topic", exact=True).click()
    page.get_by_role("textbox", name="Tên topic", exact=True).fill("Education")
    page.get_by_role("button", name="Lưu topic", exact=True).click()
    settled(page)
    page.get_by_text("Thêm nội dung / nhập JSON", exact=True).click()
    page.get_by_role("textbox", name="Tên mục học", exact=True).fill("Adapt to a new school")
    topics = page.get_by_role("combobox", name="Topic của nội dung", exact=True)
    topics.fill("Education")
    topics.press("ArrowDown")
    topics.press("Enter")
    # Multiselect stays open for more choices; Tab dismisses the popup before authoring.
    topics.press("Tab")
    page.get_by_role("textbox", name="Nguồn nội dung", exact=True).fill("Original browser fixture")
    page.get_by_role("textbox", name="Quyền sử dụng nội dung", exact=True).fill(
        "Original test only, not official IELTS"
    )
    page.get_by_role("button", name="Lưu bản nháp", exact=True).click()
    settled(page)
    page.get_by_text("Adapt to a new school · draft", exact=True).click()
    expect(page.get_by_role("button", name="Tạo Short từ mục này", exact=True)).to_be_disabled()
    page.get_by_role("textbox", name="Người duyệt", exact=True).fill("Teacher fixture")
    page.get_by_role(
        "textbox", name="Ghi chú kiểm tra kiến thức và quyền sử dụng", exact=True
    ).fill("Checked original example and meaning")
    page.get_by_role("button", name="Duyệt mục học", exact=True).click()
    settled(page)
    page.get_by_text("Adapt to a new school · reviewed", exact=True).click()
    script = "Adapt means to change. Students adapt to a new school."
    page.get_by_role(
        "textbox", name="Lời đọc cho một Short (một ý, tối đa 85 từ)", exact=True
    ).fill(script)
    page.get_by_role("button", name="Tạo Short từ mục này", exact=True).click()
    workspace = page.locator(".st-key-workspace-panel")
    expect(workspace.get_by_text("Chờ kiểm duyệt", exact=True)).to_be_visible(timeout=20000)
    with httpx.Client(base_url=studio.api_url) as api:
        library = api.get("/api/ielts/vocabulary").json()["items"]
        assert len(library) == 1 and library[0]["status"] == "reviewed"
        jobs = api.get("/api/jobs").json()
        assert len(jobs) == 1
        job_id = jobs[0]["id"]
        assert jobs[0]["package"]["language"] == "en"
        assert jobs[0]["package"]["scenes"][0]["narration"] == script
    page.get_by_role("tab", name="Phase 2 · Kiểm duyệt", exact=True).click()
    settled(page)
    page.get_by_role("button", name="Duyệt nội dung", exact=True).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    settled(page)
    page.get_by_role("button", name="Dùng Khung trắng", exact=True).click()
    settled(page)
    expect(page.get_by_role("combobox", name="Giọng đọc", exact=True)).to_have_value(
        "Sonia · English (UK) · Microsoft Edge"
    )
    expect(page.get_by_role("radio", name="Không dùng", exact=True)).to_be_checked()
    # The declared offline fixture supports Aria. This is not an audition of UK TTS.
    voice = page.get_by_role("combobox", name="Giọng đọc", exact=True)
    voice.fill("Aria")
    voice.press("ArrowDown")
    voice.press("Enter")
    page.get_by_role("button", name="Dựng video", exact=True).click()
    expect(page.get_by_role("button", name="Mở video để xem và duyệt", exact=True)).to_be_visible(
        timeout=90000
    )
    rendered = studio.job(job_id)
    assert rendered["video"]["width"] == 720 and rendered["video"]["height"] == 1280
    assert rendered["render_config"]["visual"]["preset"] == "lesson-card"
    assert rendered["render_config"]["music"]["track"] is None
    page.get_by_role("button", name="Mở video để xem và duyệt", exact=True).click()
    settled(page)
    expect(page.locator("video")).to_be_visible()
    page.wait_for_function("document.querySelector('video').readyState >= 2")
    with page.expect_download() as download:
        page.get_by_role("button", name="Tải video MP4", exact=True).click()
    path = tmp_path / "library-short.mp4"
    download.value.save_as(path)
    with path.open("rb") as source:
        assert hashlib.file_digest(source, "sha256").hexdigest() == rendered["video"]["sha256"]
    assert studio.provider_requests == []
    assert httpx.get(studio.api_url + f"/api/jobs/{job_id}/youtube").json() == []
