"""Regression tests for enforcement, diff scope and change-bound exceptions."""

import json
import os
import subprocess
from datetime import date, timedelta

from scripts.review_code import analyze, exception_reason, snapshot


def review(source, before=None):
    return analyze(before or {}, {"app/modules/example.py": source.encode()})


def waiver(report, **updates):
    entry = {
        "fingerprint": report["fingerprint"],
        "owner": "Maintainer",
        "expires": (date.today() + timedelta(days=7)).isoformat(),
        "reason": "This isolated provider needs different retry semantics for its transport.",
        "common_considered": "The shared HTTP adapter was evaluated against the provider protocol.",
        "why_not_reuse": "Its streaming handshake cannot use the current shared request interface.",
        "risk_and_validation": "Contract/timeout tests cover both the existing and new providers.",
    }
    entry.update(updates)
    return json.dumps({"exceptions": [entry]})


def test_seventy_requires_exception():
    report = review("a = media_path.read_bytes()\nb = media_path.read_bytes()\n")
    assert report["score"] == 70
    assert not report["score"] > 70  # Strict threshold, not >= 70.
    assert exception_reason(report, b"{}") is None
    assert exception_reason(report, waiver(report)) is not None


def test_baseline_debt_does_not_block_unrelated_change_but_new_instances_count():
    source = "a = media_path.read_bytes()\n"
    before = {"app/modules/example.py": source.encode()}
    assert review(source + "value = 1\n", before)["score"] == 100
    report = review(source + "b = media_path.read_bytes()\n", before)
    assert report["score"] == 85
    assert len(report["findings"]) == 1


def test_shared_import_passes_and_framework_dependency_is_reported():
    report = review("from app.contracts.content import content_hash\n")
    assert report["score"] == 100
    report = review("from fastapi import HTTPException\n")
    assert report["findings"][0]["rule"] == "dependency-boundary"
    assert report["score"] == 80


def test_duplicate_function_in_other_module_has_evidence():
    source = b"""def transform(items):
    result = []
    for item in items:
        if item > 0:
            result.append(item * 2)
        else:
            result.append(0)
    return result
"""
    before = {"app/contracts/shared.py": source}
    report = analyze(before, {**before, "app/modules/copy.py": source})
    assert report["score"] == 85
    assert "app/contracts/shared.py" in report["findings"][0]["message"]


def test_alias_and_relative_imports_cannot_bypass_boundaries():
    report = review("from ..api.dependencies import get_session as session\n")
    assert report["findings"][0]["rule"] == "dependency-boundary"
    report = analyze({}, {"ui/screens/new.py": b'import httpx as net\nnet.get("url")\n'})
    assert report["findings"][0]["rule"] == "ui-http-client"


def test_exception_rejects_stale_expired_or_empty_reason():
    report = review("a = media_path.read_bytes()\nb = media_path.read_bytes()\n")
    for update in (
        {"fingerprint": "old"},
        {"reason": "because"},
        {"owner": ""},
        {"expires": "2000-01-01"},
        {"expires": "2999-01-01"},
    ):
        assert exception_reason(report, waiver(report, **update)) is None
    assert exception_reason(report, b"{invalid") is None
    changed = review("a = media_path.read_bytes()\nb = media_path.read_bytes()\nx = 1\n")
    assert exception_reason(changed, waiver(report)) is None


def test_committed_snapshot_does_not_review_dirty_worktree(tmp_path, monkeypatch):
    from scripts.review_code import ROOT

    monkeypatch.setenv("GIT_DIR", str(ROOT / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(ROOT))

    def git(*args):
        return subprocess.check_output(
            ["git", *args],
            cwd=tmp_path,
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        )

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    path = tmp_path / "app/example.py"
    path.parent.mkdir()
    path.write_text("value = 1\n")
    git("add", ".")
    git("commit", "-qm", "baseline")
    path.write_text("value = 2\n")
    (path.parent / "new.py").write_text("value = 3\n")
    assert snapshot("HEAD", tmp_path)["app/example.py"] == b"value = 1\n"
    assert snapshot("WORKTREE", tmp_path)["app/new.py"] == b"value = 3\n"


def test_cli_rejects_low_score_accepts_reason_and_preserves_original_score(monkeypatch, tmp_path):
    from scripts import review_code

    before = {}
    after = {
        "app/modules/example.py": b"a = media_path.read_bytes()\nb = media_path.read_bytes()\n"
    }
    monkeypatch.setattr(review_code, "snapshot", lambda ref: before if ref == "base" else after)
    output = tmp_path / "report.json"
    args = ["--base", "base", "--head", "tip", "--output", str(output)]
    assert review_code.main(args) == 1
    report = json.loads(output.read_text())
    assert report["score"] == 70 and not report["allowed"]
    after[review_code.EXCEPTIONS] = waiver(report).encode()
    assert review_code.main(args) == 0
    approved = json.loads(output.read_text())
    assert approved["score"] == 70 and approved["exception"]["owner"] == "Maintainer"
    after["app/modules/example.py"] += b"changed = True\n"
    assert review_code.main(args) == 1


def test_cli_high_score_and_invalid_base(monkeypatch):
    from scripts import review_code

    monkeypatch.setattr(review_code, "snapshot", lambda _ref: {})
    assert review_code.main([]) == 0

    def invalid(_ref):
        raise subprocess.CalledProcessError(128, ["git", "show"])

    monkeypatch.setattr(review_code, "snapshot", invalid)
    assert review_code.main([]) == 2


def test_push_gate_checks_actual_commit_and_propagates_failure(monkeypatch):
    import importlib
    import io
    import sys
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    gate = importlib.import_module("check_quality")
    head = "a" * 40
    remote = "b" * 40
    calls = []

    def git(*args):
        if args[0] == "status":
            return b""
        if args[0] == "rev-parse":
            return head.encode()
        assert args == ("merge-base", remote, head)
        return b"baseline"

    monkeypatch.setattr(gate, "git", git)
    monkeypatch.setattr(sys, "argv", ["check_quality.py", "push"])
    line = f"refs/heads/main {head} refs/heads/main {remote}\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(line))
    monkeypatch.setattr(gate, "checks", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert gate.main() == 0
    assert calls == [(("baseline", head), {"full": True})]

    def fail(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["pytest"])

    monkeypatch.setattr(gate, "checks", fail)
    monkeypatch.setattr(sys, "stdin", io.StringIO(line))
    assert gate.main() == 1
    monkeypatch.setattr(gate, "git", lambda *_args: b" M app/example.py")
    assert gate.main() == 1


def test_commit_gate_rejects_partially_staged_python(monkeypatch):
    import importlib
    import sys
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    gate = importlib.import_module("check_quality")
    monkeypatch.setattr(sys, "argv", ["check_quality.py", "commit"])
    monkeypatch.setattr(gate, "git", lambda *_args: b"app/example.py\0")
    assert gate.main() == 1


def test_check_runner_removes_hook_git_environment(monkeypatch):
    import importlib
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    gate = importlib.import_module("check_quality")
    monkeypatch.setenv("GIT_DIR", "/foreign/repository")
    monkeypatch.setenv("GIT_INDEX_FILE", "/foreign/index")
    received = {}
    monkeypatch.setattr(gate.subprocess, "run", lambda *_args, **kwargs: received.update(kwargs))
    gate.run("python", "-m", "pytest")
    assert not any(key.startswith("GIT_") for key in received["env"])
