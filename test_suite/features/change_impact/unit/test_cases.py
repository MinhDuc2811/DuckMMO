"""Impact v1 boundaries, scope accounting and stale commit-review rejection."""

import pytest

from scripts.change_review import fingerprint
from scripts.commit_review import render, validate
from scripts.review_code import TreeSnapshot
from scripts.review_impact import assess


def files(count=100):
    return {f"docs/file-{index}.md": b"original" for index in range(count)}


@pytest.mark.parametrize(
    "changed,score,expected",
    [(19, 81, "low"), (20, 80, "medium"), (50, 50, "medium"), (51, 49, "high")],
)
def test_exact_impact_boundaries(changed, score, expected):
    before = files()
    after = {
        path: b"new" if index < changed else content
        for index, (path, content) in enumerate(before.items())
    }
    report = assess(before, after)
    assert report["score"] == score
    assert report["level"] == expected
    assert report["human_review_required"] == (score <= 80)


def test_additions_use_baseline_denominator_and_deletions_still_count():
    before = files()
    report = assess(before, {**before, "docs/new.md": b"new"})
    assert report["append_create_percent_v1"] == 1
    assert report["baseline_file_count"] == 100
    assert report["score"] == 99
    after = dict(before)
    del after["docs/file-0.md"]
    report = assess(before, after)
    assert report["append_create_percent_v1"] == 0
    assert report["effective_changed_percent"] == 1
    assert report["score"] == 99


def test_core_and_policy_changes_cannot_be_diluted_by_many_docs():
    before = files(1000)
    core = assess(before, {**before, "app/modules/content/service.py": b"changed = True"})
    assert core["level"] == "medium" and core["human_review_required"]
    assert core["core_paths"] == ["app/modules/content/service.py"]
    policy = assess(before, {**before, "scripts/check_quality.py": b"changed = True"})
    assert policy["level"] == "medium" and policy["policy_paths"]
    both = assess(
        before,
        {**before, "scripts/check_quality.py": b"policy", "app/contracts/content.py": b"core"},
    )
    assert both["level"] == "high"


def test_direct_dependants_are_reported_without_claiming_runtime_coverage():
    before = {
        "app/contracts/content.py": b"value = 1",
        "app/modules/content/service.py": b"from ...contracts.content import value",
    }
    after = {**before, "app/contracts/content.py": b"value = 2"}
    report = assess(before, after)
    assert report["direct_dependants"] == ["app/modules/content/service.py"]
    assert report["deductions"]["dependants"] == 2
    assert report["business_flow"]["status"] == "not_run"


def test_file_mode_changes_invalidate_review_and_count_as_changes():
    before = TreeSnapshot({"launch.sh": b"run"}, {"launch.sh": "100644"})
    after = TreeSnapshot({"launch.sh": b"run"}, {"launch.sh": "100755"})
    assert fingerprint(before, after) != fingerprint(before, before)
    assert assess(before, after)["changed_file_count"] == 1


def test_commit_description_covers_every_file_and_is_bound_to_actual_change():
    report = assess({}, {"docs/readme.md": b"new"})
    record = {
        "fingerprint": report["fingerprint"],
        "summary": "Document change impact review",
        "reason": "Make changes traceable before a future revert is necessary.",
        "files": [
            {
                "path": "docs/readme.md",
                "what": "Describe the scoring formula",
                "why": "Make review rules understandable",
            }
        ],
    }
    assert validate(record, report) is record
    message = render(record, report)
    assert all(section in message for section in ("What changed:", "Where:", "Why:", "Impact:"))
    assert record["reason"] in message and report["fingerprint"] in message
    with pytest.raises(ValueError, match="stale"):
        validate(record, assess({}, {"docs/readme.md": b"different"}))
    record["files"] = []
    with pytest.raises(ValueError, match="every staged file"):
        validate(record, report)


def test_playwright_failure_is_reported_and_cannot_be_overridden_by_approval(monkeypatch, tmp_path):
    import importlib
    import json
    import subprocess

    from test_suite.support.paths import PROJECT_ROOT

    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    gate = importlib.import_module("check_quality")
    before = {"ui/screens/new.py": b"value = 1"}
    after = {"ui/screens/new.py": b"value = 2"}
    monkeypatch.setattr(gate, "comparison", lambda *_args: (before, after))
    monkeypatch.setattr(gate, "local_directory", lambda: tmp_path)
    monkeypatch.setattr(gate, "migration_check", lambda *_args: None)
    calls = []

    def run(*args):
        calls.append(args)
        if "--run-e2e" in args:
            raise subprocess.CalledProcessError(1, ["pytest", "--run-e2e"])

    monkeypatch.setattr(gate, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        gate.checks("base", "head", True, enforce_impact=True)
    report = json.loads(next((tmp_path / "reports").glob("*.json")).read_text())
    assert report["business_flow"]["checks"]["offline_tests"] == "passed"
    assert report["business_flow"]["checks"]["playwright"] == "failed_or_unavailable"
    assert report["business_flow"]["status"] == "failed_or_unavailable"
    assert report["gate_status"] == "blocked"
    assert not any("--enforce" in call for call in calls)


def test_missing_human_approval_does_not_relabel_successful_tests_as_failed(monkeypatch, tmp_path):
    import importlib
    import json
    import subprocess

    from test_suite.support.paths import PROJECT_ROOT

    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    gate = importlib.import_module("check_quality")
    monkeypatch.setattr(gate, "comparison", lambda *_args: ({}, {"app/contracts/new.py": b"x = 1"}))
    monkeypatch.setattr(gate, "local_directory", lambda: tmp_path)
    monkeypatch.setattr(gate, "migration_check", lambda *_args: None)

    def run(*args):
        if "--enforce" in args:
            raise subprocess.CalledProcessError(1, ["review_impact", "--enforce"])

    monkeypatch.setattr(gate, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        gate.checks("base", "head", True, enforce_impact=True)
    report = json.loads(next((tmp_path / "reports").glob("*.json")).read_text())
    assert report["business_flow"]["status"] == "passed_for_tested_scope"
    assert report["gate_status"] == "blocked"
