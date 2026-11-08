"""Opt-in real en-GB synthesis. Network failure remains a failed test."""

import json
import shutil
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.config import Settings
from app.contracts.errors import VideoFailure
from app.infrastructure.media.audio import validate_pcm
from app.infrastructure.media.speech import synthesize
from test_suite.support.paths import PROJECT_ROOT


@pytest.mark.live_tts
@pytest.mark.parametrize("voice", ["en-GB-SoniaNeural", "en-GB-RyanNeural"])
def test_real_british_voice_sample(voice, tmp_path):
    run = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    evidence = PROJECT_ROOT / "test-results" / "lesson-card" / "live" / run
    evidence.mkdir(parents=True)
    text = (
        "Although online courses are convenient, some learners need face-to-face support. "
        "Self-paced learning allows you to review a difficult lesson at your own pace."
    )
    report = {
        "voice": voice,
        "locale": "en-GB",
        "live": True,
        "cached": False,
        "text": text,
        "pronunciation_review": "Human listening required",
    }
    failure = None
    try:
        filename, _ = synthesize(
            text, voice, tmp_path, 0, settings=Settings(speech_cache_enabled=False)
        )
        report.update(status="passed", duration=validate_pcm(tmp_path / filename))
        shutil.copyfile(tmp_path / filename, evidence / "british-voice.wav")
    except VideoFailure as exc:
        cause = exc
        while cause.__cause__ is not None:
            cause = cause.__cause__
        report.update(
            status="failed",
            cause_type=type(cause).__name__,
            network_status=getattr(cause, "status", None),
        )
        failure = f"Real {voice} unavailable: {report['cause_type']}; evidence: {evidence}"
    finally:
        (evidence / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if failure:
        pytest.fail(failure, pytrace=False)
