# Ambient background / delivery cases

- API: Final requires lesson-card; optimized background requires an owned clip and lesson-card.
- Integration: real gradient clip demonstrates reduced decoded pixel jump across loop seam;
  head buffer <=64 MB, selected intervals stay in range, closing generator reaps decoder.
- Integration: red/blue source hard cut selects the longer single shot through real FFmpeg scene detection.
- Integration: Final creates 1080×1920/30fps MP4; exact H.264 packet hash survives mux and right control region stays outside white card.
- E2E: browser uploads clip, chooses Final + ambient optimization, invokes actual renderer/QA, downloads MP4 and remains awaiting review.
- Only speech is a declared synthetic tone; no external stock/AI/TTS service or real platform publication is claimed.
- Existing preview/regression defaults and test assertions are retained; no new skip/xfail added.

- API wallpaper regression: original 3840×2160 image is cropped before resizing to portrait Full HD,
  through the shared image preparation owner; preview image behavior is retained.
- Final render variants cover lesson-card preset, auto + explicit lesson_card layout, and another
  preset + explicit lesson_card layout, avoiding an accepted-contract branch with missing PRESETS[auto].
