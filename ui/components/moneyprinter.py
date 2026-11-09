"""Prepare real footage using MPT; author still chooses the background explicitly."""

import hashlib
import json

import streamlit as st


def footage_controls(request, job):
    job_id = job["id"]
    with st.expander("MoneyPrinterTurbo · Tự chuẩn bị clip nền"):
        st.caption(
            "MPT tìm, tải và ghép clip thật. Không tạo lời đọc/nhạc hoặc tự đăng video. "
            "Xem nguồn và clip trước khi dùng."
        )
        if st.button("Kiểm tra MPT runtime", key=f"mpt-doctor-{job_id}"):
            result = request("GET", "/api/production/moneyprinter", timeout=60)
            if result:
                st.json(result)
        with st.form(f"mpt-prepare-{job_id}"):
            provider = st.selectbox("Nguồn footage MPT", ["pexels", "pixabay", "coverr"])
            terms = st.text_input(
                "Từ khóa footage (tối đa 3, cách nhau dấu phẩy)",
                value=job["package"]["title"][:80],
                max_chars=240,
            )
            st.caption(
                "Gợi ý ban đầu lấy từ tiêu đề; sửa thành từ khóa hình ảnh cụ thể bằng tiếng Anh."
            )
            seconds = st.number_input(
                "Độ dài clip nền MPT (giây)", min_value=5, max_value=30, value=15, step=5
            )
            ratio = st.selectbox("Khung footage MPT", ["9:16", "16:9"])
            rights = st.text_input("Ghi chú kiểm tra quyền dùng footage", max_chars=1000)
            submit = st.form_submit_button("Chuẩn bị footage MPT")
        if submit:
            text = job["package"].get("video_content") or "\n\n".join(
                s["narration"] for s in job["package"]["scenes"]
            )
            with st.spinner("MoneyPrinterTurbo đang tìm/tải/ghép footage…"):
                result = request(
                    "POST",
                    f"/api/jobs/{job_id}/moneyprinter/footage",
                    timeout=620,
                    json={
                        "provider": provider,
                        "terms": [t.strip() for t in terms.split(",") if t.strip()],
                        "seconds": seconds,
                        "ratio": ratio,
                        "rights_note": rights,
                        "expected_content_hash": hashlib.sha256(text.encode()).hexdigest(),
                    },
                )
            if result:
                st.session_state[f"mpt-prepared-{job_id}"] = result
        if asset := st.session_state.get(f"mpt-prepared-{job_id}"):
            provenance = asset.get("provenance", {})
            preview = request(
                "GET", f"/api/jobs/{job_id}/assets/{asset['id']}/file", raw=True, timeout=60
            )
            if preview:
                st.video(preview)
            st.json(provenance)
            st.download_button(
                "Tải nguồn footage (.json)",
                json.dumps(provenance, ensure_ascii=False, indent=2),
                file_name="footage-sources.json",
                key=f"mpt-credit-{job_id}",
            )
            if st.button("Dùng clip MPT làm nền", key=f"mpt-use-{job_id}"):
                st.session_state[f"media-mode-{job_id}"] = "Clip"
                st.session_state[f"mpt-selected-{job_id}"] = asset["id"]
                st.rerun()
