"""Canonical narration and fingerprint shared by review, rendering and quality."""

import hashlib


def content_text(package):
    return package.get("video_content") or "\n\n".join(
        scene["narration"] for scene in package.get("scenes", [])
    )


def content_hash(package):
    return hashlib.sha256(content_text(package).encode()).hexdigest()
