# Presentation and soundtrack cases

- Unit: reject invalid/multiple music sources, nonfinite volumes and arbitrary templates;
  all six styles work across all branches; deterministic seeded plans and moving layers;
  old requests retain defaults.
- API: catalog and real GIF preview; real WAV upload/probe/deduplication;
  cross-job isolation; pinned audio survives asset deletion; malformed audio and offsets;
  mixed preview uses fixture speech and the real mixer.
- Integration: real FFmpeg mixing, measured ducking, unmodified narration and duration;
  four real scene encodes; full production export with fixture speech (no live provider).
- Screen flow: style and music selection independently reach component output.
- E2E: real Chromium/UI/API/DB queues selected style + track, renders GIF preview;
  worker stopped before external speech. Live Edge is not verified here.

Tests must not be weakened to fit faulty production behavior; see test_suite/AGENTS.md.
