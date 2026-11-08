"""Offline E2E worker: real claim/pipeline/render; only speech is synthetic PCM.

This does not exercise the production supervisor or validate English pronunciation.
Explicit isolated-directory opt-in prevents accidentally processing the user's DB.
"""

import array
import logging
import math
import os
import time
import wave
from functools import partial
from pathlib import Path

from app.config import Settings
from app.db import make_engine, make_sessions
from app.modules.production.render import MediaAdapters, render_video
from app.pipeline.lifecycle import claim_one
from app.pipeline.runner import PipelineDependencies, execute_job
from app.services.preflight import preflight


def synthetic_speech(text, voice, directory, index, rate=0):
    """Audible fixture tone, explicitly not TTS; pace scales with script length."""
    if voice != "en-US-AriaNeural":
        raise ValueError(f"Expected the English voice to reach the worker, got {voice}")
    seconds = max(2.0, len(text.split()) / 3)
    sample_rate = 22050
    values = array.array(
        "h",
        (
            round(5000 * math.sin(2 * math.pi * 220 * index / sample_rate))
            for index in range(round(seconds * sample_rate))
        ),
    )
    if os.sys.byteorder == "big":
        values.byteswap()
    filename = f"fixture-speech-{index:04}.wav"
    with wave.open(str(directory / filename), "wb") as output:
        output.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        output.writeframes(values.tobytes())
    return filename, len(values) / sample_rate


def forbid_external_provider(*args, **kwargs):
    raise AssertionError("Offline IELTS baseline must not call crawling or AI providers")


def main():
    logging.basicConfig(level=logging.INFO)
    isolated = os.environ.get("IELTS_E2E_ISOLATED_DIRECTORY")
    if not isolated:
        raise RuntimeError("This fixture worker requires an explicitly isolated test directory")
    root = Path(isolated).resolve()
    settings = Settings(_env_file=None)
    if settings.database_url != f"sqlite:///{root / 'studio.db'}":
        raise RuntimeError("Fixture database does not match the isolated test directory")
    if settings.artifact_dir.resolve() != root / "artifacts":
        raise RuntimeError("Fixture artifacts do not match the isolated test directory")
    engine = make_engine(settings.database_url)
    sessions = make_sessions(engine)
    dependencies = PipelineDependencies(
        import_url=forbid_external_provider,
        analyse=forbid_external_provider,
        preflight=preflight,
        render_video=partial(render_video, adapters=MediaAdapters(synthesize=synthetic_speech)),
    )
    try:
        while True:
            job_id = claim_one(sessions)
            if job_id is None:
                time.sleep(0.1)
            else:
                execute_job(sessions, job_id, dependencies)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
