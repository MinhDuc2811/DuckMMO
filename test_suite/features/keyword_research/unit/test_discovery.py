from datetime import date

import pytest
from pydantic import ValidationError

from app.contracts.research import ResearchPreferences, ResearchRequest
from app.services.discovery import discover_sources
from app.services.web_import import ImportFailure


def research(**options):
    return ResearchRequest(keyword="FC Online update", target_date=date(2026, 10, 23), **options)


def test_preferred_articles_and_supplemental_web_sources_are_both_selected():
    queries = []

    def search(query, limit):
        queries.append(query)
        return ["https://other.example/report", "http://127.0.0.1/private"]

    result = discover_sources(
        research(preferred_url="https://official.example/news", max_sources=2),
        fetch=lambda url: ('<a href="/update">FC Online update</a>', url),
        search=search,
    )
    assert result["urls"] == ["https://official.example/update", "https://other.example/report"]
    assert queries == ["FC Online update 2026-10-23"]


def test_no_sources_fails_instead_of_generating_content():
    with pytest.raises(ImportFailure, match="Không tìm thấy nguồn"):
        discover_sources(research(), search=lambda *args: [])


def test_site_only_and_cross_domain_link_rejection():
    result = discover_sources(
        research(preferred_url="https://official.example/news", search_web=False),
        fetch=lambda url: (
            '<a href="https://evil.example/update">FC update</a><a href="/update">FC update</a>',
            url,
        ),
        search=lambda *args: [],
    )
    assert result["urls"] == ["https://official.example/update"]


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://localhost", "https://a:b@site.com"])
def test_private_or_credentialed_preferred_url_rejected(url):
    with pytest.raises(ValidationError):
        research(preferred_url=url)


def test_duplicate_profiles_rejected():
    profile = {"branch": "research", "topic_path": ["news", "esport"]}
    with pytest.raises(ValidationError):
        ResearchPreferences(profiles=[profile, profile])


def test_duckduckgo_adapter_decodes_redirect_links(monkeypatch):
    from app.config import Settings
    from app.services.discovery import search_urls

    monkeypatch.setattr(
        "app.services.discovery.fetch_page",
        lambda url: (
            '<a class="result__a" href="//duckduckgo.com/l/?uddg='
            'https%3A%2F%2Fnews.example%2Fpatch">Patch</a>',
            url,
        ),
    )
    assert search_urls("patch", 2, Settings(search_provider="duckduckgo")) == [
        "https://news.example/patch"
    ]


def test_google_adapter_uses_configured_engine_and_does_not_fall_back(monkeypatch):
    import httpx

    from app.config import Settings
    from app.services.discovery import search_urls

    settings = Settings(
        search_provider="google",
        google_search_api_key="fixture-key",
        google_search_engine_id="fixture-engine",
    )
    calls = []

    def get(self, url, **kwargs):
        calls.append((url, kwargs["params"]))
        return httpx.Response(200, json={"items": [{"link": "https://news.example/patch"}]})

    monkeypatch.setattr(httpx.Client, "get", get)
    assert search_urls("patch", 1, settings) == ["https://news.example/patch"]
    assert calls[0][0] == "https://www.googleapis.com/customsearch/v1"
    assert calls[0][1]["cx"] == "fixture-engine"
    assert calls[0][1]["q"] == "patch"
    with pytest.raises(ImportFailure, match="API key"):
        search_urls("patch", 1, Settings(search_provider="google"))


def test_site_only_never_calls_external_search_when_site_has_no_articles():
    def forbidden_search(*args):
        raise AssertionError("Website-only research must not contact a search provider")

    result = discover_sources(
        research(preferred_url="https://official.example/news", search_web=False),
        fetch=lambda url: ("<html><body>No article links</body></html>", url),
        search=forbidden_search,
    )
    assert result["urls"] == ["https://official.example/news"]


@pytest.mark.parametrize(
    "markup,expected",
    [
        (
            '<meta property="article:published_time" content="2026-10-25T09:00:00+07:00">',
            "2026-10-25T09:00:00+07:00",
        ),
        (
            '<time itemprop="datePublished" datetime="2026-10-24">Yesterday</time>',
            "2026-10-24T00:00:00",
        ),
        ('<meta property="article:modified_time" content="2026-10-25">', None),
        ('<meta property="article:published_time" content="invalid">', None),
        ("<p>Last crawled today: 2026-10-25</p>", None),
    ],
)
def test_publication_metadata_never_substitutes_modified_or_retrieved_date(markup, expected):
    from app.services.web_import import publication_date

    assert publication_date("<html><head>" + markup + "</head></html>") == expected
