"""Streamlit composition root. Screens own phase-specific widgets."""

import sys
from pathlib import Path

# Streamlit executes this file with ui/ on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from ui.client.api import request
from ui.components.activity import render_activity_log
from ui.components.workspace import render_workspace
from ui.screens import content_review, ingestion, production, publishing, video_review
from ui.state.workspace import apply_pending_navigation

st.set_page_config(page_title="AI Content Studio", page_icon="🦆", layout="wide")
apply_pending_navigation()
st.title("🦆 AI Content Studio")
st.caption("Soạn, chỉnh sửa và tải nội dung video")
if notice := st.session_state.pop("submission_notice", None):
    st.success(notice)
with st.sidebar:
    with st.container(key="workspace-panel"):
        render_workspace()
opened = None
if selection := st.session_state.get("workspace_selection"):
    opened = request("GET", f"/api/jobs/{selection}")
    if opened:
        st.subheader(opened["package"]["title"])
main_column, activity_column = st.columns([3, 1.25], gap="large")
with activity_column:
    with st.container(border=True, key="activity-panel"):
        render_activity_log()
jobs_snapshot = request("GET", "/api/jobs")
with main_column:
    tabs = st.tabs(
        [
            "Phase 1 · Nguồn & phân tích",
            "Phase 2 · Kiểm duyệt",
            "Phase 3 · Sản xuất video",
            "Phase 4 · Duyệt video",
            "Phase 5 · YouTube",
        ],
        key="workflow_phase",
        on_change="rerun",
    )
    for tab, screen in zip(tabs, (ingestion, content_review, production, video_review, publishing)):
        with tab:
            screen.render(opened=opened, active=tab.open, jobs_snapshot=jobs_snapshot)
