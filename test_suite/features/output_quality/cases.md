# Output quality cases

- Unit: non-finite silence measurements become JSON null; true peak headroom warns without claiming distortion.
- Integration: real FFmpeg MP4 scan accepts a static background without rewriting; blocks silence,
  near-total black, absent audio, corrupt files, wrong duration/dimensions; records measured pause timecodes.
- API: real worker/FFmpeg with synthetic PCM speech persists exact artifact-bound report,
  authenticated report download and QA evidence; silent final output fails and cannot be approved.
- E2E: real browser/API/DB/worker/FFmpeg, explicit PCM speech fixture; download report from final
  review and compare with rendered artifact SHA; no automatic approval/publication.
- No external model/stock/TTS services are claimed tested. Default live skips remain unchanged.
- During development an API fixture initially assigned a plain string to SecretStr settings;
  corrected to SecretStr to exercise the existing authentication contract, assertions unchanged.

Run `uv run pytest --feature output_quality -q` and
`uv run pytest --feature output_quality --test-layer e2e -q --output test-results/output-quality/browser`.

Browser setup correction: a job already awaiting video review opens Phase 4 directly when
selected in Workspace (confirmed by navigation code and failure screenshot). Removed the
extra production-only navigation click; all report/hash/status assertions remain intact.
