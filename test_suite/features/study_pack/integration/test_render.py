from app.modules.production.render import MediaAdapters, render_video
from tests.test_media import audio_fixture
from tests.test_video import approved_script


def test_library_assets_render_with_real_encoder_and_mixer(client):
    job_id, digest = approved_script(client)
    response = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": digest,
            "background_id": "misty-lake",
            "voice": "en-GB-SoniaNeural",
            "visual": {"preset": "lesson-card"},
            "music": {"track": "soft-focus", "volume": 0.10, "ducking": True},
        },
    )
    assert response.status_code == 200, response.text
    job = response.json()
    result = render_video(
        job_id,
        job["package"],
        job["render_config"],
        lambda _: None,
        adapters=MediaAdapters(synthesize=audio_fixture),
    )
    assert result["visuals"] == "library_background"
    assert result["music"]["track"] == "soft-focus" and result["music"]["mixed"]
    assert result["voice"] == "en-GB-SoniaNeural"
    assert result["width"] == 720 and result["height"] == 1280
    assert result["audio_checked"] and result["video_checked"]
