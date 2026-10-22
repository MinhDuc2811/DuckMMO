import re

import streamlit as st

from ui.client.api import request


@st.fragment(run_every="2s")
def render_production_progress(job_id):
    job = request("GET", f"/api/jobs/{job_id}")
    if not job:
        return
    if job["status"] not in ("queued", "running", "cancelling"):
        st.rerun()
    items = request("GET", "/api/workspace/jobs") or []
    stage = next((item["stage"] for item in items if item["id"] == job_id), "")
    count = re.search(r"Voice and visuals (\d+)/(\d+)", stage)
    if count:
        current, total = map(int, count.groups())
        st.progress(current / total, text=f"Tạo giọng đọc và hình ảnh: {current}/{total} đoạn")
    elif "Encoding MP4" in stage:
        st.info("Đang xuất file MP4. Kịch bản dài có thể cần vài phút.")
    elif "Checking video" in stage:
        st.info("Đang kiểm tra hình ảnh và âm thanh của video.")
    elif "Combining narration" in stage:
        st.info("Đang ghép giọng đọc.")
    else:
        st.info(
            "Đang dừng video…" if job["status"] == "cancelling" else "Đang chuẩn bị dựng video…"
        )
    st.caption("Tiến trình tự cập nhật. Bạn có thể dừng tác vụ trong Workspace bên trái.")
