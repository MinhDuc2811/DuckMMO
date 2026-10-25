import hashlib
import re

import streamlit as st

from ui.client.api import request


def render(opened=None, active=True, jobs_snapshot=None):
    st.subheader("Nội dung video")
    jobs = list(jobs_snapshot) if jobs_snapshot is not None else request("GET", "/api/jobs")
    if jobs is not None:
        jobs = [
            job
            for job in jobs
            if job["status"]
            in (
                "awaiting_review",
                "approved",
                "rejected",
                "awaiting_video_review",
                "video_approved",
                "video_rejected",
            )
        ]
    if opened:
        jobs = (
            [opened]
            if opened["status"]
            in (
                "awaiting_review",
                "approved",
                "rejected",
                "awaiting_video_review",
                "video_approved",
                "video_rejected",
            )
            else []
        )
    if jobs:
        by_id = {j["id"]: j for j in jobs}
        if st.session_state.get("selected_content") not in by_id:
            st.session_state["selected_content"] = jobs[0]["id"]
        selected = st.selectbox(
            "Chọn nội dung",
            list(by_id),
            key="selected_content",
            format_func=lambda job_id: (
                f"{by_id[job_id]['package']['title']} · "
                f"{by_id[job_id]['package']['branch'].upper()}"
            ),
        )
        job = by_id[selected]
        package = job["package"]
        saved_content = package.get("video_content") or "\n\n".join(
            scene["narration"] for scene in package["scenes"]
        )
        st.caption("Nội dung đã qua Phase 1. Đọc, chỉnh sửa và duyệt bên dưới.")
        if job["result"] and job["result"].get("analysis"):
            analysis = job["result"]["analysis"]
            st.caption(
                f"{job['result']['word_count']} từ · "
                f"{analysis['source_count']} nguồn · "
                + ("Đã phân tích AI" if analysis.get("ai_generated") else "Nội dung nhập thủ công")
            )
        if package.get("research"):
            research = package["research"]
            st.caption(f"Keyword: {research['keyword']} · Ngày yêu cầu: {research['target_date']}")
            with st.expander("Nguồn và giới hạn của nghiên cứu"):
                for index, document in enumerate(package.get("source_documents", []), 1):
                    st.write(f"[{index}] {document['title']}")
                    st.write(document["source_url"])
                    st.caption(
                        "Ngày đăng theo website: "
                        + (document.get("published_at") or "Chưa xác định")
                        + " · Lấy dữ liệu: "
                        + (document.get("retrieved_at") or "Chưa ghi nhận")
                    )
                discovery = package.get("discovery") or {}
                for warning in discovery.get("date_warnings", []):
                    reason = (
                        "khác ngày yêu cầu"
                        if warning["reason"] == "different_date"
                        else "chưa xác định ngày đăng"
                    )
                    st.warning(f"Nguồn {reason}: {warning['url']}")
                for warning in discovery.get("warnings", []):
                    st.warning(warning)
                for warning in discovery.get("crawl_warnings", []):
                    st.warning(f"Không đọc được nguồn {warning['url']}: {warning['error']}")
                st.caption("Dẫn nguồn giúp truy vết; cần tự kiểm tra ngày đăng và độ chính xác.")
        # Bind each editor to its loaded revision to prevent stale overwrites.
        editor_key = f"editor-{selected}"
        revision_key = f"revision-{selected}"
        if editor_key not in st.session_state:
            st.session_state[revision_key] = hashlib.sha256(saved_content.encode()).hexdigest()
        content = st.text_area(
            "Nội dung video của bạn",
            value=saved_content,
            height=420,
            max_chars=200000,
            key=editor_key,
        )
        save, download = st.columns(2)
        if save.button("Lưu nội dung", type="primary", use_container_width=True):
            if not content.strip():
                st.error("Nội dung không được để trống.")
            else:
                result = request(
                    "PUT",
                    f"/api/jobs/{selected}/content",
                    json={
                        "content": content,
                        "expected_content_hash": st.session_state[revision_key],
                    },
                )
                if result:
                    st.session_state[revision_key] = hashlib.sha256(
                        content.strip().encode()
                    ).hexdigest()
                    st.success("Đã lưu nội dung.")
        filename = re.sub(r"[^\w\- ]", "", package["title"]).strip()[:80] or "content"
        download.download_button(
            "Tải file content (.txt)",
            data=content,
            file_name=f"{filename}.txt",
            mime="text/plain; charset=utf-8",
            use_container_width=True,
        )
        st.caption("File tải về chứa đúng nội dung đang hiển thị trong ô soạn thảo.")
        if job["status"] in (
            "approved",
            "awaiting_video_review",
            "video_approved",
            "video_rejected",
        ):
            st.success("Nội dung đã được duyệt.")
            if st.button("Tiếp tục dựng video", type="primary"):
                if content.strip() != saved_content.strip():
                    st.error("Lưu và duyệt lại phần chỉnh sửa trước khi dựng video.")
                else:
                    st.session_state["pending_workspace"] = (
                        selected,
                        job["status"],
                        "production",
                    )
                    st.rerun()
        elif job["status"] == "awaiting_review":
            with st.expander("Phản hồi nội dung"):
                content_labels = st.multiselect(
                    "Lý do cần sửa",
                    ["incorrect_fact", "missing_content", "wording", "other"],
                    format_func=lambda x: {
                        "incorrect_fact": "Sai thông tin",
                        "missing_content": "Thiếu ý",
                        "wording": "Cách diễn đạt",
                        "other": "Khác",
                    }[x],
                )
                content_note = st.text_area("Nhận xét nội dung", max_chars=4000)
                if st.button("Yêu cầu sửa nội dung"):
                    if not content_note.strip():
                        st.error("Nhập nội dung cần sửa.")
                    elif request(
                        "POST",
                        f"/api/jobs/{selected}/review",
                        json={
                            "decision": "reject",
                            "reviewer": "Người dùng workspace",
                            "note": content_note,
                            "labels": content_labels,
                            "expected_content_hash": st.session_state[revision_key],
                        },
                    ):
                        st.rerun()
            if st.button("Duyệt nội dung", use_container_width=True):
                if content.strip() != saved_content.strip():
                    st.error("Hãy lưu phần chỉnh sửa trước khi duyệt.")
                else:
                    if request(
                        "POST",
                        f"/api/jobs/{selected}/review",
                        json={
                            "decision": "approve",
                            "reviewer": "Người dùng workspace",
                            "note": content_note.strip() or "Đã kiểm duyệt nội dung trong Phase 2.",
                            "labels": content_labels,
                            "expected_content_hash": st.session_state[revision_key],
                        },
                    ):
                        st.rerun()
    elif jobs == []:
        st.info("Chưa có nội dung sẵn sàng. Hoàn tất Phase 1 trước khi kiểm duyệt.")
