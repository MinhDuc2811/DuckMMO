# Phong cách và nhạc nền (v1)

## Sử dụng

Bước chuẩn bị video có thư viện 6 preset, lựa chọn bố cục riêng (full/collage/panels/quote/mix),
mức chuyển động, màu nhấn và seed. Không ràng buộc style với branch nội dung.
`auto` là chế độ tương thích renderer cũ; tùy chỉnh bố cục/chuyển động chỉ áp dụng với preset mới.
Nút xem mẫu xuất GIF 2 giây bằng chính scene component của renderer, dùng hình minh họa;
đây không phải preview có ảnh/clip thật của cả job. Tuỳ chỉnh áp dụng toàn video ở v1.

Âm thanh có tắt nhạc, hai loop nền tổng hợp nguyên bản (không dùng bản thu bên thứ ba),
hoặc file upload WAV/MP3/FLAC/OGG/M4A tối đa 20 MB, 0,5–600 giây. Chỉ upload bản nhạc
có quyền sử dụng. Chỉnh volume 0–50%, offset và ducking. Nghe thử giọng + nhạc dùng TTS
thật (hoặc cache hợp lệ) và cùng mixer với bản xuất; cần provider miễn phí hoạt động.
Không thay giọng bằng âm thanh giả khi provider lỗi. Preview không đổi trạng thái job.

## Các owner

- `app/contracts/presentation.py`: options validation, catalog, resolver dữ liệu.
- `app/infrastructure/media/scene_components.py`: card, title, progress, rule,
  bubble, decorative geometry và các layout, không gọi AI hoặc chạy mã tải về.
- `app/infrastructure/media/scenes.py`: visual plan v1 + streaming 24fps -> FFmpeg.
- `app/infrastructure/media/music.py`: pin track, loop có crossfade, normalization,
  ducking, fade và limiter; `narration.wav` luôn giữ riêng.
- `app/modules/production/previews.py`: use case preview, locks, cleanup.
- `ui/components/presentation.py`: controls tái sử dụng; đọc catalog qua API.

Không thêm Revideo/Node/Chrome vào production ở v1: dùng Pillow đã có để có renderer
scene theo lớp với ít dependency, giữ registry/data contract để có thể thay adapter sau.
Đây không phải AI image-to-video hoặc automatic depth segmentation. Bố cục card/panel có
thể lặp lại cùng một asset. Nhạc nền có sẵn chỉ là nền tổng hợp đơn giản.

## Render, tài nguyên và debug

`prepare_render` pin snapshot style/options/seed, audio và ảnh/clip trong run folder.
DB chỉ chứa metadata/config và asset ID; không chứa audio/video base64.
Worker giữ một job; scene renderer là process con, bộ giám sát hiện có dừng cả descendants.
Ảnh đọc theo cảnh; clip decode tuần tự; mỗi lần chỉ giữ source/output frame, không giữ toàn
video trong RAM. Có timeout và kiểm tra dung lượng trước render. Giới hạn đồng thời có
sẵn vẫn áp dụng. Không tuyên bố benchmark throughput sản xuất từ smoke test ngắn.

`scene-plan.json`: timeline/layout/seed/style/renderer version của lượt dựng.
`speech-timeline.json`: timeline giọng gốc, không chia lại theo animation.
`narration.wav`: lời đọc nguyên bản; `music-loop.wav`: đoạn nhạc tối đa 60 giây nối mềm;
`soundtrack.wav`: audio đã trộn; `motion.mp4`: visual intermediate; `video.mp4`: thành phẩm.
`manifest.json`: lựa chọn presentation/music và QA. File audio pin dùng digest và snapshot;
xóa asset thư viện không phá lượt render đã queue.

Nhạc được normalize, giảm theo volume, duck theo giọng, fade đầu/cuối và limiter.
TTS dùng cache hiện có; đổi style/nhạc không đổi cache key lời đọc. Bộ trộn không sửa WAV gốc.
Mức âm lượng cuối vẫn cần nghe đánh giá; kiểm tra PCM không chứng minh cảm nhận tự nhiên.
Intermediate làm tăng dung lượng; cần cleanup theo lifecycle local hiện có.

## API và kiểm thử

- GET `/api/production/catalog`
- POST `/api/production/style-preview` (`VisualOptions`) -> GIF
- POST `/api/jobs/{id}/assets?kind=audio` -> local asset metadata
- POST `/api/jobs/{id}/audio-preview` (`VoicePreview` + `music`) -> WAV
- POST `/api/jobs/{id}/render`: thêm `visual`, `music`, request cũ giữ nguyên defaults.
- GET `/api/jobs/{id}/artifacts/soundtrack`: tải bản mix, audio cũ vẫn là narration.

`uv run pytest --feature presentation -q`; thêm `--test-layer e2e --browser chromium`
để chạy browser thật. Integration dùng FFmpeg thật và fixture speech, không xác nhận Edge live.
Giữ nguyên các test regression cũ và rule không sửa test để hợp thức hóa bug.

## Kết quả xác minh của đợt triển khai

- Offline cuối: **172 passed, 5 skipped** (Windows/live provider theo scope hiện có).
- Lint/format và kiểm tra diff whitespace đạt. Test mới nằm ở feature `presentation`,
  đủ 5 tầng. Kiểm tra reuse không phát hiện vi phạm mới; điểm heuristic không chứng minh
  correctness hoặc performance.
- Browser thật dùng `/usr/bin/chromium` qua helper môi trường
  `/workspace/shared/duckmmo_test_browser.py` vì CDN tải Chromium của Playwright trả 403.
  Lượt mở rộng: 8 passed, 3 failed. Hai ca video/quality legacy gọi Edge thật thất bại
  do proxy HTTP 403; ca crawl nhiều nguồn lỗi DNS. Không sửa/skip các ca này để báo pass.
  Ca chọn style/nhạc mới và regression upload clip/chọn giọng đều đạt.
- Integration kiểm tra cả encode/decode clip thật, ducking bằng RMS, bảo toàn narration,
  worker checkpoints/artifact downloads, xóa asset sau queue, thiếu dung lượng,
  cancel và timeout có thu hồi encoder/decoder. Speech integration dùng fixture PCM,
  không phải bằng chứng chất lượng giọng live.
- Đo scene stage cuối bằng runner cố định `test_suite/support/presentation_benchmark.py`:
  ảnh 1920×1080, output 720×1280, 24 fps, 2 thread; 30 giây mất 27,02 giây,
  60 giây mất 43,81 giây. Peak RSS tổng renderer + FFmpeg khoảng 234,3 MiB ở cả hai.
  Đo trên instance hiện tại có workload chia sẻ; không gồm TTS/mix/final encode,
  không có baseline renderer scene cũ và không phải cam kết throughput production.
