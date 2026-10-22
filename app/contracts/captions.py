def split_captions(text, limit=105):
    words = text.split()
    chunks, current = [], ""
    for word in words:
        if current and len(current) + len(word) + 1 > limit:
            chunks.append(current)
            current = ""
        current = f"{current} {word}".strip()
        if current[-1:] in ".!?。！？" and len(current) > 30:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
