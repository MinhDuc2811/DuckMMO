# Vietnamese speech and continuous narration

## Root cause and change

Previously, the renderer used the subtitle splitter (105 characters) as its TTS
segmenter. Even a continuous sentence was synthesized as multiple independent
utterances. Each restarted provider prosody and retained its leading/trailing
silence. Joining the WAV files could therefore sound fragmented. The original
signal check detected silence/clipping globally, not long internal gaps.

Speech is now segmented independently. Short scripts fit in one utterance; long
scripts group whole sentences within provider limits, using clause/word boundaries
only for oversized sentences. The common limit is 2500 characters. Edge also has a
3500-byte **XML-escaped UTF-8** budget, below its client's internal 4096-byte split,
so Vietnamese and special characters do not cause hidden library splits.

Subtitle layout and image changes remain separate, so one utterance can span many
subtitle cues and image frames. Content hash/approval still binds the original
script. Subtitle timing remains a duration/word-count estimate, not verified word
alignment. Long utterances may need a future provider timestamp/alignment adapter.

Between utterances, only leading/trailing low-signal edges are shortened, retaining
80 ms at the start and 160 ms at the end. The outer start/end of the entire narration
and all pauses inside each utterance are retained. There is no phoneme crossfade.
Internal low-signal spans of at least 0.8 seconds are recorded as `audio_pauses`
warnings; punctuation can legitimately require pauses, so this is not a failure.

## Voices and providers

The shared catalog is `app/contracts/voices.py`; API validation and UI consume it
through authenticated `GET /api/voices`. Edge HoaiMy and NamMinh remain available,
and the default is now `vi-VN-HoaiMyNeural`, including for direct API clients.
Windows local voices remain explicit options on Windows, selecting an installed
voice matching the language. No missing provider silently falls back to another.

Only free voice sources are included: Edge HoaiMy/NamMinh and installed Windows
voices. There are no paid-provider adapters, API key requirements, or automatic
fallbacks to a paid service. This does not add more distinct free Vietnamese Edge
voices than the two already supported; rate controls are not presented as new voices.

Catalog `available` means the platform permits use, not that installed Windows
voices or network access have been verified. Edge depends on Microsoft's online
service and can be rate-limited or unavailable; it is not a contracted SLA service.

`RenderOptions.speech_rate` accepts -30 through +30. Edge uses percentage rate;
Windows maps to discrete -3 through +3 levels, so its changes are not exact
percentages. UI controls use increments of 10. Existing jobs missing the field use 0.

## Listen before rendering

Phase 3 offers **Đoạn nghe thử** (maximum 300 characters) and **Nghe thử giọng**.
Authenticated `POST /api/voices/preview` returns a real WAV and never queues a video.
Previews use the selected free voice source and are only generated on explicit
button clicks. One preview is admitted at a time with a local OS lock.
Temporary preview files are deleted after serving the response. A forced process
termination can leave a directory under `voice-previews` for manual cleanup.

## Cache, components and debug

Raw, untrimmed PCM is cached in `STUDIO_ARTIFACT_DIR/speech-cache`, keyed by text,
voice, rate, output format and implementation/client version. Render copies are
independent, so boundary trimming cannot damage cached audio. Invalid, silent,
clipped or truncated canonical PCM is not saved. Windows audio is not cached because
installed voices can change outside the application. Set
`STUDIO_SPEECH_CACHE_ENABLED=false` to disable the cache.

Cache files count toward the existing local artifact budget; no automatic cache
expiry is implemented. To reclaim space, stop generation/preview activity and remove
unneeded files from `speech-cache`. Existing finished videos do not depend on it.
No API keys are included in cache identities or speech timeline metadata.

- `app/contracts/speech.py`: provider-limit-aware speech segmentation.
- `app/contracts/voices.py`: shared voice identifiers and segmentation capabilities.
- `app/infrastructure/media/speech.py`: provider dispatch, PCM conversion and cache.
- `app/infrastructure/media/audio.py`: edge trimming, PCM validation and pause measurement.
- `app/modules/production/voices.py`: catalog availability and preview lifecycle.
- `app/modules/production/render.py`: narration timeline, visuals and subtitle orchestration.

Each rendered run includes `speech-timeline.json` and the same `speech` section in
`manifest.json`: segment times/durations, removed boundary silence, provider, rate,
and internal pause warnings. Job voice checkpoints contain the trimming metrics.
FFmpeg diagnostics remain in `engine-error.log`; provider errors avoid echoing API
keys or returned audio URLs. Failed provider jobs are visible and retryable.

## Validation and limits of evidence

`pytest --feature speech -q` exercises continuous Vietnamese segmentation,
escaped UTF-8 limits, boundary/internal pause preservation, cache isolation/rate
changes, free-only voice validation, authenticated preview cleanup, UI preview without
queueing a render, and a real FFmpeg video
with one synthetic utterance spanning multiple visual/subtitle chunks.

Encoding uses deterministic PCM fixtures. These prove integration behavior, not
naturalness/pronunciation or provider availability. Live Edge access was blocked by
the cloud proxy during diagnosis. Listen to real provider previews before
choosing the final voice for a Vietnamese audience.

The test layout and per-layer commands are documented in [test_suite](../test_suite/README.md).
Edge WebSocket connections reuse an explicit WSS proxy or the injected HTTPS proxy,
respecting NO_PROXY. No TLS verification is disabled to make a provider test pass.
