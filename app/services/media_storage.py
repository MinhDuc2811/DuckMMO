"""Local filesystem backend. DB stores keys/metadata, never media bodies."""

import hashlib
import shutil
from uuid import UUID

from app.services.media_probe import MediaFailure


def file_digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


class LocalMediaStorage:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.artifact_dir.resolve()
        self.assets = self.root / "assets"
        self.assets.mkdir(parents=True, exist_ok=True)

    def asset_path(self, asset_id):
        return self.assets / str(UUID(str(asset_id)))

    def ensure_capacity(self, additional=0):
        # Hard-linked clip snapshots occupy disk once. Files may disappear during cleanup.
        used, seen = 0, set()
        for path in self.root.rglob("*"):
            try:
                if not path.is_file() or path.is_symlink():
                    continue
                info = path.stat()
            except FileNotFoundError:
                continue
            identity = (info.st_dev, info.st_ino)
            if identity not in seen:
                used += info.st_size
                seen.add(identity)
        free = shutil.disk_usage(self.root).free
        if used + additional > self.settings.media_storage_max_bytes:
            raise MediaFailure("Kho local đã đạt giới hạn. Dọn dữ liệu trước khi tải/dựng thêm.")
        if free - additional < self.settings.media_min_free_bytes:
            raise MediaFailure("Ổ đĩa sắp đầy. Dọn dữ liệu trước khi tải/dựng thêm.")

    def verify(self, asset):
        path = self.asset_path(asset.id)
        if not path.is_file() or file_digest(path) != asset.sha256:
            raise MediaFailure("File nguồn bị thiếu hoặc đã đổi. Hãy tải lại.")
        return path
