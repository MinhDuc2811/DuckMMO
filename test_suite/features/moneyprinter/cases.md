# MoneyPrinter feature cases

- Unit: absent isolated interpreter is reported as unavailable, never success.
- API: stale content hashes, missing keys, unsupported paid generator names and invalid term
  counts reject before preparing any footage. Normal job narration is unchanged.
- Integration: actual mpt 1.3.10 search/download/assembly with only external stock HTTP fixtures;
  inspect real MP4 dimensions, duration, lack of audio, SHA, source credit and no key leakage;
  select imported MediaAsset through the existing lesson-card render API; verify temporary
  request credentials are removed and not written to MPT config.
- E2E: real UI/API/DB/MPT/MoviePy/FFmpeg → prepared clip/credit → explicit background selection
  → white-card final render/download/hash. Stock HTTP and speech are explicitly declared
  fixtures; no route mocking, paid generation or actual publication.

```bash
uv sync --project integrations/moneyprinter-turbo --frozen --no-dev
uv run pytest --feature moneyprinter -q --output test-results/moneyprinter/offline
uv run pytest --feature moneyprinter --test-layer e2e -q --tracing retain-on-failure \
  --screenshot only-on-failure --output test-results/moneyprinter/browser
```

No added skip/xfail or weakened existing assertions. The actual runtime must be installed
for integration tests; CI installs it explicitly. Existing live-network failures from the
previous task are not made passing by this offline feature scope.
