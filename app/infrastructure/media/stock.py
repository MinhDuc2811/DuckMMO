"""Stock discovery only: fixed provider endpoints, bounded JSON, no arbitrary downloads."""

import json
from urllib.parse import urlsplit

import httpx

from app.infrastructure.media.probe import MediaFailure


def public_link(value):
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
        return value
    return None


def search_stock(provider, kind, query, page, settings, *, transport=None):
    headers = {"User-Agent": "DuckMMO-learning-studio/0.1"}
    if provider == "pexels":
        if kind == "audio":
            raise MediaFailure("Pexels không cung cấp tìm nhạc trong tích hợp này.")
        key = settings.pexels_api_key.get_secret_value()
        if not key:
            raise MediaFailure("Cần STUDIO_PEXELS_API_KEY để tìm ảnh/video trên Pexels.")
        headers["Authorization"] = key
        endpoint = (
            "https://api.pexels.com/v1/search"
            if kind == "image"
            else "https://api.pexels.com/videos/search"
        )
        params = {"query": query, "orientation": "portrait", "per_page": 12, "page": page}
    else:
        if kind == "video":
            raise MediaFailure("Openverse trong ứng dụng tìm ảnh hoặc audio, không có video.")
        endpoint = "https://api.openverse.org/v1/" + ("audio/" if kind == "audio" else "images/")
        params = {"q": query, "page_size": 12, "page": page, "mature": "false"}
    try:
        with httpx.Client(timeout=20, follow_redirects=False, transport=transport) as client:
            with client.stream("GET", endpoint, params=params, headers=headers) as response:
                if response.status_code != 200:
                    raise MediaFailure(
                        f"Nguồn stock trả HTTP {response.status_code}; chưa có kết quả."
                    )
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise MediaFailure("Kết quả stock vượt giới hạn 2 MB.")
        payload = json.loads(data)
        results = []
        if provider == "pexels":
            for item in payload.get("photos" if kind == "image" else "videos", [])[:12]:
                source = public_link(item.get("url"))
                if not source:
                    continue
                author = (
                    item.get("photographer")
                    if kind == "image"
                    else item.get("user", {}).get("name")
                )
                results.append(
                    {
                        "provider": provider,
                        "provider_id": str(item["id"]),
                        "kind": kind,
                        "title": item.get("alt") or f"Pexels {item['id']}",
                        "author": author or "Unknown",
                        "source_url": source,
                        "license": "Pexels License — review current terms",
                        "license_url": "https://www.pexels.com/license/",
                        "rights_verified": False,
                    }
                )
        else:
            for item in payload.get("results", [])[:12]:
                source = public_link(item.get("foreign_landing_url"))
                if not source:
                    continue
                results.append(
                    {
                        "provider": provider,
                        "provider_id": str(item["id"]),
                        "kind": kind,
                        "title": item.get("title") or "Untitled",
                        "author": item.get("creator") or "Unknown",
                        "source_url": source,
                        "license": (
                            str(item.get("license", "unknown"))
                            + " "
                            + str(item.get("license_version", ""))
                        ).strip(),
                        "license_url": public_link(item.get("license_url")),
                        "rights_verified": False,
                    }
                )
        return {"provider": provider, "page": page, "results": results}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise MediaFailure(
            "Không đọc được nguồn stock. Thử lại sau; không dùng kết quả giả."
        ) from exc
