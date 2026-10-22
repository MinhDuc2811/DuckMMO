from pathlib import Path

import httpx
import imageio_ffmpeg
import psutil
import pytest
from PIL import Image
from playwright.sync_api import expect


def workspace_card(page, job_id):
    return page.locator(f".st-key-workspace-job-{job_id}")


def test_create_edit_save_download_and_approve(page, studio, tmp_path):
    studio.start_worker()
    page.goto(studio.ui_url)
    page.get_by_text("Hoặc nhập nội dung thủ công", exact=True).click()
    page.get_by_role("textbox", name="Tiêu đề", exact=True).fill("E2E kịch bản video")
    page.get_by_role("textbox", name="Tên nguồn", exact=True).fill("Bản thảo tự viết")
    page.get_by_role("textbox", name="Ghi chú quyền sử dụng / giấy phép").fill("Tự sáng tác")
    page.get_by_role("textbox", name="Lời dẫn (mỗi đoạn").fill("Lời dẫn ban đầu cho video.")
    page.get_by_role("button", name="Đưa vào hàng đợi", exact=True).click()
    workspace = page.locator(".st-key-workspace-panel")
    expect(workspace.get_by_text("E2E kịch bản video", exact=True)).to_be_visible()
    expect(workspace.get_by_text("Chờ kiểm duyệt", exact=True)).to_be_visible(timeout=20000)
    page.get_by_role("tab", name="Phase 2 · Kiểm duyệt", exact=True).click()
    editor = page.get_by_role("textbox", name="Nội dung video của bạn", exact=True)
    expect(editor).to_have_value("Lời dẫn ban đầu cho video.")
    edited = "Nội dung video đã sửa bằng trình duyệt thật.\n\nKết thúc mới."
    editor.fill(edited)
    page.get_by_role("button", name="Lưu nội dung", exact=True).click()
    expect(page.get_by_text("Đã lưu nội dung.", exact=True)).to_be_visible()
    with page.expect_download() as pending:
        page.get_by_role("button", name="Tải file content (.txt)", exact=True).click()
    download = pending.value
    target = tmp_path / download.suggested_filename
    download.save_as(target)
    assert target.read_text(encoding="utf-8") == edited
    page.reload()
    page.get_by_role("tab", name="Phase 2 · Kiểm duyệt", exact=True).click()
    expect(editor).to_have_value(edited)
    page.get_by_role("button", name="Duyệt nội dung", exact=True).click()
    expect(page.get_by_text("Nội dung đã được duyệt.", exact=True)).to_be_visible()


def test_cancel_existing_queued_job(page, studio):
    job = studio.create_job("E2E tác vụ có sẵn trong hàng đợi")
    page.goto(studio.ui_url)
    card = workspace_card(page, job["id"])
    expect(card.get_by_text("E2E tác vụ có sẵn trong hàng đợi", exact=True)).to_be_visible()
    card.get_by_role("button", name="Dừng tác vụ", exact=True).click()
    expect(card.get_by_text("Đã dừng", exact=True)).to_be_visible()
    expect(card.get_by_role("button", name="Dừng tác vụ")).to_have_count(0)
    assert studio.job(job["id"])["status"] == "cancelled"
    page.reload()
    expect(card.get_by_text("Đã dừng", exact=True)).to_be_visible()


def test_cancel_running_job_kills_real_worker_child(page, studio):
    studio.block_provider = True
    job = studio.create_job("E2E dừng tiến trình đang phân tích", with_source=True)
    studio.start_worker()
    assert studio.provider_started.wait(timeout=20), "Worker did not call provider fixture"
    children = [
        p
        for p in psutil.Process(studio.worker.pid).children(recursive=True)
        if "--job-id" in p.cmdline()
    ]
    assert children, "No isolated job process found in supervisor process tree"
    page.goto(studio.ui_url)
    card = workspace_card(page, job["id"])
    expect(card.get_by_text("Đang phân tích nội dung", exact=True)).to_be_visible()
    card.get_by_role("button", name="Dừng tác vụ", exact=True).click()
    expect(card.get_by_text("Đã dừng", exact=True)).to_be_visible(timeout=15000)
    assert studio.job(job["id"])["status"] == "cancelled"
    _, survivors = psutil.wait_procs(children, timeout=5)
    assert not survivors, f"Job descendants still alive: {survivors}"
    assert studio.worker.poll() is None  # The supervisor stays alive for other jobs.


def test_crawl_failure_does_not_appear_in_phase2(page, studio):
    studio.start_worker()
    page.goto(studio.ui_url)
    page.get_by_role("textbox", name="Link nguồn (mỗi dòng một URL)").fill(
        "https://no-such-source.invalid/article"
    )
    page.get_by_role("button", name="Bắt đầu Phase 1", exact=True).click()
    workspace = page.locator(".st-key-workspace-panel")
    expect(workspace.get_by_text("Gặp lỗi", exact=True)).to_be_visible(timeout=20000)
    expect(workspace.get_by_text("Crawl [dns]:", exact=False)).to_be_visible()
    page.get_by_role("tab", name="Phase 2 · Kiểm duyệt", exact=True).click()
    expect(page.get_by_role("textbox", name="Nội dung video của bạn")).to_have_count(0)
    assert studio.provider_requests == []


def test_left_sidebar_switch_workspace_delete_and_restore(page, studio):
    first = studio.create_job("Workspace A", content="Nội dung video A")
    second = studio.create_job("Workspace B", content="Nội dung video B")
    studio.start_worker()
    studio.wait_status(first["id"], "awaiting_review")
    studio.wait_status(second["id"], "awaiting_review")
    page.goto(studio.ui_url)
    sidebar = page.get_by_test_id("stSidebar")
    expect(sidebar.get_by_role("heading", name="Workspace", exact=True)).to_be_visible()
    assert sidebar.bounding_box()["x"] == 0
    editor = page.get_by_role("textbox", name="Nội dung video của bạn", exact=True)
    workspace_card(page, first["id"]).get_by_role("button", name="Workspace A", exact=True).click()
    expect(editor).to_have_value("Nội dung video A")

    workspace_card(page, second["id"]).get_by_role("button", name="Workspace B", exact=True).click()
    expect(editor).to_have_value("Nội dung video B")
    workspace_card(page, second["id"]).get_by_role("button", name="Xóa", exact=True).click()
    expect(workspace_card(page, second["id"])).to_have_count(0)
    assert httpx.get(studio.api_url + f"/api/jobs/{second['id']}").status_code == 404
    assert studio.job(first["id"])["status"] == "awaiting_review"
    sidebar.get_by_role("button", name="Hoàn tác xóa", exact=True).click()
    expect(workspace_card(page, second["id"])).to_be_visible()
    # Streamlit briefly keeps stale sidebar nodes while reconciling a full rerun.
    first_button = workspace_card(page, first["id"]).get_by_role(
        "button", name="Workspace A", exact=True
    )
    expect(first_button).to_have_count(1)
    first_button.click()
    expect(editor).to_have_value("Nội dung video A")


@pytest.mark.browser_context_args(viewport={"width": 1440, "height": 1100})
def test_steps5_to7_actual_voice_video_play_download_and_review(page, studio, tmp_path):
    job = studio.create_job(
        "E2E · Duyệt video cuối",
        content=(
            "Bình minh lên trên dãy núi. Một người lữ khách bắt đầu hành trình mới, "
            "mang theo niềm tin và hy vọng. "
            "Anh dừng chân bên dòng suối, lắng nghe tiếng chim "
            "và chuẩn bị cho chặng đường tiếp theo."
        ),
    )
    studio.start_worker()
    studio.wait_status(job["id"], "awaiting_review")
    picture = tmp_path / "background.png"
    Image.new("RGB", (720, 1280), "#526b85").save(picture)
    page.goto(studio.ui_url)
    card = workspace_card(page, job["id"])
    card.get_by_role("button", name="E2E · Duyệt video cuối", exact=True).click()
    page.get_by_role("button", name="Duyệt nội dung", exact=True).click()
    original = studio.job(job["id"])["package"]["scenes"][0]["narration"]
    editor = page.get_by_role("textbox", name="Nội dung video của bạn", exact=True)
    editor.fill(original + " Chỉnh sửa chưa lưu.")
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    expect(
        page.get_by_text("Lưu và duyệt lại phần chỉnh sửa trước khi dựng video.", exact=True)
    ).to_be_visible()
    editor.fill(original)
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    expect(page.get_by_role("tab", name="Phase 3 · Sản xuất video")).to_have_attribute(
        "aria-selected", "true"
    )
    page.locator('input[type="file"]').set_input_files(picture)
    page.get_by_role("button", name="Dựng video", exact=True).click()
    expect(card.get_by_text("Video chờ duyệt", exact=True)).to_be_visible(timeout=60000)
    assert studio.job(job["id"])["video"]["caption_count"] >= 2
    assert studio.job(job["id"])["video"]["visuals"] == "uploaded_images"
    assert studio.job(job["id"])["video"]["style"]["engine"] == "ffmpeg-libass"
    activity = page.locator(".st-key-activity-panel")
    expect(activity.get_by_text("Hoàn tất · Video sẵn sàng", exact=True)).to_be_visible(
        timeout=15000
    )
    assert activity.bounding_box()["x"] > page.get_by_test_id("stSidebar").bounding_box()["width"]
    activity.get_by_role("tab", name="Log", exact=True).click()
    expect(activity.locator("code")).to_contain_text("Video đã sẵn sàng để duyệt")
    with page.expect_download() as log_download:
        activity.get_by_role("button", name="Tải log", exact=True).click()
    assert "Video đã sẵn sàng để duyệt" in Path(log_download.value.path()).read_text(
        encoding="utf-8-sig"
    )
    expect(page.get_by_text("Đã dựng xong video.", exact=True)).to_be_visible(timeout=15000)
    page.get_by_role("button", name="Mở video để xem và duyệt", exact=True).click()
    expect(page.get_by_role("tab", name="Phase 4 · Duyệt video")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.get_by_text("Style tự động: Kể chuyện · Điện ảnh", exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Tải phụ đề có style ASS", exact=True)).to_be_visible()
    video = page.locator("video")
    expect(video).to_be_visible()
    page.wait_for_function("""() => {
        const v = document.querySelector('video');
        return v && v.readyState >= 2 && v.videoWidth === 720 && v.duration > 1;
    }""")
    video.evaluate("v => v.play()")
    page.wait_for_function("document.querySelector('video').currentTime > 0.2")
    video.evaluate("v => v.pause()")
    artifact_dir = Path("artifacts/e2e")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    video.screenshot(path=artifact_dir / "video-preview.png")
    with page.expect_download() as pending:
        page.get_by_role("button", name="Tải video MP4", exact=True).click()
    downloaded = artifact_dir / "rendered-video.mp4"
    pending.value.save_as(downloaded)
    assert b"ftyp" in downloaded.read_bytes()[:40]
    reader = imageio_ffmpeg.read_frames(str(downloaded))
    try:
        metadata = next(reader)
        assert metadata["size"] == (720, 1280)
        assert metadata["duration"] > 1
    finally:
        reader.close()
    page.get_by_role("textbox", name="Nhận xét video", exact=True).fill(
        "Đã phát video, kiểm tra giọng đọc và phụ đề."
    )
    page.get_by_role("button", name="Duyệt video", exact=True).click()
    expect(
        page.get_by_text("Video đã được duyệt. Sẵn sàng cho bước đăng bài.", exact=True)
    ).to_be_visible()
    assert studio.job(job["id"])["status"] == "video_approved"


@pytest.mark.live
def test_live_multisource_crawl_then_analysis_then_review(page, studio):
    studio.start_worker()
    page.goto(studio.ui_url)
    page.get_by_role("textbox", name="Link nguồn (mỗi dòng một URL)").fill(
        "https://metruyenchu.com.vn/hoa-son-tai-khoi/chuong-80-LQ_6GUMpZ0Bv\n"
        "https://docs.python.org/3/tutorial/introduction.html"
    )
    page.get_by_role("button", name="Bắt đầu Phase 1", exact=True).click()
    workspace = page.locator(".st-key-workspace-panel")
    expect(workspace.get_by_text("Chờ kiểm duyệt", exact=True)).to_be_visible(timeout=90000)
    jobs = httpx.get(studio.api_url + "/api/jobs").json()
    assert len(jobs) == 1
    job = jobs[0]
    assert len(job["package"]["source_documents"]) == 2
    assert all(len(d["content"]) > 10000 for d in job["package"]["source_documents"])
    assert studio.provider_requests  # Actual worker HTTP call, not a browser route mock.
    page.get_by_role("tab", name="Phase 2 · Kiểm duyệt", exact=True).click()
    expect(page.get_by_role("textbox", name="Nội dung video của bạn")).to_have_value(
        "Kịch bản từ AI fixture để test luồng ứng dụng."
    )
    page.get_by_role("button", name="Duyệt nội dung", exact=True).click()
    expect(page.get_by_text("Nội dung đã được duyệt.", exact=True)).to_be_visible()


def test_quality_feedback_and_learning_gate(page, studio):
    job = studio.create_job(
        "E2E harness chất lượng",
        content="Một buổi sáng, người lữ khách lên đường tìm hiểu thế giới.",
    )
    studio.start_worker()
    studio.wait_status(job["id"], "awaiting_review")
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "E2E", "note": "Test script"},
    ).raise_for_status()
    page.goto(studio.ui_url)
    workspace_card(page, job["id"]).get_by_role(
        "button", name="E2E harness chất lượng", exact=True
    ).click()
    page.get_by_role("button", name="Tiếp tục dựng video", exact=True).click()
    page.get_by_role("button", name="Dựng video", exact=True).click()
    expect(page.get_by_role("button", name="Mở video để xem và duyệt", exact=True)).to_be_visible(
        timeout=60000
    )
    page.get_by_role("button", name="Mở video để xem và duyệt", exact=True).click()
    activity = page.locator(".st-key-activity-panel")
    activity.get_by_role("tab", name="Chất lượng", exact=True).click()
    expect(activity.get_by_text("✅ audio_signal", exact=True).first).to_be_visible()
    expect(activity.get_by_text("○ word_alignment", exact=True)).to_be_visible()
    page.get_by_role("textbox", name="Nhận xét video", exact=True).fill(
        "Kiểm thử vòng phản hồi: phụ đề cần chỉnh bố cục."
    )
    labels = page.get_by_role("combobox", name="Vấn đề cần cải thiện", exact=True)
    labels.fill("Phụ đề tràn")
    labels.press("Enter")
    labels.press("Escape")
    page.get_by_role("button", name="Yêu cầu chỉnh sửa", exact=True).click()
    expect(
        page.get_by_text("Video cần chỉnh sửa. Sửa kịch bản hoặc dựng lại ở Phase 3.", exact=True)
    ).to_be_visible()
    activity.get_by_role("tab", name="Cải thiện", exact=True).click()
    expect(activity.get_by_text("blocked", exact=False).first).to_be_visible()
    expect(activity.get_by_role("button", name="Áp dụng cho video mới", exact=True)).to_have_count(
        0
    )
    quality = httpx.get(studio.api_url + f"/api/jobs/{job['id']}/quality").json()
    assert quality["feedback"][-1]["labels"] == ["subtitle_overflow"]
    assert quality["feedback"][-1]["scope"] == "video"
    page.get_by_role("tab", name="Phase 5 · YouTube", exact=True).click()
    expect(
        page.get_by_text("Duyệt video cuối ở Phase 4 trước khi đăng.", exact=True)
    ).to_be_visible()
    assert httpx.get(studio.api_url + f"/api/jobs/{job['id']}/youtube").json() == []
