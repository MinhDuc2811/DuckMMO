# Integration verification — 2026-11-08

Baseline: origin/main `441d4f49ac137b67a94ec24f6e307cc576558889`. Python 3.12,
Streamlit 1.66, system Chromium 154 via Playwright, real FastAPI/SQLite/worker/FFmpeg.

| Check | Result | Evidence/scope |
| --- | --- | --- |
| Full default offline regression (`-m 'not live'`) | 227 passed, 7 skipped | `test-results/toolkit/offline-final.xml`; opt-in live and unsupported Windows skips are not passes |
| Fresh SQLite schema | Passed | Existing `scripts/check_quality.py::migration_check`, revision 0006 |
| Baseline SQLite → new schema | Passed | Same checker creates actual baseline DB in a temporary checkout, then upgrades |
| Required browser upload + voice/rate smoke | 2 passed | `test-results/toolkit/smoke-verified.xml`; genuine browser/API/DB, worker stopped before live TTS |
| Library topic/vocabulary → review → one-focus script → MP4/download | Passed | `test-results/toolkit/browser-sync.xml`; real persistence/encoder, explicitly synthetic PCM speech |
| Readiness, English edit/review/render/play/download/invalidation, white-card UK config, stock-pack selection | 4 passed | Passing nodes in `test-results/toolkit/browser-verified.xml`; that run also contains failures below, not an all-green suite |
| Lint/format/diff whitespace | Passed | ruff + git diff --check |
| Reuse heuristic | 100, no new findings | Static AST heuristic only; not a performance/correctness certificate |
| Live Edge English UK | Blocked/failed | Earlier Sonia/Ryan attempts return proxy HTTP 403; no pronunciation audition completed |
| Expanded legacy browser run | Failed | Real Edge video/quality tests fail HTTP 403; live multisource crawl fails DNS |
| Live Pexels/Openverse | Not verified | External hosts outside environment allowlist; Pexels also needs a configured key |
| PostgreSQL, production data volumes, peak RAM/latency benchmark | Not run | Do not infer capacity/performance from SQLite query-count tests |

## Browser failures and corrections retained for review

The expanded run (`test-results/toolkit/browser-full`) had 6 failures and 9 passes: three
external-network failures plus popup/navigation failures in the offline browser flows.
Later combined runs exposed duplicate old/new upload widgets during reruns, a closed React
Aria popup, and the IELTS multiselect remaining open. Failures/traces were retained rather
than reported as passing. The following corrections preserve all business assertions:

- Clip upload waits for the selected production tab, completed rerun and exactly one uploader;
  the trace showed both old image and new clip uploaders during the transition.
- Voice selection waits for the same settled view and uses the searchable combobox keyboard
  path. A standalone real-browser diagnostic showed `Open` leaving aria-expanded=false with
  zero options; typing Nam Minh + ArrowDown + Enter selected the full expected voice.
- IELTS multiselect is dismissed with Tab after selecting the topic, before accessing the next
  input. Its popup intentionally remains open to allow additional selections.
- Music tests changed because the user explicitly rejected generated tracks and stopped that
  work: fresh white-card music must be off; explicit selection, volume, ducking and digests
  remain checked. Catalog asserts all six original presets plus the new seventh preset.

No retry loop, force-click, skip/xfail, timeout increase or reduced expected state was added.
The successful final scoped runs above verify all seven offline browser scenarios across runs;
this does not make the expanded live browser suite green. Required hooks remain installed.

## Git delivery gate

The user authorized integration and Git push. However, AGENTS.md states that failed or
unavailable tests/Playwright verification block push independently of impact confirmation.
The three external-network browser failures remain unresolved, so they cannot be treated as
an approved waiver or silently excluded from the reported outcome. Code can be reviewed and
committed locally; pushing must wait for the blocked live checks to be run successfully in
an environment permitting the relevant Edge service and crawl/DNS access. No environment or
YouTube publication was performed. No hook or test policy was weakened to bypass this gate.
