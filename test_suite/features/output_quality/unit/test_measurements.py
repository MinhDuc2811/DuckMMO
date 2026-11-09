import json

from app.infrastructure.media.output_quality import signal_checks


def test_nonfinite_silence_is_json_safe_and_fails_signal():
    report = signal_checks('{"input_i":"-inf","input_tp":"-inf"}', 2)
    assert report[0]["outcome"] == "fail"
    json.dumps(report, allow_nan=False)


def test_true_peak_warning_does_not_claim_distortion():
    report = signal_checks('{"input_i":"-16","input_tp":"0.5"}', 2)
    peak = next(e for e in report if e["dimension"] == "output_audio_peak")
    assert peak["outcome"] == "warn"
    assert "not proof of clipping" in peak["evidence"]["limitation"]
