"""Bounded local music preparation and narration-first mixing, without paid providers."""

import array
import math
import os
import shutil
import wave

import imageio_ffmpeg

from app.db import MediaAsset
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.storage import file_digest


def original_track(path, track):
    """Eight-second original synthesized loops; no downloaded/licensed recordings."""
    rate, duration = 22050, 8
    notes = (130.81, 164.81, 196.0) if track == "ambient" else (146.83, 174.61, 220.0)
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        for second in range(duration):
            samples = array.array("h")
            for i in range(rate):
                t = second + i / rate
                envelope = min(1, t / 0.4, (duration - t) / 0.4)
                pulse = 0.65 + 0.35 * math.cos(2 * math.pi * 2 * t) if track == "pulse" else 1
                value = sum(math.sin(2 * math.pi * f * t) for f in notes) / len(notes)
                samples.append(int(7000 * envelope * pulse * value))
            if os.sys.byteorder == "big":
                samples.byteswap()
            output.writeframes(samples.tobytes())


def pin_music(session, storage, job_id, options, directory, config):
    if not (options.asset_id or options.track):
        return
    destination = directory / "input-music"
    if options.asset_id:
        asset = session.get(MediaAsset, str(options.asset_id)) if session is not None else None
        if not asset or asset.job_id != str(job_id) or asset.kind != "audio":
            raise MediaFailure("Nhạc không thuộc nội dung này hoặc không đúng loại audio.")
        if options.start_seconds >= asset.details["duration"] - 0.2:
            raise MediaFailure(
                "Điểm bắt đầu nhạc phải trước khi bài nhạc kết thúc ít nhất 0,2 giây."
            )
        source = storage.verify(asset)
        storage.ensure_capacity(asset.size)
        try:
            os.link(source, destination)
        except OSError:
            shutil.copyfile(source, destination)
        duration = asset.details["duration"]
    else:
        duration = 8
        if options.start_seconds >= 7.8:
            raise MediaFailure("Nhạc có sẵn dài 8 giây; chọn điểm bắt đầu dưới 7,8 giây.")
        storage.ensure_capacity(1_000_000)
        original_track(destination, options.track)
    config["music_file"] = destination.name
    config["music_sha256"] = file_digest(destination)
    config["music_duration"] = duration


def mix_audio(directory, config, duration, *, run_command=run_command):
    """Preserve narration.wav; loop a <=60s crossfaded bed and duck only the bed."""
    if not config.get("music_file"):
        return "narration.wav"
    source = directory / "input-music"
    if not source.is_file() or file_digest(source) != config["music_sha256"]:
        raise MediaFailure("Nhạc của lượt dựng bị thiếu hoặc đã đổi.")
    music = config["music"]
    length = min(60, config["music_duration"] - music["start_seconds"])
    seam = min(0.5, length / 4)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # Rotate the loop: middle + crossfade(tail, head), avoiding a hard wrap.
    loop = (
        f"[0:a]atrim=duration={length},asetpts=PTS-STARTPTS,"
        "aresample=22050,aformat=sample_fmts=fltp:channel_layouts=mono,"
        "loudnorm=I=-23:TP=-3:LRA=7,asplit=3[body][tail][head];"
        f"[body]atrim=start={seam}:end={length - seam},asetpts=PTS-STARTPTS[b];"
        f"[tail]atrim=start={length - seam},asetpts=PTS-STARTPTS[t];"
        f"[head]atrim=end={seam},asetpts=PTS-STARTPTS[h];"
        f"[t][h]acrossfade=d={seam}:c1=tri:c2=tri[j];"
        "[b][j]concat=n=2:v=0:a=1[out]"
    )
    run_command(
        [
            ffmpeg,
            "-y",
            "-nostdin",
            "-protocol_whitelist",
            "file,pipe",
            "-ss",
            str(music["start_seconds"]),
            "-i",
            source.name,
            "-filter_complex_threads",
            "1",
            "-filter_complex",
            loop,
            "-map",
            "[out]",
            "-ar",
            "22050",
            "-ac",
            "1",
            "music-loop.wav",
        ],
        cwd=directory,
    )
    fades = min(1.0, duration / 4)
    filters = (
        f"[1:a]volume={music['volume']},afade=t=in:d={fades},"
        f"afade=t=out:st={max(0, duration - fades)}:d={fades}[bed];"
    )
    if music["ducking"]:
        filters += (
            "[0:a]asplit=2[voice][side];"
            "[bed][side]sidechaincompress=threshold=0.025:ratio=8:attack=20:release=350[ducked];"
            "[voice][ducked]amix=inputs=2:duration=first:normalize=0,"
        )
    else:
        filters += "[0:a][bed]amix=inputs=2:duration=first:normalize=0,"
    filters += "alimiter=limit=0.95:level=0:latency=1[out]"
    run_command(
        [
            ffmpeg,
            "-y",
            "-nostdin",
            "-i",
            "narration.wav",
            "-stream_loop",
            "-1",
            "-i",
            "music-loop.wav",
            "-filter_complex_threads",
            "1",
            "-filter_complex",
            filters,
            "-map",
            "[out]",
            "-t",
            str(duration),
            "-ar",
            "22050",
            "-ac",
            "1",
            "soundtrack.wav",
        ],
        cwd=directory,
    )
    return "soundtrack.wav"
