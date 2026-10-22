import httpx
from playwright.sync_api import expect

from e2e.conftest import stop_tree


def test_free_vietnamese_voice_and_rate_are_queued(page, studio):
    """SPT-E2E-001: real browser/API/DB; no external TTS call in the offline flow."""
    job = studio.create_job("Chọn giọng Việt miễn phí")
    studio.start_worker()
    studio.wait_status(job["id"], "awaiting_review")
    stop_tree(studio.worker)
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={
            "decision": "approve",
            "reviewer": "E2E",
            "note": "Self-authored voice fixture",
        },
    ).raise_for_status()
    voices = httpx.get(studio.api_url + "/api/voices").json()["voices"]
    assert {voice["provider"] for voice in voices} == {"edge", "windows"}
    page.goto(studio.ui_url)
    page.get_by_role("button", name="Chọn giọng Việt miễn phí", exact=True).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    voice = page.get_by_role("combobox", name="Giọng đọc", exact=True)
    voice.click()
    page.get_by_role("option", name="Nam Minh · nam · Microsoft Edge", exact=True).click()
    expect(voice).to_have_value("Nam Minh · nam · Microsoft Edge")
    rate = page.get_by_role("group", name="Tốc độ đọc (%)", exact=True).get_by_role("slider")
    rate.focus()
    rate.press("ArrowRight")
    expect(rate).to_have_value("10")
    expect(page.get_by_role("button", name="Nghe thử giọng", exact=True)).to_be_visible()
    page.get_by_role("button", name="Dựng video", exact=True).click()
    current = studio.wait_status(job["id"], "queued")
    assert current["render_config"]["voice"] == "vi-VN-NamMinhNeural"
    assert current["render_config"]["speech_rate"] == 10
    assert httpx.get(studio.api_url + f"/api/jobs/{job['id']}/assets").json() == []
