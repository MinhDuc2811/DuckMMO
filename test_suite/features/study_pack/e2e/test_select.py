import httpx
from playwright.sync_api import expect

from e2e.conftest import stop_tree


def test_bundled_background_and_new_music_selected_in_browser(page, studio):
    job = studio.create_job("Study pack browser fixture")
    studio.start_worker()
    studio.wait_status(job["id"], "awaiting_review")
    stop_tree(studio.worker)
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "E2E", "note": "Original fixture"},
    ).raise_for_status()
    page.goto(studio.ui_url)
    page.get_by_role("button", name="Study pack browser fixture", exact=True).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    page.get_by_role("button", name="Dùng Khung trắng", exact=True).click()
    background = page.get_by_role("combobox", name="Ảnh nền có sẵn", exact=True)
    background.fill("Ảnh thật · gia vị")
    background.press("ArrowDown")
    background.press("Enter")
    expect(background).to_have_value("Ảnh thật · gia vị")
    with page.expect_download() as credit_download:
        page.get_by_role("button", name="Tải credit ảnh (.txt)", exact=True).click()
    credit = credit_download.value.path().read_text(encoding="utf-8")
    assert "Riyaad Minty" in credit and "CC BY 2.0" in credit
    # Requirement changed: rejected generated music must never be selected automatically.
    expect(page.get_by_role("radio", name="Không dùng", exact=True)).to_be_checked()
    page.get_by_text("Bản thử nghiệm cũ", exact=True).click()
    expect(page.get_by_role("radio", name="Bản thử nghiệm cũ", exact=True)).to_be_checked()
    expect(page.get_by_test_id("stApp")).to_have_attribute("data-test-script-state", "notRunning")
    music = page.get_by_role("combobox", name="Bản nhạc", exact=True)
    expect(music).to_have_value("Nền êm")
    page.get_by_test_id("stSelectbox").filter(has=music).get_by_role(
        "button", name="Open", exact=True
    ).click()
    page.get_by_role("option", name="Open Road · country-pop", exact=True).click()
    expect(music).to_have_value("Open Road · country-pop")
    page.get_by_role("button", name="Dựng video", exact=True).click()
    queued = studio.wait_status(job["id"], "queued")
    assert queued["render_config"]["background_id"] == "study-morning"
    assert queued["render_config"]["music"]["track"] == "soft-focus"
    assert queued["render_config"]["music"]["volume"] == 0.10
    assert queued["render_config"]["image_files"] == ["library-background.png"]
