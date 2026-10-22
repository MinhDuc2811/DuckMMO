"""Provider-independent voice IDs shared by validation and the voice catalog."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    provider: str
    locale: str = "vi-VN"
    max_characters: int = 2500

    @property
    def max_bytes(self):
        # Edge internally splits escaped UTF-8 at 4096 bytes. Keep our own natural boundaries.
        return 3500 if self.provider == "edge" else None


VOICES = (
    Voice("vi-VN-HoaiMyNeural", "Hoài My · nữ · Microsoft Edge", "edge"),
    Voice("vi-VN-NamMinhNeural", "Nam Minh · nam · Microsoft Edge", "edge"),
    Voice("local-vi", "Tiếng Việt · giọng Windows đã cài", "windows"),
    Voice("en-US-AriaNeural", "Aria · English · Microsoft Edge", "edge", "en-US"),
    Voice("local-en", "English · giọng Windows đã cài", "windows", "en-US"),
)


def get_voice(voice_id):
    for voice in VOICES:
        if voice.id == voice_id:
            return voice
    raise ValueError("Giọng đọc không được hỗ trợ.")
