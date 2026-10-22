import streamlit as st


def select_workspace(job_id, status, phase="content"):
    st.session_state["pending_workspace"] = (job_id, status, phase)


def apply_pending_navigation():
    if pending := st.session_state.pop("pending_workspace", None):
        st.session_state["workspace_selection"] = pending[0]
        st.session_state["selected_content"] = pending[0]
        st.session_state["selected_render_job"] = pending[0]
        st.session_state["selected_video_job"] = pending[0]
        phase = pending[2] if len(pending) > 2 else "content"
        st.session_state["workflow_phase"] = (
            "Phase 3 · Sản xuất video"
            if phase == "production"
            else "Phase 4 · Duyệt video"
            if phase == "video_review"
            else "Phase 2 · Kiểm duyệt"
            if phase == "content_review"
            or pending[1] in ("awaiting_review", "approved", "rejected")
            else "Phase 1 · Nguồn & phân tích"
        )

    if deleted := st.session_state.pop("pending_delete", None):
        if st.session_state.get("workspace_selection") == deleted:
            st.session_state.pop("workspace_selection", None)
            st.session_state.pop("selected_content", None)
            st.session_state["workflow_phase"] = "Phase 1 · Nguồn & phân tích"
