import streamlit as st

from ui.client.api import request


def render(opened=None, active=True, jobs_snapshot=None):
    st.subheader("Đăng YouTube và theo dõi hiệu quả")
    connection = request("GET", "/api/youtube/status")
    if connection and not connection["connected"]:
        st.info("Chưa kết nối YouTube. Cần OAuth của kênh; không dùng key Gemini.")
        with st.expander("Kết nối một lần"):
            st.write(
                "Thiết lập Google OAuth với quyền youtube.upload và yt-analytics.readonly. "
                "Lưu client ID, client secret và refresh token trong cấu hình cục bộ."
            )
            st.code(
                "STUDIO_YOUTUBE_CLIENT_ID\nSTUDIO_YOUTUBE_CLIENT_SECRET\nSTUDIO_YOUTUBE_REFRESH_TOKEN"
            )
            st.caption("Không gửi token hoặc client secret vào chat.")
    if opened:
        publish_job = request("GET", f"/api/jobs/{opened['id']}")
        if publish_job and publish_job["status"] == "video_approved":
            with st.form(f"youtube-publish-{opened['id']}"):
                upload_title = st.text_input(
                    "Tiêu đề YouTube",
                    value=publish_job["package"]["title"][:100],
                    max_chars=100,
                )
                upload_description = st.text_area("Mô tả YouTube", max_chars=5000)
                upload_privacy = st.selectbox("Chế độ hiển thị", ["private", "unlisted", "public"])
                made_for_kids = st.checkbox("Nội dung dành cho trẻ em")
                start_upload = st.form_submit_button(
                    "Đăng / tiếp tục upload YouTube",
                    disabled=not connection or not connection["connected"],
                )
            if start_upload:
                result = request(
                    "POST",
                    f"/api/jobs/{opened['id']}/youtube",
                    timeout=90,
                    json={
                        "title": upload_title,
                        "description": upload_description,
                        "privacy": upload_privacy,
                        "made_for_kids": made_for_kids,
                        "expected_video_hash": publish_job["video"]["sha256"],
                    },
                )
                if result:
                    st.success(
                        "Đã gửi lượt upload. Trạng thái được lưu để tiếp tục; không đăng trùng."
                    )
        else:
            st.info("Duyệt video cuối ở Phase 4 trước khi đăng.")
        attempts = request("GET", f"/api/jobs/{opened['id']}/youtube") or []
        for attempt in attempts:
            st.write(f"YouTube: {attempt['state']} · Đã gửi {attempt['offset']:,} byte")
            if attempt["platform_id"]:
                st.link_button(
                    "Mở video YouTube",
                    f"https://www.youtube.com/watch?v={attempt['platform_id']}",
                )
                if st.button("Cập nhật Analytics", key=f"analytics-{attempt['id']}"):
                    request("POST", f"/api/youtube/{attempt['id']}/analytics", timeout=60)
                snapshots = request("GET", f"/api/youtube/{attempt['id']}/analytics") or []
                if snapshots:
                    metrics = snapshots[0]["metrics"]
                    if metrics["data_available"]:
                        st.json(metrics["values"])
                    else:
                        st.info("YouTube chưa trả dữ liệu. Không coi là 0 lượt xem.")
                    st.caption("Chỉ số quan sát; chưa chứng minh style mới làm tăng hiệu quả.")
    else:
        st.info("Chọn video trong Workspace trước.")
