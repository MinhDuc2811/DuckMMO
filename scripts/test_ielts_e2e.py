"""Run isolated IELTS prototype/browser checks with timestamped evidence.

Default 'all' includes the readiness gate: missing IELTS implementation is a failure.
No app/database arguments are accepted: fixtures always create their own local services.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FEATURE = "test_suite/features/ielts"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", choices=("all", "baseline", "readiness", "database", "library"), default="all"
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--browser-executable", type=Path, help="Use an installed Chromium binary")
    args = parser.parse_args()
    env = os.environ.copy()
    executable = args.browser_executable or env.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if executable:
        executable = Path(executable).resolve()
        if not executable.is_file():
            parser.error(f"Chromium executable does not exist: {executable}")
        env["PLAYWRIGHT_CHROMIUM_EXECUTABLE"] = str(executable)
    else:
        executable = shutil.which("chromium")
    if args.suite in ("all", "baseline", "library") and not shutil.which("ffprobe"):
        parser.error("ffprobe is required for video verification; install system FFmpeg first")
    paths = {
        "all": [FEATURE],
        "baseline": [f"{FEATURE}/e2e/test_video_baseline.py"],
        "readiness": [f"{FEATURE}/e2e/test_library_readiness.py"],
        "database": [f"{FEATURE}/integration"],
        "library": [f"{FEATURE}/api", f"{FEATURE}/e2e/test_library_flow.py"],
    }
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = ROOT / "test-results" / "ielts" / run_id
    output.mkdir(parents=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        *paths[args.suite],
        "--run-e2e",
        "--browser",
        "chromium",
        "--tracing",
        "on",
        "--screenshot",
        "on",
        "--video",
        "off",
        "--output",
        str(output / "browser"),
        "--junitxml",
        str(output / "results.xml"),
        "-q",
    ]
    if args.headed:
        command.append("--headed")
    result = {
        "suite": args.suite,
        "scope": (
            "Prototype + runtime library API/browser flow + English video baseline + readiness"
        ),
        "browser_executable": str(executable) if executable else "Playwright-managed Chromium",
        "speech": "synthetic PCM fixture; not real English TTS",
        "video_recording": "off; screenshots and traces enabled",
        "output": str(output),
        "started_at": datetime.now(UTC).isoformat(),
    }
    print(f"Evidence directory: {output}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, env=env)
    result["exit_code"] = completed.returncode
    result["finished_at"] = datetime.now(UTC).isoformat()
    (output / "run.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
