import pytest
from pydantic import ValidationError

from app.contracts.presentation import PRESETS, MusicOptions, VisualOptions, apply_presentation
from app.infrastructure.media.scene_components import scene_frame
from app.infrastructure.media.scenes import build_plan
from app.schemas import RenderOptions
from app.services.styles import choose_style


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 0.51])
def test_music_volume_bounds(value):
    with pytest.raises(ValidationError):
        MusicOptions(volume=value)


def test_reject_ambiguous_sources_and_arbitrary_templates():
    with pytest.raises(ValidationError):
        MusicOptions(track="ambient", asset_id="00000000-0000-0000-0000-000000000001")
    with pytest.raises(ValidationError):
        VisualOptions(preset="javascript")
    with pytest.raises(ValidationError):
        VisualOptions(accent="red; movie=remote")


@pytest.mark.parametrize("branch", ["novel", "comic", "research"])
@pytest.mark.parametrize("preset", list(PRESETS))
def test_all_styles_available_to_every_content_branch(branch, preset):
    style = apply_presentation(
        choose_style({"branch": branch}, use_learned=False), VisualOptions(preset=preset)
    )
    assert style["id"] == preset
    assert style["engine"] == "pillow-scenes-v1+ffmpeg-libass"


def test_plan_is_repeatable_and_layout_is_independent():
    visual = VisualOptions(preset="comic", layout="mix", seed=2).model_dump()
    config = dict(visual=visual, style=PRESETS["comic"], image_files=[])
    plan = build_plan(config, "Tiêu đề", [(0, 1), (1, 1), (2, 1), (3, 1)], 240, 426)
    assert plan == build_plan(config, "Tiêu đề", [(0, 1), (1, 1), (2, 1), (3, 1)], 240, 426)
    assert [s["layout"] for s in plan["scenes"]] == ["quote", "full", "collage", "panels"]


def test_components_have_actual_time_dependent_motion():
    scene = dict(index=0, total=1, duration=2, title="Chuyển động", layout="collage")
    options = VisualOptions(preset="editorial").model_dump()
    a = scene_frame((240, 426), PRESETS["editorial"], scene, 0.1, options)
    b = scene_frame((240, 426), PRESETS["editorial"], scene, 1.4, options)
    assert a.tobytes() != b.tobytes()
    assert (
        a.tobytes() == scene_frame((240, 426), PRESETS["editorial"], scene, 0.1, options).tobytes()
    )


def test_existing_requests_keep_legacy_defaults():
    options = RenderOptions(expected_content_hash="0" * 64)
    assert options.visual.preset == "auto"
    assert not options.music.asset_id and not options.music.track
