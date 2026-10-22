"""Measured checks only. Unknown semantic/word alignment stays unknown."""

import re
import wave
from array import array


def check(dimension, outcome, evidence, score=None):
    return dict(dimension=dimension, outcome=outcome, evidence=evidence, score=score)


def source_checks(documents):
    return [
        check(
            "source_text",
            "pass"
            if documents and all(len(d.get("content", "").strip()) >= 100 for d in documents)
            else "fail",
            {"source_characters": [len(d.get("content", "")) for d in documents]},
        ),
        check("source_coverage", "unknown", {"reason": "No human reference extraction available"}),
    ]


def script_checks(package):
    text = package.get("video_content") or "\n\n".join(
        s["narration"] for s in package.get("scenes", [])
    )
    sentences = [s.strip().lower() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 15]
    repeated = len(sentences) - len(set(sentences))
    sources = "\n".join(d.get("content", "") for d in package.get("source_documents", []))
    numbers = set(re.findall(r"\b\d+(?:[.,]\d+)*\b", text))
    unsupported = (
        sorted(numbers - set(re.findall(r"\b\d+(?:[.,]\d+)*\b", sources))) if sources else []
    )
    return [
        check(
            "source_numbers",
            "warn" if unsupported else "unknown" if not sources else "pass",
            {
                "numbers_not_found_in_source": unsupported,
                "limitation": "Literal number matching does not establish factual accuracy",
            },
        ),
        check("script_nonempty", "pass" if text.strip() else "fail", {"characters": len(text)}),
        check(
            "script_repetition", "warn" if repeated else "pass", {"repeated_sentences": repeated}
        ),
        check(
            "factual_accuracy",
            "unknown",
            {"reason": "Requires source claims and human verification"},
        ),
        check("language_accuracy", "unknown", {"reason": "No language evaluator configured"}),
    ]


def subtitle_checks(cues, duration, style, width, height):
    from PIL import Image, ImageDraw

    from app.infrastructure.media.frames import font, wrap

    draw = ImageDraw.Draw(Image.new("RGB", (width, height)))
    face = font(style["font_size"] if width == 720 else int(style["font_size"] * 0.85))
    invalid, overflow, fast = [], [], []
    previous = 0.0
    for i, (start, end, text) in enumerate(cues):
        if start < previous - 0.02 or end <= start or end > duration + 0.03:
            invalid.append(i)
        previous = end
        lines = wrap(draw, text, face, width - 108)
        if len(lines) > 2 or any(draw.textlength(line, font=face) > width - 108 for line in lines):
            overflow.append({"cue": i, "timecode": start, "lines": len(lines)})
        cps = len(text) / max(0.01, end - start)
        if cps > 22:
            fast.append({"cue": i, "timecode": start, "characters_per_second": round(cps, 1)})
    return [
        check("subtitle_timeline", "fail" if invalid else "pass", {"invalid_cues": invalid}),
        check("subtitle_layout", "fail" if overflow else "pass", {"overflow": overflow}),
        check(
            "subtitle_pacing",
            "warn" if fast else "pass",
            {"fast_cues": fast[:30], "threshold_cps": 22},
        ),
        check(
            "word_alignment",
            "unknown",
            {"reason": "Timing estimated within measured speech chunks"},
        ),
    ]


def audio_checks(path):
    with wave.open(str(path)) as audio:
        if audio.getsampwidth() != 2 or audio.getnchannels() != 1:
            return [check("audio_signal", "unknown", {"reason": "Expected 16-bit mono PCM"})]
        samples = array("h", audio.readframes(audio.getnframes()))
    count = len(samples)
    peak = max((abs(s) for s in samples), default=0)
    clipped = sum(abs(s) >= 32760 for s in samples) / max(1, count)
    silent = peak < 100
    return [
        check(
            "audio_signal",
            "fail" if silent or clipped > 0.01 else "pass",
            {"peak": peak, "clipped_fraction": clipped, "silent": silent},
        ),
        check(
            "pronunciation", "unknown", {"reason": "No verified ASR/pronunciation model connected"}
        ),
    ]


def has_blocker(evaluations):
    return any(item["outcome"] == "fail" for item in evaluations)
