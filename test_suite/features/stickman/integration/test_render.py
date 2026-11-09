"""Actual upstream canvas/FFmpeg preview and film lifecycle through HTTP."""

import hashlib

from test_suite.support.stickman import project_with_audio


def test_real_preview_approval_full_render_and_edit_invalidation(client):
    item = project_with_audio(client)
    endpoint = f"/api/stickman/projects/{item['id']}"
    payload = {"expected_version": item["version"], "seconds": 1}
    assert client.post(endpoint + "/actions/render", json=payload).status_code == 409
    assert client.post(endpoint + "/actions/validate", json=payload).status_code == 200
    preview = client.post(endpoint + "/actions/preview", json=payload)
    assert preview.status_code == 200, preview.text
    data = preview.json()["project"]
    assert data["state"] == "previewed" and preview.json()["report"]["full_decode"] == "pass"
    video = client.get(endpoint + "/artifacts/preview")
    assert video.status_code == 200 and b"ftyp" in video.content[:40]
    assert hashlib.sha256(video.content).hexdigest() == data["preview_sha256"]
    assert (
        client.post(
            endpoint + "/actions/approve",
            json={**payload, "note": "Reviewed fixture", "preview_sha256": "0" * 64},
        ).status_code
        == 409
    )
    approved = client.post(
        endpoint + "/actions/approve",
        json={
            **payload,
            "note": "Technical fixture approval only, not actual speech/aesthetic review",
            "preview_sha256": data["preview_sha256"],
        },
    )
    assert approved.status_code == 200, approved.text
    film = client.post(endpoint + "/actions/render", json=payload)
    assert film.status_code == 200, film.text
    assert film.json()["report"]["original_voice_duration"] == 2
    assert film.json()["report"]["voice_rate"].startswith("unchanged")
    assert client.get(endpoint + "/artifacts/film").status_code == 200
    assert "Learn one idea" in client.get(endpoint + "/artifacts/film-srt").text
    edited = client.put(
        endpoint, json={"expected_version": data["version"], "project": data["project"]}
    )
    assert edited.status_code == 200 and edited.json()["state"] == "draft"
    assert client.get(endpoint + "/artifacts/film").status_code == 409
    assert client.get(endpoint + "/artifacts/preview").status_code == 409
    assert client.post(endpoint + "/actions/render", json=payload).status_code == 409
    assert client.get("/api/jobs").json() == []
