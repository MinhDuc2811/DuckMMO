"""Shared quality checks used by hooks and CI. Run with uv run python."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from change_review import comparison, local_directory
from review_code import ROOT, git, snapshot
from review_impact import assess


def run(*args, cwd=ROOT, env=None):
    print("+ " + " ".join(map(str, args)), flush=True)
    isolated = {
        key: value for key, value in (env or os.environ).items() if not key.startswith("GIT_")
    }
    subprocess.run(list(map(str, args)), cwd=cwd, env=isolated, check=True)


def migration_check(base):
    """Test a fresh database and an actual upgrade of the baseline schema."""
    with tempfile.TemporaryDirectory(prefix="duckmmo-quality-") as directory:
        root = Path(directory)
        env = {**os.environ, "STUDIO_ARTIFACT_DIR": str(root / "artifacts")}
        for name in ("fresh", "upgrade"):
            env["STUDIO_DATABASE_URL"] = "sqlite:///" + (root / f"{name}.sqlite").as_posix()
            baseline = snapshot(base) if name == "upgrade" else {}
            if name == "upgrade" and "alembic.ini" not in baseline:
                print(
                    "Baseline has no Alembic project; verifying fresh schema initialization.",
                    flush=True,
                )
            if name == "upgrade" and "alembic.ini" in baseline:
                previous = root / "baseline"
                previous.mkdir()
                for path, data in baseline.items():
                    if path.startswith(("app/", "migrations/")) or path == "alembic.ini":
                        target = previous / path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                run(
                    sys.executable,
                    "-m",
                    "alembic",
                    "upgrade",
                    "head",
                    cwd=previous,
                    env={**env, "PYTHONPATH": str(previous)},
                )
            run(sys.executable, "-m", "alembic", "upgrade", "head", env=env)


def checks(base, head, full, *, enforce_impact=False):
    report = assess(*comparison(base, head)) if full else None
    if report:
        report["business_flow"] = {"status": "not_run", "checks": {}}
    directory = local_directory() / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        run(sys.executable, "-m", "ruff", "check", ".")
        run(sys.executable, "-m", "ruff", "format", "--check", ".")
        run("git", "diff", "--check")
        run("git", "diff", "--cached", "--check")
        if full:
            run(sys.executable, ROOT / "scripts/review_code.py", "--base", base, "--head", head)
            status = report["business_flow"]["checks"]
            status["offline_tests"] = "running"
            run(sys.executable, "-m", "pytest", "-q", "-m", "not live")
            status["offline_tests"] = "passed"
            status["migrations"] = "running"
            migration_check(base)
            status["migrations"] = "passed"
            if report["flow_tests_required"] and enforce_impact:
                status["playwright"] = "running"
                run(
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "e2e/test_media_upload.py",
                    "test_suite/features/speech/e2e",
                    "--run-e2e",
                    "--tracing",
                    "retain-on-failure",
                    "--screenshot",
                    "only-on-failure",
                )
                status["playwright"] = "passed"
            elif report["flow_tests_required"]:
                status["playwright"] = "not_run_here; required in CI browser step"
            report["business_flow"]["status"] = (
                "passed_for_tested_scope"
                if status.get("playwright") == "passed"
                else "partial; no browser evidence in this step"
            )
            command = [
                sys.executable,
                ROOT / "scripts/review_impact.py",
                "--base",
                base,
                "--head",
                head,
            ]
            if enforce_impact:
                command.append("--enforce")
            run(*command)
            report["gate_status"] = "passed"
        else:
            run(sys.executable, ROOT / "scripts/commit_review.py")
    except (subprocess.CalledProcessError, OSError):
        if report:
            report["gate_status"] = "blocked"
            if any(value == "running" for value in report["business_flow"]["checks"].values()):
                report["business_flow"]["status"] = "failed_or_unavailable"
            for name, value in report["business_flow"]["checks"].items():
                if value == "running":
                    report["business_flow"]["checks"][name] = "failed_or_unavailable"
        raise
    finally:
        if report:
            path = directory / f"{report['fingerprint']}.json"
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(f"Impact and flow report: {path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("commit", "push", "ci"))
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    try:
        if args.mode == "push":
            # Tests must run against the exact code being pushed.
            if git("status", "--porcelain").strip():
                raise ValueError("Push blocked: commit or stash working tree changes first.")
            current = git("rev-parse", "HEAD").decode().strip()
            targets = []
            for line in sys.stdin:
                local_ref, local_sha, remote_ref, remote_sha = line.split()
                if local_sha == "0" * 40:  # Branch deletion has no code to review.
                    continue
                if local_sha != current:
                    raise ValueError(
                        f"Checkout {local_ref} before pushing it; cannot test another tree."
                    )
                if not remote_ref.startswith("refs/heads/"):
                    raise ValueError("Push tags separately after the branch has passed checks.")
                base = (
                    remote_sha
                    if remote_ref == "refs/heads/main" and remote_sha != "0" * 40
                    else args.base
                )
                targets.append((git("merge-base", base, local_sha).decode().strip(), local_sha))
            if not targets:
                return 0
            # Include all outgoing branch changes relative to main, not just the last commit.
            for base, head in sorted(set(targets)):
                checks(base, head, full=True, enforce_impact=True)
        else:
            if args.mode == "commit":
                staged = set(git("diff", "--cached", "--name-only", "-z").split(b"\0"))
                unstaged = set(git("diff", "--name-only", "-z").split(b"\0"))
                if any(path.endswith(b".py") for path in staged & unstaged):
                    raise ValueError(
                        "Partial-staged Python differs from tested worktree; stage it fully."
                    )
            checks(args.base, args.head, full=args.mode == "ci")
        return 0
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        print(f"Quality check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
