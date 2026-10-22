"""Opt-in real Edge TTS + real FFmpeg; fixture audio is never substituted here."""

import json
import shutil
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.config import Settings
from app.contracts.content import content_hash
from app.contracts.errors import VideoFailure
from app.infrastructure.media.audio import long_pauses, validate_pcm
from app.infrastructure.media.speech import synthesize
from app.modules.production.render import MediaAdapters, render_video
from test_suite.support.paths import PROJECT_ROOT

SCRIPTS = {
    "continuous": (
        "Hôm nay chúng ta cùng tìm hiểu cách xây dựng một kênh video dành cho người Việt "
        "với nội dung dễ nghe và giọng đọc tự nhiên để khán giả theo dõi câu chuyện liền mạch "
        "từ đầu đến cuối mà không bị cắt thành những đoạn ngắn giữa câu"
    ),
    "punctuated": (
        "Xin chào các bạn. Hôm nay chúng ta cùng nghe một câu chuyện bằng tiếng Việt. "
        "Giọng đọc cần rõ ràng, tự nhiên và có nhịp nghỉ phù hợp. "
        "Đây là mẫu kiểm tra kỹ thuật, chưa phải đánh giá chất lượng bằng người nghe."
    ),
}


@pytest.mark.live_tts
@pytest.mark.parametrize("voice", ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"])
@pytest.mark.parametrize("script_case", SCRIPTS)
def test_real_free_voice_to_video(voice, script_case, tmp_path, monkeypatch):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
    evidence = PROJECT_ROOT / "test-results" / "speech" / "live" / stamp
    evidence.mkdir(parents=True)
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    settings = Settings(speech_cache_enabled=False)
    calls = []

    def real_provider(text, selected_voice, directory, index):
        calls.append(text)
        return synthesize(text, selected_voice, directory, index, settings=settings)

    script = SCRIPTS[script_case]
    package = {
        "title": "Vietnamese TTS self-test",
        "branch": "novel",
        "scenes": [{"narration": script}],
    }
    job_id, run_id = str(uuid4()), str(uuid4())
    directory = settings.artifact_dir / job_id / run_id
    directory.mkdir(parents=True)
    report = {"voice": voice, "case": script_case, "live_tts": True, "cached": False}
    failure = None
    try:
        result = render_video(
            job_id,
            package,
            {
                "run_id": run_id,
                "expected_content_hash": content_hash(package),
                "voice": voice,
                "image_files": [],
                "layout": "portrait",
            },
            lambda _: None,
            adapters=MediaAdapters(synthesize=real_provider),
        )
        assert calls == [script], "Short continuous script must be one actual TTS utterance"
        assert result["audio_checked"] and result["video_checked"]
        report.update(
            status="passed",
            duration=validate_pcm(directory / "narration.wav"),
            pauses=long_pauses(directory / "narration.wav"),
            visual_duration=result["duration"],
            subtitles=result["caption_count"],
        )
        for filename in ("narration.wav", "video.mp4", "speech-timeline.json", "subtitles.srt"):
            shutil.copyfile(directory / filename, evidence / filename)
    except VideoFailure as exc:
        cause = exc
        while cause.__cause__ is not None:
            cause = cause.__cause__
        report.update(
            status="blocked" if getattr(cause, "status", None) == 403 else "failed",
            error_type=type(cause).__name__,
            proxy_status=getattr(cause, "status", None),
        )
        # Delay failure until outside the exception handler to suppress provider URL/header chains.
        failure = (
            f"Live {voice}: {report['status']}, {report['error_type']}, "
            f"proxy_status={report['proxy_status']}; evidence: {evidence}"
        )
    finally:
        (evidence / "result.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if failure:
        pytest.fail(failure, pytrace=False)
