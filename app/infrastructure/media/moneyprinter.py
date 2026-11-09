"""A narrow subprocess adapter: real MPT in a separate venv, no app namespace collision."""

import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import imageio_ffmpeg

from app.contracts.errors import VideoFailure
from app.infrastructure.media.commands import run_command
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.storage import LocalMediaStorage

ROOT = Path(__file__).resolve().parents[3] / "integrations" / "moneyprinter-turbo"
BRIDGE = ROOT / "bridge.py"


def runtime_python(settings):
    return settings.mpt_python or ROOT / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )


def invoke(settings, directory, payload):
    executable = runtime_python(settings)
    if not executable.is_file():
        raise MediaFailure(
            "Chưa cài MPT runtime. Chạy uv sync "
            "--project integrations/moneyprinter-turbo --frozen --no-dev."
        )
    request = directory / "request.json"
    request.write_text(
        json.dumps(
            {
                "home": str(settings.mpt_dir.resolve()),
                "ffmpeg": imageio_ffmpeg.get_ffmpeg_exe(),
                **payload,
            }
        )
    )
    request.chmod(0o600)
    try:
        result = run_command(
            [str(executable), "-I", str(BRIDGE), str(request)], cwd=directory, timeout=600
        )
        # MoviePy can emit progress text; the bridge's final line is its JSON result.
        return json.loads(result.stdout.decode().strip().splitlines()[-1])
    except (VideoFailure, ValueError, IndexError) as exc:
        raise MediaFailure(
            "MPT chưa chuẩn bị được footage. Kiểm tra API key, mạng và từ khóa; "
            "không có clip giả thay thế."
        ) from exc
    finally:
        request.unlink(missing_ok=True)


def doctor(settings):
    with TemporaryDirectory(prefix="mpt-doctor-") as temporary:
        return invoke(settings, Path(temporary), {"command": "doctor"})


@contextmanager
def prepare(settings, payload):
    settings.mpt_dir.mkdir(parents=True, exist_ok=True)
    storage = LocalMediaStorage(settings.model_copy(update={"artifact_dir": settings.mpt_dir}))
    storage.ensure_capacity(500_000_000)
    run_id = str(uuid4())
    try:
        with TemporaryDirectory(prefix="prepare-", dir=settings.mpt_dir) as temporary:
            directory = Path(temporary)
            output = directory / "background.mp4"
            result = invoke(
                settings,
                directory,
                {"command": "prepare", "run_id": run_id, "output": str(output), **payload},
            )
            if not output.is_file() or output.stat().st_size > min(
                settings.media_upload_max_bytes, 100_000_000
            ):
                raise MediaFailure("Footage MPT thiếu hoặc vượt giới hạn 100 MB.")
            yield output, result
    finally:
        # Keep MPT's bounded search cache; discard the run's raw download copies.
        shutil.rmtree(settings.mpt_dir / "storage" / "tasks" / run_id, ignore_errors=True)
