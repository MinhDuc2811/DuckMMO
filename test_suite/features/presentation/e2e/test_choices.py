import httpx
from playwright.sync_api import expect

from e2e.conftest import stop_tree


def test_style_and_music_selections_reach_real_queue(page, studio):
    """Real UI/API/DB; worker stopped before TTS, which this test does not verify."""
    job = studio.create_job("Phong cách và nhạc nền")
    studio.start_worker()
    studio.wait_status(job["id"], "awaiting_review")
    stop_tree(studio.worker)
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "E2E", "note": "Original test content"},
    ).raise_for_status()
    page.goto(studio.ui_url)
    page.get_by_role("button", name="Phong cách và nhạc nền", exact=True).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    style = page.get_by_role("combobox", name="Phong cách", exact=True)
    style.click()
    page.get_by_role("option", name="Comic", exact=True).click()
    page.get_by_text("Nhạc có sẵn", exact=True).click()
    expect(page.get_by_role("combobox", name="Bản nhạc", exact=True)).to_be_visible()
    page.get_by_role("button", name="Xem mẫu style", exact=True).click()
    expect(
        page.get_by_text("Mẫu minh họa chuyển động; chưa phải preview toàn video.", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Dựng video", exact=True).click()
    current = studio.wait_status(job["id"], "queued")
    assert current["render_config"]["visual"]["preset"] == "comic"
    assert current["render_config"]["music"]["track"] == "ambient"
    assert current["render_config"]["music"]["ducking"] is True
    assert current["render_config"]["music_file"] == "input-music"
