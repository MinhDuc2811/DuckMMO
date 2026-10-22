"""Short previews reuse final scene and audio components, with bounded local resources."""

import shutil
import tempfile
import wave
from pathlib import Path

from app.contracts.errors import VideoFailure
from app.contracts.presentation import apply_presentation
from app.infrastructure.local_lock import LocalBusy, exclusive_lock
from app.infrastructure.media.music import mix_audio, pin_music
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.scenes import build_plan
from app.infrastructure.media.scenes import frames as render_frames
from app.infrastructure.media.storage import LocalMediaStorage
from app.modules.errors import ApplicationError
from app.modules.jobs.lookup import load_job
from app.modules.production.voices import preview_speech


def style_preview(options, settings):
    storage = LocalMediaStorage(settings)
    directory = None
    try:
        with exclusive_lock(storage.root / ".style-preview.lock"):
            storage.ensure_capacity(10_000_000)
            directory = Path(tempfile.mkdtemp(dir=storage.root))
            config = dict(
                visual=options.model_dump(), style=apply_presentation({}, options), image_files=[]
            )
            plan = build_plan(config, "Phong cách của bạn", [(0, 1), (1, 1)], 240, 426)
            plan["fps"] = 12
            frames = list(render_frames(plan, directory))
            path = directory / "style-preview.gif"
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=83, loop=0)
            return path
    except (MediaFailure, LocalBusy, OSError) as exc:
        if directory:
            shutil.rmtree(directory)
        raise ApplicationError(429 if isinstance(exc, LocalBusy) else 422, str(exc)) from exc


def audio_preview(job_id, payload, settings, *, session, music_only=False):
    load_job(session, job_id)
    storage = LocalMediaStorage(settings)
    directory = None
    try:
        with exclusive_lock(storage.root / ".audio-preview.lock"):
            # Resolve/validate the chosen music before calling an external speech provider.
            directory = Path(tempfile.mkdtemp(dir=storage.root))
            music = payload if music_only else payload.music
            config = {"music": music.model_dump(mode="json")}
            with exclusive_lock(storage.root / ".media.lock"):
                storage.ensure_capacity(30_000_000)
                pin_music(session, storage, job_id, music, directory, config)
            if music_only:
                if not config.get("music_file"):
                    raise ApplicationError(422, "Chọn một bài nhạc để nghe thử.")
                with wave.open(str(directory / "narration.wav"), "wb") as output:
                    output.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
                    for _ in range(8):
                        output.writeframes(bytes(22050 * 2))
            else:
                voice = preview_speech(payload, settings)
                try:
                    shutil.copyfile(voice, directory / "narration.wav")
                finally:
                    shutil.rmtree(voice.parent)
            with wave.open(str(directory / "narration.wav"), "rb") as source:
                duration = source.getnframes() / source.getframerate()
            filename = mix_audio(directory, config, duration)
            return directory / filename
    except (VideoFailure, MediaFailure, LocalBusy, OSError) as exc:
        if directory:
            shutil.rmtree(directory)
        raise ApplicationError(429 if isinstance(exc, LocalBusy) else 422, str(exc)) from exc
    except BaseException:
        if directory:
            shutil.rmtree(directory)
        raise
