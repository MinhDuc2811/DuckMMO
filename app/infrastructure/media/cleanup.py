"""Explicit local retention. Dry-run by default; current runs/assets are retained."""

import argparse
import shutil
import time
from uuid import UUID

from sqlalchemy import select

from app.config import Settings
from app.db import Job, MediaAsset, make_engine, make_sessions
from app.infrastructure.local_lock import exclusive_lock
from app.infrastructure.media.storage import LocalMediaStorage


def cleanup(storage, sessions, *, apply=False, older_than_days=7):
    cutoff = time.time() - older_than_days * 86400
    candidates = []
    with exclusive_lock(storage.root / ".media.lock"):
        with sessions() as session:
            asset_ids = set(session.scalars(select(MediaAsset.id)))
            retained = {
                (job.id, config["run_id"])
                for job in session.scalars(select(Job))
                for config in (job.render_config, job.video)
                if config and config.get("run_id")
            }
        for job_dir in storage.root.iterdir():
            if not job_dir.is_dir() or job_dir.is_symlink():
                continue
            try:
                UUID(job_dir.name)
            except ValueError:
                continue
            for run_dir in job_dir.iterdir():
                if not run_dir.is_dir() or run_dir.is_symlink():
                    continue
                try:
                    UUID(run_dir.name)
                except ValueError:
                    continue
                if (
                    job_dir.name,
                    run_dir.name,
                ) not in retained and run_dir.stat().st_mtime < cutoff:
                    candidates.append(run_dir)
        candidates.extend(
            p
            for p in storage.assets.glob("*.part")
            if not p.is_symlink() and p.stat().st_mtime < cutoff
        )
        for path in storage.assets.iterdir():
            if not path.is_file() or path.is_symlink() or path.name in asset_ids:
                continue
            try:
                UUID(path.name)
            except ValueError:
                continue
            if path.stat().st_mtime < cutoff:
                candidates.append(path)
        if apply:
            for path in candidates:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete the listed stale files")
    args = parser.parse_args()
    settings = Settings()
    storage = LocalMediaStorage(settings)
    engine = make_engine(settings.database_url)
    try:
        # Never race supervisor recovery or active rendering.
        with exclusive_lock(storage.root / ".worker.lock"):
            for path in cleanup(storage, make_sessions(engine), apply=args.apply):
                print(path)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
