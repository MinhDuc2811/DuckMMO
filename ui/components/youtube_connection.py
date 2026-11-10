"""Interactive Google connection; credentials are sent only to the local API."""

import streamlit as st

from ui.client.api import request


def connection_controls(key="youtube"):
    status = request("GET", "/api/youtube/status") or {}
    channel = status.get("channel")
    if channel:
        st.success(f"Kênh: {channel['title']} · {channel['id']}")
        st.caption("Đã xác minh khi kết nối; có thể kiểm tra lại nếu quyền/token thay đổi.")
    elif status.get("connected"):
        st.warning("Có token cấu hình nhưng chưa xác minh kênh. Bấm kiểm tra kết nối.")
    else:
        st.info("Kết nối kênh YouTube một lần để bật tự động đăng.")
    with st.expander("Kết nối / kiểm tra YouTube", expanded=True):
        st.caption(
            "Google Cloud: bật YouTube Data API v3 và YouTube Analytics API; tạo OAuth Web client. "
            "Khai báo redirect URI trong hướng dẫn cấu hình. Không nhập mật khẩu Google."
        )
        with st.form(key + "-config"):
            client_id = st.text_input("Google OAuth client ID")
            secret = st.text_input("Google OAuth client secret", type="password")
            save = st.form_submit_button("Lưu OAuth client")
        if save:
            if request(
                "PUT",
                "/api/youtube/connection",
                json={"client_id": client_id, "client_secret": secret},
            ):
                st.success("Đã lưu cấu hình phía server.")
        if st.button("Kết nối bằng Google", key=key + "-start"):
            started = request("POST", "/api/youtube/oauth/start")
            if started:
                st.session_state[key + "-oauth"] = started
        if started := st.session_state.get(key + "-oauth"):
            st.code(started["redirect_uri"])
            st.link_button("Đăng nhập Google và chọn kênh", started["authorization_url"])
            st.caption("Sau khi Google báo thành công, quay lại đây và bấm kiểm tra kết nối.")
        if st.button("Kiểm tra kết nối kênh", key=key + "-verify"):
            verified = request("POST", "/api/youtube/connection/verify", timeout=90)
            if verified:
                status = verified
                st.success("Kết nối kênh đã được xác minh.")
    return status
