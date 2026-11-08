# IELTS test cases

| ID | Trạng thái | Điều kiện/thao tác | Kết quả | Test |
| --- | --- | --- | --- | --- |
| IELTS-DB-001 | Implemented | Load schema/seed tạm; query sense/topic/sample | Giữ nghĩa riêng, quan hệ đúng, FK/integrity hợp lệ | integration/test_prototype.py::test_topic_senses_samples_and_single_focus_are_linked |
| IELTS-DB-002 | Implemented | Nhập hai focus, dangling FK, duplicate, sai module/JSON/pause | SQL reject; không nhận dữ liệu sai | integration/test_prototype.py::test_invalid_knowledge_is_rejected |
| IELTS-DB-003 | Implemented | Đọc trạng thái seed/rights/hash | Không có approval hoặc export readiness giả | integration/test_prototype.py::test_seed_cannot_be_mistaken_for_approved_content |
| IELTS-E2E-001 | Implemented baseline | Nhập một cụm tiếng Anh, sửa/lưu/reload/download, duyệt, chọn Aria, render, play/download/review, sửa lại | H.264/AAC 720×1280 thật; text/SRT đúng; hash đúng; approval bị hủy khi sửa; không publish | e2e/test_video_baseline.py |
| IELTS-E2E-002 | Implemented prerequisite gate | Mở app thật, đọc OpenAPI và kiểm tra tab thư viện | Fail khi API/UI thiếu; không giả vờ full acceptance pass | e2e/test_library_readiness.py |
| IELTS-E2E-003 | Planned M1/M2 | UI import preview → sửa dòng lỗi → commit → reimport | Hiển thị lỗi từng dòng, atomic, không duplicate, DB thật đúng | Chưa có implementation/test |
| IELTS-E2E-004 | Planned M2 | Chọn topic cha/con → entry → đúng sense → sample annotation | Không trộn nghĩa, filter/pagination giữ đúng bản ghi | Chưa có implementation/test |
| IELTS-E2E-005 | Planned M3 | Tạo brief, chọn hai focus rồi sửa còn một | UI/API reject hai focus, một mục tiêu được lưu | Chưa có implementation/test |
| IELTS-E2E-006 | Planned M3 | Duyệt script, sửa nguồn và export lại | Pin snapshot, phát hiện stale revision/rights | Chưa có implementation/test |
| IELTS-E2E-007 | Implemented first slice | UI tạo topic/từ → review → một focus → job → white-card → MP4 download | DB + checksum thật; audio PCM fixture; không publish, chưa có timeline quiz | e2e/test_library_flow.py |
| IELTS-E2E-008 | Planned M4 | Quiz có pause, answer riêng, lời đọc khác chữ | Không lộ answer sớm, pause thật, fingerprint đủ | Chưa có implementation/test |
| IELTS-E2E-009 | Planned live | Gọi Edge thật, nghe/phân tích output và dựng | Không dùng tone; provider lỗi phải fail; người nghe đánh giá phát âm | Chưa có implementation/test |

Không có skip/xfail dành cho IELTS thiếu implementation. Các mục planned là backlog có ghi rõ,
không tạo test chỉ assert True hoặc test mock chính tính năng mà nó tuyên bố kiểm tra.

Runtime API: `api/test_runtime.py` kiểm tra typed collections, import atomic/duplicate, fuzzy/topic,
optimistic version, edit hủy review, revision snapshots và hai SELECT cho 1/30 mục.
Các mục planned còn lại là thiết kế sâu hơn; xem docs/ielts-shorts/runtime.md.
