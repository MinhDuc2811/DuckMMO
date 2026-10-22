"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import asyncio
import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import wave
from pathlib import Path
from uuid import UUID, uuid4

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.config import Settings
from app.quality.evaluators import audio_checks, check, has_blocker, subtitle_checks
from app.services.local_lock import LocalBusy, exclusive_lock
from app.services.media_probe import MediaFailure
from app.services.media_storage import LocalMediaStorage, file_digest
from app.services.styles import choose_style, write_ass
from app.services.video_visuals import input_arguments, pin_assets, visual_filters


class VideoFailure(ValueError):
    pass


def content_text(package):
    return package.get("video_content") or "\n\n".join(s["narration"] for s in package["scenes"])


def content_hash(package):
    return hashlib.sha256(content_text(package).encode()).hexdigest()


def run_command(args, cwd=None, timeout=300):
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoFailure("Không chạy được bộ dựng hình/giọng đọc hoặc quá thời gian.") from exc
    if result.returncode:
        # Full diagnostics stay in this run's directory, not an opaque success placeholder.
        if cwd:
            Path(cwd, "engine-error.log").write_bytes(result.stderr)
        if b"No local voice installed" in result.stderr:
            raise VideoFailure("Máy chưa cài giọng đọc cho ngôn ngữ này. Hãy chọn giọng Edge TTS.")
        raise VideoFailure("Bộ dựng hình/giọng đọc báo lỗi. Xem nhật ký tác vụ để kiểm tra.")
    return result


def artifact_directory(job_id, run_id):
    return Settings().artifact_dir.resolve() / str(UUID(job_id)) / str(UUID(run_id))


def prepare_render(job_id, options, package=None, session=None):
    config = options.model_dump(mode="json", exclude={"images"})
    config["style"] = choose_style(package or {"branch": "novel"})
    config["run_id"] = str(uuid4())
    directory = artifact_directory(job_id, config["run_id"])
    directory.mkdir(parents=True, exist_ok=False)
    config["image_files"] = []
    storage = LocalMediaStorage(Settings())
    try:
        with exclusive_lock(storage.root / ".media.lock"):
            storage.ensure_capacity(len(options.images) * 12_000_000)
            pin_assets(session, storage, job_id, options, directory, config)
            for i, encoded in enumerate(options.images):
                raw = base64.b64decode(encoded, validate=True)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.width * image.height > 20_000_000:
                        raise ValueError("Image too large")
                    image = ImageOps.exif_transpose(image).convert("RGB")
                    image.thumbnail((1920, 1920))
                    filename = f"input-{i:02}.png"
                    image.save(directory / filename)
                    config["image_files"].append(filename)
        return config
    except (ValueError, OSError, Image.DecompressionBombError, LocalBusy) as exc:
        shutil.rmtree(directory)
        raise VideoFailure(
            str(exc)
            if isinstance(exc, (MediaFailure, LocalBusy))
            else "Ảnh không hợp lệ hoặc vượt giới hạn 20 megapixel."
        ) from exc


def split_captions(text, limit=105):
    words = text.split()
    chunks, current = [], ""
    for word in words:
        if current and len(current) + len(word) + 1 > limit:
            chunks.append(current)
            current = ""
        current = f"{current} {word}".strip()
        if current[-1:] in ".!?。！？" and len(current) > 30:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def synthesize(text, voice, directory, index):
    destination = directory / f"voice-{index:04}.wav"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if voice.startswith("local-"):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if os.name != "nt" or not shell:
            raise VideoFailure("Giọng trên máy cần Windows. Hãy chọn giọng Edge TTS.")
        text_path = directory / f"voice-{index:04}.txt"
        text_path.write_text(text, encoding="utf-8")
        language = "vi-VN" if voice == "local-vi" else "en-US"
        run_command(
            [
                shell,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(Path(__file__).with_name("sapi_tts.ps1").resolve()),
                "-TextPath",
                str(text_path),
                "-OutputPath",
                str(destination),
                "-Language",
                language,
            ],
            cwd=directory,
            timeout=60,
        )
    else:
        mp3 = directory / f"voice-{index:04}.mp3"
        try:
            asyncio.run(asyncio.wait_for(edge_tts.Communicate(text, voice).save(str(mp3)), 90))
        except Exception as exc:
            raise VideoFailure(
                "Không tạo được giọng Edge TTS. Kiểm tra mạng hoặc chọn giọng trên máy."
            ) from exc
        run_command(
            [ffmpeg, "-y", "-i", str(mp3), "-ar", "22050", "-ac", "1", str(destination)],
            cwd=directory,
        )
    with wave.open(str(destination)) as audio:
        duration = audio.getnframes() / audio.getframerate()
    if duration <= 0:
        raise VideoFailure("Giọng đọc tạo ra không có thời lượng.")
    return destination.name, duration


def font(size):
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, face, width):
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and draw.textlength(candidate, font=face) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def make_frame(directory, config, title, caption, index, total):
    width, height = (720, 1280) if config["layout"] == "portrait" else (1280, 720)
    style = config["style"]
    canvas = Image.new("RGB", (width, height), style["background"])
    draw = ImageDraw.Draw(canvas)
    files = config["image_files"]
    if files:
        with Image.open(directory / files[index % len(files)]) as image:
            background = ImageOps.fit(image.convert("RGB"), (width, height))
            canvas.paste(background)
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 100))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)
    pad = 54
    title_font = font(30 if width == 720 else 32)
    title_lines = wrap(draw, title, title_font, width - pad * 2)[:3]
    draw.multiline_text(
        (pad, 80 if height > 1000 else 45),
        "\n".join(title_lines),
        font=title_font,
        fill=style["accent"],
        stroke_width=2,
        stroke_fill="#101010",
        spacing=10,
    )
    filename = f"frame-{index:04}.png"
    canvas.save(directory / filename)
    return filename


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def render_video(job_id, package, config, progress, checkpoint=None):
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
    settings = Settings()
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
        if elapsed + duration > settings.render_max_duration:
            raise VideoFailure(f"Video tối đa {settings.render_max_duration:g} giây.")
        audios.append(f"file '{filename}'")
        checkpoint("visuals", "start")
        if config.get("video_file"):
            checkpoint("visuals", "end", {"filename": config["video_file"]})
        else:
            frame = make_frame(directory, config, package["title"], caption, index, len(captions))
            checkpoint(
                "visuals", "end", {"filename": frame, "sha256": file_digest(directory / frame)}
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
    if not config.get("video_file"):
        frames.append(f"file '{frame}'")
    (directory / "frames.ffconcat").write_text("\n".join(frames), encoding="utf-8")
    (directory / "audio.ffconcat").write_text("\n".join(audios), encoding="utf-8")
    (directory / "subtitles.srt").write_text("\n".join(subtitles), encoding="utf-8")
    (directory / "script.txt").write_text(text, encoding="utf-8")
    width, height = (720, 1280) if config["layout"] == "portrait" else (1280, 720)
    checkpoint("subtitles", "start")
    evaluations = subtitle_checks(cues, elapsed, style, width, height)
    repairs = 0
    while (
        any(e["dimension"] == "subtitle_layout" and e["outcome"] == "fail" for e in evaluations)
        and repairs < 2
    ):
        repairs += 1
        style = {
            **style,
            "font_size": max(32, style["font_size"] - 4),
            "caption_chars": max(24, style["caption_chars"] - 8),
        }
        repaired = []
        for start, end, phrase in cues:
            parts = split_captions(phrase, limit=style["caption_chars"])
            count = sum(len(part.split()) for part in parts)
            cursor = start
            for i, part in enumerate(parts):
                next_end = (
                    end
                    if i == len(parts) - 1
                    else cursor + (end - start) * len(part.split()) / count
                )
                repaired.append((cursor, next_end, part))
                cursor = next_end
        cues = repaired
        evaluations = subtitle_checks(cues, elapsed, style, width, height)
        progress(f"Subtitle layout repair {repairs}/2")
    write_ass(directory, cues, style, width, height)
    (directory / "subtitles.srt").write_text(
        "\n".join(
            f"{i + 1}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n"
            for i, (start, end, text) in enumerate(cues)
        ),
        encoding="utf-8",
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
    try:
        LocalMediaStorage(settings).ensure_capacity(int(elapsed * 4_000_000))
        visual_input = input_arguments(config, directory, settings.ffmpeg_threads)
    except MediaFailure as exc:
        raise VideoFailure(str(exc)) from exc
    filters = visual_filters(config, style, width, height)
    run_command(
        [
            ffmpeg,
            "-y",
            "-nostdin",
            "-filter_threads",
            str(settings.ffmpeg_threads),
            *visual_input,
            "-i",
            "narration.wav",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            filters,
            "-c:v",
            "libx264",
            "-threads",
            str(settings.ffmpeg_threads),
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-t",
            str(elapsed),
            "-fs",
            str(max(1_000_000, int(elapsed * 4_000_000))),
            "-movflags",
            "+faststart",
            "video.mp4",
        ],
        cwd=directory,
        timeout=max(300, int(elapsed * 3)),
    )
    checkpoint("render", "end", {"filename": "video.mp4"})
    checkpoint("qa", "start")
    progress("Checking video and audio")
    sample_times = sorted({0.0, max(0, elapsed / 2), max(0, elapsed - 0.25)})
    for sample_time in sample_times:
        run_command(
            [
                ffmpeg,
                "-v",
                "error",
                "-ss",
                str(sample_time),
                "-i",
                "video.mp4",
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-t",
                "0.2",
                "-f",
                "null",
                "-",
            ],
            cwd=directory,
        )
    run_command(
        [ffmpeg, "-y", "-ss", "0.5", "-i", "video.mp4", "-frames:v", "1", "poster.png"],
        cwd=directory,
    )
    reader = imageio_ffmpeg.read_frames(str(directory / "video.mp4"))
    try:
        metadata = next(reader)
    finally:
        reader.close()
    if abs(metadata["duration"] - elapsed) > 0.3:
        raise VideoFailure("Thời lượng video lệch giọng đọc. Không chuyển sang bước duyệt.")
    result = {
        "run_id": config["run_id"],
        "content_hash": config["expected_content_hash"],
        "sha256": file_digest(directory / "video.mp4"),
        "duration": metadata["duration"],
        "width": metadata["size"][0],
        "height": metadata["size"][1],
        "caption_count": len(cues),
        "style": style,
        "subtitle_timing": "phrase_duration_estimate",
        "motion": "source"
        if config.get("video_file")
        else (style["motion"] if config["image_files"] else "static"),
        "voice": config["voice"],
        "visuals": "uploaded_video"
        if config.get("video_file")
        else ("uploaded_images" if config["image_files"] else "text_cards"),
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
