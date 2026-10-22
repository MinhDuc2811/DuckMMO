from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactDownload:
    path: Path
    media_type: str
    filename: str
    inline: bool = False
