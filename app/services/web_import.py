"""Generic HTTP fetch + main-text extraction; no domain or CSS selector special cases."""

import ipaddress
import logging
import re
import socket
import time
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura
from trafilatura.metadata import extract_metadata

logger = logging.getLogger(__name__)
MAX_BYTES = 3_000_000
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi,en;q=0.9",
}


class ImportFailure(ValueError):
    def __init__(self, message: str, stage: str = "fetch"):
        super().__init__(message)
        self.stage = stage


def validate_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in ("https", "http")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 80, 443)
        ):
            raise ValueError()
        if parsed.hostname.lower() == "localhost" or parsed.hostname.endswith(".localhost"):
            raise ValueError()
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
    except ValueError as exc:
        raise ImportFailure(
            "Cần URL HTTP/HTTPS công khai, không chứa thông tin đăng nhập.", "validate_url"
        ) from exc


def public_addresses(host: str, port: int) -> list[str]:
    try:
        addresses = list(
            dict.fromkeys(
                entry[4][0] for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            )
        )
    except socket.gaierror as exc:
        raise ImportFailure("Không phân giải được tên miền website.", "dns") from exc
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ImportFailure("Website trỏ tới địa chỉ mạng nội bộ, không thể truy cập.", "dns")
    return addresses


class PublicWebTransport(httpx.HTTPTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        validate_url(str(request.url))
        addresses = public_addresses(
            request.url.host, request.url.port or (443 if request.url.scheme == "https" else 80)
        )
        # Connect to the validated address, retain Host and TLS verification/SNI.
        # This avoids a second DNS resolution changing the destination to a private IP.
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=addresses[0]),
            headers=request.headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": request.url.host},
        )
        return super().handle_request(pinned)


def fetch_page(url: str) -> tuple[str, str]:
    started = time.monotonic()
    with httpx.Client(
        headers=HEADERS,
        timeout=20,
        follow_redirects=False,
        transport=PublicWebTransport(),
        trust_env=False,
    ) as client:
        for _ in range(5):
            validate_url(url)
            if time.monotonic() - started > 60:
                raise ImportFailure("Quá thời gian lấy nội dung website.", "timeout")
            with client.stream("GET", url) as response:
                logger.info(
                    "crawl stage=fetch host=%s status=%s",
                    urlsplit(url).hostname,
                    response.status_code,
                )
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ImportFailure("Chuyển hướng thiếu địa chỉ đích.", "redirect")
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    raise ImportFailure(
                        f"Website trả HTTP {response.status_code}; chưa lấy được nội dung.",
                        "http_status",
                    )
                content_type = response.headers.get("content-type", "").lower()
                if not any(t in content_type for t in ("text/html", "application/xhtml+xml")):
                    raise ImportFailure("URL không trả trang HTML.", "content_type")
                data = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() - started > 60:
                        raise ImportFailure("Quá thời gian lấy nội dung website.", "timeout")
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ImportFailure("Trang vượt giới hạn 3 MB.", "size")
                # Pass bytes through: trafilatura detects HTTP/HTML encodings rather than
                # forcing UTF-8 and silently corrupting non-UTF-8 sources.
                return trafilatura.utils.decode_file(bytes(data)), url
    raise ImportFailure("Website chuyển hướng quá nhiều lần.", "redirect")


def extract_page(document: str) -> tuple[str, str]:
    try:
        metadata = extract_metadata(document)
        title = metadata.title if metadata and metadata.title else "Nội dung từ website"
        text = (
            trafilatura.extract(
                document, include_comments=False, include_tables=False, deduplicate=True
            )
            or ""
        )
    except (ValueError, TypeError) as exc:
        raise ImportFailure("Không phân tích được HTML của website.", "extract") from exc
    paragraphs = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    content = "\n\n".join(line for line in paragraphs if line)
    if len(content) < 100:
        raise ImportFailure(
            "Không tìm thấy đủ văn bản chính. Trang có thể cần JavaScript, đăng nhập "
            "hoặc đang chặn truy cập; chưa thể chuyển sang kiểm duyệt.",
            "extract",
        )
    if len(content) > 200000:
        raise ImportFailure("Nội dung vượt 200.000 ký tự; hãy chia nguồn nhỏ hơn.", "size")
    return title.strip()[:200], content


def import_url(url: str) -> dict:
    try:
        document, final_url = fetch_page(url)
        title, content = extract_page(document)
    except httpx.TimeoutException as exc:
        raise ImportFailure("Website không phản hồi kịp thời.", "timeout") from exc
    except httpx.RequestError as exc:
        logger.warning("crawl stage=network error_type=%s", type(exc).__name__)
        raise ImportFailure("Lỗi kết nối hoặc TLS khi tải website.", "network") from exc
    return {"title": title, "content": content, "source_url": final_url}
