"""Curated IDs and display metadata; binaries are resolved by the media adapter."""

from typing import Literal

BackgroundId = Literal["study-morning", "quiet-work", "misty-lake"]
StudyTrackId = Literal["quiet-pages", "soft-focus", "morning-air"]

BACKGROUNDS = {
    "study-morning": {
        "name": "Ảnh thật · gia vị",
        "topics": ["food", "culture", "daily-life"],
        "credit": "Riyaad Minty · CC BY 2.0 · https://www.flickr.com/photos/riym/3326786046 · https://creativecommons.org/licenses/by/2.0/",
    },
    "quiet-work": {
        "name": "Ảnh thật · di tích Petra",
        "topics": ["travel", "heritage"],
        "credit": (
            "Francois Malan · CC BY 3.0 · "
            "https://github.com/scikit-image/skimage-tutorials/blob/main/images/pano/DFM_4209.jpg"
            " · https://creativecommons.org/licenses/by/3.0/"
        ),
    },
    "misty-lake": {
        "name": "Ảnh thật · Bells Beach",
        "topics": ["environment", "travel", "wellbeing"],
        "credit": "scikit-image tutorial contributors · CC0 · https://github.com/scikit-image/skimage-tutorials/blob/main/images/Bells-Beach.jpg",
    },
}
STUDY_TRACKS = {
    "quiet-pages": {"name": "Sunny Steps · pop groove", "duration_seconds": 32, "bpm": 90},
    "soft-focus": {"name": "Open Road · country-pop", "duration_seconds": 40, "bpm": 120},
    "morning-air": {"name": "Good Mood · acoustic pop", "duration_seconds": 32, "bpm": 120},
}
