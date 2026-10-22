"""Bounded streaming scene renderer, run as an owned worker descendant."""

import json
import math
import signal
import sys
from pathlib import Path

from PIL import Image

from app.contracts.presentation import PRESETS
from app.infrastructure.media.frame_streams import clip_frames, encode_frames
from app.infrastructure.media.scene_components import scene_frame

VERSION = 1


def build_plan(config, title, timeline, width, height):
    options = config["visual"]
    preset = PRESETS[options["preset"]]
    layouts = ("collage", "panels", "quote", "full")
    scenes = []
    for index, slot in enumerate(timeline):
        start, duration = slot[:2]
        layout = options["layout"]
        if layout == "preset":
            layout = preset["layout"]
        elif layout == "mix":
            layout = layouts[(index + options["seed"]) % len(layouts)]
        scenes.append(
            dict(
                index=index,
                total=len(timeline),
                start=start,
                duration=duration,
                title=title,
                text=slot[2] if len(slot) > 2 else "",
                layout=layout,
            )
        )
    return {
        "version": VERSION,
        "size": [width, height],
        "fps": 24,
        "options": options,
        "style": config["style"],
        "images": config["image_files"],
        "video_file": config.get("video_file"),
        "video_fit": config.get("video_fit", "pad"),
        "scenes": scenes,
    }


def frames(plan, directory):
    """Hold one source and one output frame; never accumulate a video in RAM."""
    size, fps = tuple(plan["size"]), plan["fps"]
    reader = None
    source = None
    outgoing, previous = None, None
    try:
        if plan.get("video_file"):
            reader = clip_frames(directory / plan["video_file"], plan.get("threads", 2))
        current, total_frames = 0, math.ceil(sum(s["duration"] for s in plan["scenes"]) * fps)
        for number in range(total_frames):
            t = number / fps
            while current + 1 < len(plan["scenes"]) and t >= plan["scenes"][current + 1]["start"]:
                current += 1
                outgoing = previous
                source = None
            scene = plan["scenes"][current]
            if reader:
                source = next(reader)
            elif source is None and plan["images"]:
                with Image.open(directory / plan["images"][current % len(plan["images"])]) as image:
                    source = image.convert("RGB")
            frame = scene_frame(
                size,
                plan["style"],
                scene,
                t - scene["start"],
                {**plan["options"], "video_fit": plan["video_fit"] if reader else "crop"},
                source,
            )
            local_time = t - scene["start"]
            transition = plan["options"].get("transition", "fade")
            if outgoing is not None and local_time < 0.3 and transition != "cut":
                fraction = min(1, local_time / 0.3)
                if transition == "fade":
                    frame = Image.blend(outgoing, frame, fraction)
                else:
                    shifted = Image.new("RGB", size)
                    shift = round(size[0] * fraction)
                    shifted.paste(outgoing, (-shift, 0))
                    shifted.paste(frame, (size[0] - shift, 0))
                    frame = shifted
            previous = frame
            yield frame

    finally:
        if reader:
            reader.close()


def export(plan, directory, threads):
    plan = {**plan, "threads": threads}
    encode_frames(
        frames(plan, directory), directory / "motion.mp4", tuple(plan["size"]), plan["fps"], threads
    )


def _cancel_render(_signal, _frame):
    # Unwind frame/writer generators so owned FFmpeg children are waited, not orphaned.
    raise SystemExit(143)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _cancel_render)
    path = Path(sys.argv[1])
    export(json.loads(path.read_text(encoding="utf-8")), path.parent, int(sys.argv[2]))
