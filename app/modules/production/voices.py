"""Expose provider availability without exposing credentials or requiring network calls."""

import os
from dataclasses import asdict

from app.contracts.voices import VOICES


def voice_catalog(settings):
    items = []
    for voice in VOICES:
        available = voice.provider == "edge" or (voice.provider == "windows" and os.name == "nt")
        reason = "" if available else "Chỉ dùng trên Windows có giọng tương ứng."
        items.append({**asdict(voice), "available": available, "reason": reason})
    return {
        "voices": items,
        "default_voice": "vi-VN-HoaiMyNeural",
        "availability_note": "Đã cấu hình không đồng nghĩa kết nối/quota đã được xác minh.",
    }


def preview_speech(payload, settings):
    import shutil
    import tempfile
    from pathlib import Path

    from app.contracts.errors import VideoFailure
    from app.infrastructure.local_lock import LocalBusy, exclusive_lock
    from app.infrastructure.media.probe import MediaFailure
    from app.infrastructure.media.speech import synthesize
    from app.infrastructure.media.storage import LocalMediaStorage
    from app.modules.errors import ApplicationError

    storage = LocalMediaStorage(settings)
    preview_root = storage.root / "voice-previews"
    preview_root.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(dir=preview_root))
    try:
        with exclusive_lock(storage.root / ".voice-preview.lock"):
            storage.ensure_capacity(10_000_000)
            filename, _ = synthesize(
                payload.text,
                payload.voice,
                directory,
                0,
                rate=payload.speech_rate,
                settings=settings,
            )
        return directory / filename
    except (VideoFailure, MediaFailure, LocalBusy) as exc:
        shutil.rmtree(directory)
        raise ApplicationError(429 if isinstance(exc, LocalBusy) else 422, str(exc)) from exc
    except BaseException:
        shutil.rmtree(directory)
        raise
