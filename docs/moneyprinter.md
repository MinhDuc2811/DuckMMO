# MoneyPrinterTurbo footage integration

This is a real, narrow MPT integration for the existing English/IELTS Shorts workflow.
It invokes the installed **mpt 1.3.10** functions `material.download_videos` and
`video.combine_videos`. It does not replace the learning DB, existing narrator, white card,
FFmpeg mixer, content review or final video review with another complete application.

## Setup and use

The main app and MPT both have a Python package named `app`. MPT therefore has its own uv
project and lockfile; child processes run that interpreter with `-I` to avoid importing the
main app or inherited PYTHONPATH. Do not pip-install MPT into the main app's venv.

```bash
uv sync --project integrations/moneyprinter-turbo --frozen --no-dev
```

Set one or more backend environment keys:

```dotenv
STUDIO_PEXELS_API_KEY=...
STUDIO_PIXABAY_API_KEY=...
STUDIO_COVERR_API_KEY=...
STUDIO_MPT_DIR=data/moneyprinter
# Optional custom isolated interpreter:
# STUDIO_MPT_PYTHON=/absolute/path/to/python
```

API access/quota and permissions depend on the selected stock provider. The environment also
needs outbound network access to that provider and its download CDN. Local runtime readiness
is not verification of provider access. Missing runtime/keys and source failures are reported;
there is no fake-footage or paid-generation fallback.

Phase 3 → **MoneyPrinterTurbo · Tự chuẩn bị clip nền**:

1. Choose Pexels, Pixabay or Coverr; edit up to three English visual search terms. The initial
   suggestion is the lesson title, not AI-extracted keywords or a promise of semantic matching.
2. Choose a 5–30-second background and aspect ratio; record source/rights review notes.
3. MPT searches, downloads and assembles sequential footage, using its native search cache.
4. Watch the prepared silent clip, inspect/download source metadata, then explicitly click
   **Dùng clip MPT làm nền**. It selects the prepared asset in the existing Clip controls.
5. Keep the white-card preset and selected English voice; render and review through the normal
   pipeline. The existing worker fits/loops the background to the final narration duration.

The bridge uses a silent WAV solely as an internal duration reference for footage assembly.
It is not narration, never presented as speech and is not mixed into the prepared video.
No script rewriting, TTS, subtitle generation, default songs, AI music, paid image/video
provider or auto-publishing function is invoked. Source relevance and licensing still require
editorial review. MPT's default music collection is not exposed in the app.

## Persistence, bounds and ownership

- Routes: protected `/api/production/moneyprinter` and
  `/api/jobs/{id}/moneyprinter/footage`.
- Provider credentials are sent in a mode-600 temporary request file, not command arguments,
  then removed. The MPT config receives keys only in process memory; task/provenance JSON does
  not receive them. The bridge does not forward provider exception URLs or secret values.
- MPT material source records are initialized through its task-artifact owner, filtered to
  actual used source files and copied as public provenance into the imported MediaAsset.
- Existing `upload_asset` handles streaming import, decode/probe, per-job ownership, quota,
  digest, deduplication and transaction. Provenance is an internal optional argument committed
  with a new asset. Identical existing assets retain their original metadata.
- Prepared assets use the common authenticated file-download route and digest verification.
  Raw MPT per-run downloads are discarded after import; its provider search cache is retained.
- The request binds the existing canonical narration hash and checks it again after preparation.
  Content review, renderer pinning and final approval/invalidation policies remain unchanged.
- One preparation runs at a time across API processes. Busy requests return 429; MPT gets a
  600-second owned-subprocess timeout and existing descendant cleanup. This is a bounded local
  request, not a new durable queue or a separate cancelable Workspace job.
- Upstream per-file download size is narrowed to 30 MB; imported output is capped at 100 MB
  or the smaller configured upload limit. Existing media probe/size/quota/free-space checks
  apply, with a conservative separate 500 MB preparation reservation. Production-scale peak
  RAM/throughput and cache eviction have not been benchmarked or added.

## Verification

Tests replace only the MPT child's external stock HTTP with a declared fixture. Native MPT
search/filter/download/cache/assembly, MoviePy, FFmpeg, the API, SQL metadata and final renderer
remain real. The browser test prepares footage, downloads credits, explicitly chooses the clip,
then renders/downloads a white-card MP4 with declared synthetic PCM speech. It checks unchanged
narration, no selected BGM and no YouTube publishing. This is not live Pexels quality assessment
or an audition of a real British voice. The previous live Edge/crawl blockers remain unwaived.

The package version and full dependency graph are locked under `integrations/moneyprinter-turbo`.
The earlier repository inspection used commit `c235354804104665b58679223847f78c2b5e27d4` as
reference; runtime provenance reports the actual installed distribution version, not a claim
that every PyPI file is byte-identical to that Git commit. MPT code is MIT; stock assets,
providers and FFmpeg builds retain their own conditions.

The isolated lock applies upstream’s `pillow>=13,<14` security override for MoviePy’s
older dependency cap. Offline suite: 236 passed, 7 skipped; browser regression: 3 passed.
