"""Keyword discovery and persistent topic preferences; API owns storage."""

from datetime import date

import streamlit as st

from ui.client.api import request
from ui.state.workspace import select_workspace


def render():
    preferences = request("GET", "/api/settings/research") or {"profiles": []}
    profiles = preferences["profiles"]
    with st.expander("Nguồn nghiên cứu mặc định theo chủ đề"):
        st.caption("Ví dụ research / news / esport / fifa-online → trang tin cập nhật chính thức.")
        with st.form("research-preferences"):
            branch = st.selectbox("Nhánh áp dụng", ["research", "novel", "comic"])
            path = st.text_input("Đường dẫn chủ đề", placeholder="news/esport/fifa-online")
            url = st.text_input("Website mặc định", placeholder="https://website.com/tin-cap-nhat")
            save = st.form_submit_button("Lưu nguồn mặc định")
        if save:
            parts = [part.strip() for part in path.split("/") if part.strip()]
            if not parts:
                st.error("Nhập ít nhất một cấp chủ đề.")
            else:
                updated = [p for p in profiles if (p["branch"], p["topic_path"]) != (branch, parts)]
                updated.append(
                    {"branch": branch, "topic_path": parts, "preferred_url": url or None}
                )
                if request("PUT", "/api/settings/research", json={"profiles": updated}):
                    st.session_state["submission_notice"] = "Đã lưu chủ đề và website mặc định."
                    st.rerun()
        for profile in profiles:
            st.caption(
                f"{profile['branch']} / {' / '.join(profile['topic_path'])}: "
                f"{profile.get('preferred_url') or 'Tìm trên web'}"
            )
    st.markdown("**Tạo nội dung từ keyword**")
    branch = st.selectbox("Nhánh nghiên cứu", ["research", "novel", "comic"], key="keyword-branch")
    available = [p for p in profiles if p["branch"] == branch]
    selected_path = []
    # Keep the hierarchy visible; child choices become available after their parent is selected.
    max_depth = max((len(p["topic_path"]) for p in available), default=0)
    for depth in range(max_depth):
        choices = sorted(
            {
                p["topic_path"][depth]
                for p in available
                if len(p["topic_path"]) > depth
                and len(selected_path) == depth
                and p["topic_path"][:depth] == selected_path
            }
        )
        key = f"research-topic-{branch}-{depth}"
        if st.session_state.get(key) not in ["—", *choices]:
            st.session_state[key] = "—"
        selected = st.radio(
            f"Chủ đề cấp {depth + 1}",
            ["—", *choices],
            key=key,
            disabled=not choices,
            horizontal=True,
        )
        if selected != "—" and choices:
            selected_path.append(selected)
    st.caption("Chủ đề đang chọn: " + " / ".join([branch, *selected_path]))
    default_url = next(
        (p.get("preferred_url") for p in available if p["topic_path"] == selected_path), None
    )
    st.caption("Nguồn ưu tiên: " + (default_url or "Chưa đặt website mặc định"))
    with st.form("phase1-keyword"):
        keyword = st.text_area(
            "Keyword / nội dung muốn làm", placeholder="Tổng hợp bản cập nhật FC Online"
        )
        target_date = st.date_input("Ngày cần nghiên cứu", value=date.today())
        override = st.text_input("Website ưu tiên cho lần này (không bắt buộc)")
        search_web = st.checkbox("Tìm thêm nguồn trên web", value=True)
        max_sources = st.number_input("Số nguồn tối đa", min_value=1, max_value=10, value=5)
        submit = st.form_submit_button("Tìm nguồn và tổng hợp", type="primary")
    if submit:
        if not keyword.strip():
            st.error("Nhập keyword hoặc mô tả nội dung cần làm.")
        else:
            job = request(
                "POST",
                "/api/import/keyword",
                json={
                    "keyword": keyword,
                    "branch": branch,
                    "topic_path": selected_path,
                    "target_date": target_date.isoformat(),
                    "preferred_url": override or None,
                    "search_web": search_web,
                    "max_sources": int(max_sources),
                },
            )
            if job:
                st.session_state["submission_notice"] = (
                    "Đã xếp hàng tìm nguồn, crawl và tổng hợp AI."
                )
                select_workspace(job["id"], job["status"])
                st.rerun()
    st.caption(
        "Tìm kiếm mặc định dùng DuckDuckGo; Google cần cấu hình API riêng. "
        "Ngày yêu cầu không phải bằng chứng ngày đăng bài. Kết quả vẫn cần kiểm duyệt."
    )
