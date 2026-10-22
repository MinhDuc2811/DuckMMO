from app.contracts.captions import split_captions, timestamp
from app.quality.evaluators import subtitle_checks
from app.services.styles import write_ass


def resolve_subtitles(directory, cues, style, elapsed, width, height, progress):
    evaluations = subtitle_checks(cues, elapsed, style, width, height)
    repairs = 0
    while (
        any(e["dimension"] == "subtitle_layout" and e["outcome"] == "fail" for e in evaluations)
        and repairs < 2
    ):
        repairs += 1
        style = {
            **style,
            "font_size": max(32, style["font_size"] - 4),
            "caption_chars": max(24, style["caption_chars"] - 8),
        }
        repaired = []
        for start, end, phrase in cues:
            parts = split_captions(phrase, limit=style["caption_chars"])
            count = sum(len(part.split()) for part in parts)
            cursor = start
            for i, part in enumerate(parts):
                next_end = (
                    end
                    if i == len(parts) - 1
                    else cursor + (end - start) * len(part.split()) / count
                )
                repaired.append((cursor, next_end, part))
                cursor = next_end
        cues = repaired
        evaluations = subtitle_checks(cues, elapsed, style, width, height)
        progress(f"Subtitle layout repair {repairs}/2")
    write_ass(directory, cues, style, width, height)
    (directory / "subtitles.srt").write_text(
        "\n".join(
            f"{i + 1}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n"
            for i, (start, end, text) in enumerate(cues)
        ),
        encoding="utf-8",
    )
    return cues, style, repairs, evaluations
