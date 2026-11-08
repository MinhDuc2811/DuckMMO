import httpx
from PIL import Image
from playwright.sync_api import expect

from e2e.conftest import stop_tree


def test_white_card_uk_voice_background_and_quiet_music_reach_queue(page, studio, tmp_path):
    response = httpx.post(
        studio.api_url + "/api/jobs",
        json={
            "package": {
                "branch": "novel",
                "language": "en",
                "title": "British English lesson",
                "sources": [{"label": "Original fixture", "rights_note": "Test only"}],
                "scenes": [
                    {
                        "narration": "Self-paced learning means learning at your own pace.",
                        "source_indices": [0],
                    }
                ],
            }
        },
    )
    response.raise_for_status()
    job = response.json()
    studio.start_worker()
    studio.wait_status(job["id"], "awaiting_review")
    stop_tree(studio.worker)
    reviewed = httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "E2E", "note": "Original fixture"},
    )
    reviewed.raise_for_status()
    page.goto(studio.ui_url)
    page.get_by_role("button", name="British English lesson", exact=True).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    page.get_by_role("button", name="Dùng Khung trắng", exact=True).click()
    style = page.get_by_role("combobox", name="Phong cách", exact=True)
    expect(style).to_have_value("Khung trắng")
    expect(page.get_by_role("combobox", name="Giọng đọc", exact=True)).to_have_value(
        "Sonia · English (UK) · Microsoft Edge"
    )
    expect(page.get_by_role("radio", name="Không dùng", exact=True)).to_be_checked()
    image = tmp_path / "topic-background.png"
    Image.new("RGB", (720, 1280), "#355747").save(image)
    page.locator('input[type="file"]').set_input_files(image)
    page.get_by_role("button", name="Dựng video", exact=True).click()
    queued = studio.wait_status(job["id"], "queued")
    assert queued["render_config"]["voice"] == "en-GB-SoniaNeural"
    assert queued["render_config"]["visual"]["preset"] == "lesson-card"
    assert queued["render_config"]["music"]["volume"] == 0.10
    assert queued["render_config"]["music"]["ducking"]
    assert queued["render_config"]["music"]["track"] is None
    assert len(queued["render_config"]["image_files"]) == 1
    assert studio.provider_requests == []
