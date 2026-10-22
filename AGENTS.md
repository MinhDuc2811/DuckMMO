# Quality and reuse requirements

Read `docs/architecture.md` and `docs/code-quality.md` before changing application code.
Search existing owners before adding helpers. Reuse contracts, lifecycle policies,
media adapters, UI clients and components; explain deliberate alternatives.

Before commit: run `uv run python scripts/check_quality.py commit`.
Before push: use installed hooks; all offline tests and migrations must pass.
Reuse score must be strictly above 70, or provide a change-bound, expiring rationale
in `code-review-exceptions.json` as documented. An exception never bypasses failed tests.
Do not bypass hooks or weaken review rules/tests to get a feature through.
Report skipped/unavailable verification accurately. Do not claim heuristic scores prove
performance, correctness or complete reuse. Do not commit another task's workspace edits.

## Test organization and integrity

New feature tests belong in `test_suite/features/<feature>/` with separate `unit`,
`api`, `integration`, `screen_flow`, and `e2e` folders. Read `test_suite/AGENTS.md`
and `test_suite/README.md` before adding or changing tests. Never weaken assertions,
fixtures, discovery, skip rules or expected results just to make production code pass.
Fix the application when a valid test fails. Test corrections require evidence and
an explicit explanation for review. Keep existing regression coverage during migration.

## Commit descriptions and impact review

Before every commit, inspect `git diff --cached` and record what changed, where, and why
for every file using `scripts/commit_review.py`. Never use empty or generic explanations.
The commit-msg hook must preserve that reviewed description and impact summary in the
actual commit body so later investigations/reverts can identify the behavior changed.
Read `docs/change-impact.md` for scoring v1 and commands.

Before push, run impact assessment on the entire outgoing change. Score >80 is low;
50..80 is medium; <50 is high. Medium/high require human review of the exact fingerprint
and a valid trusted SSH signature. Agents must never manufacture or sign human approval,
use a human's SSH agent to approve their own change, or treat general task authorization
as a specific impact approval. Missing public-key setup means approval is unavailable,
not implicitly granted. Tests/Playwright failure or unavailable verification must be
reported and block push independently of impact score or approval. Do not weaken tests,
change thresholds, or split commits to evade review.
