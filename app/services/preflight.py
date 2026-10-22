import re

from app.schemas import ContentPackage


def preflight(package: ContentPackage) -> dict:
    """Deterministic checks only; does not claim AI generation or fact verification."""
    words = (
        len(re.findall(r"\S+", package.video_content))
        if package.video_content
        else sum(len(re.findall(r"\S+", scene.narration)) for scene in package.scenes)
    )
    return {
        "stage": "preflight",
        "phase": "phase1_complete",
        "analysis": {
            "type": "structural",
            "ai_generated": False,
            "paragraph_count": len(
                (package.video_content or "\n\n".join(s.narration for s in package.scenes)).split(
                    "\n\n"
                )
            ),
            "source_count": len(package.sources),
            "source_characters": [len(d["content"]) for d in package.source_documents],
        },
        "word_count": words,
        "scene_count": len(package.scenes),
        "estimated_narration_seconds": round(words / 2.5),
        "warnings": [
            "Narration duration is an estimate; no audio has been generated.",
            "Source references and rights notes require human verification.",
            "OCR, external fact-check, audio and video rendering have not been performed.",
        ],
    }
