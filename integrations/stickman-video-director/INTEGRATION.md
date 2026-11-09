# Pinned upstream subset

This directory vendors the local renderer, required font/pose/style-lock resources and
Skill/reference documents from kaomei/stickman-video-director. UPSTREAM.json records the
exact revision, original URLs, file hashes and local paths. LICENSE is upstream MIT;
font assets retain OFL-Caveat.txt and OFL-NotoSans.txt. The native canvas npm package has
its own MIT license. Model/provider/assets not bundled here need their own terms.

bridge.mjs is app-owned and selects trusted FFmpeg/FFprobe paths, removes inherited font
overrides and forwards only allowlisted commands. Upstream renderer scripts are not
reimplemented. Optional generation/finishing helpers are preserved as text snapshots
(.py.txt / .mjs.txt), not registered or executed as app/provider adapters. The Python
bridge restricts local paths further than the original trusted-local CLI does.

Python app and project data are outside this directory. Do not put generated projects,
credentials or installed node_modules in Git. See ../../docs/stickman-studio.md for setup,
actual capabilities, separate workspace, lifecycle and local limits.
