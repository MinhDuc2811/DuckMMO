"""Impact score v1: 100 means low potential impact. Tests decide observed flow status.

Medium/high changes require an explicit user confirmation for the exact change before push.
"""

import argparse
import ast
import json
import subprocess
from datetime import date
from pathlib import Path

try:
    from .change_review import (
        changed_files,
        comparison,
        fingerprint,
        local_directory,
    )
except ImportError:
    from change_review import changed_files, comparison, fingerprint, local_directory

CORE_PREFIXES = (
    "app/contracts/",
    "app/modules/",
    "app/pipeline/",
    "app/services/",
    "app/publishing/",
    "app/infrastructure/",
)
CORE_FILES = {
    "app/schemas.py",
    "app/config.py",
    "app/db.py",
    "app/worker.py",
    "app/bootstrap.py",
    "app/main.py",
    "app/api/dependencies.py",
    "uv.lock",
}
POLICY_PREFIXES = (".github/", ".githooks/", "scripts/", "test_suite/pytest_plugin")
POLICY_FILES = {
    "AGENTS.md",
    "test_suite/AGENTS.md",
    "pyproject.toml",
    "conftest.py",
    "pytest.ini",
    "setup.cfg",
    "tox.ini",
}


def level(score):
    return "low" if score > 80 else "medium" if score >= 50 else "high"


def dependants(before, after, paths):
    """Conservative direct-import fanout; not a complete runtime call graph."""
    modules = {
        path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
        for path in paths
        if path.endswith(".py")
    }
    result = set()
    for files in (before, after):
        for path, source in files.items():
            if path in paths or not path.endswith(".py") or not path.startswith(("app/", "ui/")):
                continue
            try:
                tree = ast.parse(source)
            except (SyntaxError, ValueError):
                continue
            for node in ast.walk(tree):
                imported = []
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    package = path.removesuffix(".py").split("/")[:-1]
                    prefix = package[: len(package) - node.level + 1] if node.level else []
                    module = ".".join(prefix + [node.module or ""]).rstrip(".")
                    imported = [module, *(f"{module}.{alias.name}" for alias in node.names)]
                if any(
                    name == mod or name.startswith(mod + ".")
                    for name in imported
                    for mod in modules
                ):
                    result.add(path)
    return sorted(result)


def assess(before, after):
    changes = changed_files(before, after)
    paths = {entry["path"] for entry in changes}
    total = max(1, len(before))  # Stable baseline denominator; no dilution by adding filler files.
    added_modified = sum(entry["status"] != "deleted" for entry in changes)
    raw_percent = 100 * added_modified / total
    effective_percent = 100 * len(changes) / total  # Deletions/renames must not escape scoring.
    core = sorted(p for p in paths if p.startswith(CORE_PREFIXES) or p in CORE_FILES)
    policy = sorted(
        p
        for p in paths
        if p.startswith(POLICY_PREFIXES)
        or p in POLICY_FILES
        or Path(p).name in ("AGENTS.md", "conftest.py")
    )
    affected = dependants(before, after, paths)
    penalties = {
        "file_scope": min(100, effective_percent),
        "core": 30 if core else 0,
        "dependants": min(20, 2 * len(affected)),
        "policy": 30 if policy else 0,
    }
    score = round(max(0, 100 - sum(penalties.values())), 2)
    flow = any(
        p.startswith(
            ("app/", "ui/", "test_suite/", "tests/", "e2e/", ".github/", ".githooks/", "scripts/")
        )
        or p in POLICY_FILES
        or p == "uv.lock"
        for p in paths
    )
    return {
        "version": 1,
        "fingerprint": fingerprint(before, after),
        "score": score,
        "level": level(score),
        "human_review_required": score <= 80,
        "baseline_file_count": len(before),
        "append_create_file_count": added_modified,
        "append_create_percent_v1": round(raw_percent, 4),
        "changed_file_count": len(changes),
        "effective_changed_percent": round(effective_percent, 4),
        "changes": changes,
        "core_paths": core,
        "policy_paths": policy,
        "direct_dependants": affected,
        "deductions": {k: round(v, 4) for k, v in penalties.items()},
        "flow_tests_required": flow,
        "business_flow": {"status": "not_run", "note": "Test/Playwright evidence required"},
        "limits": "Static potential impact only; tests cannot prove every business flow.",
    }


def confirmation_record(report, username, status, review_date, scope, confirmation):
    """Record a real user decision; this is an audit record, not identity authentication."""
    return {
        "fingerprint": report["fingerprint"],
        "username": username,
        "status": status,
        "review_date": review_date,
        "scope": scope,
        "changed_files": [entry["path"] for entry in report["changes"]],
        "score": report["score"],
        "level": report["level"],
        "confirmation": confirmation,
    }


def valid_confirmation(entry, report, today=None):
    today = today or date.today()
    if not isinstance(entry, dict):
        return False
    try:
        reviewed = date.fromisoformat(entry["review_date"])
        required_text = {"username": 1, "scope": 10, "confirmation": 10}
        return (
            all(
                isinstance(entry.get(key), str) and len(entry[key].strip()) >= minimum
                for key, minimum in required_text.items()
            )
            and entry["status"] == "approved"
            and reviewed <= today
            and entry["fingerprint"] == report["fingerprint"]
            and entry["score"] == report["score"]
            and entry["level"] == report["level"]
            and entry["changed_files"] == [item["path"] for item in report["changes"]]
        )
    except (ValueError, TypeError, KeyError):
        return False


def verify_approval(report, directory, today=None):
    try:
        path = directory / "confirmations" / f"{report['fingerprint']}.json"
        entry = json.loads(path.read_text(encoding="utf-8"))
        return entry if valid_confirmation(entry, report, today) else None
    except (OSError, ValueError, TypeError):
        return None


def save_confirmation(entry, directory):
    folder = directory / "confirmations"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{entry['fingerprint']}.json"
    serialized = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    # Keep earlier decisions when the human updates approved/rejected/pending status.
    with (folder / "history.jsonl").open("a", encoding="utf-8") as history:
        history.write(serialized + "\n")
    path.write_text(serialized + "\n", encoding="utf-8")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="WORKTREE")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--enforce", action="store_true", help="Require user confirmation for medium/high"
    )
    parser.add_argument(
        "--confirm-user", help="Username of the user who explicitly reviewed this change"
    )
    parser.add_argument("--status", choices=("approved", "rejected", "pending"))
    parser.add_argument("--review-date", help="Review date YYYY-MM-DD")
    parser.add_argument("--scope", help="Human-readable scope actually confirmed by the user")
    parser.add_argument(
        "--confirmation", help="Actual confirmation text/source; never invent approval"
    )
    args = parser.parse_args(argv)
    try:
        before, after = comparison(args.base, args.head)
        report = assess(before, after)
        directory = local_directory()
        fields = (args.confirm_user, args.status, args.review_date, args.scope, args.confirmation)
        if any(field is not None for field in fields):
            if not all(fields):
                raise ValueError(
                    "Supply username, status, review date, scope and confirmation text."
                )
            entry = confirmation_record(report, *fields)
            # Validate complete records even for an explicitly rejected/pending decision.
            candidate = {**entry, "status": "approved"}
            if not valid_confirmation(candidate, report):
                raise ValueError("Invalid confirmation: check date, username and scope text.")
            path = save_confirmation(entry, directory)
            print(f"User review recorded: {path}")
        report["approval"] = verify_approval(report, directory)
        report["allowed"] = not report["human_review_required"] or report["approval"] is not None
        output = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0 if not args.enforce or report["allowed"] else 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Impact review blocked: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
