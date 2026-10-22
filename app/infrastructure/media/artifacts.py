"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import base64
import io
from uuid import UUID, uuid4

from PIL import Image, ImageOps

from app.config import Settings
from app.contracts.errors import VideoFailure
from app.services.styles import choose_style


def artifact_directory(job_id, run_id):
    return Settings().artifact_dir.resolve() / str(UUID(job_id)) / str(UUID(run_id))


def prepare_render(job_id, options, package=None, *, session=None):
    config = options.model_dump(exclude={"images"})
    config["style"] = choose_style(package or {"branch": "novel"}, session=session)
    config["run_id"] = str(uuid4())
    directory = artifact_directory(job_id, config["run_id"])
    directory.mkdir(parents=True, exist_ok=False)
    config["image_files"] = []
    for i, encoded in enumerate(options.images):
        try:
            raw = base64.b64decode(encoded, validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > 20_000_000:
                    raise ValueError("Image too large")
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((1920, 1920))
                filename = f"input-{i:02}.png"
                image.save(directory / filename)
                config["image_files"].append(filename)
        except (ValueError, OSError, Image.DecompressionBombError) as exc:
            raise VideoFailure("Ảnh không hợp lệ hoặc vượt giới hạn 20 megapixel.") from exc
    return config
