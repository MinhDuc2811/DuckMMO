# Automation verification

- API: plan disabled by default; explicit scope consent and live-transport channel verification required to enable.
- API: reject naive dates, stale library versions, overfull one-focus Shorts; OAuth state/PKCE/replay/secret redaction.
- Integration: reviewed library → real structural preflight → real MP4/QA → policy audit → resumable scheduled upload.
  Only speech PCM and Google HTTP are declared fixtures. Verify British voice choice and no duplicate initiation on restart.
- Integration: paused/missed slots and changed channel cannot create/upload jobs; remote publication state is confirmed by fixture API.
- E2E: real UI/API/DB callback state, OAuth client form, channel verification, finite plan create, explicit activation and pause.
  Google sign-in/HTTP are fixtures; no real account access or publication is claimed.
- Existing resumable-upload regression retained. Lease guard was adjusted to compare active uploading leases only,
  preserving immediate reconciliation of an uncertain upload without weakening the regression.

Run `uv run pytest --feature automation -q`; browser: `uv run pytest --feature automation --test-layer e2e -q`.

Browser synchronization: wait for the verification-triggered Streamlit rerun to settle
before expanding the queue form; screenshot showed that an early click was reset by that
rerun. No report, authorization, scheduling or pause assertions were removed.

The scheduled-pipeline PCM fixture now lasts 6 seconds for the 14-word lesson. The prior
3-second fixture legitimately triggered the newly enforced subtitle-pacing warning; no QA
threshold/assertion was weakened. Browser selects the actual multiselect option and asserts
the episode editor is present before saving, rather than relying on a keyboard toggle.

Final UI corrections: editable expanders now default open so server reruns do not hide
active forms. Selection is batched in its own form with stable item IDs before the content
editor is built; default time no longer varies by seconds. Channel verification displays
its result without a second full-app rerun. Browser clicks the visible checkbox label
and confirms the stopped UI state before reading the database, preserving state assertions.

Timezone regression: a +07:00 timestamp was initially stored as local wall time by SQLite.
Normalize scheduled instants to UTC before persistence; the regression asserts exact instant
equality, preserving the 7-hour difference that exposed the defect.
