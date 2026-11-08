# Chuẩn bị data trước khi nhập kho

## Bộ bàn giao đề xuất

Google Sheets dùng để biên soạn/review, CSV UTF-8 hoặc JSON dùng bàn giao.
Một workbook có các sheet dưới đây; không gộp từng topic thành một database/file schema riêng.
`external_key` ổn định trong một dataset; trường FK tham chiếu external key, importer đổi sang UUID.
Không dùng số dòng Sheet làm ID.

| Sheet | Cột tối thiểu |
| --- | --- |
| sources | external_key, title, kind, publisher, edition, url, verification_status |
| source_items | external_key, source_key, locator, rights_status, rights_note |
| topics | external_key, code, name_en, name_vi, parent_key |
| vocabulary_entries | external_key, headword, kind |
| vocabulary_senses | external_key, entry_key, sense_number, part_of_speech, definition_en, meaning_vi, usage_note, source_item_key |
| sense_topics | sense_key, topic_key |
| vocabulary_examples | external_key, sense_key, text_en, translation_vi, source_item_key |
| patterns | external_key, kind, title, template, explanation_vi, usage_limits, source_item_key |
| pattern_examples | external_key, pattern_key, correct_text, translation_vi, incorrect_text, explanation_vi, source_item_key |
| prompts | external_key, module, skill, task_part, text_en, source_item_key |
| samples | external_key, prompt_key, kind, title, source_item_key |
| sample_versions | external_key, sample_key, version, parent_version_key, revision_note |
| sample_segments | external_key, version_key, position, role, text_en, translation_vi |
| sample_annotations | external_key, segment_key, quoted_text, occurrence, sense_key hoặc pattern_key, note_vi |
| exercises | external_key, format, question_text, một target key, response_spec_json, answer_key_json, explanation_vi, evidence, source_item_key |
| short_briefs | external_key, title, objective, format, một focus key, target_seconds |

Các bảng nối topic/label còn lại, pronunciation/forms/relations và scenes xuất theo field schema.sql
khi có dữ liệu thật. Không điền audio URL/IPA/band giả để đủ cột. Null có ý nghĩa khác chuỗi rỗng.
Trong CSV có JSON dùng chuẩn CSV quoting; trường JSON vẫn là JSON, không phải Python repr.
Giới hạn độ dài/enum và các field bổ sung sẽ được khóa trong Pydantic contracts ở M1.

## Pilot đề xuất

Chọn 3 topic hẹp: Online learning, Remote work, Pollution.
Mỗi topic chuẩn bị khoảng 10 nghĩa/cụm từ, 3 mẫu cấu trúc, 2 prompt và 2 sample ngắn.
Một số cấu trúc dùng chung: nhập một lần rồi liên kết, không buộc đủ số lượng bằng bản sao.
Tổng mục tiêu pilot: khoảng 30 senses, 6–9 patterns duy nhất, 6 prompts, 6 samples,
12 bài tập và 12 brief một mục tiêu. Số lượng là kế hoạch biên tập, không phải seed hiện có.

Seed hiện có nhỏ hơn pilot, chỉ minh họa mô hình. Có cả address noun/verb để phát hiện hệ thống
trộn nghĩa, một sense thuộc nhiều topic, và một điểm kiến thức được dùng ở nhiều Short.

## Quy trình nhập

1. Biên soạn mục tiêu học; chọn nghĩa/cách dùng cụ thể và nguồn cần kiểm chứng.
2. Tự viết ví dụ/sample; đánh dấu tự biên soạn/AI hỗ trợ, không giả là đề chính thức.
3. Gán topic và label có sẵn; đề xuất taxonomy mới riêng nếu chưa có, không sinh free tags.
4. Người kiểm duyệt đối chiếu nghĩa, tự nhiên, ngữ pháp, đáp án/evidence và quyền sử dụng.
5. Tạo file import; preview trả lỗi theo sheet/dòng/field và gợi ý duplicate, không ghi production.
6. Sửa lỗi; commit một batch atomically; lưu dataset ID, digest, counts và người thực hiện.
7. Từ nội dung đã duyệt chọn một focus để viết brief; soạn script có text hiển thị tách lời đọc.
8. Duyệt revision; nghe/xem video thật sau dựng trước khi quyết định đăng.

Importer/API ở bước 5–6 thuộc kế hoạch coding, chưa tồn tại. Hiện schema/seed chỉ chạy local
để thử mô hình, không là đường tắt đưa nội dung vào production.

## Checklist chất lượng dữ liệu

- Không trộn hai nghĩa vào một record; không coi near synonym là luôn thay thế được.
- Example minh họa đúng nghĩa; sample annotation match đúng đoạn và đúng occurrence.
- Dạng cấu trúc là grammar/expression/discourse, có giới hạn cách dùng.
- Mọi câu hỏi có key, giải thích và evidence; không tạo distractor cũng đúng trong ngữ cảnh.
- Writing/Speaking samples không có một đáp án duy nhất hoặc band tự khẳng định.
- Quyền nguồn chưa rõ vẫn giữ unknown/reference-only, không tự đổi thành được phép dùng.
- Không lấy nguyên sách, đề, audio thương mại để lấp kho; lưu locator và ghi chú tham khảo trước.
- Một brief không chứa hai focus dù cùng topic; chấp nhận tách thành nhiều video.
- Tất cả dữ liệu nhập đầu tiên là draft; review có người/phiên bản, không duyệt bằng cột tự khai.

## Tiêu chí sẵn sàng xây M1

Prototype truy được các câu hỏi: từ này có những nghĩa nào; nghĩa nào thuộc topic; sample nào dùng
nghĩa đó; mẫu although nằm ở đâu; focus nào đã có brief; ví dụ và quiz có cùng target không.
Pilot sau đó cần được người phụ trách nội dung duyệt. Seed minh họa chưa đáp ứng bước duyệt này.
