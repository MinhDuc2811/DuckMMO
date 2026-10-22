import array
import math
import wave

import pytest


@pytest.fixture
def narration():
    def create(path, duration=4):
        rate = 22050
        pcm = array.array(
            "h",
            (
                int(6000 * math.sin(2 * math.pi * 440 * i / rate)) if i / rate < duration / 2 else 0
                for i in range(round(rate * duration))
            ),
        )
        import sys

        if sys.byteorder == "big":
            pcm.byteswap()
        with wave.open(str(path), "wb") as output:
            output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            output.writeframes(pcm.tobytes())
        return duration

    return create
