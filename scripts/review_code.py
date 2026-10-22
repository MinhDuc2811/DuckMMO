"""Deterministic reuse review of a Git diff; no network or AI API required.

Exit 0: score > 70, or a matching documented exception. Exit 1: rejected.
Exit 2: invalid input. This is a heuristic review, not proof of good design.
"""

import argparse
import ast
import copy
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = "code-review-exceptions.json"


def git(*args, root=ROOT):
    return subprocess.check_output(
        ["git", *args],
        cwd=root,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    )


def production(path):
    return path.endswith(".py") and path.startswith(("app/", "ui/"))


def snapshot(ref, root=ROOT):
    """Read committed trees directly; worktree mode also includes untracked code."""
    if ref == "WORKTREE":
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", root=root)
        return {
            name: (root / name).read_bytes()
            for name in set(names.decode().split("\0")) - {""}
            if (root / name).is_file()
        }
    names = git("ls-tree", "-rz", "--name-only", ref, root=root).decode().split("\0")
    return {name: git("show", f"{ref}:{name}", root=root) for name in names if name}


def canonical_function(node):
    """Ignore function name/docstring; retain calls, variable names and constants."""
    node = copy.deepcopy(node)
    node.name = "FUNCTION"
    if node.body and isinstance(node.body[0], ast.Expr):
        value = node.body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            node.body.pop(0)
    return ast.dump(node, include_attributes=False)


def imports(tree, path):
    aliases = {}
    package = path.removesuffix(".py").split("/")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = ".".join(package[: len(package) - node.level + 1] + [module]).rstrip(".")
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{module}.{alias.name}"
    return aliases


def qualified(node, aliases):
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return qualified(node.value, aliases) + "." + node.attr
    return ""


def findings_for(files):
    findings = []
    functions = {}

    def add(path, node, category, points, rule, message):
        findings.append(
            {
                "path": path,
                "line": node.lineno,
                "category": category,
                "points": points,
                "rule": rule,
                "message": message,
            }
        )

    for path, source in sorted(files.items()):
        if not production(path):
            continue
        try:
            tree = ast.parse(source, filename=path)
        except (SyntaxError, ValueError) as exc:
            findings.append(
                {
                    "path": path,
                    "line": getattr(exc, "lineno", 1),
                    "category": "architecture",
                    "points": 40,
                    "rule": "syntax",
                    "message": str(exc),
                }
            )
            continue
        aliases = imports(tree, path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Avoid penalizing trivial wrappers and protocol signatures.
                if sum(1 for _ in ast.walk(node)) >= 40:
                    key = canonical_function(node)
                    functions.setdefault(key, []).append((path, node))
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [aliases.get(alias.asname or alias.name, "") for alias in node.names]
                )
                forbidden = ()
                if path.startswith("ui/"):
                    forbidden = ("app",)
                elif path.startswith("app/modules/"):
                    forbidden = ("fastapi", "starlette", "app.api", "ui", "streamlit")
                elif path.startswith("app/contracts/"):
                    forbidden = (
                        "fastapi",
                        "starlette",
                        "sqlalchemy",
                        "streamlit",
                        "app.infrastructure",
                        "app.modules",
                        "app.api",
                    )
                if any(m == f or m.startswith(f + ".") for m in modules for f in forbidden):
                    add(
                        path,
                        node,
                        "architecture",
                        20,
                        "dependency-boundary",
                        "Import crosses layer boundary; use the owning module/contract.",
                    )
            if not isinstance(node, ast.Call):
                continue
            name = qualified(node.func, aliases)
            if path.startswith("ui/screens/") and name.startswith(("httpx.", "requests.")):
                add(
                    path,
                    node,
                    "common",
                    10,
                    "ui-http-client",
                    "Move HTTP access into ui/client (including binary downloads).",
                )
            if path.startswith(("app/api/routers/", "ui/screens/")) and name.startswith(
                ("subprocess.", "os.system", "os.popen")
            ):
                add(
                    path,
                    node,
                    "common",
                    15,
                    "process-adapter",
                    "Use an infrastructure subprocess adapter.",
                )
            if path.startswith(("app/api/routers/", "app/modules/", "ui/")) and name.rsplit(".", 1)[
                -1
            ] in ("create_engine", "make_engine", "make_sessions"):
                add(
                    path,
                    node,
                    "common",
                    15,
                    "database-composition",
                    "Inject session/engine from composition root instead of constructing it here.",
                )
            if name.endswith(".read_bytes"):
                # Only flag known media bodies; small config reads are allowed.
                expression = ast.unparse(node.func.value).lower()
                if any(token in expression for token in (".mp4", ".wav", "media_path")):
                    add(
                        path,
                        node,
                        "resources",
                        15,
                        "stream-media-hash",
                        "Avoid loading media into RAM; reuse "
                        "infrastructure.media.storage.file_digest.",
                    )
    for matches in functions.values():
        if len(matches) < 2:
            continue
        for path, node in matches:
            others = sorted({p for p, _ in matches if p != path})
            if others:
                add(
                    path,
                    node,
                    "duplication",
                    15,
                    "duplicate-function",
                    f"Same function AST also in {', '.join(others)}; consider one shared owner.",
                )
    return findings


def analyze(before, after):
    changed = sorted(
        p for p in before.keys() | after.keys() if production(p) and before.get(p) != after.get(p)
    )

    def identity(finding):
        return (finding["path"], finding["category"], finding["rule"], finding["message"])

    old = Counter(identity(f) for f in findings_for(before))
    findings = []
    for finding in findings_for(after):
        key = identity(finding)
        if old[key]:
            old[key] -= 1
        elif finding["path"] in changed:
            findings.append(finding)
    caps = {"architecture": 40, "duplication": 35, "common": 25, "resources": 30}
    deductions = {
        category: min(cap, sum(f["points"] for f in findings if f["category"] == category))
        for category, cap in caps.items()
    }
    # Bind exceptions to both versions of the production tree and the scorer itself.
    digest = hashlib.sha256()
    for label, files in (("before", before), ("after", after)):
        digest.update(label.encode())
        for path in sorted(files):
            if production(path) or path in ("scripts/review_code.py", "scripts/check_quality.py"):
                digest.update(path.encode() + b"\0" + hashlib.sha256(files[path]).digest())
    return {
        "score": max(0, 100 - sum(deductions.values())),
        "threshold": "> 70",
        "fingerprint": digest.hexdigest(),
        "changed_files": changed,
        "deductions": deductions,
        "findings": findings,
        "scope": "New heuristic findings in changed app/ui Python files; not total code quality",
    }


def exception_reason(report, raw, today=None):
    """No generic bypass: require change-specific reasoning, owner and short expiry."""
    today = today or date.today()
    try:
        entries = json.loads(raw).get("exceptions", [])
        for entry in entries:
            if entry.get("fingerprint") != report["fingerprint"]:
                continue
            expiry = date.fromisoformat(entry["expires"])
            if not 0 <= (expiry - today).days <= 30:
                return None
            fields = ("reason", "common_considered", "why_not_reuse", "risk_and_validation")
            if not all(
                isinstance(entry.get(f), str) and len(entry[f].strip()) >= 40 for f in fields
            ):
                return None
            if not isinstance(entry.get("owner"), str) or not entry["owner"].strip():
                return None
            return {key: entry[key] for key in (*fields, "owner", "expires")}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="Git ref to compare from")
    parser.add_argument(
        "--head", default="WORKTREE", help="Git ref, or WORKTREE including untracked"
    )
    parser.add_argument("--output", type=Path, help="Write machine-readable JSON report")
    args = parser.parse_args(argv)
    try:
        before, after = snapshot(args.base), snapshot(args.head)
        report = analyze(before, after)
        waiver = None
        if report["score"] <= 70:
            waiver = exception_reason(report, after.get(EXCEPTIONS, b"{}"))
        report["exception"] = waiver
        report["allowed"] = report["score"] > 70 or waiver is not None
        output = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0 if report["allowed"] else 1
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Review could not run: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
