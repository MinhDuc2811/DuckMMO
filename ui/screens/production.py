import base64
import hashlib
import os

import streamlit as st

from ui.client.api import request
from ui.components.progress import render_production_progress
from ui.state.workspace import select_workspace


def render(opened=None, active=True, jobs_snapshot=None):
    st.subheader("Bước 5–6 · Chuẩn bị và dựng video")
    st.write("Hệ thống tự chọn style theo nội dung, căn phụ đề và dựng video từ ảnh của bạn.")
    st.info(
        "Style tự động: kể chuyện điện ảnh, truyện tranh nổi bật hoặc thông tin rõ ràng. "
        "Không cần chỉnh font và hiệu ứng từng video."
    )
    candidates = (
        list(jobs_snapshot) if jobs_snapshot is not None else request("GET", "/api/jobs")
    ) or []
    if opened and opened["id"] not in [item["id"] for item in candidates]:
        candidates.append(opened)
    candidates = [
        item
        for item in candidates
        if item["status"]
        in ("approved", "awaiting_video_review", "video_approved", "video_rejected")
        or item.get("render_config")
    ]
    if opened:
        candidates = [item for item in candidates if item["id"] == opened["id"]]
    if candidates:
        render_jobs = {item["id"]: item for item in candidates}
        if st.session_state.get("selected_render_job") not in render_jobs:
            st.session_state["selected_render_job"] = candidates[0]["id"]
        render_id = st.selectbox(
            "Chọn kịch bản đã duyệt",
            list(render_jobs),
            key="selected_render_job",
            format_func=lambda value: render_jobs[value]["package"]["title"],
        )
        render_job = render_jobs[render_id]
        if render_job["status"] in ("queued", "running", "cancelling"):
            render_production_progress(render_id)
        else:
            if render_job.get("video"):
                st.success("Đã dựng xong video.")
                if st.button("Mở video để xem và duyệt", type="primary"):
                    select_workspace(render_id, render_job["status"], "video_review")
                    st.rerun()
            if render_job.get("error"):
                st.error(render_job["error"])
            with st.form(f"render-{render_id}"):
                voices = {
                    "local-vi": "Tiếng Việt · giọng trên máy",
                    "local-en": "English · giọng trên máy",
                    "vi-VN-HoaiMyNeural": "Tiếng Việt · Hoài My (Edge online)",
                    "vi-VN-NamMinhNeural": "Tiếng Việt · Nam Minh (Edge online)",
                    "en-US-AriaNeural": "English · Aria (Edge online)",
                }
                if os.name != "nt":
                    voices = {
                        key: label for key, label in voices.items() if not key.startswith("local-")
                    }
                voice = st.selectbox("Giọng đọc", list(voices), format_func=voices.get)
                layout = st.selectbox(
                    "Khung hình",
                    ["portrait", "landscape"],
                    format_func=lambda value: (
                        "Dọc 9:16 · 720×1280" if value == "portrait" else "Ngang 16:9 · 1280×720"
                    ),
                )
                pictures = st.file_uploader(
                    "Ảnh cho video (không bắt buộc)",
                    type=["png", "jpg", "jpeg"],
                    accept_multiple_files=True,
                )
                st.caption(
                    "Tối đa 10 ảnh, mỗi ảnh 3 MB. Không thêm ảnh: dùng nền chữ có phụ đề. "
                    + ("Giọng trên máy không gửi kịch bản ra ngoài; " if os.name == "nt" else "")
                    + "Edge TTS gửi lời dẫn tới dịch vụ giọng đọc Microsoft và cần mạng."
                )
                build = st.form_submit_button("Dựng video", type="primary")
            if build:
                if len(pictures) > 10 or any(p.size > 3_000_000 for p in pictures):
                    st.error("Tối đa 10 ảnh và mỗi ảnh không quá 3 MB.")
                else:
                    script = render_job["package"].get("video_content") or "\n\n".join(
                        scene["narration"] for scene in render_job["package"]["scenes"]
                    )
                    result = request(
                        "POST",
                        f"/api/jobs/{render_id}/render",
                        json={
                            "voice": voice,
                            "layout": layout,
                            "images": [base64.b64encode(p.getvalue()).decode() for p in pictures],
                            "expected_content_hash": hashlib.sha256(script.encode()).hexdigest(),
                        },
                    )
                    if result:
                        st.session_state["pending_workspace"] = (
                            render_id,
                            "queued",
                            "production",
                        )
                        st.rerun()
    else:
        st.info("Duyệt kịch bản ở Phase 2 để bắt đầu dựng video.")
