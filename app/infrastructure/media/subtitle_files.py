"""SRT serialization preserving literal grammar notation, Unicode and backslashes."""

from uuid import uuid4

import pysubs2


def write_srt(path, cues):
    # pysubs2's ASS intermediary interprets literal \\N, \\n and \\h as whitespace.
    # Protect source backslashes until after SRT serialization; never lose lesson text.
    marker = uuid4().hex
    while any(marker in text for _, _, text in cues):
        marker = uuid4().hex
    subtitles = pysubs2.SSAFile()
    for start, end, text in cues:
        event = pysubs2.SSAEvent(start=round(start * 1000), end=round(end * 1000))
        event.plaintext = text.replace("\\", marker)
        subtitles.append(event)
    serialized = subtitles.to_string("srt", keep_ssa_tags=True).replace(marker, "\\")
    path.write_text(serialized, encoding="utf-8")
