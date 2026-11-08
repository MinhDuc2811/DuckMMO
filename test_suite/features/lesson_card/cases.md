# Lesson card — cases

| ID | Layer | Yêu cầu | Test |
| --- | --- | --- | --- |
| LC-001 | unit | Thẻ trắng, chữ tối, nền ảnh không chuyển động ở 3 tỷ lệ | unit/test_layout.py::test_white_card_preserves_static_background_and_does_not_drift |
| LC-002 | unit | Nội dung quá dài phải reject, không truncate | unit/test_layout.py::test_long_content_is_rejected_instead_of_truncated |
| LC-003 | unit | Không burn caption trùng trong card, legacy vẫn có caption | unit/test_layout.py::test_white_card_suppresses_only_duplicate_burned_subtitles |
| LC-004 | unit | Clip đổi frame mà thẻ vẫn trắng | unit/test_layout.py::test_video_background_changes_while_white_card_stays_white |
| LC-005 | api | Catalog có Sonia/Ryan en-GB và preview thật | api/test_voice.py |
| LC-006 | integration | Ảnh/clip → card → mixer → MP4 thật, giữ SRT | integration/test_render.py::test_real_card_render_with_quiet_music_and_british_voice |
| LC-007 | integration | Nhạc 10%/ducking nhỏ hơn fixture narration | integration/test_render.py::test_music_stays_quieter_than_voice_during_speech |
| LC-008 | screen_flow | English mặc định UK; card music mặc định tắt; mức 10% khi bật; giữ lựa chọn | screen_flow/test_defaults.py |
| LC-009 | e2e | Browser chọn style, giọng, upload ảnh, cấu hình tới queue thật | e2e/test_choices.py |
| LC-010 | integration/live | Edge thật en-GB; không cache/tone; lỗi provider phải fail | integration/test_live_uk_voice.py |

Offline render dùng fixture PCM của bộ media hiện có, không mock renderer/encoder/mixer.
E2E dừng worker trước TTS; không tuyên bố test queue là kiểm tra giọng thật.
Baseline IELTS từ bước trước vẫn giữ riêng; lát cắt thư viện IELTS runtime đã có suite riêng.
