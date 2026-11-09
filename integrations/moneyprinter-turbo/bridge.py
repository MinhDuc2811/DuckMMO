"""Run only MoneyPrinterTurbo's stock-footage functions in its isolated environment."""

import importlib.metadata
import json
import os
import sys
import wave
from pathlib import Path


def main():
    request_path = Path(sys.argv[1]).resolve()
    request = json.loads(request_path.read_text())
    home = Path(request["home"]).resolve()
    os.environ["MPT_HOME"] = str(home)
    os.environ["IMAGEIO_FFMPEG_EXE"] = request["ffmpeg"]
    from loguru import logger

    logger.remove()  # Do not emit provider URLs/credentials to the parent log.
    from app.models.schema import VideoAspect, VideoConcatMode, VideoFitMode
    from app.utils import utils

    from app.config import config
    from app.services import material, task_artifacts, video

    version = importlib.metadata.version("mpt")
    if version != "1.3.10":
        raise ValueError("Unexpected MoneyPrinterTurbo version")
    if request["command"] == "doctor":
        print(
            json.dumps(
                {
                    "version": version,
                    "isolated": True,
                    "stock_providers": ["pexels", "pixabay", "coverr"],
                    "generation_enabled": False,
                }
            )
        )
        return
    provider = request["provider"]
    if provider not in ("pexels", "pixabay", "coverr"):
        raise ValueError("Only stock sources are enabled")
    config.app.update(
        {
            f"{provider}_api_keys": [request["api_key"]],
            "material_directory": "task",
            "material_concurrency": 1,
            "clip_processing_concurrency": 1,
            "video_codec": "libx264",
            "ffmpeg_path": request["ffmpeg"],
            "tls_verify": True,
        }
    )
    material.MAX_VIDEO_DOWNLOAD_BYTES = 30_000_000
    task_id = request["run_id"]
    output = Path(request["output"]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    aspect = VideoAspect(request["ratio"])
    task_artifacts.write_script_data(task_id, {"terms": request["terms"]})
    files = material.download_videos(
        task_id=task_id,
        search_terms=request["terms"],
        source=provider,
        video_aspect=aspect,
        video_concat_mode=VideoConcatMode.sequential,
        audio_duration=request["seconds"],
        max_clip_duration=5,
        match_script_order=True,
    )
    if not files:
        raise ValueError("No stock footage downloaded")
    timing = output.parent / "timing.wav"
    # Duration reference only: never returned as narration or mixed into the clip.
    with wave.open(str(timing), "wb") as audio:
        audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * (8000 * request["seconds"]))
    used = []
    video.combine_videos(
        str(output),
        files,
        str(timing),
        video_aspect=aspect,
        video_concat_mode=VideoConcatMode.sequential,
        max_clip_duration=5,
        threads=2,
        video_fit_mode=VideoFitMode.cover,
        used_video_paths=used,
    )
    manifest = Path(utils.task_dir(task_id)) / "script.json"
    sources = (
        json.loads(manifest.read_text()).get("material_sources", []) if manifest.exists() else []
    )
    # The upstream record is already whitelisted; keep only public provenance again.
    safe = []
    for source in sources:
        if used and source.get("local_file") not in {Path(f).name for f in used}:
            continue
        safe.append(
            {
                key: source[key]
                for key in (
                    "provider",
                    "asset_id",
                    "source_page",
                    "creator",
                    "rendition",
                    "search_term",
                )
                if key in source
            }
        )
    if not safe:
        raise ValueError("Missing footage provenance")
    print(
        json.dumps(
            {
                "version": version,
                "provider": provider,
                "terms": request["terms"],
                "sources": safe,
                "source_count": len(files),
                "output": str(output),
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Deliberately do not forward URLs, API keys or provider exception strings.
        print(
            json.dumps({"error": type(error).__name__, "stage": "stock_footage"}), file=sys.stderr
        )
        sys.exit(1)
