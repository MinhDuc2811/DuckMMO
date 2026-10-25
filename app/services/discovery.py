"""Bounded source discovery; every fetched source still uses the public-web crawler."""

from datetime import datetime, timezone
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit, urlunsplit

import httpx
from lxml import html

from app.config import Settings
from app.services.web_import import ImportFailure, fetch_page, validate_url


def canonical_url(value):
    validate_url(value)
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", parts.query, ""))


def search_urls(query, limit, settings=None):
    settings = settings or Settings()
    try:
        if settings.search_provider == "google":
            key = settings.google_search_api_key.get_secret_value()
            if not key or not settings.google_search_engine_id:
                raise ImportFailure("Google Search cần API key và Search engine ID.", "search")
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                response = client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": key,
                        "cx": settings.google_search_engine_id,
                        "q": query,
                        "num": min(limit, 10),
                    },
                )
            if response.status_code != 200:
                raise ImportFailure(f"Google Search trả HTTP {response.status_code}.", "search")
            return [item["link"] for item in response.json().get("items", [])][:limit]
        if settings.search_provider != "duckduckgo":
            raise ImportFailure("Search provider không được hỗ trợ.", "search")
        document, _ = fetch_page("https://html.duckduckgo.com/html/?q=" + quote_plus(query))
        tree = html.fromstring(document)
        links = tree.xpath(
            '//a[contains(concat(" ",normalize-space(@class)," ")," result__a ")]/@href'
        )
        result = []
        for link in links:
            target = urljoin("https://html.duckduckgo.com", link)
            wrapped = parse_qs(urlsplit(target).query).get("uddg")
            result.append(wrapped[0] if wrapped else target)
        return result[:limit]
    except (httpx.RequestError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, ImportFailure):
            raise
        raise ImportFailure(
            "Không tìm kiếm được nguồn; kiểm tra provider hoặc mạng.", "search"
        ) from exc


def discover_sources(request, *, search=search_urls, fetch=fetch_page, checkpoint=lambda: None):
    """Preferred-site articles first, then supplemental web results. Snapshot before crawling."""
    urls, warnings = [], []

    def add(value):
        try:
            normalized = canonical_url(value)
        except (ValueError, ImportFailure):
            return
        if normalized not in urls and len(urls) < request.max_sources:
            urls.append(normalized)

    context = " ".join([request.keyword, *request.topic_path, request.target_date.isoformat()])
    if request.preferred_url:
        preferred = str(request.preferred_url)
        host = urlsplit(preferred).hostname
        preferred_limit = max(1, request.max_sources - int(request.search_web))
        checkpoint()
        try:
            document, final_url = fetch(preferred)
            if urlsplit(final_url).hostname != host:
                raise ImportFailure("Website ưu tiên chuyển sang tên miền khác.", "discovery")
            tree = html.fromstring(document)
            words = set((request.keyword + " " + " ".join(request.topic_path)).lower().split())
            candidates = []
            for anchor in tree.xpath("//a[@href]")[:1000]:
                url = urljoin(final_url, anchor.get("href"))
                parts = urlsplit(url)
                if parts.hostname != host or not parts.path or parts.path == "/":
                    continue
                label = (anchor.text_content() + " " + parts.path).lower()
                score = sum(word in label for word in words if len(word) > 2)
                if score:
                    candidates.append((score, url))
            for _, url in sorted(candidates, key=lambda item: item[0], reverse=True):
                add(url)
                if len(urls) >= preferred_limit:
                    break
            if not urls:
                add(final_url)
        except (ImportFailure, httpx.RequestError, ValueError):
            warnings.append(
                "Chưa đọc được trang ưu tiên."
                + (" Sẽ tìm bài qua search." if request.search_web else "")
            )
        if request.search_web and len(urls) < preferred_limit:
            checkpoint()
            try:
                for url in search(f"site:{host} {context}", request.max_sources):
                    if urlsplit(url).hostname == host:
                        add(url)
                        if len(urls) >= preferred_limit:
                            break
            except ImportFailure as exc:
                warnings.append(str(exc))
    if request.search_web:
        checkpoint()
        try:
            for url in search(context, request.max_sources):
                add(url)
        except ImportFailure as exc:
            warnings.append(str(exc))
    if not urls:
        raise ImportFailure("Không tìm thấy nguồn phù hợp. " + " ".join(warnings), "discovery")
    return {
        "urls": urls,
        "query": context,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
    }
