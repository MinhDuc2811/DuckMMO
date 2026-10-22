"""PCM boundary handling; never remove pauses inside an utterance."""

import array
import os
import wave

from app.contracts.errors import VideoFailure


def trim_boundary_silence(path, *, trim_start, trim_end, threshold=100):
    with wave.open(str(path), "rb") as source:
        channels, width, rate, frames, codec, _ = source.getparams()
        if channels != 1 or width != 2 or codec != "NONE":
            raise VideoFailure("Audio ghép cần WAV PCM mono 16-bit.")
        pcm = source.readframes(frames)
    samples = array.array("h", pcm)
    if os.sys.byteorder == "big":
        samples.byteswap()
    first = next((i for i, value in enumerate(samples) if abs(value) >= threshold), None)
    if first is None:
        raise VideoFailure("Đoạn giọng đọc không có tín hiệu nghe được.")
    last = next(i for i in range(len(samples) - 1, -1, -1) if abs(samples[i]) >= threshold)
    # Keep conservative edges; do not crossfade spoken phonemes.
    start = max(0, first - int(rate * 0.08)) if trim_start else 0
    end = min(frames, last + 1 + int(rate * 0.16)) if trim_end else frames
    temporary = path.with_suffix(".trim.wav")
    with wave.open(str(temporary), "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(pcm[start * 2 : end * 2])
    temporary.replace(path)
    return {
        "duration": (end - start) / rate,
        "trimmed_start_seconds": start / rate,
        "trimmed_end_seconds": (frames - end) / rate,
    }


def long_pauses(path, minimum_seconds=0.8):
    """Report internal low-signal spans; punctuation pauses remain warnings, never failures."""
    spans = []
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            return spans
        rate, total = source.getframerate(), source.getnframes()
        block_size = max(1, int(rate * 0.02))
        cursor, silence_start = 0, None
        while pcm := source.readframes(block_size):
            samples = array.array("h", pcm)
            if os.sys.byteorder == "big":
                samples.byteswap()
            if max((abs(v) for v in samples), default=0) < 100:
                if silence_start is None:
                    silence_start = cursor
            elif silence_start is not None:
                duration = (cursor - silence_start) / rate
                if silence_start > 0 and duration >= minimum_seconds and len(spans) < 20:
                    spans.append({"start": silence_start / rate, "duration": duration})
                silence_start = None
            cursor += len(samples)
        # Trailing silence is an edge, not an internal pause.
        if cursor != total:
            raise VideoFailure("Audio WAV bị thiếu dữ liệu.")
    return spans


def validate_pcm(path):
    """Validate canonical TTS PCM before caching, with bounded memory."""
    peak, clipped, count = 0, 0, 0
    with wave.open(str(path), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 22050):
            raise VideoFailure("Giọng đọc cần WAV PCM mono 16-bit 22050 Hz.")
        expected = source.getnframes()
        while pcm := source.readframes(22050):
            samples = array.array("h", pcm)
            if os.sys.byteorder == "big":
                samples.byteswap()
            count += len(samples)
            peak = max(peak, max((abs(v) for v in samples), default=0))
            clipped += sum(abs(v) >= 32760 for v in samples)
    if count != expected or count == 0 or peak < 100 or clipped / count > 0.01:
        raise VideoFailure("Audio TTS bị thiếu, im lặng hoặc clipping; không lưu cache.")
    return count / 22050
