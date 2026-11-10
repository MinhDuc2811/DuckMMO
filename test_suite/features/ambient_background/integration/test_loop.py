import itertools
import json

import pytest
from PIL import ImageChops, ImageStat

from app.contracts.errors import VideoFailure
from app.infrastructure.media.backgrounds import ambient_frames


def jump(a, b):
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]


def test_crossfade_reduces_actual_seam_and_bounds_buffer(gradient_clip):
    options = {"start_seconds": 0, "duration_seconds": 4, "auto_scene": False, "smooth_loop": False}
    plain = ambient_frames(gradient_clip, options, 30, 1)
    try:
        frames = list(itertools.islice(plain, 122))
    finally:
        plain.close()
    hard_jump = jump(frames[119], frames[120])
    del frames
    smooth = ambient_frames(gradient_clip, {**options, "smooth_loop": True}, 30, 1)
    try:
        previous = next(smooth)
        maximum = 0
        for current in itertools.islice(smooth, 140):
            maximum = max(maximum, jump(previous, current))
            previous = current
    finally:
        smooth.close()
    assert maximum < hard_jump * 0.3
    report = json.loads((gradient_clip.parent / "background-analysis.json").read_text())
    assert report["crossfade_frames"] > 0
    assert report["head_buffer_max_bytes"] <= 64_000_000


def test_out_of_range_clip_is_rejected(gradient_clip):
    reader = ambient_frames(
        gradient_clip,
        {"start_seconds": 3, "duration_seconds": 4, "auto_scene": False, "smooth_loop": True},
        30,
        1,
    )
    with pytest.raises(VideoFailure, match="ít nhất 3"):
        next(reader)


def test_scene_selection_avoids_crossing_a_hard_cut(tmp_path):
    import imageio_ffmpeg

    from app.infrastructure.media.backgrounds import select_background
    from app.infrastructure.media.commands import run_command

    path = tmp_path / "cuts.mp4"
    run_command(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=240x426:r=30:d=2",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=240x426:r=30:d=4",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            str(path),
        ],
        cwd=tmp_path,
    )
    _, report = select_background(
        path,
        {"start_seconds": 0, "duration_seconds": 6, "auto_scene": True, "smooth_loop": True},
        30,
        1,
    )
    assert report["start_seconds"] == pytest.approx(2, abs=0.25)
    assert report["duration_seconds"] <= 4.25
    assert report["detected_cuts_seconds"]


def test_closing_loop_reaps_owned_decoder(gradient_clip):
    import psutil

    parent = psutil.Process()
    before = {p.pid for p in parent.children(recursive=True)}
    reader = ambient_frames(
        gradient_clip,
        {"start_seconds": 0, "duration_seconds": 4, "auto_scene": False, "smooth_loop": True},
        30,
        1,
    )
    next(reader)
    assert {p.pid for p in parent.children(recursive=True)} - before
    reader.close()
    assert not {p.pid for p in parent.children(recursive=True)} - before
