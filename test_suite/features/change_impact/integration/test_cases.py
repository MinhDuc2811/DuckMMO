"""Real Git commit hook and SSH verification, using disposable keys/repos only."""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from scripts.change_review import encoded, local_directory
from scripts.review_code import git, snapshot
from scripts.review_impact import approval_request, assess, verify_approval
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


def test_real_ssh_signature_required_and_tampering_or_expiry_rejected(tmp_path):
    key = tmp_path / "fixture-key"
    generated = command(tmp_path, "ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key))
    assert generated.returncode == 0, generated.stderr
    signers = tmp_path / "allowed_signers"
    signers.write_text("human-fixture " + key.with_suffix(".pub").read_text())
    report = assess({}, {"app/contracts/new.py": b"x = 1"})
    payload = tmp_path / f"{report['fingerprint']}.json"
    now = datetime.now(timezone.utc)
    entry = approval_request(report, "human-fixture", now=now)
    payload.write_bytes(encoded(entry))
    assert verify_approval(report, tmp_path, signers, now=now) is None  # Unsigned is not approval.
    signed = command(
        tmp_path,
        "ssh-keygen",
        "-Y",
        "sign",
        "-f",
        str(key),
        "-n",
        "duckmmo-impact-review",
        str(payload),
    )
    assert signed.returncode == 0, signed.stderr
    assert verify_approval(report, tmp_path, signers, now=now)["reviewer"] == "human-fixture"
    assert verify_approval(report, tmp_path, signers, now=now + timedelta(days=8)) is None
    changed = assess({}, {"app/contracts/new.py": b"x = 2"})
    assert verify_approval(changed, tmp_path, signers, now=now) is None
    entry["reviewer"] = "someone-else"
    payload.write_bytes(encoded(entry))
    assert verify_approval(report, tmp_path, signers, now=now) is None
