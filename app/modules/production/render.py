"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import hashlib
import json
from dataclasses import dataclass
from typing import Callable

import imageio_ffmpeg

from app.contracts.captions import split_captions, timestamp
from app.contracts.content import content_hash, content_text
from app.contracts.errors import VideoFailure
from app.infrastructure.media.artifacts import artifact_directory
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.encoding import encode_video, inspect_video
from app.infrastructure.media.frames import make_frame
from app.infrastructure.media.speech import synthesize
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
    captions = split_captions(text)
    if not captions:
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
    elapsed = 0.0
    for index, caption in enumerate(captions):
        progress(f"Voice and visuals {index + 1}/{len(captions)}")
        checkpoint("voice", "start")
        filename, duration = synthesize(caption, config["voice"], directory, index)
        checkpoint(
            "voice",
            "end",
            {
                "filename": filename,
                "duration": duration,
                "sha256": hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
            },
            audio_checks(directory / filename),
        )
        audios.append(f"file '{filename}'")
        checkpoint("visuals", "start")
        frame = make_frame(directory, config, package["title"], caption, index, len(captions))
        checkpoint(
            "visuals",
            "end",
            {
                "filename": frame,
                "sha256": hashlib.sha256((directory / frame).read_bytes()).hexdigest(),
            },
        )
        frames.extend([f"file '{frame}'", f"duration {duration:.6f}"])
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
    checkpoint("audio", "end", {"duration": elapsed}, audio_evaluations)
    if has_blocker(audio_evaluations):
        raise VideoFailure("Giọng đọc bị im lặng hoặc clipping. Xem tab Chất lượng.")
    checkpoint("render", "start")
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
        "motion": style["motion"] if config["image_files"] else "static",
        "voice": config["voice"],
        "visuals": "uploaded_images" if config["image_files"] else "text_cards",
        "audio_checked": True,
        "video_checked": True,
    }
    result["quality"] = {"subtitle_repairs": repairs, "sample_times": sample_times}
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
