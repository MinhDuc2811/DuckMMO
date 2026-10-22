# Local media: upload, storage and clip rendering

DuckMMO supports images, text cards, or one uploaded clip as the visual source for an
approved script. Files live on the local disk; SQLite stores metadata and job state.
No video generation API, GPU, S3 account or new Python dependency is required.

## Use

1. Install locked dependencies with `uv sync --frozen --group dev` and run
   `uv run alembic upgrade head` (migration `0005` adds `media_assets`).
2. Install **FFprobe**, normally supplied by your operating system's FFmpeg package,
   and make `ffprobe` available on PATH. For Ubuntu/Debian: `apt-get install ffmpeg`.
   Encoding still uses the FFmpeg binary supplied by `imageio-ffmpeg`.
3. Start the API, **one** `python -m app.worker` supervisor, and Streamlit as in README.
4. Approve a script, open Phase 3, and select **Ảnh** or **Clip**. Select previously
   uploaded files or upload new ones. Clip mode accepts one MP4/MOV/WebM.
5. Choose pad (keep the complete frame) or crop (center crop). Short clips loop;
   long clips stop at narration length. Original audio is discarded. Generated
   narration and styled subtitles use the existing pipeline and final approval gate.

This first version uses the complete clip; it does not offer trim points, multiple
clips, original audio mixing, automatic scene selection, or AI script extraction.
Windows local voices still require Windows. On Linux, select an Edge voice and
allow the appropriate network connection. Tests use a deterministic local WAV
fixture to exercise encoding without depending on external TTS.

### Limits and resource use

Default limits (override using the usual `STUDIO_` environment prefix):

| Variable | Default | Purpose |
| --- | --- | --- |
| `STUDIO_MEDIA_UPLOAD_MAX_BYTES` | 100000000 | Maximum clip upload bytes; image uploads additionally cap at 3000000 |
| `STUDIO_MEDIA_STORAGE_MAX_BYTES` | 10000000000 | Local artifact storage admission threshold |
| `STUDIO_MEDIA_MIN_FREE_BYTES` | 500000000 | Keep free disk headroom when admitting work |
| `STUDIO_MEDIA_MAX_DURATION` | 120 | Maximum source clip seconds |
| `STUDIO_RENDER_MAX_DURATION` | 600 | Maximum narrated output seconds |
| `STUDIO_FFMPEG_THREADS` | 2 | Decoder/filter/encoder concurrency for clip encoding |
| `STUDIO_ARTIFACT_DIR` | data/artifacts | Shared root for API and worker |

Clips must be at most 1920×1080 or 1080×1920 and 60 fps. Images must be PNG/JPEG,
at most 20 megapixels, with at most 10 per render. Each job may retain 20 uploaded
assets. Uploads have a 120-second body deadline. One upload is admitted at a time;
competing requests receive 429 and should retry later. File type is checked from
content with Pillow or FFprobe plus a real FFmpeg frame decode, not from its name.

The supervisor holds an OS file lock **before** recovering interrupted jobs, preventing
a second supervisor from marking live work failed or running another encode. The
existing DB queue holds other requests until the current job completes. FFmpeg video
encoding uses the configured thread count, H.264 `veryfast`, CRF 23, 24 fps and AAC.
It runs in the existing isolated job process, so cancellation terminates descendants.

Disk checks run before upload/preparation and before encoding. Encoding reserves
headroom by admission estimate (4 MB per output second) and caps output file bytes.
These are application admission checks, **not a filesystem hard quota or a guarantee
against writes by other applications**. Monitor the disk and lower limits on small
machines. Outputs longer than the configured maximum fail rather than continuing.
The local mode is deliberately one API/storage machine and one supervisor; do not
scale by pointing independent machines at unrelated local directories.

**Streamlit limitation:** its browser uploader buffers files in the UI server before
our client streams them to FastAPI. This implementation removes base64/full-body
buffering on the API leg, but does not make Streamlit a zero-buffer upload gateway.
Keep UI uploads small. Batch clients should stream directly to the API below. A
browser-to-storage uploader is the next step for a multi-user deployment.

## Components and extension points

| Component | Responsibility |
| --- | --- |
| `app/api/routers/media.py` | Authenticated HTTP streaming adapters |
| `app/infrastructure/media/storage.py` | UUID storage keys, bounded-memory hashes, capacity checks, file integrity |
| `app/infrastructure/media/probe.py` | Actual image/video validation and clip limits |
| `app/infrastructure/media/visuals.py` | Pin inputs for a run, clip/image FFmpeg input and frame layout |
| `app/modules/production/assets.py` | Upload/list/delete lifecycle and job ownership |
| `app/modules/production/render.py` | Narration/subtitle/encoding/QA orchestration |
| `app/infrastructure/media/encoding.py` | FFmpeg encoding and output validation |
| `app/infrastructure/local_lock.py` | Cross-process Windows/POSIX local locks |
| `app/infrastructure/media/cleanup.py` | Retention command and worker-startup cleanup |
| `ui/client/media.py` | Chunked upload client reused by images and clips |

An asset is scoped to its job and addressed by UUID, never a client-supplied path.
SQLite stores `{id, job_id, kind, size, sha256, details, created_at}`. File bytes and
base64 are absent from these rows. SHA-256 deduplication reuses identical uploads
within a job. Source clips are immutable; a render pins a hard link (or copies on
filesystems without hard links). Images are normalized into the run directory.
Deleting an uploaded asset leaves already queued/current runs valid. Upload/render
preparation/deletion coordinate through `.media.lock`. A future storage backend can
replace the filesystem adapter and input pinning without replacing jobs or TTS.

The old base64 `images` render field remains accepted for existing API clients.
The UI uses asset IDs and no longer creates base64 media payloads.

## Streaming API

All routes use the same `X-API-Key` protection as the existing API, when configured.

- `POST /api/jobs/{job_id}/assets?kind=image|video`: raw file body, preferably with
  Content-Length; returns asset ID and metadata. Content is streamed to a unique
  `.part` file, verified, and atomically renamed. Failed/interrupted requests delete
  the partial file during normal exception cleanup.
- `GET /api/jobs/{job_id}/assets`: list reusable source assets.
- `DELETE /api/jobs/{job_id}/assets/{asset_id}`: remove uploaded source and metadata.
- Existing `POST /api/jobs/{job_id}/render`: send `image_asset_ids` or `video_asset_id`,
  plus `video_fit: "pad" | "crop"`, voice, layout and `expected_content_hash`.
  Image and clip sources cannot be mixed in a render request.

Example upload (add your API header if protection is configured):

```bash
curl --fail-with-body -X POST \
  'http://127.0.0.1:8000/api/jobs/JOB_UUID/assets?kind=video' \
  -H 'Content-Type: application/octet-stream' --data-binary @clip.mp4
```

## Retention and debugging

At supervisor startup, unreferenced render directories and abandoned `.part` files
older than seven days are removed. All current render/video references are retained,
including trashed jobs, so undo-delete remains possible. Uploaded source assets are
retained until explicitly deleted through the UI/API; they are not silently expired.
Cleanup skips when an upload owns the media lock.

To inspect retention manually, stop the supervisor first (the command requires the
same worker lock), then run:

```bash
uv run python -m app.infrastructure.media.cleanup          # dry-run paths
uv run python -m app.infrastructure.media.cleanup --apply  # apply the same retention policy
```

Failed and cancelled current runs are retained for investigation. A new render makes
the old run eligible for the retention window. Do not manually delete lock files while
processes are running: the OS lock is attached to the open file, not its pathname.

- DB: inspect `media_assets`, job `render_config`, job events and quality step runs.
- Files: sources at `data/artifacts/assets/<asset_uuid>`; pinned clip at
  `<job_uuid>/<run_uuid>/input-clip`; final files and `manifest.json` in that run.
- FFmpeg failures: `engine-error.log` in the run directory and worker process logs.
- Missing FFprobe: install the system FFmpeg package; do not disable input checks.
- 429: an upload/preparation owns the local media lock; retry after it completes.
- Storage limit: delete unused assets, inspect retention, then retry.

Back up **both the SQLite database and artifact directory** together. The database
alone does not contain source media or rendered videos.

## Validation

`uv run pytest tests/test_media.py -q` covers chunked uploads, invalid/oversized files,
quota/auth enforcement, job scoping, deduplication, cleanup, supervisor exclusivity,
real image rendering, and real clip encode/loop/pad/crop/review. An FFT check verifies
that output audio uses the narration fixture rather than the source clip's tone.
`e2e/test_media_upload.py` exercises the real browser → UI → streaming API → SQLite
upload and queued clip configuration. It stops the worker before queueing so it does
not invoke external TTS. See `e2e/README.md` for browser setup and evidence locations.
