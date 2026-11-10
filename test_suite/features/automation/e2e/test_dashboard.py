"""Real OAuth state/API/UI/DB, with declared Google HTTP fixture; no real Google sign-in."""

from urllib.parse import parse_qs, urlsplit

import httpx
from playwright.sync_api import expect


def settled(page):
    expect(page.get_by_test_id("stApp")).to_have_attribute("data-test-script-state", "notRunning")


def test_connect_channel_and_enable_disable_finite_schedule(page, studio):
    topic = httpx.post(studio.api_url + "/api/ielts/topics", json={"name": "Environment"}).json()
    item = httpx.post(
        studio.api_url + "/api/ielts/vocabulary",
        json={
            "title": "Green space fixture",
            "topic_ids": [topic["id"]],
            "source": {"label": "Original fixture", "rights_note": "Original test, no publishing"},
            "data": {
                "lemma": "green space",
                "part_of_speech": "noun",
                "sense": "park land",
                "ipa_uk": "/ɡriːn speɪs/",
                "definition": "An area with grass and trees.",
                "examples": ["The city needs more green space."],
            },
        },
    ).json()
    httpx.post(
        studio.api_url + f"/api/ielts/items/{item['id']}/review",
        json={
            "expected_version": item["version"],
            "reviewer": "Fixture",
            "note": "Original fixture",
        },
    ).raise_for_status()
    page.goto(studio.ui_url)
    page.get_by_role("tab", name="Tự động hóa", exact=True).click()
    settled(page)
    page.get_by_role("textbox", name="Google OAuth client ID", exact=True).fill("fixture-client")
    page.get_by_role("textbox", name="Google OAuth client secret", exact=True).fill(
        "fixture-secret"
    )
    page.get_by_role("button", name="Lưu OAuth client", exact=True).click()
    settled(page)
    page.get_by_role("button", name="Kết nối bằng Google", exact=True).click()
    link = page.get_by_role("link", name="Đăng nhập Google và chọn kênh", exact=True)
    expect(link).to_be_visible()
    state = parse_qs(urlsplit(link.get_attribute("href")).query)["state"][0]
    # Google's redirect is simulated; actual state validation/token exchange uses fixture HTTP.
    response = httpx.get(
        studio.api_url + "/api/youtube/oauth/callback",
        params={"code": "fixture-code", "state": state},
    )
    assert response.status_code == 200, response.text
    page.get_by_role("button", name="Kiểm tra kết nối kênh", exact=True).click()
    expect(page.get_by_text("Kết nối kênh đã được xác minh.", exact=True)).to_be_visible()
    expect(page.get_by_text("Kênh: Fixture channel · fixture-channel", exact=True)).to_be_visible()
    settled(page)
    selected = page.get_by_role("combobox", name="Bài học đã duyệt", exact=True)
    selected.click()
    selected.fill("Green space fixture")
    expect(selected).to_have_value("Green space fixture")
    page.get_by_role("option", name="Green space fixture", exact=True).click()
    selected.press("Tab")
    page.get_by_role("button", name="Chuẩn bị nội dung hàng đợi", exact=True).click()
    expect(
        page.get_by_role("textbox", name="Nội dung đọc · Green space fixture", exact=True)
    ).to_be_visible()
    settled(page)
    page.get_by_role("button", name="Lưu lịch ở trạng thái dừng", exact=True).click()
    plan = page.get_by_text("Đã dừng · English Shorts", exact=True)
    expect(plan).to_be_visible()
    consent_label = "Cho phép tự tạo, duyệt theo chính sách và đăng các video trong lịch này"
    page.get_by_text(consent_label, exact=True).click()
    expect(page.get_by_role("checkbox", name=consent_label, exact=True)).to_be_checked()
    page.get_by_role("button", name="Bật lịch tự động", exact=True).click()
    expect(page.get_by_text("Đang bật · English Shorts", exact=True)).to_be_visible()
    plans = httpx.get(studio.api_url + "/api/automation/plans").json()
    assert plans[0]["enabled"] and len(plans[0]["runs"]) == 1
    assert plans[0]["runs"][0]["state"] == "pending"
    page.get_by_role("button", name="Dừng lịch", exact=True).click()
    expect(page.get_by_text("Đã dừng · English Shorts", exact=True)).to_be_visible()
    assert not httpx.get(studio.api_url + "/api/automation/plans").json()[0]["enabled"]
