import hashlib
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.db import Job, PublishAttempt
from app.publishing import youtube
from app.services.video import artifact_directory, content_hash
from tests.test_pipeline import client, submit  # noqa: F401


def video_fixture(api_client):
    row = submit(api_client).json()
    with api_client.app.state.sessions() as session:
        job = session.get(Job, row["id"])
        run_id = str(uuid4())
        directory = artifact_directory(job.id, run_id)
        directory.mkdir(parents=True)
        # Protocol fixture, not claimed to be a rendered video.
        data = b"protocol-fixture"
        (directory / "video.mp4").write_bytes(data)
        video_hash = hashlib.sha256(data).hexdigest()
        job.status = "video_approved"
        job.video = {
            "run_id": run_id,
            "sha256": video_hash,
            "content_hash": content_hash(job.package),
        }
        session.commit()
    return row["id"], {
        "title": "Protocol test",
        "made_for_kids": False,
        "expected_video_hash": video_hash,
        "privacy": "private",
    }


def fake_oauth(monkeypatch):
    monkeypatch.setenv("STUDIO_YOUTUBE_CLIENT_ID", "test-client")
    monkeypatch.setenv("STUDIO_YOUTUBE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("STUDIO_YOUTUBE_REFRESH_TOKEN", "test-refresh")


def test_youtube_rejects_unapproved_or_disconnected(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("STUDIO_YOUTUBE_CLIENT_ID", "")
    job = submit(client).json()
    payload = {"title": "Test", "made_for_kids": False, "expected_video_hash": "0" * 64}
    assert client.post(f"/api/jobs/{job['id']}/youtube", json=payload).status_code == 409
    job_id, payload = video_fixture(client)
    assert client.post(f"/api/jobs/{job_id}/youtube", json=payload).status_code == 409
    assert not client.get("/api/youtube/status").json()["connected"]


def test_upload_reconciles_and_missing_metrics_stay_unknown(client, monkeypatch):  # noqa: F811
    fake_oauth(monkeypatch)
    job_id, payload = video_fixture(client)
    calls = []

    def transport(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "test-access"})
        if request.url.path == "/upload/youtube/v3/videos":
            return httpx.Response(
                200, headers={"Location": "https://www.googleapis.com/session/test"}
            )
        if request.url.path == "/session/test":
            if request.headers.get("Content-Range", "").startswith("bytes */"):
                return httpx.Response(201, json={"id": "test-video-id"})
            raise httpx.ReadTimeout("simulated uncertain completion")
        if request.url.path == "/v2/reports":
            return httpx.Response(200, json={"columnHeaders": [{"name": "views"}], "rows": []})
        raise AssertionError(str(request.url))

    real_client = httpx.Client
    monkeypatch.setattr(
        youtube.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs),
    )
    first = client.post(f"/api/jobs/{job_id}/youtube", json=payload)
    assert first.status_code == 502
    resumed = client.post(f"/api/jobs/{job_id}/youtube", json=payload)
    assert resumed.status_code == 200
    assert resumed.json()["state"] == "uploaded"
    assert "session_url" not in str(resumed.json())
    again = client.post(f"/api/jobs/{job_id}/youtube", json=payload)
    assert again.json()["id"] == resumed.json()["id"]
    assert calls.count(("POST", "/upload/youtube/v3/videos")) == 1
    attempt_id = resumed.json()["id"]
    metrics = client.post(f"/api/youtube/{attempt_id}/analytics").json()
    assert metrics["metrics"]["data_available"] is False
    assert metrics["metrics"]["values"] == {}
    client.post(f"/api/youtube/{attempt_id}/analytics")
    assert calls.count(("GET", "/v2/reports")) == 1
    with client.app.state.sessions() as session:
        assert len(list(session.scalars(select(PublishAttempt)))) == 1
