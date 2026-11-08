"""Existing manual English flow, not the unimplemented IELTS library workflow."""

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import httpx
from playwright.sync_api import expect

from test_suite.support.paths import PROJECT_ROOT


def wait_for_streamlit(page):
    # A full rerun briefly keeps old and new widget trees mounted together.
    expect(page.get_by_test_id("stApp")).to_have_attribute("data-test-script-state", "notRunning")


def test_english_short_create_edit_render_download_approve_and_invalidate(
    page, studio, tmp_path, output_path
):
    """IELTS-E2E-001: real UI/API/DB/encoder; speech is a declared offline PCM fixture."""
    with sqlite3.connect(tmp_path / "knowledge-prototype.sqlite") as knowledge:
        folder = PROJECT_ROOT / "docs" / "ielts-shorts"
        knowledge.executescript((folder / "schema.sql").read_text())
        knowledge.executescript((folder / "seed.sql").read_text())
        phrase, meaning = knowledge.execute(
            "SELECT e.headword, s.meaning_vi FROM lexical_entries e "
            "JOIN lexical_senses s ON s.entry_id=e.id WHERE s.id='sense-self-paced'"
        ).fetchone()
        example = knowledge.execute(
            "SELECT text_en FROM vocabulary_examples WHERE id='example-self-paced'"
        ).fetchone()[0]
    assert phrase == "self-paced learning"
    assert meaning
    original = f"What is {phrase}? {example}"
    edited = f"{original} It means learning at your own pace."
    title = "IELTS fixture — one phrase"

    # Stack.spawn owns cleanup/logging. Only the speech adapter differs from production.
    studio.env["IELTS_E2E_ISOLATED_DIRECTORY"] = str(studio.directory.resolve())
    studio.env["STUDIO_STYLE_CATALOG_URL"] = ""
    studio.worker = studio.spawn("worker", ["-m", "test_suite.support.ielts_fixture_worker"])
    page.goto(studio.ui_url)
    page.get_by_text("Hoặc nhập nội dung thủ công", exact=True).click()
    language = page.get_by_role("combobox", name="Ngôn ngữ", exact=True)
    language.click()
    page.get_by_role("option", name="en", exact=True).click()
    page.get_by_role("textbox", name="Tiêu đề", exact=True).fill(title)
    page.get_by_role("textbox", name="Tên nguồn", exact=True).fill("Original offline test fixture")
    page.get_by_role("textbox", name="Ghi chú quyền sử dụng / giấy phép").fill(
        "Original illustrative test content; not official IELTS or publishable material."
    )
    page.get_by_role("textbox", name="Lời dẫn (mỗi đoạn").fill(original)
    page.get_by_role("button", name="Đưa vào hàng đợi", exact=True).click()
    workspace = page.locator(".st-key-workspace-panel")
    expect(workspace.get_by_text(title, exact=True)).to_be_visible()
    expect(workspace.get_by_text("Chờ kiểm duyệt", exact=True)).to_be_visible(timeout=20000)

    with httpx.Client(base_url=studio.api_url) as api:
        response = api.get("/api/jobs")
        response.raise_for_status()
        jobs = response.json()
        assert len(jobs) == 1
        job_id = jobs[0]["id"]
        assert jobs[0]["package"]["language"] == "en"
        # Legacy branch is acknowledged: no claim that IELTS branch already exists.
        assert jobs[0]["package"]["branch"] == "novel"

    page.get_by_role("tab", name="Phase 2 · Kiểm duyệt", exact=True).click()
    wait_for_streamlit(page)
    editor = page.get_by_role("textbox", name="Nội dung video của bạn", exact=True)
    expect(editor).to_have_count(1)
    expect(editor).to_have_value(original)
    editor.fill(edited)
    page.get_by_role("button", name="Lưu nội dung", exact=True).click()
    expect(page.get_by_text("Đã lưu nội dung.", exact=True)).to_be_visible()
    with page.expect_download() as content_download:
        page.get_by_role("button", name="Tải file content (.txt)", exact=True).click()
    assert content_download.value.path().read_text(encoding="utf-8") == edited

    page.reload()
    page.get_by_role("tab", name="Phase 2 · Kiểm duyệt", exact=True).click()
    wait_for_streamlit(page)
    expect(editor).to_have_count(1)
    expect(editor).to_have_value(edited)
    page.get_by_role("button", name="Duyệt nội dung", exact=True).click()
    expect(page.get_by_text("Nội dung đã được duyệt.", exact=True)).to_be_visible()
    assert studio.job(job_id)["status"] == "approved"
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    wait_for_streamlit(page)
    voice = page.get_by_role("combobox", name="Giọng đọc", exact=True)
    # React Aria can close its transient popup on a rerender; use supported keyboard selection.
    voice.fill("Aria")
    voice.press("ArrowDown")
    voice.press("Enter")
    expect(voice).to_have_value("Aria · English · Microsoft Edge")
    page.get_by_role("button", name="Dựng video", exact=True).click()
    expect(page.get_by_role("button", name="Mở video để xem và duyệt", exact=True)).to_be_visible(
        timeout=90000
    )
    rendered = studio.job(job_id)
    assert rendered["status"] == "awaiting_video_review", rendered["error"]
    assert rendered["render_config"]["voice"] == "en-US-AriaNeural"
    assert rendered["render_config"]["layout"] == "portrait"
    page.get_by_role("button", name="Mở video để xem và duyệt", exact=True).click()
    wait_for_streamlit(page)
    video = page.locator("video")
    expect(video).to_be_visible()
    page.wait_for_function("""() => {
        const v = document.querySelector('video');
        return v && v.readyState >= 2 && v.videoWidth === 720 && v.videoHeight === 1280;
    }""")
    video.evaluate("v => { v.muted = true; return v.play(); }")
    page.wait_for_function("document.querySelector('video').currentTime > 0.2")
    video.evaluate("v => v.pause()")
    with page.expect_download() as video_download:
        page.get_by_role("button", name="Tải video MP4", exact=True).click()
    evidence = Path(output_path)
    evidence.mkdir(parents=True, exist_ok=True)
    video.screenshot(path=evidence / "video-review.png")
    downloaded = evidence / "english-short.mp4"
    video_download.value.save_as(downloaded)
    with downloaded.open("rb") as downloaded_file:
        assert (
            hashlib.file_digest(downloaded_file, "sha256").hexdigest()
            == rendered["video"]["sha256"]
        )
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(downloaded)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    media = json.loads(probe.stdout)
    streams = {stream["codec_type"]: stream for stream in media["streams"]}
    assert streams["video"]["codec_name"] == "h264"
    assert (streams["video"]["width"], streams["video"]["height"]) == (720, 1280)
    assert streams["audio"]["codec_name"] == "aac"
    assert float(media["format"]["duration"]) > 2
    with page.expect_download() as subtitle_download:
        page.get_by_role("button", name="Tải phụ đề SRT", exact=True).click()
    subtitle_path = evidence / "english-short.srt"
    subtitle_download.value.save_as(subtitle_path)
    subtitles = subtitle_path.read_text(encoding="utf-8-sig")
    assert "self-paced learning" in subtitles
    assert "-->" in subtitles

    page.get_by_role("textbox", name="Nhận xét video", exact=True).fill(
        "Automated encoding fixture check only; synthetic tone is not English speech review."
    )
    page.get_by_role("button", name="Duyệt video", exact=True).click()
    expect(
        page.get_by_text("Video đã được duyệt. Sẵn sàng cho bước đăng bài.", exact=True)
    ).to_be_visible()
    assert studio.job(job_id)["status"] == "video_approved"
    # Editing the actual saved script must invalidate approval and the previous video.
    page.get_by_role("button", name="Sửa kịch bản của video này", exact=True).click()
    wait_for_streamlit(page)
    expect(editor).to_have_count(1)
    editor.fill(edited + " Review the phrase once more.")
    page.get_by_role("button", name="Lưu nội dung", exact=True).click()
    expect(page.get_by_text("Đã lưu nội dung.", exact=True)).to_be_visible()
    changed = studio.job(job_id)
    assert changed["status"] == "awaiting_review"
    assert changed["video"] is None
    assert changed["render_config"] is None
    assert studio.provider_requests == []
    published = httpx.get(studio.api_url + f"/api/jobs/{job_id}/youtube")
    published.raise_for_status()
    assert published.json() == []
