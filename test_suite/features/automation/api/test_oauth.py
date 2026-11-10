from urllib.parse import parse_qs, urlsplit

from app.publishing import connection


def test_pkce_one_use_state_channel_verification_and_secret_redaction(client, google_http):
    response = client.put(
        "/api/youtube/connection", json={"client_id": "new-client", "client_secret": "new-secret"}
    )
    assert response.status_code == 200
    assert "new-secret" not in response.text
    begin = client.post("/api/youtube/oauth/start").json()
    params = parse_qs(urlsplit(begin["authorization_url"]).query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["access_type"] == ["offline"]
    invalid = client.get(
        "/api/youtube/oauth/callback", params={"code": "fixture-code", "state": "wrong"}
    )
    assert invalid.status_code == 409
    done = client.get(
        "/api/youtube/oauth/callback", params={"code": "fixture-code", "state": params["state"][0]}
    )
    assert done.status_code == 200, done.text
    assert client.get("/api/youtube/status").json()["channel"]["id"] == "fixture-channel"
    assert "fixture-refresh" not in client.get("/api/youtube/status").text
    replay = client.get(
        "/api/youtube/oauth/callback", params={"code": "fixture-code", "state": params["state"][0]}
    )
    assert replay.status_code == 409
    file = connection.directory(client.app.state.settings) / "youtube.json"
    assert file.stat().st_mode & 0o077 == 0
