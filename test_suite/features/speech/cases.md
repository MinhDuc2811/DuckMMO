# Speech test cases

Các case sử dụng giọng miễn phí; không thêm provider TTS trả phí.

| ID | Tầng / file | Thao tác và kết quả mong đợi |
| --- | --- | --- |
| SPT-U01 | unit/test_cases.py | Script liền >105 ký tự: giữ một utterance khi nằm trong giới hạn provider |
| SPT-U02 | unit/test_cases.py | Script dài: không mất từ/dấu câu, mỗi đoạn nằm trong giới hạn; text rỗng không tạo đoạn |
| SPT-U03 | unit/test_cases.py | Tiếng Việt + XML special chars: từng đoạn ≤3500 byte escaped UTF-8 |
| SPT-U04 | unit/test_cases.py | ID giọng trả phí bị schema từ chối |
| SPT-U05 | unit/test_cases.py | WSS dùng HTTPS proxy hiện có nếu không có WSS override |
| SPT-U06 | unit/test_cases.py | WSS override có ưu tiên; NO_PROXY được tôn trọng |
| SPT-A01 | api/test_cases.py | Catalog chỉ Edge/Windows; preview validation, WAV thật từ fixture, dọn file tạm; unknown voice/rate sai bị từ chối |
| SPT-A02 | api/test_cases.py | Catalog/preview yêu cầu auth khi cấu hình; preview dùng đúng artifact root của app |
| SPT-I01 | integration/test_cases.py | Trim chỉ biên nối, giữ khoảng nghỉ nội bộ và biên ngoài; ghi duration đúng |
| SPT-I02 | integration/test_cases.py | Cache dùng lại PCM; sửa file render không làm hỏng cache; đổi rate tạo yêu cầu khác |
| SPT-I03 | integration/test_cases.py | MP4 FFmpeg thật: một TTS call có nhiều image/subtitle chunk và speech timeline |
| SPT-I04 | integration/test_cases.py | Audio im lặng không được lưu cache |
| SPT-S01 | screen_flow/test_cases.py | Tạo → duyệt nội dung → Phase 3 → nghe thử: UI không lỗi, gửi đúng giọng, không queue video |
| SPT-E01 | e2e/test_voice_selection.py | Browser chọn Nam Minh và rate +10 → DB giữ đúng config; không có voice trả phí |
| SPT-L01–04 | integration/test_live_edge.py | Hoài My/Nam Minh × script liền/có dấu câu → audio thực + MP4; không cache/mock provider; lỗi dịch vụ báo failed |

## Giới hạn bằng chứng

Offline integration/screen-flow dùng PCM fixture, không chứng minh chất giọng thật.
E2E offline queue xong dừng trước gọi TTS. Live chạy riêng có network prerequisite.
Audio/video hoàn thành cần nghe thủ công để chấm phát âm/ngữ điệu và chất lượng.

## Chỉnh test vì lỗi test, không vì application sai

- Sau relocation, AppTest lấy `PROJECT_ROOT` từ common helper thay vì `parents[1]` của
  file cũ. Assertion và hành vi mong đợi không thay đổi.
- SPT-E01 lần đầu dùng `to_contain_text` trên Streamlit combobox. DOM thực là `<input
  role="combobox" value="Nam Minh · nam · Microsoft Edge">`, nên `textContent` rỗng dù
  chọn đúng. Sửa sang `to_have_value` với đầy đủ nhãn chính xác; không đổi expected
  voice và vẫn kiểm tra config trong database. Đây là sửa phép đọc DOM bị sai.

- Với slider Streamlit 1.66, accessible name của input range bị lặp nhãn và giá trị
  là native `value`, không có attribute `aria-valuenow`. Chọn group theo nhãn rồi
  slider bên trong, kiểm tra `to_have_value("10")`. Vẫn giữ thao tác ArrowRight
  và assert `speech_rate == 10` trong DB; không giảm kỳ vọng sản phẩm.
