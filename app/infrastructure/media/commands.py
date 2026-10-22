"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import os
import subprocess
from pathlib import Path

from app.contracts.errors import VideoFailure


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
