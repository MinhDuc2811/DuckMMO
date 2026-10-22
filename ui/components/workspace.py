import streamlit as st

from ui.client.api import request
from ui.state.workspace import select_workspace


@st.fragment(run_every="2s")
def render_workspace():
    st.header("Workspace")
    if st.button("＋ Nội dung mới", use_container_width=True):
        st.session_state.pop("workspace_selection", None)
        st.session_state["workflow_phase"] = "Phase 1 · Nguồn & phân tích"
        st.rerun()
    if deleted_id := st.session_state.get("last_deleted"):
        st.caption("Đã xóa khỏi Workspace.")
        if st.button("Hoàn tác xóa", use_container_width=True):
            if request("POST", f"/api/jobs/{deleted_id}/restore"):
                st.session_state.pop("last_deleted", None)
                st.rerun()
    items = request("GET", "/api/workspace/jobs")
    if items is None:
        return
    active_statuses = ("queued", "running", "cancelling")
    active = [j for j in items if j["status"] in active_statuses]
    recent = [j for j in items if j["status"] not in active_statuses]
    labels = {
        "queued": "Chờ xử lý",
        "running": "Đang xử lý",
        "cancelling": "Đang dừng…",
        "cancelled": "Đã dừng",
        "failed": "Gặp lỗi",
        "awaiting_review": "Chờ kiểm duyệt",
        "approved": "Đã duyệt",
        "rejected": "Đã từ chối",
        "awaiting_video_review": "Video chờ duyệt",
        "video_approved": "Video đã duyệt",
        "video_rejected": "Video cần chỉnh sửa",
    }
    st.caption(f"{len(active)} tác vụ đang hoạt động · Tự cập nhật")
    if not active:
        st.info("Không có tác vụ đang chạy.")
    for item in active:
        with st.container(border=True, key=f"workspace-job-{item['id']}"):
            if st.button(
                item["title"],
                key=f"open-{item['id']}",
                on_click=select_workspace,
                args=(item["id"], item["status"], item.get("phase", "content")),
                use_container_width=True,
            ):
                st.rerun()
            st.caption(f"{item['branch'].upper()} · {labels[item['status']]}")
            stage = item["stage"]
            if "Voice and visuals" in stage:
                st.caption("Tạo giọng đọc và hình ảnh: " + stage.rsplit(" ", 1)[-1])
            elif "Encoding MP4" in stage:
                st.caption("Đang dựng video MP4")
            elif "Checking video" in stage:
                st.caption("Kiểm tra video và âm thanh")
            elif item.get("phase") == "production":
                st.caption("Chuẩn bị video")
            elif "Analysis started" in stage:
                st.caption("Đang phân tích nội dung")
            elif "Crawl completed" in stage:
                st.caption("Đã lấy dữ liệu nguồn")
            elif item["status"] == "running":
                st.caption("Đang lấy dữ liệu và xử lý nguồn")
            if st.button(
                "Dừng tác vụ",
                key=f"stop-{item['id']}",
                disabled=item["status"] == "cancelling",
                use_container_width=True,
            ):
                if request("POST", f"/api/jobs/{item['id']}/cancel"):
                    st.rerun()
            st.button(
                "Xóa",
                key=f"delete-{item['id']}",
                disabled=True,
                help="Dừng tác vụ trước khi xóa.",
                use_container_width=True,
            )
    with st.expander(f"Gần đây ({len(recent)})", expanded=True):
        for item in recent:
            with st.container(border=True, key=f"workspace-job-{item['id']}"):
                if st.button(
                    item["title"],
                    key=f"open-{item['id']}",
                    on_click=select_workspace,
                    args=(item["id"], item["status"], item.get("phase", "content")),
                    use_container_width=True,
                ):
                    st.rerun()
                st.caption(labels.get(item["status"], item["status"]))
                if item["error"]:
                    st.caption(item["error"])
                if st.button("Xóa", key=f"delete-{item['id']}", use_container_width=True):
                    if request("DELETE", f"/api/jobs/{item['id']}"):
                        st.session_state["last_deleted"] = item["id"]
                        st.session_state["pending_delete"] = item["id"]
                        st.rerun()
    if st.button("Làm mới Workspace", use_container_width=True):
        st.rerun()
