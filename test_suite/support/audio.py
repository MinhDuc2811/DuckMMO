import struct
import wave


def write_pcm(path, segments):
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        for seconds, value in segments:
            out.writeframes(struct.pack("<h", value) * int(seconds * 22050))
