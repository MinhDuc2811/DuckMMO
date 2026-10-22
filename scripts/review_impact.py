"""Impact score v1: 100 means low potential impact. Tests decide observed flow status.

Medium/high changes require a human SSH signature before push. No self-approval flag.
"""

import argparse
import ast
import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from .change_review import (
        changed_files,
        comparison,
        encoded,
        fingerprint,
        local_directory,
    )
except ImportError:
    from change_review import changed_files, comparison, encoded, fingerprint, local_directory

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
    "reviewers.allowed_signers",
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


def approval_request(report, reviewer, now=None):
    now = now or datetime.now(timezone.utc)
    return {
        "fingerprint": report["fingerprint"],
        "reviewer": reviewer,
        "decision": "approve",
        "score": report["score"],
        "level": report["level"],
        "approved_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    }


def verify_approval(report, directory, signers, now=None):
    """Trust configured SSH public keys, never an unsigned approved=true in the repository."""
    try:
        payload = directory / f"{report['fingerprint']}.json"
        signature = payload.with_suffix(".json.sig")
        data = payload.read_bytes()
        entry = json.loads(data)
        now = now or datetime.now(timezone.utc)
        created, expiry = (
            datetime.fromisoformat(entry[key]) for key in ("approved_at", "expires_at")
        )
        if (
            entry["fingerprint"] != report["fingerprint"]
            or entry["decision"] != "approve"
            or entry["score"] != report["score"]
            or entry["level"] != report["level"]
            or not isinstance(entry["reviewer"], str)
            or not entry["reviewer"].strip()
            or not created <= now <= expiry
            or expiry - created > timedelta(days=7)
        ):
            return None
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                str(signers),
                "-I",
                entry["reviewer"],
                "-n",
                "duckmmo-impact-review",
                "-s",
                str(signature),
            ],
            input=data,
            capture_output=True,
            timeout=10,
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        )
        return entry if result.returncode == 0 else None
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="WORKTREE")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--enforce", action="store_true", help="Require signed review for medium/high"
    )
    parser.add_argument("--request-for", help="Generate an unsigned request; this is NOT approval")
    args = parser.parse_args(argv)
    try:
        before, after = comparison(args.base, args.head)
        report = assess(before, after)
        directory = local_directory()
        if args.request_for:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{report['fingerprint']}.json"
            if path.exists():
                raise ValueError(f"Request already exists; inspect before replacing: {path}")
            path.write_bytes(encoded(approval_request(report, args.request_for)) + b"\n")
            print(f"Unsigned request: {path}; human must review and sign it.")
        # Public keys are provisioned outside the proposed diff, or from the trusted baseline.
        with tempfile.TemporaryDirectory(prefix="impact-signers-") as temporary:
            signers = directory / "allowed_signers"
            if not signers.exists():
                signers = Path(temporary) / "allowed_signers"
                signers.write_bytes(before.get("reviewers.allowed_signers", b""))
            report["approval"] = verify_approval(report, directory, signers)
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
