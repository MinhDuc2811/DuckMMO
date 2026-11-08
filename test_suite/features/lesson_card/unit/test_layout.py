import pytest
from PIL import Image

from app.contracts.errors import VideoFailure
from app.contracts.presentation import PRESETS, VisualOptions, uses_lesson_card
from app.infrastructure.media.scene_components import scene_frame
from app.infrastructure.media.visuals import visual_filters


@pytest.mark.parametrize("size", [(240, 426), (720, 1280), (1280, 720)])
def test_white_card_preserves_static_background_and_does_not_drift(size):
    background = Image.new("RGB", size, "#a26030")
    scene = dict(
        index=0,
        total=1,
        duration=3,
        title="Vocabulary",
        text="Self-paced learning.",
        layout="lesson_card",
    )
    options = VisualOptions(preset="lesson-card").model_dump()
    first = scene_frame(size, PRESETS["lesson-card"], scene, 0.1, options, background)
    later = scene_frame(size, PRESETS["lesson-card"], scene, 2.1, options, background)
    assert first.tobytes() == later.tobytes()
    assert first.getpixel((size[0] // 2, round(size[1] * 0.9))) == (162, 96, 48)
    assert first.getpixel((round(size[0] * 0.09), round(size[1] * 0.20))) == (255, 255, 255)
    assert (
        first.crop(
            (
                round(size[0] * 0.12),
                round(size[1] * 0.20),
                round(size[0] * 0.8),
                round(size[1] * 0.35),
            )
        ).getextrema()[0][0]
        < 100
    )


def test_long_content_is_rejected_instead_of_truncated():
    scene = dict(
        index=0, total=1, duration=3, title="Vocabulary", text="word " * 1000, layout="lesson_card"
    )
    with pytest.raises(VideoFailure, match="quá dài"):
        scene_frame(
            (240, 426),
            PRESETS["lesson-card"],
            scene,
            0,
            VisualOptions(preset="lesson-card").model_dump(),
        )


def test_white_card_suppresses_only_duplicate_burned_subtitles():
    config = {
        "motion_file": "motion.mp4",
        "visual": VisualOptions(preset="lesson-card").model_dump(),
    }
    assert uses_lesson_card(config["visual"])
    assert visual_filters(config, {}, 720, 1280) == "fps=24"
    config["visual"] = VisualOptions(preset="comic").model_dump()
    assert visual_filters(config, {}, 720, 1280) == "fps=24,ass=subtitles.ass"


def test_video_background_changes_while_white_card_stays_white():
    scene = dict(
        index=0,
        total=1,
        duration=3,
        title="Vocabulary",
        text="Learn at your own pace.",
        layout="lesson_card",
    )
    options = VisualOptions(preset="lesson-card").model_dump()
    first = scene_frame(
        (240, 426), PRESETS["lesson-card"], scene, 0, options, Image.new("RGB", (240, 426), "red")
    )
    later = scene_frame(
        (240, 426), PRESETS["lesson-card"], scene, 1, options, Image.new("RGB", (240, 426), "blue")
    )
    assert first.getpixel((120, 400)) != later.getpixel((120, 400))
    assert first.getpixel((22, 90)) == later.getpixel((22, 90)) == (255, 255, 255)
