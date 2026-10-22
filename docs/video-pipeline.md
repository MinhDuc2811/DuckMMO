# Production through final video review

Content approval remains a separate gate from final video approval.

1. Phase 2 approves the current script: `approved`.
2. Upload image/clip assets through the streaming local media API when needed (see
   [local media](local-media.md)); DB rows contain metadata, file bytes stay on disk.
   `POST /api/jobs/{id}/render` checks the approved content hash, validates images or pins uploaded asset references,
   creates a unique artifact run, clears the prior video result and queues production.
3. The existing isolated worker recognises `render_config` and runs actual TTS/rendering,
   without recrawling or regenerating the script.
4. Each short caption gets real speech and measured WAV duration. Its frame uses the
   selected photo or a text-card background; the spoken caption is burned into the frame.
   A separate SRT file records the same measured intervals.
5. FFmpeg combines narration and the timed image sequence into H.264/AAC MP4, yuv420p,
   faststart, 24 fps. Audio/video streams are decoded for a basic validation and video
   duration is compared against narration duration before publishing the result to review.
6. Status becomes `awaiting_video_review`. Phase 4 plays the actual returned MP4 and
   offers video/SRT downloads plus approve/reject with notes.
7. Review checks the expected artifact hash, current script hash and the on-disk video.
   Approval sets `video_approved`; rejection sets `video_rejected` and allows a new render.

Editing an approved/reviewed script returns it to `awaiting_review` and clears render
configuration and video references. Old files remain on disk for recovery, but cannot be
served as current artifacts. Concurrent content changes cannot silently render/approve
the wrong revision. Cancelling production kills the worker and its TTS/FFmpeg descendants.

Artifacts are under `{artifact_dir}/{job_uuid}/{run_uuid}/`: video.mp4, narration.wav,
subtitles.srt, script.txt, poster.png, per-caption assets and manifest.json. UUID validation
and a fixed artifact-kind mapping avoid accepting file paths from the HTTP client.

Limits: 30,000 script characters per video, 10 images, 3 MB/image and 20 megapixels.
Visuals are user-uploaded images, one uploaded clip, or text cards. Clips loop/cut to
narration duration, discard original audio and use pad/crop with styled captions.
They are not AI-generated illustrations. Music,
automatic image sourcing/generation, transitions and social publishing are not implemented.
Speech timing is at caption/phrase level, not word-highlight karaoke.

Local synthesis uses Windows System.Speech with an installed matching-language voice,
preferring PowerShell 7. Edge TTS is an online alternative and reports provider/network
errors without substituting silent or fake speech. Tests on this machine use real local
Vietnamese voice, real uploaded PNGs, real FFmpeg encoding and real browser playback.
