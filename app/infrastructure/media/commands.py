"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import os
import subprocess
from pathlib import Path

from app.contracts.errors import VideoFailure
from app.infrastructure.processes import stop_process


def run_command(args, cwd=None, timeout=300):
    try:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except BaseException:
            stop_process(process)
            raise
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
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
