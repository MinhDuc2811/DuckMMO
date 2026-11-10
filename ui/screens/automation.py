"""Finite unattended lesson production and YouTube scheduling dashboard."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from ui.client.api import request
from ui.components.youtube_connection import connection_controls


def suggested_focus(item):
    data = item["data"]
    if item["kind"] == "vocabulary":
        return f"{data['lemma']}. {data['definition']} Example: {data['examples'][0]}"
    if item["kind"] == "patterns":
        return f"{data['form']}. {data['explanation']} Example: {data['examples'][0]}"
    if item["kind"] == "samples":
        return data["response"]
    return f"{data['question']} Answer: {data['answer']}. {data['explanation']}"


@st.fragment(run_every="10s")
def plans_dashboard():
    plans = request("GET", "/api/automation/plans") or []
    errors = [r for p in plans for r in p["runs"] if r["error"]]
    if errors:
        st.error(f"Có {len(errors)} lượt cần xử lý. Xem lỗi trong lịch bên dưới.")
    if not plans:
        st.info("Chưa có lịch tự động.")
    for plan in plans:
        with st.expander(
            f"{'Đang bật' if plan['enabled'] else 'Đã dừng'} · {plan['name']}", expanded=True
        ):
            st.caption(f"Kênh: {plan['channel_id'] or 'chưa xác minh'}")
            st.dataframe(
                [
                    {
                        **r,
                        "publish_at": datetime.fromisoformat(r["publish_at"])
                        .astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
                        .strftime("%d/%m/%Y %H:%M"),
                    }
                    for r in plan["runs"]
                ],
                hide_index=True,
            )
            st.caption("Giờ đăng hiển thị theo Việt Nam (UTC+7).")
            if plan["enabled"]:
                if st.button("Dừng lịch", key="pause-" + plan["id"]):
                    if request(
                        "PUT", "/api/automation/plans/" + plan["id"], json={"enabled": False}
                    ):
                        st.rerun()
            else:
                authorize = st.checkbox(
                    "Cho phép tự tạo, duyệt theo chính sách và đăng các video trong lịch này",
                    key="consent-" + plan["id"],
                )
                if st.button(
                    "Bật lịch tự động", key="enable-" + plan["id"], disabled=not authorize
                ):
                    if request(
                        "PUT",
                        "/api/automation/plans/" + plan["id"],
                        timeout=90,
                        json={"enabled": True, "authorize_auto_publish": True},
                    ):
                        st.rerun()
            st.caption(
                "Video đã upload và hẹn giờ trên YouTube phải hủy/đổi lịch trong YouTube Studio. "
                "Dừng lịch ở đây chỉ ngăn các bước tiếp theo trong tool."
            )


def render(opened=None, active=True, jobs_snapshot=None):
    if not active:
        return
    st.subheader("Tự tạo và đăng Shorts theo lịch")
    connection_controls("automation-youtube")
    st.caption(
        "Chạy API và worker liên tục. Mỗi bài học được dựng thành một video riêng, "
        "giọng Anh–Anh, khung trắng, nền ảnh thật đã chọn, không nhạc mặc định."
    )
    with st.expander("Tạo hàng đợi bài học tự động", expanded=True):
        kind = st.selectbox("Loại bài học", ["vocabulary", "patterns", "samples", "exercises"])
        result = (
            request("GET", f"/api/ielts/{kind}", params={"status": "reviewed", "limit": 60}) or {}
        )
        items = result.get("items", [])
        by_id = {item["id"]: item for item in items}
        with st.form("automation-select"):
            selected_ids = st.multiselect(
                "Bài học đã duyệt",
                list(by_id),
                format_func=lambda item_id: by_id[item_id]["title"],
                key="automation-items-" + kind,
            )
            prepare = st.form_submit_button("Chuẩn bị nội dung hàng đợi")
        if prepare:
            st.session_state["automation-queue"] = selected_ids
        selected = [
            by_id[item_id]
            for item_id in st.session_state.get("automation-queue", [])
            if item_id in by_id
        ]
        with st.form("automation-create"):
            name = st.text_input("Tên lịch", value="English Shorts")
            tomorrow = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")) + timedelta(days=1)
            date = st.date_input("Ngày đăng đầu (giờ Việt Nam)", tomorrow.date())
            time = st.time_input(
                "Giờ đăng đầu", tomorrow.replace(hour=19, minute=0, second=0, microsecond=0).time()
            )
            interval = st.number_input(
                "Khoảng cách giữa hai video (giờ)", min_value=6, max_value=168, value=24
            )
            background = st.selectbox("Ảnh nền", ["misty-lake", "study-morning", "quiet-work"])
            kids = st.checkbox("Nội dung dành cho trẻ em", value=False)
            warnings = st.checkbox(
                "Cho phép đăng khi chỉ có cảnh báo kỹ thuật (cần tự đánh giá trước khi bật)",
                value=False,
            )
            episodes = []
            for item in selected:
                focus = st.text_area(
                    "Nội dung đọc · " + item["title"],
                    suggested_focus(item),
                    key="focus-" + item["id"],
                    max_chars=650,
                )
                st.caption(f"{len(focus.split())}/85 từ · chỉ một ý cho mỗi Short")
                episodes.append(
                    {
                        "item_id": item["id"],
                        "expected_version": item["version"],
                        "focus_text": focus,
                    }
                )
            submitted = st.form_submit_button("Lưu lịch ở trạng thái dừng", disabled=not selected)
        if submitted:
            first = datetime.combine(date, time, ZoneInfo("Asia/Ho_Chi_Minh"))
            if request(
                "POST",
                "/api/automation/plans",
                json={
                    "name": name,
                    "first_publish_at": first.isoformat(),
                    "interval_hours": interval,
                    "episodes": episodes,
                    "background_id": background,
                    "made_for_kids": kids,
                    "allow_quality_warnings": warnings,
                },
            ):
                st.rerun()
    plans_dashboard()
