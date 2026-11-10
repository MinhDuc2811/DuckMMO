import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.publishing import connection


@pytest.fixture
def google_http(client, monkeypatch):
    """Only Google HTTP is a declared fixture, never real account authorization/upload."""
    calls = []

    def transport(request):
        calls.append(request)
        if request.url.path == "/token":
            return httpx.Response(
                200, json={"access_token": "fixture-access", "refresh_token": "fixture-refresh"}
            )
        if request.url.path == "/youtube/v3/channels":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "fixture-channel", "snippet": {"title": "Fixture channel"}}]
                },
            )
        if request.url.path == "/upload/youtube/v3/videos":
            metadata = json.loads(request.content)
            assert metadata["status"]["privacyStatus"] == "private"
            assert datetime.fromisoformat(metadata["status"]["publishAt"]).tzinfo
            return httpx.Response(
                200, headers={"Location": "https://www.googleapis.com/session/fixture"}
            )
        if request.url.path == "/youtube/v3/videos":
            return httpx.Response(
                200,
                json={
                    "items": [{"status": {"privacyStatus": "public", "uploadStatus": "processed"}}]
                },
            )
        if request.url.path == "/session/fixture":
            return httpx.Response(201, json={"id": "fixture-video"})
        raise AssertionError(request.url)

    real = httpx.Client
    monkeypatch.setattr(
        connection.httpx,
        "Client",
        lambda **kwargs: real(transport=httpx.MockTransport(transport), **kwargs),
    )
    settings = client.app.state.settings
    connection.write(
        "youtube.json",
        {
            "client_id": "fixture-client",
            "client_secret": "fixture-secret",
            "refresh_token": "fixture-refresh",
            "channel": {"id": "fixture-channel", "title": "Fixture channel", "verified_at": 0},
        },
        settings,
    )
    return calls


@pytest.fixture
def plan_payload(client):
    topic = client.post("/api/ielts/topics", json={"name": "Environment"}).json()
    item = client.post(
        "/api/ielts/vocabulary",
        json={
            "title": "Green space",
            "topic_ids": [topic["id"]],
            "source": {
                "label": "Original fixture",
                "rights_note": "Original fixture, not published",
            },
            "data": {
                "lemma": "green space",
                "part_of_speech": "noun",
                "sense": "park land",
                "ipa_uk": "/ɡriːn speɪs/",
                "definition": "An area with grass and trees.",
                "examples": ["The city needs more green space."],
            },
        },
    )
    assert item.status_code == 201, item.text
    item = item.json()
    response = client.post(
        f"/api/ielts/items/{item['id']}/review",
        json={
            "expected_version": item["version"],
            "reviewer": "Fixture",
            "note": "Original fixture",
        },
    )
    assert response.status_code == 200, response.text
    item = response.json()
    return {
        "name": "Daily English",
        "first_publish_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        "interval_hours": 24,
        "episodes": [
            {
                "item_id": item["id"],
                "expected_version": item["version"],
                "focus_text": (
                    "Green space. An area with grass and trees. The city needs more green space."
                ),
            }
        ],
        "made_for_kids": False,
    }
