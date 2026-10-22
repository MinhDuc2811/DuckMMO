import re
from datetime import datetime, timedelta, timezone

import streamlit as st

from ui.client.api import request
from ui.state.workspace import select_workspace


def stage_label(message):
    labels = {
        "Video production started": "Bắt đầu dựng video",
        "Combining narration": "Ghép giọng đọc",
        "Encoding MP4": "Xuất file MP4",
        "Checking video and audio": "Kiểm tra hình và tiếng",
        "Video ready for final review": "Video đã sẵn sàng để duyệt",
        "Phase 1 started": "Bắt đầu lấy dữ liệu nguồn",
        "Analysis started": "Phân tích nội dung",
        "Phase 1 complete; ready for Phase 2 review": "Nội dung sẵn sàng để duyệt",
    }
    if count := re.fullmatch(r"Voice and visuals (\d+)/(\d+)", message):
        return f"Tạo giọng đọc và hình ảnh: {count[1]}/{count[2]} đoạn"
    if message.startswith("Auto style:"):
        return message.replace("Auto style:", "Đã tự chọn style:", 1)
    return labels.get(message, message)


@st.fragment(run_every="2s")
def render_activity_log():
    st.subheader("Theo dõi tác vụ")
    job_id = st.session_state.get("workspace_selection")
    if not job_id:
        st.info("Chọn một nội dung trong Workspace để xem tiến trình và log.")
        return
    job = request("GET", f"/api/jobs/{job_id}")
    events = request("GET", f"/api/jobs/{job_id}/events")
    if not job or events is None:
        return
    st.caption(job["package"]["title"])
    progress_tab, log_tab, quality_tab, learning_tab = st.tabs(
        ["Tiến trình", "Log", "Chất lượng", "Cải thiện"]
    )
    with progress_tab:
        latest = events[-1]["message"] if events else "Chờ xử lý"
        st.write(stage_label(latest))
        if job.get("error"):
            st.error(job["error"])
        elif job["status"] in ("cancelled", "cancelling"):
            st.warning("Đã dừng tác vụ" if job["status"] == "cancelled" else "Đang dừng…")
        if job.get("render_config"):
            starts = [
                i
                for i, event in enumerate(events)
                if event["message"] == "Video production started"
            ]
            run = events[starts[-1] :] if starts else []
            messages = [event["message"] for event in run]
            done = bool(job.get("video"))
            stages = [
                ("Tạo giọng đọc và hình ảnh", "Voice and visuals"),
                ("Ghép giọng đọc", "Combining narration"),
                ("Xuất MP4", "Encoding MP4"),
                ("Kiểm tra hình và tiếng", "Checking video and audio"),
            ]
            current = max(
                (i for i, (_, token) in enumerate(stages) if any(token in m for m in messages)),
                default=-1,
            )
            for i, (label, _) in enumerate(stages):
                icon = "✅" if done or i < current else "⏳" if i == current else "○"
                st.write(f"{icon} {i + 1}. {label}")
            counts = [re.fullmatch(r"Voice and visuals (\d+)/(\d+)", m) for m in messages]
            counts = [c for c in counts if c]
            if counts:
                count = counts[-1]
                st.progress(
                    int(count[1]) / int(count[2]),
                    text=f"Giọng đọc và hình ảnh: {count[1]}/{count[2]} đoạn",
                )
            if done:
                st.success("Hoàn tất · Video sẵn sàng")
                if st.button("Xem video", key="activity-open-video", use_container_width=True):
                    select_workspace(job_id, job["status"], "video_review")
                    st.rerun()
        st.caption("Tự cập nhật mỗi 2 giây. Các bước xuất và kiểm tra hiển thị trạng thái thực tế.")
    with log_tab:
        st.caption(f"{len(events)} sự kiện · Mới nhất ở trên · Giờ Việt Nam")
        lines = []
        for event in reversed(events):
            timestamp = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            local = timestamp.astimezone(timezone(timedelta(hours=7)))
            lines.append(f"{local:%H:%M:%S} [{event['status']}] {stage_label(event['message'])}")
        with st.container(height=540):
            st.code("\n".join(lines) or "Chưa có sự kiện", language=None, wrap_lines=True)
        st.download_button(
            "Tải log",
            "\n".join(lines),
            file_name=f"log-{job_id[:8]}.txt",
            mime="text/plain",
            key=f"log-download-{job_id}",
        )

    with quality_tab:
        quality = request("GET", f"/api/jobs/{job_id}/quality")
        if quality:
            current = [e for e in quality["evaluations"] if e["current"]]
            st.caption(f"{len(quality['runs'])} lượt xử lý · {len(current)} kiểm tra hiện tại")
            if not current:
                st.info("Chưa có đánh giá cho phiên bản này. Job cũ không được gán điểm hồi tố.")
            for item in current:
                icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "unknown": "○"}[item["outcome"]]
                with st.expander(f"{icon} {item['dimension']}"):
                    st.json(item["evidence"])
            with st.expander("Lịch sử từng bước"):
                st.dataframe(
                    [
                        {"Bước": r["step"], "Trạng thái": r["state"], "Hiện tại": r["current"]}
                        for r in quality["runs"]
                    ],
                    hide_index=True,
                )
            st.caption("Độ đúng sự thật, phát âm và khớp từng từ vẫn cần người duyệt.")
    with learning_tab:
        experiments = request("GET", "/api/learning/experiments") or []
        if not experiments:
            st.info("Chưa có thử nghiệm. Gắn nhãn lỗi phụ đề khi duyệt video để tạo candidate.")
        for experiment in experiments[:5]:
            report = experiment["report"]
            with st.expander(f"{experiment['state']} · {experiment['id'][:8]}"):
                st.write(
                    f"Điểm bố cục: {report['baseline']['score']:.1f} → "
                    f"{report['candidate']['score']:.1f}"
                )
                st.caption(
                    f"{report['supporting_jobs']}/{report['required_jobs']} job phản hồi độc lập"
                )
                st.write(report["reason"])
                st.caption(
                    "Benchmark bố cục offline; chưa chứng minh tăng chất lượng "
                    "nội dung hay lượt xem."
                )
                if st.button("Chạy benchmark lại", key=f"benchmark-{experiment['id']}"):
                    if request("POST", f"/api/learning/experiments/{experiment['id']}/benchmark"):
                        st.rerun()
                if experiment["state"] == "eligible" and st.button(
                    "Áp dụng cho video mới", key=f"promote-{experiment['id']}"
                ):
                    if request("POST", f"/api/learning/experiments/{experiment['id']}/promote"):
                        st.rerun()
                if experiment["state"] in ("canary", "promoted") and st.button(
                    "Quay về style mặc định", key=f"rollback-{experiment['id']}"
                ):
                    if request(
                        "POST", f"/api/learning/configs/{experiment['candidate_id']}/rollback"
                    ):
                        st.rerun()
