"""Real MPT + UI/API/DB/render; only external stock HTTP and TTS are declared fixtures."""

import hashlib

import httpx
from playwright.sync_api import expect


def settled(page):
    expect(page.get_by_test_id("stApp")).to_have_attribute("data-test-script-state", "notRunning")


def test_moneyprinter_footage_to_white_card_short(page, studio):
    studio.env["IELTS_E2E_ISOLATED_DIRECTORY"] = str(studio.directory.resolve())
    studio.worker = studio.spawn("worker", ["-m", "test_suite.support.ielts_fixture_worker"])
    job = httpx.post(
        studio.api_url + "/api/jobs",
        json={
            "package": {
                "branch": "novel",
                "language": "en",
                "title": "English footage fixture",
                "sources": [{"label": "Original test", "rights_note": "Test only"}],
                "scenes": [
                    {
                        "narration": "Green spaces make a city more pleasant to live in.",
                        "source_indices": [0],
                    }
                ],
            }
        },
    ).json()
    studio.wait_status(job["id"], "awaiting_review")
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "Fixture", "note": "Original test only"},
    ).raise_for_status()
    page.goto(studio.ui_url)
    page.get_by_role("button", name="English footage fixture", exact=True).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    settled(page)
    page.get_by_role("button", name="Dùng Khung trắng", exact=True).click()
    settled(page)
    page.get_by_text("MoneyPrinterTurbo · Tự chuẩn bị clip nền", exact=True).click()
    page.get_by_role(
        "textbox", name="Từ khóa footage (tối đa 3, cách nhau dấu phẩy)", exact=True
    ).fill("green city")
    page.get_by_role("spinbutton", name="Độ dài clip nền MPT (giây)", exact=True).fill("5")
    page.get_by_role("textbox", name="Ghi chú kiểm tra quyền dùng footage", exact=True).fill(
        "Original offline HTTP fixture, not production stock"
    )
    page.get_by_role("button", name="Chuẩn bị footage MPT", exact=True).click()
    expect(page.get_by_role("button", name="Dùng clip MPT làm nền", exact=True)).to_be_visible(
        timeout=90000
    )
    with page.expect_download() as credit:
        page.get_by_role("button", name="Tải nguồn footage (.json)", exact=True).click()
    provenance = credit.value.path().read_text()
    assert "https://www.pexels.com/video/101/" in provenance
    assert "fixture-only" not in provenance
    page.get_by_role("button", name="Dùng clip MPT làm nền", exact=True).click()
    settled(page)
    expect(page.get_by_role("radio", name="Clip", exact=True)).to_be_checked()
    voice = page.get_by_role("combobox", name="Giọng đọc", exact=True)
    voice.fill("Aria")
    voice.press("ArrowDown")
    voice.press("Enter")
    page.get_by_role("button", name="Dựng video", exact=True).click()
    expect(page.get_by_role("button", name="Mở video để xem và duyệt", exact=True)).to_be_visible(
        timeout=90000
    )
    rendered = studio.job(job["id"])
    assert rendered["video"]["width"] == 720 and rendered["video"]["height"] == 1280
    assert rendered["render_config"]["visual"]["preset"] == "lesson-card"
    assert rendered["render_config"]["video_file"] == "input-clip"
    assert rendered["render_config"]["music"]["track"] is None
    assert rendered["package"]["scenes"][0]["narration"] == job["package"]["scenes"][0]["narration"]
    page.get_by_role("button", name="Mở video để xem và duyệt", exact=True).click()
    settled(page)
    with page.expect_download() as download:
        page.get_by_role("button", name="Tải video MP4", exact=True).click()
    with download.value.path().open("rb") as file:
        assert hashlib.file_digest(file, "sha256").hexdigest() == rendered["video"]["sha256"]
    assert httpx.get(studio.api_url + f"/api/jobs/{job['id']}/youtube").json() == []
    assert studio.provider_requests == []
