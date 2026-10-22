"""Manual, repeatable scene-render measurements; no invented performance threshold.

uv run python -m test_suite.support.presentation_benchmark --output /tmp/scene-benchmark
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil
from PIL import Image, ImageDraw

from app.contracts.presentation import VisualOptions, apply_presentation
from app.infrastructure.media.scenes import build_plan


def measure(directory, duration):
    directory.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1920, 1080), "#305878")
    draw = ImageDraw.Draw(image)
    for i in range(24):
        draw.rectangle((i * 80, i * 22, i * 80 + 50, 1000), fill=(20 + i * 8, 110, 150))
    image.save(directory / "source.png")
    options = VisualOptions(preset="editorial", layout="mix", seed=0)
    config = dict(
        visual=options.model_dump(),
        style=apply_presentation({}, options),
        image_files=["source.png"],
    )
    timeline = [(float(t), min(5.0, duration - t)) for t in range(0, duration, 5)]
    plan = build_plan(config, "Chuyển động nhiều lớp · bản đo cố định", timeline, 720, 1280)
    path = directory / "scene-plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    started, peak = time.monotonic(), 0
    with (directory / "renderer.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.infrastructure.media.scenes", str(path), "2"],
            stdout=log,
            stderr=log,
        )
        while process.poll() is None:
            try:
                parent = psutil.Process(process.pid)
                resident = 0
                for item in [parent, *parent.children(recursive=True)]:
                    try:
                        resident += item.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                peak = max(peak, resident)
            except psutil.NoSuchProcess:
                pass
            if time.monotonic() - started > 600:
                from app.pipeline.supervisor import stop_process

                stop_process(process)
                raise TimeoutError("Benchmark exceeded 600 seconds")
            time.sleep(0.05)
        if process.returncode:
            raise RuntimeError(f"Renderer failed; see {directory / 'renderer.log'}")
    return dict(
        duration_seconds=duration,
        wall_seconds=round(time.monotonic() - started, 2),
        peak_tree_rss_mib=round(peak / 1024**2, 1),
        output_bytes=(directory / "motion.mp4").stat().st_size,
        size=[720, 1280],
        fps=24,
        threads=2,
        source_size=[1920, 1080],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {
        "scope": "Scene stage only, synthetic image fixture; no speech/mix/final encoding",
        "baseline": "No prior comparable scene-renderer baseline",
        "measurements": [],
    }
    for duration in (30, 60):
        measurement = measure(args.output / str(duration), duration)
        report["measurements"].append(measurement)
        print(json.dumps(measurement), flush=True)
    (args.output / "results.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
