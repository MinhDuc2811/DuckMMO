import array
import json
import math
import wave

import imageio_ffmpeg
import pytest

from app.config import Settings
from app.contracts.presentation import VisualOptions, apply_presentation
from app.infrastructure.media.music import mix_audio, original_track
from app.infrastructure.media.scenes import build_plan, export
from app.infrastructure.media.storage import file_digest
from app.modules.production.render import MediaAdapters, render_video
from tests.test_video import approved_script


def samples(path):
    with wave.open(str(path), "rb") as source:
        return array.array("h", source.readframes(source.getnframes()))


def rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values))


def test_ducking_lowers_music_during_voice_and_preserves_dry_audio(tmp_path, narration):
    narration(tmp_path / "narration.wav")
    original = (tmp_path / "narration.wav").read_bytes()
    original_track(tmp_path / "input-music", "ambient")
    config = dict(
        music_file="input-music",
        music_sha256=file_digest(tmp_path / "input-music"),
        music_duration=8,
        music=dict(start_seconds=0, volume=0.3, ducking=False),
    )
    assert mix_audio(tmp_path, config, 4) == "soundtrack.wav"
    plain = samples(tmp_path / "soundtrack.wav")
    config["music"]["ducking"] = True
    mix_audio(tmp_path, config, 4)
    ducked = samples(tmp_path / "soundtrack.wav")
    voice = samples(tmp_path / "narration.wav")
    start, end = 22050, round(1.8 * 22050)
    assert rms([du - v for du, v in zip(ducked[start:end], voice[start:end])]) < 0.7 * rms(
        [pl - v for pl, v in zip(plain[start:end], voice[start:end])]
    )
    assert len(ducked) == len(voice)
    assert max(abs(v) for v in ducked) < 32760
    assert (tmp_path / "narration.wav").read_bytes() == original
    assert (tmp_path / "soundtrack.wav").stat().st_size > 0


@pytest.mark.parametrize("preset", ["editorial", "comic", "minimal", "kinetic"])
def test_real_scene_encoder(tmp_path, preset):
    options = VisualOptions(preset=preset)
    config = dict(
        visual=options.model_dump(), style=apply_presentation({}, options), image_files=[]
    )
    plan = build_plan(config, "Chữ Việt có dấu", [(0, 1)], 240, 426)
    export(plan, tmp_path, 1)
    reader = imageio_ffmpeg.read_frames(str(tmp_path / "motion.mp4"))
    metadata = next(reader)
    first = next(reader)
    last = first
    for frame in reader:
        last = frame
    assert metadata["size"] == (240, 426)
    assert abs(metadata["duration"] - 1) < 0.1
    assert last != first


def test_full_production_pipeline_with_real_scene_and_audio_engines(client, monkeypatch, narration):
    job_id, digest = approved_script(client)
    response = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": digest,
            "visual": {"preset": "editorial", "layout": "mix"},
            "music": {"track": "pulse", "ducking": True},
        },
    )
    assert response.status_code == 200, response.text
    job = response.json()

    def speech(text, voice, directory, index, **kwargs):
        narration(directory / "speech.wav", 2)
        return "speech.wav", 2

    result = render_video(
        job_id,
        job["package"],
        job["render_config"],
        lambda message: None,
        adapters=MediaAdapters(synthesize=speech),
    )
    directory = Settings().artifact_dir / job_id / result["run_id"]
    assert result["music"]["mixed"]
    assert result["presentation"]["preset"] == "editorial"
    assert result["duration"] == pytest.approx(2, abs=0.1)
    assert result["speech"]["segments"][0]["duration"] == 2
    assert json.loads((directory / "scene-plan.json").read_text())["version"] == 1
    assert (directory / "soundtrack.wav").is_file()
    assert (directory / "video.mp4").is_file()


def test_missing_or_modified_music_fails_without_overwriting_narration(tmp_path, narration):
    narration(tmp_path / "narration.wav")
    from app.infrastructure.media.probe import MediaFailure

    with pytest.raises(MediaFailure):
        mix_audio(tmp_path, dict(music_file="input-music", music_sha256="0" * 64), 4)


def test_worker_checkpoints_and_download_of_mixed_video(client, monkeypatch, narration):
    from app.worker import process_one

    job_id, digest = approved_script(client)
    queued = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": digest,
            "visual": {"preset": "comic"},
            "music": {"track": "ambient"},
        },
    )
    assert queued.status_code == 200

    def speech(text, voice, directory, index, **kwargs):
        narration(directory / "speech.wav", 2)
        return "speech.wav", 2

    def renderer(*args, **kwargs):
        return render_video(*args, **kwargs, adapters=MediaAdapters(synthesize=speech))

    monkeypatch.setattr("app.worker.render_video", renderer)
    assert process_one(client.app.state.sessions)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "awaiting_video_review", job["error"]
    assert job["video"]["motion"] == "scene_components"
    for artifact in ("audio", "soundtrack", "video"):
        response = client.get(f"/api/jobs/{job_id}/artifacts/{artifact}")
        assert response.status_code == 200
        assert len(response.content) > 100
    quality = client.get(f"/api/jobs/{job_id}/quality").json()
    assert any(r["step"] == "audio_mix" for r in quality["runs"])


@pytest.mark.parametrize("with_clip", [False, True])
def test_scene_renderer_cancellation_reaps_encoder(tmp_path, with_clip):
    import subprocess
    import sys
    import time

    import psutil

    from app.pipeline.supervisor import stop_process

    options = VisualOptions(preset="editorial")
    config = dict(
        visual=options.model_dump(), style=apply_presentation({}, options), image_files=[]
    )
    if with_clip:
        from app.infrastructure.media.commands import run_command

        run_command(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x180:rate=24",
                "-t",
                "0.5",
                "-c:v",
                "libx264",
                "-threads",
                "1",
                "-f",
                "mp4",
                str(tmp_path / "input-clip"),
            ]
        )
        config["video_file"] = "input-clip"
    required_children = 2 if with_clip else 1
    plan = build_plan(config, "Cancellation fixture", [(0, 600)], 720, 1280)
    path = tmp_path / "scene-plan.json"
    path.write_text(json.dumps(plan))
    process = subprocess.Popen(
        [sys.executable, "-m", "app.infrastructure.media.scenes", str(path), "1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    children = []
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and process.poll() is None:
            children = psutil.Process(process.pid).children(recursive=True)
            if len(children) >= required_children:
                break
            time.sleep(0.02)
        assert len(children) >= required_children, (
            "Real encoder/decoder must start before cancellation"
        )
        stop_process(process)
        assert process.poll() is not None
        assert all(not p.is_running() or p.status() == psutil.STATUS_ZOMBIE for p in children)
    finally:
        if process.poll() is None:
            stop_process(process)


def test_scene_renderer_loops_real_clip(tmp_path):
    from app.infrastructure.media.commands import run_command

    source = tmp_path / "input-clip"
    run_command(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=24",
            "-t",
            "0.5",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-f",
            "mp4",
            str(source),
        ]
    )
    options = VisualOptions(preset="kinetic")
    config = dict(
        visual=options.model_dump(),
        style=apply_presentation({}, options),
        image_files=[],
        video_file="input-clip",
        video_fit="pad",
    )
    plan = build_plan(config, "Clip loop", [(0, 1.5)], 240, 426)
    export(plan, tmp_path, 1)
    reader = imageio_ffmpeg.read_frames(str(tmp_path / "motion.mp4"))
    metadata = next(reader)
    assert metadata["duration"] == pytest.approx(1.5, abs=0.1)
    assert sum(1 for _ in reader) == 36


def test_command_timeout_stops_scene_renderer_and_descendants(tmp_path):
    import time
    from concurrent.futures import ThreadPoolExecutor

    import psutil

    from app.contracts.errors import VideoFailure
    from app.infrastructure.media.commands import run_command

    options = VisualOptions(preset="editorial")
    config = dict(
        visual=options.model_dump(), style=apply_presentation({}, options), image_files=[]
    )
    path = tmp_path / "timeout-plan.json"
    path.write_text(json.dumps(build_plan(config, "Timeout", [(0, 600)], 720, 1280)))
    import sys

    descendants = []
    with ThreadPoolExecutor() as executor:
        future = executor.submit(
            run_command,
            [sys.executable, "-m", "app.infrastructure.media.scenes", str(path), "1"],
            timeout=1,
        )
        deadline = time.monotonic() + 0.8
        while time.monotonic() < deadline and not future.done():
            for child in psutil.Process().children():
                try:
                    if str(path) in child.cmdline():
                        descendants = child.children(recursive=True)
                        if descendants:
                            break
                except psutil.NoSuchProcess:
                    pass
            if descendants:
                break
            time.sleep(0.01)
        assert descendants, "Real encoder must start before timeout"
        with pytest.raises(VideoFailure):
            future.result(timeout=10)
    assert all(not p.is_running() or p.status() == psutil.STATUS_ZOMBIE for p in descendants)
