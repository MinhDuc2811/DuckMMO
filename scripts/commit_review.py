"""Review staged changes before commit; preserve what/where/why in the commit body."""

import argparse
import json
import subprocess
from pathlib import Path

try:
    from .change_review import comparison, local_directory
    from .review_impact import assess
except ImportError:
    from change_review import comparison, local_directory
    from review_impact import assess


def validate(record, report):
    if not isinstance(record, dict):
        raise ValueError("Review must be a JSON object.")
    if record.get("fingerprint") != report["fingerprint"]:
        raise ValueError("Review is stale: staged files or baseline changed; review again.")
    for field, minimum in (("summary", 10), ("reason", 20)):
        if not isinstance(record.get(field), str) or len(record[field].strip()) < minimum:
            raise ValueError(f"Review needs a meaningful {field} (at least {minimum} characters).")
    files = record.get("files", [])
    if not isinstance(files, list) or not all(isinstance(item, dict) for item in files):
        raise ValueError("Review files must be a list of file descriptions.")
    expected = {change["path"] for change in report["changes"]}
    if len(files) != len(expected) or {item.get("path") for item in files} != expected:
        raise ValueError("Review must describe every staged file exactly once.")
    for item in files:
        for field in ("what", "why"):
            if not isinstance(item.get(field), str) or len(item[field].strip()) < 10:
                raise ValueError(
                    f"Explain {field} for {item.get('path')} (at least 10 characters)."
                )
    return record


def render(record, report):
    lines = ["Summary: " + record["summary"], "", "What changed:"]
    lines += [f"- {item['path']}: {item['what']}" for item in record["files"]]
    lines += ["", "Where:"]
    lines += [f"- {item['status']}: {item['path']}" for item in report["changes"]]
    lines += ["", "Why:", record["reason"]]
    lines += [f"- {item['path']}: {item['why']}" for item in record["files"]]
    lines += [
        "",
        f"Impact: {report['score']}/100 ({report['level']}; v{report['version']})",
        "Core paths: " + (", ".join(report["core_paths"]) or "none"),
        "Flow verification: see test/Playwright results; static score is not test evidence.",
        f"Change-Review: {report['fingerprint']}",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prepare", action="store_true", help="Create a template; fill it after review"
    )
    parser.add_argument(
        "--message-file", type=Path, help="commit-msg hook: append verified review body"
    )
    args = parser.parse_args(argv)
    try:
        report = assess(*comparison("HEAD", "STAGED"))
        if not report["changes"]:
            raise ValueError("No staged changes to review.")
        directory = local_directory() / "commits"
        path = directory / f"{report['fingerprint']}.json"
        if args.prepare:
            directory.mkdir(parents=True, exist_ok=True)
            template = {
                "fingerprint": report["fingerprint"],
                "summary": "",
                "reason": "",
                "files": [
                    {"path": item["path"], "what": "", "why": ""} for item in report["changes"]
                ],
            }
            with path.open("x", encoding="utf-8") as handle:
                json.dump(template, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            print(f"Review staged diff, then fill: {path}")
            return 0
        record = validate(json.loads(path.read_text(encoding="utf-8")), report)
        body = render(record, report)
        print(body)
        if args.message_file:
            message = args.message_file.read_text(encoding="utf-8")
            if "Change-Review:" in message:
                if body not in message:
                    raise ValueError("Commit review body differs from the verified staged review.")
            else:
                with args.message_file.open("a", encoding="utf-8") as handle:
                    handle.write("\n\n" + body + "\n")
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Commit blocked: {exc}\nRun: uv run python scripts/commit_review.py --prepare")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
