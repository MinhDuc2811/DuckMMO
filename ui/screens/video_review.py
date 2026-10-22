import httpx
import streamlit as st

from ui.client.api import API_URL, HEADERS, request


def render(opened=None, active=True, jobs_snapshot=None):
    st.subheader("Bước 7 · Xem và duyệt video cuối")
    ready = (
        list(jobs_snapshot) if jobs_snapshot is not None else request("GET", "/api/jobs")
    ) or []
    if opened and opened["id"] not in [item["id"] for item in ready]:
        ready.append(opened)
    ready = [
        item
        for item in ready
        if item["status"] in ("awaiting_video_review", "video_approved", "video_rejected")
        and item.get("video")
    ]
    if opened:
        ready = [item for item in ready if item["id"] == opened["id"]]
    if ready:
        videos = {item["id"]: item for item in ready}
        if st.session_state.get("selected_video_job") not in videos:
            st.session_state["selected_video_job"] = ready[0]["id"]
        video_id = st.selectbox(
            "Chọn video",
            list(videos),
            key="selected_video_job",
            format_func=lambda value: videos[value]["package"]["title"],
        )
        video_job = videos[video_id]
        meta = video_job["video"]
        if style := meta.get("style"):
            st.caption(f"Style tự động: {style['name']} · Thư viện v{style['catalog_version']}")
            st.caption("Phụ đề căn theo thời lượng đoạn đọc; chưa căn chính xác từng từ.")
        st.caption(
            f"{meta['width']}×{meta['height']} · {meta['duration']:.1f} giây · "
            f"{meta['caption_count']} đoạn phụ đề · Đã kiểm tra hình và tiếng"
        )
        if active:
            try:
                media = httpx.get(
                    f"{API_URL}/api/jobs/{video_id}/artifacts/video",
                    headers=HEADERS,
                    timeout=60,
                )
                media.raise_for_status()
                st.video(media.content, format="video/mp4", width=420)
                st.download_button(
                    "Tải video MP4",
                    media.content,
                    file_name=f"video-{video_id[:8]}.mp4",
                    mime="video/mp4",
                )
                srt = httpx.get(
                    f"{API_URL}/api/jobs/{video_id}/artifacts/subtitles",
                    headers=HEADERS,
                    timeout=15,
                )
                if srt.status_code == 200:
                    st.download_button(
                        "Tải phụ đề SRT",
                        srt.content,
                        file_name=f"subtitles-{video_id[:8]}.srt",
                        mime="application/x-subrip",
                    )
                if meta.get("style"):
                    styled_subtitles = httpx.get(
                        f"{API_URL}/api/jobs/{video_id}/artifacts/styled_subtitles",
                        headers=HEADERS,
                        timeout=15,
                    )
                    if styled_subtitles.status_code == 200:
                        st.download_button(
                            "Tải phụ đề có style ASS",
                            styled_subtitles.content,
                            file_name=f"subtitles-{video_id[:8]}.ass",
                            mime="text/plain",
                        )
            except httpx.HTTPError:
                st.error("Chưa mở được file video. Hãy thử tải lại.")
        if video_job["status"] == "video_approved":
            st.success("Video đã được duyệt. Sẵn sàng cho bước đăng bài.")
        elif video_job["status"] == "video_rejected":
            st.warning("Video cần chỉnh sửa. Sửa kịch bản hoặc dựng lại ở Phase 3.")
        else:
            with st.form(f"video-review-{video_id}"):
                feedback = st.text_area(
                    "Nhận xét video",
                    max_chars=4000,
                    placeholder="Kiểm tra giọng đọc, hình ảnh, phụ đề và nhịp dựng…",
                )
                feedback_labels = st.multiselect(
                    "Vấn đề cần cải thiện",
                    [
                        "subtitle_overflow",
                        "subtitle_pacing",
                        "subtitle_sync",
                        "pronunciation",
                        "visual_relevance",
                        "editing_pace",
                        "incorrect_fact",
                        "missing_content",
                        "other",
                    ],
                    format_func=lambda x: {
                        "subtitle_overflow": "Phụ đề tràn/nhiều dòng",
                        "subtitle_pacing": "Phụ đề quá nhanh",
                        "subtitle_sync": "Phụ đề lệch tiếng",
                        "pronunciation": "Phát âm",
                        "visual_relevance": "Ảnh không phù hợp",
                        "editing_pace": "Nhịp dựng",
                        "incorrect_fact": "Sai thông tin",
                        "missing_content": "Thiếu nội dung",
                        "other": "Khác",
                    }[x],
                )
                feedback_time = st.number_input(
                    "Vị trí lỗi (giây)",
                    min_value=0.0,
                    max_value=float(meta["duration"]),
                    value=0.0,
                )
                approve_video = st.form_submit_button("Duyệt video", type="primary")
                reject_video = st.form_submit_button("Yêu cầu chỉnh sửa")
            if approve_video or reject_video:
                if reject_video and not feedback.strip():
                    st.error("Nhập nội dung cần chỉnh sửa để lưu kết quả.")
                else:
                    if request(
                        "POST",
                        f"/api/jobs/{video_id}/video-review",
                        json={
                            "decision": "approve" if approve_video else "reject",
                            "reviewer": "Người dùng workspace",
                            "note": feedback.strip() or "Đã xem và duyệt video.",
                            "expected_video_hash": meta["sha256"],
                            "labels": feedback_labels,
                            "timecode": feedback_time if feedback_labels else None,
                        },
                    ):
                        st.rerun()
        if st.button("Sửa kịch bản của video này"):
            st.session_state["pending_workspace"] = (
                video_id,
                "awaiting_review",
                "content_review",
            )
            st.rerun()
        if st.button("Dựng lại video"):
            st.session_state["pending_workspace"] = (video_id, "approved", "production")
            st.rerun()
    else:
        st.info("Chưa có video để duyệt. Hoàn tất bước dựng ở Phase 3 trước.")
