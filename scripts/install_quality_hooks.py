"""Install repository-local hooks without replacing an existing custom hook setup."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
result = subprocess.run(
    ["git", "config", "--get", "core.hooksPath"], cwd=ROOT, capture_output=True, text=True
)
existing = result.stdout.strip()
if existing and existing != ".githooks":
    raise SystemExit(f"Existing hooksPath {existing!r}; integrate .githooks manually.")
if not existing:
    hooks = subprocess.check_output(
        ["git", "rev-parse", "--git-path", "hooks"], cwd=ROOT, text=True
    ).strip()
    for name in ("pre-commit", "pre-push"):
        if (ROOT / hooks / name).exists():
            raise SystemExit(f"Existing {name} hook; integrate .githooks manually.")
subprocess.run(["git", "config", "--local", "core.hooksPath", ".githooks"], cwd=ROOT, check=True)
print("Installed pre-commit/pre-push hooks for this checkout.")
