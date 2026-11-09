# Stickman feature verification

- API/integration: actual upstream CLI doctor; Director ZIP and auth; real PCM → preview →
  checksum-bound approval → full MP4/SRT; edits revoke outputs and stale versions fail.
- Boundary checks: external/absolute/parent/unuploaded paths and arbitrary fonts rejected;
  unsupported command/upload kinds fail; source files require rights notes.
- Style validation: B2/B3/B4 retain their own style IDs; B4 test uses an explicitly labelled
  PCM narrator override, not a false Brian identity or a paid synthesis service.
- Provenance unit test checks every vendored file hash and MIT/OFL license files.
- Screen flow uses real API/SQLite and asserts Stickman navigation stops mounting/requesting
  the old job/IELTS workspace.
- Browser: real API, Streamlit, Node/canvas/FFmpeg and filesystem; upload a declared fixture
  tone, author B1 starter, preview, explicitly approve, render, download MP4/SRT, verify hash,
  check no original jobs and no AI provider calls. No live speech/aesthetic claim.

Commands:

```bash
npm ci --prefix integrations/stickman-video-director --ignore-scripts
uv run pytest --feature stickman -q --output test-results/stickman/offline
uv run pytest --feature stickman --test-layer e2e -q --tracing retain-on-failure \
  --screenshot only-on-failure --output test-results/stickman/e2e
```

Runtime setup is required for actual integration tests; missing Node/canvas is not skipped
or substituted. Expanded live Edge/crawl failures recorded by the previous task remain
separate unresolved verification; this feature neither changes those tests nor waives push gates.

The full render case was moved to the integration layer and its shared PCM/HTTP setup
to test_suite/support/stickman.py before commit. Its function AST was checked unchanged;
no assertion, expected result, timeout or provider behavior was relaxed during relocation.
