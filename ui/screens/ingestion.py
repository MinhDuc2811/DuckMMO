from types import SimpleNamespace
from uuid import uuid4

import streamlit as st

from ui.client.api import request
from ui.components.research import render as render_research
from ui.state.workspace import select_workspace


def render(opened=None, active=True, jobs_snapshot=None):
    st.subheader("Lấy dữ liệu từ nguồn")
    try:
        data = request("GET", "/api/settings/ai")
        connection = SimpleNamespace(**data) if data else None
    except (ValueError, OSError):
        connection = None
    with st.expander("Kết nối AI", expanded=connection is None):
        if connection:
            st.caption(f"Đã cấu hình model: {connection.model}")
        else:
            st.warning("Chưa kết nối AI. Cấu hình một lần để phân tích các nguồn web.")
        with st.form("ai-connection"):
            ai_url = st.text_input(
                "URL API AI",
                value=connection.base_url if connection else "",
                placeholder="https://your-provider.example/v1",
            )
            ai_model = st.text_input("Model AI", value=connection.model if connection else "")
            ai_key = st.text_input(
                "API key AI", type="password", help="Để trống để giữ key đã lưu."
            )
            st.caption("Key được lưu cục bộ trên máy chạy DuckMMO. Không cần gửi key vào chat.")
            save_ai = st.form_submit_button("Lưu kết nối AI")
        if save_ai:
            saved = request(
                "PUT",
                "/api/settings/ai",
                json={
                    "base_url": ai_url,
                    "model": ai_model,
                    "api_key": ai_key,
                    "structured_output": connection.structured_output if connection else False,
                    "timeout_seconds": connection.timeout_seconds if connection else 120,
                },
            )
            if saved:
                st.session_state["submission_notice"] = (
                    "Đã lưu kết nối AI. Bấm Thử lại ở tác vụ lỗi để tiếp tục phân tích."
                )
                st.rerun()
    render_research()
    st.markdown("**Hoặc chỉ định link nguồn**")
    with st.form("phase1-web"):
        website_urls = st.text_area(
            "Link nguồn (mỗi dòng một URL)", placeholder="https://website.com/bai-viet"
        )
        source_branch = st.selectbox("Loại nội dung", ["novel", "comic", "research"])
        fetch = st.form_submit_button("Bắt đầu Phase 1", type="primary")
    if fetch:
        urls = list(
            dict.fromkeys(line.strip() for line in website_urls.splitlines() if line.strip())
        )
        if not urls:
            st.error("Nhập ít nhất một link nguồn.")
        elif len(urls) > 10:
            st.error("Mỗi nội dung tối đa 10 link nguồn.")
        else:
            imported = request(
                "POST", "/api/import/web", json={"urls": urls, "branch": source_branch}
            )
            if imported:
                st.session_state["submission_notice"] = (
                    "Đã nhận nguồn. Đang chờ lấy dữ liệu và phân tích ở Phase 1."
                )
                select_workspace(imported["id"], imported["status"])
                st.rerun()
    st.caption(
        "Nguồn được lấy trước rồi phân tích AI. Chỉ nội dung phân tích thành công mới sang Phase 2."
    )
    with st.expander("Hoặc nhập nội dung thủ công"):
        st.subheader("Nội dung đầu vào")
        st.write("Nhập kịch bản đã chuẩn bị. Bước này kiểm tra cấu trúc, không tự sinh recap.")
        with st.form("package"):
            left, right = st.columns(2)
            branch = left.selectbox("Nhánh", ["novel", "comic", "research"])
            language = right.selectbox("Ngôn ngữ", ["vi", "en", "zh", "ja", "ko"])
            title = st.text_input("Tiêu đề", max_chars=200)
            source = st.text_input("Tên nguồn", max_chars=300)
            source_url = st.text_input("URL nguồn (không bắt buộc)")
            rights = st.text_area("Ghi chú quyền sử dụng / giấy phép", max_chars=2000)
            narration = st.text_area(
                "Lời dẫn (mỗi đoạn cách nhau một dòng trống là một cảnh)", height=220
            )
            visual = st.text_input("Gợi ý hình ảnh cho các cảnh", max_chars=2000)
            submit = st.form_submit_button("Đưa vào hàng đợi", type="primary")
        if submit:
            paragraphs = [p.strip() for p in narration.split("\n\n") if p.strip()]
            if not all([title.strip(), source.strip(), rights.strip(), paragraphs]):
                st.error("Điền tiêu đề, tên nguồn, quyền sử dụng và lời dẫn.")
            else:
                package = {
                    "schema_version": "1.0",
                    "branch": branch,
                    "title": title,
                    "language": language,
                    "sources": [
                        {"label": source, "url": source_url or None, "rights_note": rights}
                    ],
                    "scenes": [
                        {"narration": p, "visual_note": visual, "source_indices": [0]}
                        for p in paragraphs
                    ],
                }
                if "submission_key" not in st.session_state:
                    st.session_state.submission_key = str(uuid4())
                # Keep the key on transport failure so resubmission cannot duplicate the job.
                payload_signature = repr(package)
                if st.session_state.get("submission_payload") != payload_signature:
                    st.session_state.submission_key = str(uuid4())
                st.session_state.submission_payload = payload_signature
                result = request(
                    "POST",
                    "/api/jobs",
                    json={"package": package},
                    extra_headers={"Idempotency-Key": st.session_state.submission_key},
                )
                if result:
                    st.session_state["submission_notice"] = f"Đã tạo job: {result['id']}"
                    st.session_state.pop("submission_key", None)
                    select_workspace(result["id"], result["status"])
                    st.rerun()
    phase1_jobs = list(jobs_snapshot) if jobs_snapshot is not None else request("GET", "/api/jobs")
    if phase1_jobs:
        phase1_jobs = [item for item in phase1_jobs if not item.get("render_config")]
    if phase1_jobs and opened:
        phase1_jobs = [item for item in phase1_jobs if item["id"] == opened["id"]]
    if phase1_jobs:
        st.subheader("Tiến trình Phase 1")
        for item in phase1_jobs:
            if item["status"] in ("queued", "running", "cancelling", "cancelled", "failed"):
                with st.container(border=True):
                    st.write(item["package"]["title"])
                    st.caption(
                        {
                            "queued": "Chờ xử lý",
                            "running": "Đang xử lý",
                            "failed": "Xử lý thất bại",
                            "cancelling": "Đang dừng",
                            "cancelled": "Đã dừng",
                        }[item["status"]]
                    )
                    for source in item["package"]["sources"]:
                        if source.get("url"):
                            st.write(source["url"])
                    if item["error"]:
                        st.error(item["error"])
                    if item["status"] == "failed" and st.button(
                        "Thử lại", key=f"retry-{item['id']}"
                    ):
                        if request("POST", f"/api/jobs/{item['id']}/retry"):
                            st.rerun()
            else:
                st.caption(f"{item['package']['title']} — Đã sẵn sàng kiểm duyệt ở Phase 2")
