# Test integrity rules

- Test cases express the required behavior, not whatever the current implementation returns.
- Never change an assertion, expected value, threshold, fixture input, marker, timeout,
  skip/xfail, test discovery, or mock solely to make failing application code pass.
- When a regression fails, fix production code first and retain the regression case.
- A test correction is allowed only for a demonstrated test defect or an explicitly
  changed requirement. Record the reason, preserve equivalent/stronger coverage,
  and identify the correction for human review. Moving a test or repairing its root
  path after relocation must preserve its assertions and expected behavior.
- Never mock the behavior the case claims to verify. Unit tests may isolate external
  dependencies; integration and E2E must state which external providers are fixtures.
- No trivial passing test, blanket exception swallowing, unconditional skip, or
  zero-test success may replace meaningful validation.
- An unavailable live service is blocked/failed verification, not a passed test.
  Live provider tests are opt-in to keep the default offline suite deterministic;
  explicit live runs must report real failures instead of skipping them.
- Free voices only. Never add paid TTS adapters, credentials, or fallback services.
- Every feature belongs in features/<feature> with unit, api, integration,
  screen_flow, and e2e folders. Put reusable fixtures in support or conftest.py.
- Preserve unrelated workspace edits and existing legacy regression tests.
