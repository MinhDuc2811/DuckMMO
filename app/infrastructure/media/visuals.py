"""Resolve media references and compose FFmpeg visual inputs without owning jobs/TTS."""

import os
import shutil

from PIL import Image, ImageOps

from app.db import MediaAsset
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.storage import file_digest


def pin_assets(session, storage, job_id, options, directory, config):
    ids = options.image_asset_ids or ([options.video_asset_id] if options.video_asset_id else [])
    for index, asset_id in enumerate(ids):
        asset = session.get(MediaAsset, str(asset_id)) if session is not None else None
        expected_kind = "video" if options.video_asset_id else "image"
        if asset is None or asset.job_id != str(job_id) or asset.kind != expected_kind:
            raise MediaFailure("File nguồn không thuộc nội dung này hoặc không đúng loại.")
        source = storage.verify(asset)
        storage.ensure_capacity(asset.size if expected_kind == "video" else 12_000_000)
        if expected_kind == "video":
            destination = directory / "input-clip"
            try:
                os.link(source, destination)
            except OSError:
                shutil.copyfile(source, destination)
            config["video_file"] = destination.name
            config["video_sha256"] = asset.sha256
        else:
            filename = f"asset-{index:02}.png"
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((1920, 1920))
                image.save(directory / filename)
            config["image_files"].append(filename)


def input_arguments(config, directory, threads):
    if config.get("motion_file"):
        return ["-i", "motion.mp4"]
    if config.get("video_file"):
        source = directory / "input-clip"
        if not source.is_file() or file_digest(source) != config["video_sha256"]:
            raise MediaFailure("Clip của lượt dựng bị thiếu hoặc đã đổi.")
        return [
            "-stream_loop",
            "-1",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,matroska,webm",
            "-threads",
            str(threads),
            "-i",
            source.name,
        ]
    return ["-f", "concat", "-safe", "1", "-i", "frames.ffconcat"]


def visual_filters(config, style, width, height):
    filters = "fps=24"
    if config.get("motion_file"):
        return filters + ",ass=subtitles.ass"
    if config.get("video_file"):
        if config["video_fit"] == "crop":
            filters += (
                f",scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}"
            )
        else:
            filters += (
                f",scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
        filters += ",setsar=1"
    elif config["image_files"] and style["motion"] == "slow_zoom":
        filters += (
            f",zoompan=z='min(1+on*0.000015,1.06)':"
            f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=24"
        )
    return filters + ",ass=subtitles.ass"
