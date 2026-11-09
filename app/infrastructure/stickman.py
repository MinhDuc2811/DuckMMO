"""Pinned upstream CLI and isolated filesystem adapter; no generation API calls."""

import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import imageio_ffmpeg

from app.contracts.errors import VideoFailure
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.storage import LocalMediaStorage, file_digest

VENDOR = Path(__file__).resolve().parents[2] / "integrations" / "stickman-video-director"
TOP_FIELDS = {
    "version",
    "style",
    "width",
    "height",
    "fps",
    "voice",
    "captions",
    "shots",
    "sfx",
    "music",
    "captionSize",
    "grid",
    "television",
    "ambience",
    "dialogue",
    "audio_cuts",
    "opening_audio_override",
}


def run_cli(command, *args, directory=None):
    if directory is None:
        with TemporaryDirectory(prefix="stickman-runtime-") as temporary:
            return run_cli(command, *args, directory=Path(temporary))
    node, ffprobe = shutil.which("node"), shutil.which("ffprobe")
    if not node or not ffprobe:
        raise MediaFailure("Cần Node.js >=20 và FFmpeg/FFprobe. Xem hướng dẫn Stickman Studio.")
    try:
        result = run_command(
            [
                node,
                str(VENDOR / "bridge.mjs"),
                imageio_ffmpeg.get_ffmpeg_exe(),
                ffprobe,
                command,
                *map(str, args),
            ],
            cwd=directory or VENDOR,
            timeout=600,
        )
    except VideoFailure as exc:
        log = (directory or VENDOR) / "engine-error.log"
        detail = log.read_text(errors="replace")[-1800:] if log.is_file() else str(exc)
        raise MediaFailure("Stickman runtime: " + detail) from exc
    text = result.stdout.decode()
    # Renderer emits NDJSON progress before its final formatted JSON report.
    decoder = json.JSONDecoder()
    position, last = 0, None
    while position < len(text):
        if text[position].isspace():
            position += 1
            continue
        try:
            last, length = decoder.raw_decode(text[position:])
        except ValueError as exc:
            raise MediaFailure("Runtime trả report không hợp lệ.") from exc
        position += length
    return last


class StickmanStore:
    def __init__(self, settings):
        self.root = settings.stickman_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.media_settings = settings.model_copy(
            update={
                "artifact_dir": self.root,
                "media_storage_max_bytes": min(settings.media_storage_max_bytes, 1_000_000_000),
            }
        )
        self.storage = LocalMediaStorage(self.media_settings)

    def project(self, project_id):
        path = self.root / str(UUID(str(project_id)))
        if path.is_symlink() or not path.is_dir():
            raise FileNotFoundError("Không tìm thấy dự án Stickman.")
        return path

    def read(self, project_id):
        base = self.project(project_id)
        metadata = json.loads((base / "studio.json").read_text())
        return metadata

    def save(self, base, name, value):
        temporary = base / (name + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(base / name)

    def check_project(self, project_id, project):
        base = self.project(project_id)
        if len(json.dumps(project, allow_nan=False).encode()) > 256_000:
            raise MediaFailure("Timeline tối đa 256 KB.")
        if set(project) - TOP_FIELDS:
            raise MediaFailure("Timeline có trường không được hỗ trợ trong tích hợp local.")
        if project.get("version") != 1 or project.get("style") not in ("B1", "B2", "B3", "B4"):
            raise MediaFailure("Chọn version 1 và style B1–B4.")
        width, height, fps = (project.get(k, 0) for k in ("width", "height", "fps"))
        if not all(type(v) is int for v in (width, height, fps)) or not (
            256 <= width <= 1280
            and 256 <= height <= 1280
            and width * height <= 921600
            and width % 2 == height % 2 == 0
            and 12 <= fps <= 30
        ):
            raise MediaFailure("Tối đa 720×1280 / 1280×720 và 12–30 fps, kích thước chẵn.")
        assets = {a["path"]: a for a in self.read(project_id)["assets"]}
        visited = 0

        def walk(value, depth=0):
            nonlocal visited
            visited += 1
            if depth > 20 or visited > 25000:
                raise MediaFailure("Timeline quá phức tạp.")
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "path":
                        if (
                            not isinstance(child, str)
                            or not re.fullmatch(
                                r"inputs/[a-f0-9]{64}\.(wav|mp3|flac|ogg|m4a|png|jpg)", child
                            )
                            or child not in assets
                        ):
                            raise MediaFailure("Chỉ dùng đường dẫn file đã upload trong dự án này.")
                        file = base / child
                        if (
                            file.is_symlink()
                            or not file.resolve().is_relative_to(base.resolve())
                            or file_digest(file) != assets[child]["sha256"]
                        ):
                            raise MediaFailure("File nguồn thiếu hoặc đã thay đổi.")
                    walk(child, depth + 1)
            elif isinstance(value, list):
                for child in value:
                    walk(child, depth + 1)

        walk(project)
        if not isinstance(project.get("voice"), dict):
            raise MediaFailure("Lời đọc phải có đối tượng voice.path hợp lệ.")
        voice = assets.get(project["voice"].get("path"))
        if not voice or voice["kind"] != "audio":
            raise MediaFailure("Chọn file lời đọc đã upload; không tự sinh hoặc thay giọng.")
        if voice["duration"] > 120:
            raise MediaFailure("Tích hợp local hiện giới hạn lời đọc 120 giây.")


def director_kit(payload):
    manifest = json.loads((VENDOR / "UPSTREAM.json").read_text())
    brief = (
        f"Use Director Mode, {payload.style}, {payload.ratio}, {payload.seconds} seconds.\n"
        "Read SKILL.md and the selected style reference. Produce a director treatment first; "
        "do not claim generated footage or a completed video.\n\nSource:\n" + payload.source
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("director-request.md", brief)
        archive.writestr("UPSTREAM.json", json.dumps(manifest, indent=2))
        for entry in manifest["files"]:
            local = entry["local_path"]
            if local == "SKILL.md" or local == "LICENSE" or local.startswith("references/"):
                archive.write(VENDOR / local, local)
    return output.getvalue()
