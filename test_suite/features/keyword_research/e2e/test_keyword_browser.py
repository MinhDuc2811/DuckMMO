"""Real browser/API/SQLite. No external search or AI is called before worker startup."""

import httpx
import pytest
from playwright.sync_api import expect


@pytest.mark.browser_context_args(viewport={"width": 1440, "height": 1100})
def test_persist_preferred_topic_and_submit_keyword_without_url(page, studio):
    page.goto(studio.ui_url)
    page.get_by_text("Nguồn nghiên cứu mặc định theo chủ đề", exact=True).click()
    page.get_by_role("textbox", name="Đường dẫn chủ đề", exact=True).fill("news/esport/fifa-online")
    page.get_by_role("textbox", name="Website mặc định", exact=True).fill(
        "https://official.example/news"
    )
    page.get_by_role("button", name="Lưu nguồn mặc định", exact=True).click()
    expect(page.get_by_text("Đã lưu chủ đề và website mặc định.", exact=True)).to_be_visible()
    page.get_by_text("news", exact=True).click()
    expect(page.get_by_text("Chủ đề đang chọn: research / news", exact=True)).to_be_visible()
    page.get_by_text("esport", exact=True).click()
    expect(
        page.get_by_text("Chủ đề đang chọn: research / news / esport", exact=True)
    ).to_be_visible()
    page.get_by_text("fifa-online", exact=True).click()
    expect(
        page.get_by_text("Nguồn ưu tiên: https://official.example/news", exact=True)
    ).to_be_visible()
    page.get_by_role("textbox", name="Keyword / nội dung muốn làm", exact=True).fill(
        "Bản cập nhật FC Online"
    )
    page.get_by_role("button", name="Tìm nguồn và tổng hợp", exact=True).click()
    expect(
        page.get_by_text("Đã xếp hàng tìm nguồn, crawl và tổng hợp AI.", exact=True)
    ).to_be_visible()
    response = httpx.get(studio.api_url + "/api/jobs")
    response.raise_for_status()
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["package"]["research"]["preferred_url"] == "https://official.example/news"
    assert jobs[0]["package"]["research"]["topic_path"] == ["news", "esport", "fifa-online"]
    assert jobs[0]["status"] == "queued"
    page.reload()
    expect(page.get_by_text("Bản cập nhật FC Online", exact=False).first).to_be_visible()
