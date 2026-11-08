# Khung trắng cho video học tiếng Anh

## Cách dùng

1. Tạo nội dung với ngôn ngữ `en`, duyệt kịch bản.
2. Phase 3 → chọn ảnh hoặc clip có liên quan tới bài làm nguồn hình.
3. Chọn phong cách **Khung trắng**, giữ bố cục **Theo phong cách đã chọn**.
4. Giọng mặc định cho nội dung `en` là **Sonia · English (UK)**; có thể chọn **Ryan · English (UK)**.
5. Nhạc mặc định tắt theo phản hồi mới; khi bật, khởi đầu mức 10% và tự giảm nhạc khi có lời.
   Thay đổi của người dùng được giữ, không bật nhạc trở lại sau khi đã chọn tắt.
6. Nghe thử giọng + nhạc, dựng video, duyệt đầu ra thực tế rồi tải về.

Ảnh nền giữ tĩnh trong mỗi cảnh, không tự zoom/pan. Clip tiếp tục chạy sau thẻ trắng,
giữ cơ chế lặp/crop/pad hiện có và thay tiếng gốc bằng lời đọc/nhạc.
Ảnh/clip do người dùng chọn; có tìm stock theo từ khóa và tải metadata, chưa tự chọn hình theo topic.
Nếu không chọn nguồn hình, nền là màu mặc định; không khẳng định có ảnh liên quan tự động.

## Thiết kế

- Thẻ trắng bo nhẹ, bóng đổ, chữ tối, title nhỏ nằm trong thẻ. Không sao chép tài khoản,
  bình luận hoặc chỉ số tương tác từ ảnh tham chiếu.
- Mỗi cảnh giữ ít chữ; text quá dài không vừa sau điều chỉnh font sẽ báo lỗi, không cắt mất chữ.
- Nội dung hiện tại vẫn phân cảnh theo caption của renderer; đây chưa là scene editor IELTS
  có lời đọc/chữ hiển thị độc lập.
- Không burn thêm cùng lời đọc ở đáy video vì chữ đã nằm trong thẻ. SRT/ASS vẫn tạo để tải.
- Kho preset có thêm `lesson-card`, layout `lesson_card`; catalog presentation tăng lên v2.
- Các preset cũ, giọng cũ và API default tiếng Việt giữ tương thích.
- Nhạc dùng mixer cũ: normalize bed, volume và sidechain ducking; narration giữ riêng.
  Mức 10% là gain thiết lập, không phải chứng nhận mức loudness cho mọi file âm thanh.

## Kiểm tra đã thực hiện

- 73 kiểm tra offline liên quan presentation/speech/lesson-card đạt, gồm render FFmpeg thật
  trên ảnh và clip, giữ nền tĩnh, giới hạn text, trộn nhạc nhỏ và UI defaults.
- Toàn bộ suite offline sau thay đổi: **201 passed, 7 skipped**. Skip gồm các live tests opt-in
  và kiểm thử giọng Windows không khả dụng trên Linux; không phải bằng chứng live voice đạt.
- Playwright Chromium thật: chọn Khung trắng + Sonia UK + ảnh nền, music 10%/ducking tới queue: đạt.
- Integration dùng PCM tone thay speech; chỉ kiểm tra pipeline/encoding, không đánh giá phát âm.
- Đã thử gọi Edge thật cho Sonia và Ryan: **cả hai failed**, nguyên nhân ClientHttpProxyError 403
  từ policy mạng. Chưa có audio thật để nghe/đánh giá phát âm. Không đổi sang giọng Mỹ để che lỗi.
- Để thử giọng thật, môi trường chạy cần kết nối được dịch vụ Edge TTS
  (`speech.platform.bing.com` và các endpoint provider thực tế cần thiết), rồi chạy:

```bash
uv run pytest test_suite/features/lesson_card/integration/test_live_uk_voice.py --run-live-tts -q
```

Mỗi live test lưu result.json riêng tại `test-results/lesson-card/live/`; thành công mới có WAV.
Chọn locale en-GB không đủ chứng minh mọi IPA/từ riêng/từ học thuật phát âm chính xác;
người phụ trách nội dung cần nghe đoạn học thực tế trước khi duyệt.

## Thay đổi test theo yêu cầu mới

Test catalog cũ cố định đúng 6 preset. Do yêu cầu thêm Khung trắng, cập nhật thành đúng 7
và kiểm tra chính xác tập IDs gồm toàn bộ 6 preset cũ + lesson-card. Không bỏ assertion,
không hạ tiêu chí, không sửa các test audio/render cũ để che lỗi.

Các số kiểm tra ở trên là lịch sử riêng của bước dựng thẻ; kết quả tích hợp mới nằm trong báo cáo toolkit.
