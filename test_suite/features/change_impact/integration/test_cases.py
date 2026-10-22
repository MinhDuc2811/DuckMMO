"""Real Git commit hook and user confirmation, using disposable repositories."""

import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta

import pytest

from scripts.change_review import local_directory
from scripts.review_code import git, snapshot
from scripts.review_impact import assess, confirmation_record, save_confirmation, verify_approval
from test_suite.support.paths import PROJECT_ROOT


@pytest.fixture
def repository(tmp_path):
    git("init", "-q", root=tmp_path)
    git("config", "user.name", "Fixture", root=tmp_path)
    git("config", "user.email", "fixture@example.invalid", root=tmp_path)
    destination = tmp_path / "scripts"
    destination.mkdir()
    for name in ("commit_review.py", "review_impact.py", "change_review.py", "review_code.py"):
        shutil.copyfile(PROJECT_ROOT / "scripts" / name, destination / name)
    git("add", ".", root=tmp_path)
    git("commit", "-qm", "fixture baseline", root=tmp_path)
    path = tmp_path / "docs/new.md"
    path.parent.mkdir()
    path.write_text("first version")
    git("add", "docs/new.md", root=tmp_path)
    return tmp_path


def command(root, *args):
    return subprocess.run(
        [*args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    )


def test_real_commit_keeps_review_body_and_staged_changes_invalidate_it(repository):
    root = repository
    hook = root / ".git/hooks/commit-msg"
    hook.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" scripts/commit_review.py --message-file "$1"\n'
    )
    hook.chmod(0o755)
    before = git("rev-parse", "HEAD", root=root)
    blocked = command(root, "git", "commit", "-m", "Describe docs")
    assert blocked.returncode != 0 and "Commit blocked" in (blocked.stdout + blocked.stderr)
    assert git("rev-parse", "HEAD", root=root) == before
    assert command(root, sys.executable, "scripts/commit_review.py", "--prepare").returncode == 0
    path = next((local_directory(root) / "commits").glob("*.json"))
    record = json.loads(path.read_text())
    record.update(
        summary="Describe the new documentation",
        reason="Explain the change clearly so a later revert is understandable.",
    )
    record["files"][0].update(
        what="Add documentation explaining impact checks",
        why="Allow maintainers to understand the review process",
    )
    path.write_text(json.dumps(record))
    result = command(root, "git", "commit", "-m", "Document impact checks")
    assert result.returncode == 0, result.stdout + result.stderr
    message = git("log", "-1", "--format=%B", root=root).decode()
    assert "What changed:" in message and "Where:" in message and "Why:" in message
    assert record["reason"] in message and record["fingerprint"] in message
    assert snapshot("HEAD", root)["docs/new.md"] == b"first version"
    (root / "docs/new.md").write_text("second version")
    git("add", ".", root=root)
    assert command(root, "git", "commit", "-m", "Unreviewed change").returncode != 0


def test_staged_review_ignores_unstaged_bytes_and_inherited_git_env(repository, monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/not/the/fixture/repository")
    (repository / "docs/new.md").write_text("unstaged change")
    assert snapshot("STAGED", repository)["docs/new.md"] == b"first version"
    assert snapshot("WORKTREE", repository)["docs/new.md"] == b"unstaged change"


def test_user_confirmation_requires_complete_matching_approved_record(tmp_path):
    report = assess({}, {"app/contracts/new.py": b"x = 1"})
    today = date.today()
    entry = confirmation_record(
        report,
        "human-fixture",
        "approved",
        today.isoformat(),
        "The complete contract change shown in review",
        "User explicitly approved this change in the chat",
    )
    assert verify_approval(report, tmp_path) is None
    save_confirmation(entry, tmp_path)
    assert verify_approval(report, tmp_path)["username"] == "human-fixture"
    changed = assess({}, {"app/contracts/new.py": b"x = 2"})
    assert verify_approval(changed, tmp_path) is None
    for override in (
        {"username": ""},
        {"scope": ""},
        {"status": "pending"},
        {"status": "rejected"},
        {"changed_files": []},
        {"review_date": (today + timedelta(days=1)).isoformat()},
    ):
        save_confirmation({**entry, **override}, tmp_path)
        assert verify_approval(report, tmp_path) is None
    assert len((tmp_path / "confirmations/history.jsonl").read_text().splitlines()) == 7
