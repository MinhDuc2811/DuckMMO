# Stickman Studio — independent integration

Source: [kaomei/stickman-video-director](https://github.com/kaomei/stickman-video-director),
pinned to `eb4bb378c4716a617f9ad7d98a60379b9d1fa54a`, inspected 2026-11-09.
Local files and SHA-256 provenance: `integrations/stickman-video-director/UPSTREAM.json`.

## What the repository actually provides

The repository is an agent Skill plus a Node/canvas/FFmpeg local renderer, not a hosted
text-to-video API or a bundled image/voice model. Director A1–A6 produces creative treatments
and scene-generation prompts through an external assistant. Autopilot B1–B4 assembles authored
images/layers, supplied narration, timed captions and optional audio. Some documented image/
voice providers require accounts, keys or paid access. README marketing about free production,
virality or visual similarity is not a result verified by this integration.

This app integrates the actual local renderer and Director guidance, not automatic topic-to-
finished-film generation. It makes no paid generation calls or TTS substitutions. The existing
English IELTS voice selection remains separate; Stickman uses the uploaded audio unchanged.

## Separation

Select **Không gian làm việc → Stickman Studio** in the sidebar. It replaces the visible
content workspace with its own controls; IELTS/production tabs and job queries are not mounted.
Switch back to **Nội dung & IELTS** to return to the existing workflow.

- API: authenticated `/api/stickman/*`, using the existing API key.
- Data: `STUDIO_STICKMAN_DIR`, default `data/stickman`, separate from IELTS SQL/jobs/artifacts.
- Project JSON, uploaded inputs, shot cache and output live under a generated project UUID.
- No SQL migration, extra Job branch, replacement renderer or modification of IELTS presets.
- The wrapper reuses local locks, bounded media inspection, storage/free-space checks and owned
  subprocess cleanup. A separate file-based project owner is deliberate: upstream's JSON/cache/
  preview-fingerprint lifecycle is not an IELTS narration job or an alternate copy of that queue.

## Setup

Python setup is unchanged. Install Node.js 20+ (CI uses Node 22) and system FFmpeg/FFprobe:

```bash
npm ci --prefix integrations/stickman-video-director --ignore-scripts --no-audit --no-fund
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
uv run streamlit run ui/studio.py
```

The only Node dependency is pinned `@napi-rs/canvas` 0.1.100. On this Linux environment its
prebuilt optional native package installs successfully without lifecycle scripts. Use an npm
cache you can write if the default home cache is restricted, e.g. `--cache /tmp/stickman-npm-cache`.
Dependencies are optional for using the original workspace; Stickman's doctor reports missing
runtime setup honestly. Its passing state does not verify image/TTS providers or voice quality.
CI installs this dependency before the actual runtime integration tests, without skipping them.

## Autopilot workflow

1. Create a separately named B1/B2/B3/B4 project with an explicit aspect ratio.
2. Upload narration/images/audio and record source/rights notes. Copy the returned `inputs/...`
   paths into the timeline; arbitrary filesystem paths, URLs, custom font paths and unuploaded
   files are rejected. Inputs are digest checked and cannot be replaced via the upload API.
3. B1 has an optional quick starter using its bundled pose atlas and one supplied audio clip.
   Its single caption covers the clip's measured duration. This is a demonstrator, not automatic
   speech alignment, semantic segmentation, original storyboarding or inferred character motion.
4. Edit the timeline for real story-specific shots, motions and properly timed captions. B2/B3/B4
   retain their independent visual contracts; B1's pose atlas is rejected by upstream outside B1.
5. Validate, render a preview, watch/listen, explicitly approve that preview with a note, then render
   the film. Approval binds the current preview digest and upstream fingerprint. A full render is
   blocked without approval. Saving an edit increments the version, revokes approval and hides old
   outputs; expected_version prevents stale overwrites. Technical validation never auto-approves.
6. Download MP4 and SRT. The upstream renderer also writes VTT, contact sheets and technical reports.
   Nothing is automatically uploaded to YouTube or connected to IELTS's publishing phase.

B4's five image references, prompt and integrity manifest are included and pass the upstream
style-lock check. Original private comparison footage is not included or evaluated. B4 retains
its voice-identity/explicit-override and continuous-audio requirements; this app does not acquire
Brian or claim that an uploaded file's metadata proves the actual speaker. B3/B4 style fidelity,
storytelling, intelligibility and musical quality still require visual/listening review.

## Director workflow

Choose **Director · Brief & prompt**, enter source, A-style, ratio and target duration. Download
a ZIP with the request, upstream Skill/reference documents and license. This is a handoff to an
AI assistant, not an already-generated storyboard, animated footage or a complete install of the
upstream project. Follow the pinned repository for full agent installation and generator setup.
No assistant, image generator or external model is silently invoked by this export action.

## Limits and verification

The first local bridge accepts narration up to 120 seconds, at most 20 uploaded files/project,
3 MB / 4 MP images, 20 MB audio, 256 KB bounded-depth timelines and up to 720p at 12–30 fps.
Quota is at most 1 GB (or a smaller configured shared media limit), with existing free-space
checks and conservative render reservation. These are wrapper limits, not upstream's long-form
capability. Project listing shows the 100 most recently modified projects.

Operations are synchronous local requests, serialized across processes by a dedicated lock;
busy calls return 429. A CLI call times out at 600 seconds and the common process owner stops
its descendants. This is not a durable background queue: closing the browser does not provide
a cancel control or a restart recovery guarantee. Do not use this as a public multi-tenant service.
Rendering/encoding resource use has not been benchmarked at production volume. No distributed
worker, cancellation UI, external model download or automatic aligned-caption engine was added.

Tests use real Node, canvas, uploaded files and FFmpeg; audio is a declared synthetic PCM fixture,
not a paid provider, actual speech or a pronunciation/aesthetic audition. Cases cover path
confinement, type/version validation, rejected upload kinds, preview checksum and approval,
edit invalidation, independent styles, provenance hashes, workspace isolation and the real
browser upload → preview → approve → film/SRT download flow. See test suite cases for results.

## Checked in this workspace (2026-11-09)

- Upstream doctor: Node, canvas, FFmpeg/FFprobe and fonts available; no provider network check.
- B4 style-lock resource integrity: passed against its bundled five references and prompt.
- Full offline regression: **233 passed, 7 skipped** (existing live/Windows opt-ins, not new skips).
- Browser regression: **4 passed** — clip upload, voice/rate, IELTS library-to-MP4 and the new
  separate Stickman upload/preview/approval/MP4+SRT download flow. Both render flows use explicit
  synthetic PCM speech fixtures; this is not an audition of actual UK speech or Brian.
- Fresh SQLite and upgrade from the existing local baseline passed using the repository checker.
  The first invocation used system Python without Alembic; it was corrected to the project's uv
  environment before recording the passing migration result. No migration file/schema change.
- Ruff/format/whitespace and reuse heuristic checks pass; heuristic score 100 is not correctness
  proof or a benchmark. No paid generation, model download, environment/YouTube publication.

The previous branch's live Edge/crawl browser checks remain blocked by restricted networking
(Edge hostname and crawl hosts are not allowed). These failures are not reclassified as passed
by the new offline results, and the repository's existing push gate remains in force.
