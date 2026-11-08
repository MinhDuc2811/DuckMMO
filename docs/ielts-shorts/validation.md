# Kết quả kiểm tra database thử

Ngày 2026-11-08. Chạy bằng Python sqlite3, không cần cài package.

Database tạo mới, độc lập: `/workspace/ielts-preparation/ielts-shorts-prototype.sqlite`.
Báo cáo chi tiết: `/workspace/ielts-preparation/validation-report.json`.
Schema và seed nằm cùng thư mục tài liệu để tái tạo, không lưu binary vào repository.

## Kết quả

- 29 bảng, bao gồm các bảng nối; schema/seed load thành công.
- 31 kiểm tra cấu trúc/nghiệp vụ mẫu vượt qua; đây không phải bộ test production.
- `PRAGMA integrity_check`: ok; `PRAGMA foreign_key_check`: không có lỗi.
- Trường hợp dữ liệu không hợp lệ được thử trong savepoint rồi rollback, không để lại dữ liệu xấu.

Seed thực tế: 7 topic, 5 lexical entries / 6 senses, 3 patterns, 2 prompts,
2 sample versions / 3 segments, 3 exercises, 6 short briefs, 1 script revision / 5 scenes.
29 bảng không có nghĩa là 29 loại nội dung người dùng phải nhập; nhiều bảng chỉ là quan hệ.

Các nhóm kiểm tra:

- Tách hai nghĩa address; một sense thuộc nhiều topic; sample liên kết đúng sense.
- Mọi brief có đúng một focus; từ chối thiếu focus/hai focus/FK không tồn tại.
- Từ chối annotation chọn cả sense và pattern; bài tập có hai target.
- Từ chối JSON đáp án sai cú pháp, key từ vựng trùng, topic link trùng.
- Từ chối Writing module both, topic tự làm cha, pause âm và scene trùng vị trí.
- Không xóa được sense đang được tham chiếu.
- Tất cả nội dung có review status vẫn draft; nguồn chưa verified; script chưa có hash đủ export.

## Không được suy ra từ kết quả này

Chưa chạy PostgreSQL, Alembic production, API, UI, browser, TTS, render video hoặc benchmark dữ liệu lớn.
Không xác nhận chất lượng học thuật, phát âm, band IELTS, quyền tái sử dụng hay xu hướng YouTube.
SQL chỉ validate JSON cú pháp, không chứng minh đáp án đúng; dictionary ghi rõ phần service phải bổ sung.
Không có application code, migration hiện hữu, cấu hình môi trường hoặc dữ liệu app nào bị sửa.
Không commit, push hay xuất bản.
