"""Declared synthetic PCM and HTTP project setup shared across Stickman tests."""

import array
import io
import math
import wave


def pcm():
    output = io.BytesIO()
    samples = array.array(
        "h", (int(5000 * math.sin(2 * math.pi * 220 * i / 22050)) for i in range(44100))
    )
    with wave.open(output, "wb") as file:
        file.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        file.writeframes(samples.tobytes())
    return output.getvalue()


def project_with_audio(client):
    created = client.post(
        "/api/stickman/projects",
        json={"title": "Independent fixture", "style": "B1", "ratio": "9:16"},
    )
    assert created.status_code == 201, created.text
    item = created.json()
    uploaded = client.post(
        f"/api/stickman/projects/{item['id']}/assets",
        params={
            "filename": "voice.wav",
            "rights_note": "Original synthetic test tone; not actual TTS",
        },
        content=pcm(),
    )
    assert uploaded.status_code == 201, uploaded.text
    assert client.get("/api/jobs").json() == []
    response = client.post(
        f"/api/stickman/projects/{item['id']}/starter",
        json={
            "expected_version": item["version"],
            "audio_path": uploaded.json()["path"],
            "caption": "Learn one idea at a time.",
        },
    )
    assert response.status_code == 200, response.text
    item = response.json()
    # Small real encoder fixture, retaining portrait geometry and upstream caption sizing.
    item["project"].update(width=360, height=640, fps=12)
    edited = client.put(
        f"/api/stickman/projects/{item['id']}",
        json={"expected_version": item["version"], "project": item["project"]},
    )
    assert edited.status_code == 200, edited.text
    return edited.json()
