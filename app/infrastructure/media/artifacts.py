"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import base64
import io
import shutil
from uuid import UUID, uuid4

from PIL import Image, ImageOps

from app.config import Settings
from app.contracts.errors import VideoFailure
from app.infrastructure.local_lock import LocalBusy, exclusive_lock
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.storage import LocalMediaStorage
from app.infrastructure.media.visuals import pin_assets
from app.services.styles import choose_style


def artifact_directory(job_id, run_id):
    return Settings().artifact_dir.resolve() / str(UUID(job_id)) / str(UUID(run_id))


def prepare_render(job_id, options, package=None, *, session=None):
    config = options.model_dump(mode="json", exclude={"images"})
    config["style"] = choose_style(package or {"branch": "novel"}, session=session)
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
