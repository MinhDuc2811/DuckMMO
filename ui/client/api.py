import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("STUDIO_API_URL", "http://127.0.0.1:8000").rstrip("/")
HEADERS = {"X-API-Key": os.getenv("STUDIO_API_KEY", "")}


def request(method, path, extra_headers=None, **kwargs):
    try:
        response = httpx.request(
            method,
            f"{API_URL}{path}",
            headers={**HEADERS, **(extra_headers or {})},
            timeout=kwargs.pop("timeout", 15),
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        st.error(
            detail
            if isinstance(detail, str)
            else "Chưa xử lý được yêu cầu. Kiểm tra nội dung nhập."
        )
    except httpx.RequestError:
        st.error("Không kết nối được API. Hãy chạy migration và khởi động FastAPI.")
    return None
