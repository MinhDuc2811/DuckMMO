"""Shared change inventory and exact-tree fingerprints for commit and impact reviews."""

import hashlib
import json
from pathlib import Path

try:
    from .review_code import ROOT, git, snapshot
except ImportError:
    from review_code import ROOT, git, snapshot


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def changed_files(before, after):
    return [
        {
            "path": path,
            "status": "created"
            if path not in before
            else "deleted"
            if path not in after
            else "modified",
        }
        for path in sorted(before.keys() | after.keys())
        if before.get(path) != after.get(path)
        or getattr(before, "modes", {}).get(path) != getattr(after, "modes", {}).get(path)
    ]


def fingerprint(before, after):
    digest = hashlib.sha256(b"duckmmo-change-review-v1")
    for label, files in (("before", before), ("after", after)):
        digest.update(label.encode())
        for path, source in sorted(files.items()):
            digest.update(
                encoded(
                    [
                        path,
                        getattr(files, "modes", {}).get(path, "100644"),
                        hashlib.sha256(source).hexdigest(),
                    ]
                )
            )
    return digest.hexdigest()


def local_directory(root=ROOT):
    common = Path(git("rev-parse", "--git-common-dir", root=root).decode().strip())
    return (root / common).resolve() / "change-reviews"


def comparison(base, head, root=ROOT):
    before, after = snapshot(base, root), snapshot(head, root)
    return before, after
