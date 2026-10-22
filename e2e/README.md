# Browser tests

These tests drive an actual Playwright Chromium browser through the actual Streamlit UI,
FastAPI, migrated SQLite database and isolated job worker. Each test starts its own services
on free ports and a temporary database. The user's running app/database are not modified.

```powershell
./scripts/test-e2e.ps1
./scripts/test-e2e.ps1 -LiveWeb
```

First run installs dependencies and Chromium. The standard suite needs no external AI key.
`-LiveWeb` additionally fetches two real websites through the production crawler.
External website/network changes can fail that test and are reported as failures.

Equivalent commands:

```powershell
uv sync --group dev
uv run playwright install chromium
uv run pytest e2e -m "not live" --browser chromium --tracing on --video on --screenshot on --output test-results/e2e
```

Covered flows:

- Enter a script in the browser, queue it, see Workspace update, switch to Phase 2.
- Edit and save text, download the actual TXT and verify bytes, reload and verify persistence, approve.
- Stop a pre-existing queued job and verify cancelled state survives reload.
- Stop a job blocked on an HTTP analysis call and verify every job Python descendant exits,
  while the supervisor remains alive.
- DNS/crawl failure stays in Phase 1 and never calls the AI provider or appears in Phase 2.
- Verify Workspace is in the left sidebar; switch between two distinct contents,
  delete one, and restore it without affecting the other.
- Steps 5–7: approve a script, upload an image, create real local Vietnamese speech,
  encode an actual MP4, play it in Chromium, download and inspect it, then approve the video.
  Requires Windows with the local Vietnamese voice installed (verified on this machine).
- Live: fetch two different websites, persist their source texts, call analysis, review the result.

The external AI provider is a controlled local HTTP fixture with known responses. This verifies
request/response integration and cancellation, not model quality or a paid provider's availability.
The live test really fetches external source HTML; no browser route or crawler mocks are used.
The running-cancel fixture seeds a self-authored input snapshot to hold analysis open reliably.

Evidence:

- `artifacts/e2e/<test-name>/result.png`: screenshot before test servers shut down.
- `artifacts/e2e/<test-name>/*.log`: API, UI and worker logs.
- `artifacts/e2e/results.xml`: machine-readable results.
- `test-results/e2e/<test-name>/trace.zip`, video and screenshots.

Open a trace locally:

```powershell
uv run playwright show-trace <path-to-trace.zip>
```

Unit/integration/AppTest checks remain `uv run pytest -q`; browser tests run explicitly via
the commands above. During development, browser tests found stale Phase 2 data on tab switches
and the Windows Python launcher/descendant distinction in cancellation verification.
