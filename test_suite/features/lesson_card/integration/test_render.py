import base64
import io
import json

import imageio_ffmpeg
import pytest
from PIL import Image

from app.config import Settings
from app.infrastructure.media.music import original_track
from app.modules.production.render import MediaAdapters, render_video
from tests.test_media import audio_fixture, clip  # noqa: F401
from tests.test_video import approved_script


@pytest.mark.parametrize("background", ["image", "video"])
def test_real_card_render_with_quiet_music_and_british_voice(client, tmp_path, clip, background):  # noqa: F811
    job_id, digest = approved_script(client)
    options = {
        "voice": "en-GB-SoniaNeural",
        "expected_content_hash": digest,
        "visual": {"preset": "lesson-card"},
        "music": {"track": "ambient", "volume": 0.10, "ducking": True},
    }
    if background == "image":
        picture = io.BytesIO()
        Image.new("RGB", (720, 1280), "#a26030").save(picture, format="PNG")
        options["images"] = [base64.b64encode(picture.getvalue()).decode()]
    else:
        uploaded = client.post(f"/api/jobs/{job_id}/assets?kind=video", content=clip.read_bytes())
        assert uploaded.status_code == 201, uploaded.text
        options["video_asset_id"] = uploaded.json()["id"]
    response = client.post(f"/api/jobs/{job_id}/render", json=options)
    assert response.status_code == 200, response.text
    queued = response.json()
    observed = []

    def speech(text, voice, directory, index):
        observed.append(voice)
        return audio_fixture(text, voice, directory, index)

    result = render_video(
        job_id,
        queued["package"],
        queued["render_config"],
        lambda _: None,
        adapters=MediaAdapters(synthesize=speech),
    )
    assert observed == ["en-GB-SoniaNeural"]
    assert result["music"]["mixed"] and result["music"]["volume"] == 0.10
    assert result["music"]["ducking"]
    directory = Settings().artifact_dir / job_id / result["run_id"]
    plan = json.loads((directory / "scene-plan.json").read_text())
    assert all(scene["layout"] == "lesson_card" for scene in plan["scenes"])
    assert (directory / "subtitles.srt").is_file()
    assert (directory / "soundtrack.wav").is_file()
    reader = imageio_ffmpeg.read_frames(str(directory / "video.mp4"))
    try:
        metadata = next(reader)
        frame = Image.frombytes("RGB", metadata["size"], next(reader))
    finally:
        reader.close()
    assert metadata["size"] == (720, 1280)
    assert frame.getpixel((65, 256))[0] > 230
    assert result["voice"] == "en-GB-SoniaNeural"


def test_music_stays_quieter_than_voice_during_speech(tmp_path):
    import array
    import math
    import wave

    from app.infrastructure.media.music import mix_audio
    from app.infrastructure.media.storage import file_digest

    audio_fixture("fixture", "en-GB-SoniaNeural", tmp_path, 0)
    (tmp_path / "voice-0000.wav").replace(tmp_path / "narration.wav")
    original_track(tmp_path / "input-music", "ambient")
    config = {
        "music_file": "input-music",
        "music_sha256": file_digest(tmp_path / "input-music"),
        "music_duration": 8,
        "music": {"start_seconds": 0, "volume": 0.10, "ducking": True},
    }
    mix_audio(tmp_path, config, 3)
    with wave.open(str(tmp_path / "narration.wav")) as source:
        voice = array.array("h", source.readframes(source.getnframes()))
    with wave.open(str(tmp_path / "soundtrack.wav")) as source:
        mixed = array.array("h", source.readframes(source.getnframes()))
    start, end = 22050, 22050 * 2
    voice_rms = math.sqrt(sum(v * v for v in voice[start:end]) / (end - start))
    bed_rms = math.sqrt(
        sum((m - v) ** 2 for m, v in zip(mixed[start:end], voice[start:end])) / (end - start)
    )
    assert bed_rms < voice_rms * 0.25
