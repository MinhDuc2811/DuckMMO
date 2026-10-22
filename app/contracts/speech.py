"""Speech segmentation is independent of subtitle layout and image changes."""

import re
from xml.sax.saxutils import escape


def speech_segments(text, max_characters=2500, *, max_bytes=None):
    if max_characters < 1 or (max_bytes is not None and max_bytes < 1):
        raise ValueError("Speech limits must be positive")

    def fits(value):
        return len(value) <= max_characters and (
            max_bytes is None or len(escape(value).encode("utf-8")) <= max_bytes
        )

    parts = re.split(r"(?<=[.!?。！？])\s+|\n\s*\n", text.strip())
    segments, current = [], ""
    for part in parts:
        part = part.strip()
        while not fits(part):
            if current:
                segments.append(current)
                current = ""
            lo, hi = 0, min(len(part), max_characters)
            while lo < hi:
                middle = (lo + hi + 1) // 2
                if fits(part[:middle]):
                    lo = middle
                else:
                    hi = middle - 1
            if lo == 0:
                raise ValueError("Speech byte limit cannot fit a character")
            punctuation = max(part.rfind(mark, 0, lo) + 1 for mark in ",;:")
            boundary = punctuation if punctuation >= lo // 2 else part.rfind(" ", 0, lo + 1)
            split_at = boundary if boundary >= max(1, lo // 2) else lo
            segments.append(part[:split_at].strip())
            part = part[split_at:].strip()
        if not part:
            continue
        combined = f"{current} {part}".strip()
        if current and not fits(combined):
            segments.append(current)
            current = part
        else:
            current = combined
    if current:
        segments.append(current)
    return segments
