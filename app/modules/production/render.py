"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import imageio_ffmpeg

from app.config import Settings
from app.contracts.captions import split_captions, timestamp
from app.contracts.content import content_hash, content_text
from app.contracts.errors import VideoFailure
from app.contracts.speech import speech_segments
from app.contracts.voices import get_voice
from app.infrastructure.media.artifacts import artifact_directory
from app.infrastructure.media.audio import long_pauses, trim_boundary_silence
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.encoding import encode_video, inspect_video
from app.infrastructure.media.frames import make_frame
from app.infrastructure.media.music import mix_audio
from app.infrastructure.media.scenes import build_plan
from app.infrastructure.media.speech import synthesize
from app.infrastructure.media.storage import LocalMediaStorage
from app.infrastructure.media.visuals import input_arguments
from app.modules.production.subtitles import resolve_subtitles
from app.quality.evaluators import audio_checks, check, has_blocker
from app.services.styles import choose_style


@dataclass(frozen=True)
class MediaAdapters:
    synthesize: Callable = synthesize
    make_frame: Callable = make_frame
    run_command: Callable = run_command


def render_video(job_id, package, config, progress, checkpoint=None, *, adapters=None):
    adapters = adapters or MediaAdapters()
    synthesize = adapters.synthesize
    make_frame = adapters.make_frame
    run_command = adapters.run_command
    checkpoint = checkpoint or (lambda *args: None)
    directory = artifact_directory(job_id, config["run_id"])
    text = content_text(package)
    if content_hash(package) != config["expected_content_hash"]:
        raise VideoFailure("Kịch bản đã thay đổi. Hãy duyệt và dựng lại từ phiên bản mới.")
    if len(text) > 30000:
        raise VideoFailure("Mỗi video tối đa 30.000 ký tự. Hãy rút gọn hoặc chia kịch bản.")
    voice_definition = get_voice(config["voice"])
    segments = speech_segments(
        text, voice_definition.max_characters, max_bytes=voice_definition.max_bytes
    )
    if not segments:
        raise VideoFailure("Kịch bản trống, không thể dựng video.")
    config = {**config, "style": config.get("style") or choose_style(package)}
    style = config["style"]
    checkpoint("storyboard", "start")
    checkpoint(
        "storyboard",
        "end",
        {"style": style, "image_count": len(config["image_files"])},
        [check("visual_relevance", "unknown", {"reason": "Requires human image review"})],
    )
    progress(f"Auto style: {style['name']} · v{style['catalog_version']}")
    if "failure" in style.get("sync_status", ""):
        progress("Style catalog: nguồn cập nhật lỗi; đang dùng thư viện đã lưu")
    elif style.get("sync_status") == "synced":
        progress("Style catalog: đã đồng bộ phiên bản mới nhất từ nguồn kết nối")
    frames, audios, subtitles, cues = [], [], [], []
    scene_timeline = []
    elapsed = 0.0
    settings = Settings()
    speech_timeline = []
    visual_groups = [split_captions(part) for part in segments]
    visual_total = sum(map(len, visual_groups))
    visual_offset = 0
    for index, caption in enumerate(segments):
        progress(f"Voice and visuals {index + 1}/{len(segments)}")
        checkpoint("voice", "start")
        if config.get("speech_rate", 0):
            filename, duration = synthesize(
                caption, config["voice"], directory, index, rate=config["speech_rate"]
            )
        else:
            filename, duration = synthesize(caption, config["voice"], directory, index)
        boundary = {"trimmed_start_seconds": 0, "trimmed_end_seconds": 0}
        if len(segments) > 1:
            boundary = trim_boundary_silence(
                directory / filename, trim_start=index > 0, trim_end=index < len(segments) - 1
            )
            duration = boundary["duration"]
        speech_timeline.append(
            {
                "index": index,
                "start": elapsed,
                "duration": duration,
                "text_characters": len(caption),
                **boundary,
            }
        )
        checkpoint(
            "voice",
            "end",
            {
                "filename": filename,
                "duration": duration,
                "boundary": boundary,
                "sha256": hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
            },
            audio_checks(directory / filename),
        )
        if elapsed + duration > settings.render_max_duration:
            raise VideoFailure(f"Video tối đa {settings.render_max_duration:g} giây.")
        audios.append(f"file '{filename}'")
        checkpoint("visuals", "start")
        if config.get("video_file"):
            scene_timeline.append((elapsed, duration, caption))
            checkpoint("visuals", "end", {"filename": config["video_file"]})
        else:
            visual_chunks = visual_groups[index]
            visual_weight = sum(len(part.split()) for part in visual_chunks)
            visual_files = []
            for visual_index, part in enumerate(visual_chunks):
                frame = make_frame(
                    directory,
                    config,
                    package["title"],
                    part,
                    visual_offset + visual_index,
                    visual_total,
                )
                part_duration = duration * len(part.split()) / visual_weight
                scene_timeline.append(
                    (
                        elapsed
                        + sum(
                            duration * len(p.split()) / visual_weight
                            for p in visual_chunks[:visual_index]
                        ),
                        part_duration,
                        part,
                    )
                )
                frames.extend([f"file '{frame}'", f"duration {part_duration:.6f}"])
                visual_files.append(frame)
            checkpoint("visuals", "end", {"filenames": visual_files})
            visual_offset += len(visual_chunks)
        phrases = split_captions(caption, limit=style["caption_chars"])
        weight = sum(len(phrase.split()) for phrase in phrases)
        start = elapsed
        for phrase_index, phrase in enumerate(phrases):
            end = (
                elapsed + duration
                if phrase_index == len(phrases) - 1
                else start + duration * len(phrase.split()) / weight
            )
            cues.append((start, end, phrase))
            subtitles.append(f"{len(cues)}\n{timestamp(start)} --> {timestamp(end)}\n{phrase}\n")
            start = end
        elapsed += duration
    if not config.get("video_file"):
        frames.append(f"file '{frame}'")
    (directory / "frames.ffconcat").write_text("\n".join(frames), encoding="utf-8")
    (directory / "audio.ffconcat").write_text("\n".join(audios), encoding="utf-8")
    (directory / "subtitles.srt").write_text("\n".join(subtitles), encoding="utf-8")
    (directory / "script.txt").write_text(text, encoding="utf-8")
    width, height = (720, 1280) if config["layout"] == "portrait" else (1280, 720)
    checkpoint("subtitles", "start")
    cues, style, repairs, evaluations = resolve_subtitles(
        directory, cues, style, elapsed, width, height, progress
    )
    checkpoint(
        "subtitles",
        "end",
        {"cue_count": len(cues), "repairs": repairs, "resolved_style": style},
        evaluations,
    )
    if has_blocker(evaluations):
        raise VideoFailure(
            "Phụ đề không đạt kiểm tra bố cục/timestamp sau 2 lần sửa. Xem tab Chất lượng."
        )
    checkpoint("audio", "start")
    progress("Combining narration")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    run_command(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            "audio.ffconcat",
            "-ar",
            "22050",
            "-ac",
            "1",
            "narration.wav",
        ],
        cwd=directory,
    )
    audio_evaluations = audio_checks(directory / "narration.wav")
    pauses = long_pauses(directory / "narration.wav")
    audio_evaluations.append(
        check(
            "audio_pauses",
            "warn" if pauses else "pass",
            {
                "spans": pauses,
                "threshold_seconds": 0.8,
                "limitation": "Pauses may be natural punctuation; human listening required",
            },
        )
    )
    checkpoint("audio", "end", {"duration": elapsed}, audio_evaluations)
    if has_blocker(audio_evaluations):
        raise VideoFailure("Giọng đọc bị im lặng hoặc clipping. Xem tab Chất lượng.")
    # Budget both intermediate motion/audio and final output before expensive work.
    LocalMediaStorage(settings).ensure_capacity(int(elapsed * 8_100_000) + 10_000_000)
    checkpoint("audio_mix", "start")
    config["audio_file"] = mix_audio(directory, config, elapsed, run_command=run_command)
    if config["audio_file"] != "narration.wav":
        mixed_checks = audio_checks(directory / config["audio_file"])
        checkpoint("audio_mix", "end", {"filename": config["audio_file"]}, mixed_checks)
        if has_blocker(mixed_checks):
            raise VideoFailure("Âm thanh trộn không đạt kiểm tra; xem tab Chất lượng.")
    else:
        checkpoint("audio_mix", "end", {"filename": "narration.wav"})
    checkpoint("render", "start")
    if config.get("visual", {}).get("preset", "auto") != "auto":
        input_arguments(config, directory, settings.ffmpeg_threads)  # verify pinned clip
        plan = build_plan(config, package["title"], scene_timeline, width, height)
        plan_path = directory / "scene-plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        progress("Rendering scene components")
        run_command(
            [
                sys.executable,
                "-m",
                "app.infrastructure.media.scenes",
                str(plan_path),
                str(settings.ffmpeg_threads),
            ],
            cwd=Path(__file__).resolve().parents[3],
            timeout=max(300, int(elapsed * 10)),
        )
        config["motion_file"] = "motion.mp4"
    progress("Encoding MP4")
    encode_video(directory, config, style, width, height, elapsed, run_command=run_command)
    checkpoint("render", "end", {"filename": "video.mp4"})
    checkpoint("qa", "start")
    progress("Checking video and audio")
    metadata, sample_times = inspect_video(directory, elapsed, run_command=run_command)
    result = {
        "run_id": config["run_id"],
        "content_hash": config["expected_content_hash"],
        "sha256": hashlib.sha256((directory / "video.mp4").read_bytes()).hexdigest(),
        "duration": metadata["duration"],
        "width": metadata["size"][0],
        "height": metadata["size"][1],
        "caption_count": len(cues),
        "style": style,
        "subtitle_timing": "phrase_duration_estimate",
        "motion": "scene_components"
        if config.get("motion_file")
        else "source"
        if config.get("video_file")
        else (style["motion"] if config["image_files"] else "static"),
        "voice": config["voice"],
        "visuals": "uploaded_video"
        if config.get("video_file")
        else ("uploaded_images" if config["image_files"] else "text_cards"),
        "audio_checked": True,
        "video_checked": True,
    }
    result["presentation"] = config.get("visual", {"preset": "auto"})
    result["music"] = {**config.get("music", {}), "mixed": bool(config.get("music_file"))}
    result["quality"] = {"subtitle_repairs": repairs, "sample_times": sample_times}
    result["speech"] = {
        "segmentation_version": 2,
        "segments": speech_timeline,
        "rate": config.get("speech_rate", 0),
        "provider": get_voice(config["voice"]).provider,
        "long_pauses": pauses,
    }
    (directory / "speech-timeline.json").write_text(
        json.dumps(result["speech"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    checkpoint(
        "qa",
        "end",
        {"sha256": result["sha256"], "sample_times": sample_times},
        [
            check("video_decode_samples", "pass", {"sample_times": sample_times}),
            check(
                "audio_video_duration",
                "pass",
                {"difference_seconds": abs(metadata["duration"] - elapsed)},
            ),
            check("black_frames", "unknown", {"reason": "No intent-aware black-frame detection"}),
        ],
    )
    (directory / "manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
