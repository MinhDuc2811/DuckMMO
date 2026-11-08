"""Offline provider boundary fixtures; no claim of live stock access."""

import httpx
import pytest

from app.config import Settings
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.stock import search_stock


def test_pexels_endpoint_credit_and_key_are_not_returned():
    def handler(request):
        assert request.url.host == "api.pexels.com"
        assert request.headers["Authorization"] == "fixture-secret"
        assert request.url.params["orientation"] == "portrait"
        return httpx.Response(
            200,
            json={
                "photos": [
                    {
                        "id": 7,
                        "url": "https://www.pexels.com/photo/7/",
                        "photographer": "Artist",
                        "alt": "A real library",
                    }
                ]
            },
        )

    result = search_stock(
        "pexels",
        "image",
        "library",
        1,
        Settings(pexels_api_key="fixture-secret"),
        transport=httpx.MockTransport(handler),
    )
    assert result["results"][0]["author"] == "Artist"
    assert result["results"][0]["rights_verified"] is False
    assert "fixture-secret" not in str(result)


def test_openverse_per_file_license_and_unsafe_links_filtered():
    def handler(request):
        assert request.url.host == "api.openverse.org"
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "cc",
                        "foreign_landing_url": "https://example.org/photo",
                        "creator": "Author",
                        "license": "by",
                        "license_version": "4.0",
                        "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    },
                    {"id": "bad", "foreign_landing_url": "javascript:alert(1)"},
                ]
            },
        )

    result = search_stock(
        "openverse", "image", "library", 1, Settings(), transport=httpx.MockTransport(handler)
    )
    assert len(result["results"]) == 1
    assert result["results"][0]["license"] == "by 4.0"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429),
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, content=b"x" * 2_000_001),
    ],
)
def test_unavailable_or_oversize_source_fails_without_fake_results(response):
    with pytest.raises(MediaFailure):
        search_stock(
            "openverse",
            "image",
            "library",
            1,
            Settings(),
            transport=httpx.MockTransport(lambda _: response),
        )


def test_unsupported_video_and_missing_key():
    with pytest.raises(MediaFailure):
        search_stock("openverse", "video", "city", 1, Settings())
    with pytest.raises(MediaFailure, match="PEXELS"):
        search_stock("pexels", "image", "city", 1, Settings(pexels_api_key=""))


def test_openverse_audio_and_no_invented_pexels_music_api():
    def handler(request):
        assert request.url.path == "/v1/audio/"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "music",
                        "foreign_landing_url": "https://example.org/music",
                        "title": "Original instrumental",
                        "creator": "Composer",
                        "license": "cc0",
                        "license_version": "1.0",
                    }
                ]
            },
        )

    result = search_stock(
        "openverse",
        "audio",
        "happy instrumental",
        1,
        Settings(),
        transport=httpx.MockTransport(handler),
    )
    assert result["results"][0]["kind"] == "audio"
    assert result["results"][0]["author"] == "Composer"
    assert result["results"][0]["rights_verified"] is False
    with pytest.raises(MediaFailure, match="Pexels"):
        search_stock("pexels", "audio", "happy instrumental", 1, Settings(pexels_api_key="fixture"))
