import base64
import hashlib
import io
import os

import pytest
from PIL import Image

from app.services.video import artifact_directory, split_captions
from app.worker import process_one
from tests.test_pipeline import client, submit  # noqa: F401


def approved_script(api_client):
    job = submit(api_client).json()
    process_one(api_client.app.state.sessions)
    api_client.post(
        f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "Tester", "note": "Self-authored test"},
    )
    text = job["package"]["scenes"][0]["narration"]
    return job["id"], hashlib.sha256(text.encode()).hexdigest()


def test_render_requires_approved_and_current_script(client):  # noqa: F811
    job = submit(client).json()
    assert (
        client.post(
            f"/api/jobs/{job['id']}/render", json={"expected_content_hash": "0" * 64}
        ).status_code
        == 409
    )
    job_id, _ = approved_script(client)
    assert (
        client.post(
            f"/api/jobs/{job_id}/render", json={"expected_content_hash": "0" * 64}
        ).status_code
        == 409
    )


def test_invalid_image_rejected(client):  # noqa: F811
    job_id, content_hash = approved_script(client)
    assert (
        client.post(
            f"/api/jobs/{job_id}/render",
            json={
                "expected_content_hash": content_hash,
                "images": [base64.b64encode(b"not an image").decode()],
            },
        ).status_code
        == 422
    )


@pytest.mark.skipif(os.name != "nt", reason="Real Windows local TTS integration")
def test_actual_video_render_review_and_edit_invalidates_media(client):  # noqa: F811
    job_id, content_hash = approved_script(client)
    image = io.BytesIO()
    Image.new("RGB", (640, 360), "#537f88").save(image, format="PNG")
    queued = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": content_hash,
            "voice": "local-vi",
            "layout": "landscape",
            "images": [base64.b64encode(image.getvalue()).decode()],
        },
    )
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"
    process_one(client.app.state.sessions)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "awaiting_video_review", job["error"]
    assert job["video"]["width"] == 1280
    assert job["video"]["height"] == 720
    assert job["video"]["visuals"] == "uploaded_images"
    assert job["video"]["audio_checked"]
    assert job["video"]["style"]["id"] == "story-cinematic"
    assert job["video"]["motion"] == "slow_zoom"
    assert job["video"]["duration"] > 0
    media = client.get(f"/api/jobs/{job_id}/artifacts/video")
    assert media.status_code == 200
    assert b"ftyp" in media.content[:40]
    assert client.get(f"/api/jobs/{job_id}/artifacts/audio").content.startswith(b"RIFF")
    assert "-->" in client.get(f"/api/jobs/{job_id}/artifacts/subtitles").text
    styled = client.get(f"/api/jobs/{job_id}/artifacts/styled_subtitles")
    assert styled.status_code == 200
    assert "[V4+ Styles]" in styled.text
    assert "Dialogue:" in styled.text
    assert client.get(f"/api/jobs/{job_id}/artifacts/style").json() == job["video"]["style"]
    directory = artifact_directory(job_id, job["video"]["run_id"])
    assert (directory / "manifest.json").is_file()
    report = client.get(f"/api/jobs/{job_id}/quality").json()
    steps = {run["step"] for run in report["runs"] if run["current"]}
    assert {"storyboard", "voice", "visuals", "subtitles", "audio", "render", "qa"} <= steps
    assert any(
        e["dimension"] == "video_decode_samples" and e["outcome"] == "pass"
        for e in report["evaluations"]
    )
    assert not any(e["outcome"] == "fail" and e["current"] for e in report["evaluations"])
    review = {
        "reviewer": "Tester",
        "note": "Checked video",
        "decision": "approve",
        "expected_video_hash": "0" * 64,
    }
    assert client.post(f"/api/jobs/{job_id}/video-review", json=review).status_code == 409
    review["expected_video_hash"] = job["video"]["sha256"]
    review["decision"] = "reject"
    assert client.post(f"/api/jobs/{job_id}/video-review", json=review).json()["status"] == (
        "video_rejected"
    )
    client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": content_hash,
            "voice": "local-vi",
            "layout": "landscape",
        },
    )
    process_one(client.app.state.sessions)
    new_job = client.get(f"/api/jobs/{job_id}").json()
    assert new_job["status"] == "awaiting_video_review"
    assert new_job["video"]["run_id"] != job["video"]["run_id"]
    review["decision"] = "approve"
    review["expected_video_hash"] = new_job["video"]["sha256"]
    assert client.post(f"/api/jobs/{job_id}/video-review", json=review).json()["status"] == (
        "video_approved"
    )
    edited = client.put(
        f"/api/jobs/{job_id}/content",
        json={"content": "Kịch bản đã sửa", "expected_content_hash": content_hash},
    )
    assert edited.json()["status"] == "awaiting_review"
    assert edited.json()["video"] is None
    assert client.get(f"/api/jobs/{job_id}/artifacts/video").status_code == 404


def test_caption_chunking_preserves_every_word():
    text = "Đây là kịch bản có nhiều đoạn. " * 50
    chunks = split_captions(text)
    assert " ".join(chunks).split() == text.split()
    assert all(len(chunk) <= 105 for chunk in chunks)
