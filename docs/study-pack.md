# Backgrounds and music

Phase 3 supports real stock discovery (Openverse images/audio, Pexels images/videos), three bundled
sample photographs, and user uploads. Stock results link to the original page for inspection
and download and export source metadata as JSON. The user then uploads the chosen file through
the existing bounded media storage. Search is not an automatic licensing decision or importer.
Set `STUDIO_PEXELS_API_KEY` in the backend environment; Openverse search needs no configured key
but may be rate limited. Secrets are never returned in search results. Provider failures are
reported and do not produce fabricated results. No arbitrary remote URL download was added.

Bundled real photos retain original JPEGs, source/license snapshots and credits under
`app/assets/study-pack/v3`. UI can download the attribution TXT. Rendering pins a checksum.
Image relevance and suitability behind the white card still need the author's judgment.

Music now defaults **off**, including fresh white-card jobs. The mix level starts at 10%
for the card when enabled, with ducking on. Existing saved choices are preserved. Upload a
track you have heard and have permission to use; preview music alone and voice+music before
rendering. The existing FFmpeg mixer performs loudness normalization, crossfaded looping,
ducking, fades and clipping checks. It cannot assess melody, fatigue or pronunciation.

The user rejected the generated v1–v4 music. Current v4 binaries remain only as explicit
legacy selections; they are not recommended or auto-chosen. Earlier duplicate media were
moved to `/workspace/archive/rejected-study-assets/` and downloadable ZIPs remain outside git.
The generator scripts are archived outside git with the rejected experiments; they are not the production music sourcing strategy.

Tests whose previous expectation was automatic Sunny Steps selection were updated because
of the user's explicit rejection and stop request. They now assert music is off by default;
manual legacy selection, pinned digest, quiet level, ducking and image credit remain covered.
This is a changed product requirement, not an assertion relaxed to hide a regression.

See [research and integration choices](research/shorts-toolkit/README.md).

The browser legacy-selection test clicks the visible Streamlit radio label, rather than its
covered input element. Trace showed the radio group intercepted pointer events; assertions
on checked state and the submitted config remain intact. No force-click or weakened timeout.

The clip-upload regression now waits for the production tab/rerun and exactly one
uploader before checking its unchanged Clip label. The failed trace showed both the
old image uploader and the new clip uploader in the DOM simultaneously. The IELTS
multiselect test dismisses its intentionally persistent popup with Tab before
accessing the next field. Provider fixtures and all final state assertions are unchanged.
