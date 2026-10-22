# Change impact review cases

| Case | Expected behavior | Layer |
| --- | --- | --- |
| IMP-001 | >80 low, 50..80 medium, <50 high; only low needs no human signature | unit |
| IMP-002 | Added/modified ratio uses baseline tracked files; deletions still penalized | unit |
| IMP-003 | Core and policy edits need review even in a large repo | unit |
| IMP-004 | Direct import dependants reported; no runtime coverage inferred | unit |
| IMP-005 | Executable mode-only edits invalidate fingerprints | unit |
| IMP-006 | Stale/missing/incomplete what/where/why blocks commit | unit/integration |
| IMP-007 | Actual Git commit retains the review text and fingerprint for revert investigation | integration |
| IMP-008 | Index snapshot differs from unstaged bytes; foreign GIT_* cannot redirect reads | integration |
| IMP-009 | Real fixture SSH key/signature accepted; unsigned/tampered/stale/expired rejected | integration |
| IMP-010 | Playwright failure blocks and persists failure report before approval gate | unit |
| IMP-011 | Missing human approval blocks push without falsifying successful test evidence | unit |

No API/UI feature is introduced here, so api/screen_flow/e2e folders have no artificial tests.
Business-flow smoke checks reuse the existing real Playwright suites; unit tests of gate
propagation mock only execution of these external checks, never claim the product flow passed.

Test adjustment evidence: Git forwards commit hook output to stderr. IMP-007 checks stdout
and stderr for the block diagnostic while still requiring a nonzero exit and unchanged HEAD.
The legacy gate test now also requires enforce_impact=True, reflecting the new push rule.
