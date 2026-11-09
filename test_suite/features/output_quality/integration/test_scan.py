import json

import pytest

from app.infrastructure.media.output_quality import inspect_output
from app.infrastructure.media.storage import file_digest


def outcome(report, dimension):
    return next(e for e in report["evaluations"] if e["dimension"] == dimension)["outcome"]


def test_actual_scan_accepts_static_background_without_rewriting(output_clip):
    path = output_clip()
    before = file_digest(path)
    report = inspect_output(path.parent, 2, 240, 426)
    assert report["status"] in ("pass", "warn"), report
    assert outcome(report, "output_full_decode") == "pass"
    assert outcome(report, "output_audio_signal") == "pass"
    assert outcome(report, "black_frames") == "pass"
    assert file_digest(path) == before == report["sha256"]
    assert json.loads((path.parent / "output-quality.json").read_text()) == report


@pytest.mark.parametrize(
    "defect", ["silent", "black", "no_audio", "duration", "dimensions", "corrupt"]
)
def test_actual_scan_blocks_defective_output(output_clip, defect):
    options = {}
    if defect == "silent":
        options["sound"] = "anullsrc=r=22050:cl=mono"
    if defect == "black":
        options["color"] = "black"
    if defect == "no_audio":
        options["audio"] = False
    path = output_clip(**options)
    if defect == "corrupt":
        path.write_bytes(b"not an mp4")
    report = inspect_output(
        path.parent, 5 if defect == "duration" else 2, 720 if defect == "dimensions" else 240, 426
    )
    assert report["status"] == "fail", report
    assert any(e["outcome"] == "fail" for e in report["evaluations"])


def test_warning_has_real_silent_timecodes(output_clip):
    path = output_clip(
        sound="aevalsrc=if(lt(t\\,1.2)\\,0\\,0.1*sin(2*PI*440*t)):s=22050",
    )
    report = inspect_output(path.parent, 2, 240, 426)
    assert report["status"] == "warn"
    silence = next(e for e in report["evaluations"] if e["dimension"] == "output_silence")
    assert silence["outcome"] == "warn"
    assert silence["evidence"]["spans"][0]["start"] < 0.1
    assert silence["evidence"]["spans"][0]["end"] == pytest.approx(1.2, abs=0.1)


def test_partial_black_warns_with_timecodes_instead_of_blocking(output_clip):
    path = output_clip(
        video_filter="drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='lt(t,0.8)'"
    )
    report = inspect_output(path.parent, 2, 240, 426)
    assert report["status"] == "warn", report
    black = next(e for e in report["evaluations"] if e["dimension"] == "black_frames")
    assert black["outcome"] == "warn"
    assert black["evidence"]["spans"][0]["start"] == 0
    assert black["evidence"]["spans"][0]["end"] == pytest.approx(0.8, abs=0.1)


def test_missing_ffprobe_fails_closed(output_clip, monkeypatch):
    path = output_clip()
    monkeypatch.setattr("app.infrastructure.media.output_quality.shutil.which", lambda _: None)
    report = inspect_output(path.parent, 2, 240, 426)
    assert report["status"] == "fail"
    assert outcome(report, "output_full_decode") == "fail"
