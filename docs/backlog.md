# Backlog theo Master Plan V1 (tạm từ trang chia sẻ)

Nguồn: https://chatgpt.com/s/t_6ad8c23195fc8191835fc846ff5c5e35
Trang chỉ cung cấp bản tóm tắt; cần file DOCX gốc để đối chiếu 18 mục và tiêu chí nghiệm thu.

| Sprint | Phạm vi | Trạng thái |
| --- | --- | --- |
| 0 Foundation | Môi trường, Content Package, schema, migration, tests, API/UI nền tảng | Đã triển khai; chờ đối chiếu DOCX và kiểm thử PostgreSQL |
| 1 Core + Video | AI Gateway, job lease/heartbeat, TTS, FFmpeg, phụ đề, artifact storage | Có AI adapter, TTS, MP4, phụ đề, lưu artifact và duyệt video; lease phân tán còn thiếu |
| 2 Novel | TXT/EPUB ingestion, recap, scene planning → video | Có URL → analysis → duyệt → video; TXT/EPUB chưa tích hợp |
| 3 Comic + Chinese | OCR Nhật/Hàn/Trung, panel order, DeepSeek benchmark | Chưa triển khai |
| 4 Research | SearXNG, Crawl4AI, citations, fact-check, RAG | Chưa triển khai |
| 5 QA & Optimization | benchmark, quota, cache, retry/backoff, chi phí, vận hành | Chưa triển khai |

## Tiêu chí Foundation đề xuất

- Một schema dùng chung cho ba nhánh; từ chối gói sai cấu trúc hoặc tham chiếu nguồn không tồn tại.
- Migration tái lập được database rỗng; cấu hình database không hardcode trong code.
- API/UI tạo, liệt kê, xem, duyệt nội dung và xem lịch sử xử lý.
- Worker không tự duyệt. Chỉ job chờ duyệt nhận quyết định, không ghi đè quyết định cũ.
- Gửi lại cùng idempotency key không tạo job trùng; retry giới hạn ba attempts.
- Lỗi nội bộ không đưa chi tiết exception ra response.
- Kiểm thử không phụ thuộc dịch vụ AI hoặc credential thật.

## Cần xác minh trước khi nối dịch vụ

- DOCX gốc, danh sách model Leader/Worker, API tier và quota.
- GPU/VRAM, benchmark DeepSeek/Gemini, OCR với nội dung thực tế.
- Phạm vi quyền sử dụng nguồn, người duyệt, định dạng video và mức QA.
- Kế hoạch 300 nội dung/tháng, ngân sách trần và quy tắc model routing.
- n8n orchestration, hợp đồng API adapter và cách lưu artifact.


## Harness chất lượng và vòng cải thiện

Kế hoạch xuyên suốt các bước: [quality-learning-plan.md](quality-learning-plan.md).
Các ticket H01–H12 hiện ở trạng thái **Planned**, chưa triển khai. Thứ tự:
A — ghi dữ liệu/revision/feedback; B — đánh giá và repair có giới hạn;
C — benchmark và promotion/rollback; D — publish và analytics; E — fine-tune có điều kiện.
Epic này mở rộng Sprint 5 và đưa hook vào các sprint trước; không chờ làm xong publish mới thu feedback.
