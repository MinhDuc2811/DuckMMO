"""Real API; Google HTTP only is a declared local test fixture. Never use against user data."""

import os
from pathlib import Path

import httpx

root = Path(os.environ["AUTOMATION_FIXTURE_ROOT"]).resolve()
if os.environ.get("STUDIO_DATABASE_URL") != f"sqlite:///{root / 'studio.db'}":
    raise RuntimeError("Google HTTP fixture requires isolated browser database")

real_client = httpx.Client


def transport(request):
    if request.url.path == "/token":
        return httpx.Response(
            200, json={"access_token": "fixture-access", "refresh_token": "fixture-refresh"}
        )
    if request.url.path == "/youtube/v3/channels":
        return httpx.Response(
            200,
            json={"items": [{"id": "fixture-channel", "snippet": {"title": "Fixture channel"}}]},
        )
    raise AssertionError("Unexpected external Google HTTP request")


def google_client(**kwargs):
    return real_client(transport=httpx.MockTransport(transport), **kwargs)


from app.publishing import connection  # noqa: E402

connection.httpx.Client = google_client
from app.main import app  # noqa: E402

__all__ = ["app"]
