"""Real stock discovery with downloadable source metadata; no unreviewed auto-import."""

import json

import streamlit as st


def stock_controls(request, job_id):
    with st.expander("Tìm ảnh, video và audio theo bài học"):
        st.caption(
            "Tìm → mở nguồn để xem và tải → upload ở phần hình ảnh hoặc nhạc. "
            "Kiểm giấy phép và lưu credit cùng file."
        )
        with st.form(f"stock-{job_id}"):
            provider = st.selectbox("Nguồn stock", ["openverse", "pexels"])
            kind = st.selectbox("Loại stock", ["image", "video", "audio"])
            query = st.text_input(
                "Từ khóa stock",
                placeholder="quiet library, green city, healthy food",
                max_chars=160,
            )
            page = st.number_input("Trang kết quả stock", min_value=1, max_value=20, value=1)
            search = st.form_submit_button("Tìm stock")
        key = f"stock-results-{job_id}"
        if search:
            st.session_state.pop(key, None)
            result = request(
                "GET",
                "/api/production/stock/search",
                params={"provider": provider, "kind": kind, "q": query, "page": page},
                timeout=30,
            )
            if result:
                st.session_state[key] = result
        if result := st.session_state.get(key):
            if not result["results"]:
                st.info("Không có kết quả. Thử từ khóa khác.")
            for item in result["results"]:
                st.markdown(f"**{item['title']}**")
                st.caption(f"{item['author']} · {item['license']}")
                st.link_button("Xem và tải tại nguồn", item["source_url"])
                if item.get("license_url"):
                    st.link_button("Điều khoản sử dụng", item["license_url"])
            st.download_button(
                "Tải metadata nguồn (.json)",
                json.dumps(result, ensure_ascii=False, indent=2),
                file_name="stock-sources.json",
                mime="application/json",
                key=f"stock-metadata-{job_id}",
            )
