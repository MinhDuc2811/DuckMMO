import array
import wave

import pytest
from pydantic import ValidationError

from app.contracts.study_pack import BACKGROUNDS, STUDY_TRACKS
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.study_pack import bundled_asset
from app.schemas import RenderOptions


@pytest.mark.parametrize("track", list(STUDY_TRACKS))
def test_instrumentals_have_headroom_and_no_exceptional_loop_jump(track):
    with wave.open(str(bundled_asset("music", track))) as source:
        assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (
            1,
            2,
            22050,
        )
        samples = array.array("h", source.readframes(source.getnframes()))
    assert len(samples) / 22050 == STUDY_TRACKS[track]["duration_seconds"]
    assert 1000 < max(abs(value) for value in samples) < 30000
    jumps = sorted(abs(b - a) for a, b in zip(samples, samples[1:]))
    assert abs(samples[0] - samples[-1]) <= jumps[int(len(jumps) * 0.99)]


def test_render_rejects_ambiguous_backgrounds_and_unlisted_ids():
    for background in BACKGROUNDS:
        assert (
            RenderOptions(background_id=background, expected_content_hash="0" * 64).background_id
            == background
        )
    with pytest.raises(ValidationError):
        RenderOptions(background_id="study-morning", images=["a"], expected_content_hash="0" * 64)
    with pytest.raises(ValidationError):
        RenderOptions(background_id="../private", expected_content_hash="0" * 64)
    with pytest.raises(MediaFailure):
        bundled_asset("music", "../private")


def test_changed_bundled_file_is_rejected(tmp_path, monkeypatch):
    import json

    from app.infrastructure.media import study_pack

    (tmp_path / "bad.wav").write_bytes(b"changed content")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"assets": {"music/quiet-pages": {"file": "bad.wav", "sha256": "0" * 64}}})
    )
    monkeypatch.setattr(study_pack, "ROOT", tmp_path)
    with pytest.raises(MediaFailure, match="thay đổi"):
        study_pack.bundled_asset("music", "quiet-pages")
