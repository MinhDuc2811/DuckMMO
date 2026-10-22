from uuid import uuid4

import pytest

from app.contracts.content import content_hash
from app.contracts.errors import VideoFailure
from app.infrastructure.media.audio import long_pauses, trim_boundary_silence
from app.infrastructure.media.speech import synthesize
from app.modules.production.render import MediaAdapters, render_video
from test_suite.support.audio import write_pcm
from tests.test_media import audio_fixture


def test_boundary_trim_keeps_internal_pause_and_outside_edges(tmp_path):
    path = tmp_path / "voice.wav"
    write_pcm(path, [(0.5, 0), (1, 2000), (1, 0), (1, 2000), (0.5, 0)])
    result = trim_boundary_silence(path, trim_start=True, trim_end=True)
    assert result["trimmed_start_seconds"] == pytest.approx(0.42, abs=0.01)
    assert result["trimmed_end_seconds"] == pytest.approx(0.34, abs=0.01)
    assert result["duration"] == pytest.approx(3.24, abs=0.01)
    pauses = long_pauses(path)
    assert len(pauses) == 1 and pauses[0]["duration"] == pytest.approx(1, abs=0.05)
    untouched = tmp_path / "outside.wav"
    write_pcm(untouched, [(0.5, 0), (1, 2000), (0.5, 0)])
    assert trim_boundary_silence(untouched, trim_start=False, trim_end=False)["duration"] == 2


def test_cache_reuses_audio_but_rate_changes_and_trim_do_not_poison_it(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    calls = []

    def provider(text, voice, directory, index, rate=0, **kwargs):
        calls.append((text, voice, rate))
        return audio_fixture(text, voice, directory, index)

    monkeypatch.setattr("app.infrastructure.media.speech._synthesize", provider)
    directory = tmp_path / "render"
    directory.mkdir()
    first, duration = synthesize("Lời dẫn", "vi-VN-HoaiMyNeural", directory, 0)
    (directory / first).write_bytes(b"changed run file")
    second, repeated_duration = synthesize("Lời dẫn", "vi-VN-HoaiMyNeural", directory, 1)
    assert repeated_duration == duration == 3
    assert (directory / second).read_bytes().startswith(b"RIFF")
    assert len(calls) == 1
    synthesize("Lời dẫn", "vi-VN-HoaiMyNeural", directory, 2, rate=10)
    assert len(calls) == 2


def test_real_render_calls_tts_once_but_keeps_multiple_visuals_and_subtitles(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path))
    script = ("Một câu chuyện được kể liền mạch cho người Việt nghe thật tự nhiên " * 3).strip()
    package = {"title": "Speech regression", "branch": "novel", "scenes": [{"narration": script}]}
    job_id, run_id = str(uuid4()), str(uuid4())
    directory = tmp_path / job_id / run_id
    directory.mkdir(parents=True)
    calls = []

    def provider(text, voice, directory, index):
        calls.append(text)
        return audio_fixture(text, voice, directory, index)

    result = render_video(
        job_id,
        package,
        {
            "run_id": run_id,
            "expected_content_hash": content_hash(package),
            "voice": "vi-VN-HoaiMyNeural",
            "image_files": [],
            "layout": "portrait",
        },
        lambda _: None,
        adapters=MediaAdapters(synthesize=provider),
    )
    assert calls == [script]
    assert len(result["speech"]["segments"]) == 1
    assert len(list(directory.glob("frame-*.png"))) > 1
    assert result["caption_count"] > 1
    assert result["audio_checked"] and result["video_checked"]
    assert (directory / "speech-timeline.json").is_file()


def test_silent_tts_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    directory = tmp_path / "render"
    directory.mkdir()

    def silent_provider(text, voice, directory, index, rate=0, **kwargs):
        path = directory / f"voice-{index:04}.wav"
        write_pcm(path, [(1, 0)])
        return path.name, 1

    monkeypatch.setattr("app.infrastructure.media.speech._synthesize", silent_provider)
    with pytest.raises(VideoFailure, match="không lưu cache"):
        synthesize("Lời dẫn", "vi-VN-HoaiMyNeural", directory, 0)
    assert not list((tmp_path / "artifacts" / "speech-cache").glob("*.wav"))
