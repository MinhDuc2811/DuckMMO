# AI Content Studio

Dự án MMO (Make Money Online): một ứng dụng cho ba nhánh **Comic / Novel / Research**,
dùng chung Content Package, AI Gateway và Video Engine. Tên repository cũ là DuckMMO.

Hiện thực **Sprint 0 — Foundation** theo bản tóm tắt Master Plan V1:
FastAPI, Streamlit, SQLAlchemy, migration Alembic, PostgreSQL hoặc SQLite local,
hàng đợi job bền vững, kiểm tra Content Package và duyệt thủ công có audit trail.
Chưa có DOCX gốc nên schema và backlog là đề xuất tạm, chưa phải bản đối chiếu đủ 18 mục.

## Chạy local (PowerShell)

Yêu cầu Python 3.12+ và uv. Không cần API key AI hoặc Docker cho chế độ SQLite.

```powershell
uv sync --group dev
Copy-Item .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở terminal thứ hai để chạy worker:

```powershell
uv run python -m app.worker
```

Mở terminal thứ ba để chạy UI:

```powershell
uv run streamlit run ui/studio.py --server.address 127.0.0.1
```

UI: http://127.0.0.1:8501 · Swagger: http://127.0.0.1:8000/docs.
**Phase 1 · Nguồn & phân tích**: nhập một hoặc nhiều URL (mỗi dòng một link), chọn nhánh,
bấm Bắt đầu Phase 1. Worker tải từng nguồn bằng crawler HTTP chung, trích xuất văn bản,
lưu nguồn gốc rồi gọi dịch vụ AI phân tích và viết lời dẫn. Lỗi ở bất kỳ bước nào giữ job
ở Phase 1, ghi rõ stage lỗi và cho retry. Không còn domain allowlist hay selector riêng cho website.

Để chạy phân tích AI thật, cấu hình trong `.env`:

```dotenv
STUDIO_ANALYSIS_BASE_URL=https://your-provider.example/v1
STUDIO_ANALYSIS_MODEL=your-model
STUDIO_ANALYSIS_API_KEY=your-key
```

Provider cần hỗ trợ API `/chat/completions`. Không có cấu hình thì crawl vẫn chạy và lưu
nguồn, nhưng analysis dừng với lỗi rõ ràng, không lấy raw text giả làm kết quả AI.
Retry sau khi cấu hình sẽ dùng lại nguồn đã lưu.

**Phase 2 · Kiểm duyệt**: chỉ hiển thị nội dung Phase 1 thành công. Đọc, sửa, lưu, duyệt,
và tải file TXT. Không crawl hoặc gọi AI trong Phase 2. Sửa nội dung đã duyệt đưa về
chờ duyệt; không tự chạy lại Phase 1.
Nhánh nhập thủ công dành cho kịch bản đã chuẩn bị, chỉ kiểm tra cấu trúc.
`approved` là duyệt nội dung, chưa phải video hoàn thành hoặc đã xuất bản.

**Phase 3 · Sản xuất video (bước 5–6)**: chọn kịch bản đã duyệt, giọng đọc Việt/Anh,
khung dọc 720×1280 hoặc ngang 1280×720, thêm tối đa 10 ảnh PNG/JPEG (3 MB/ảnh),
rồi bấm **Dựng video**. Không thêm ảnh thì video dùng nền chữ. Worker tạo giọng đọc
thật, đo thời lượng từng đoạn, tạo phụ đề, ghép hình và tiếng thành H.264/AAC MP4.
Theo dõi hoặc dừng tác vụ trong Workspace.

**Phase 4 · Duyệt video (bước 7)**: mở video từ Workspace hoặc chọn tab này, phát MP4,
tải video/phụ đề, nhập nhận xét rồi **Duyệt video** hoặc **Yêu cầu chỉnh sửa**.
Video bị trả lại có thể dựng lại; sửa kịch bản làm mất hiệu lực video cũ và yêu cầu duyệt
lại nội dung. Chỉ video dựng và kiểm tra thành công mới xuất hiện ở bước này.

Giọng trên máy dùng Windows System.Speech (cần giọng tương ứng; PowerShell 7 ưu tiên).
Đã kiểm thử giọng Việt Microsoft An trên máy hiện tại. Giọng Edge TTS cần Internet;
không cần API key. FFmpeg được đóng gói qua imageio-ffmpeg, không yêu cầu cài vào PATH.
File được lưu trong `STUDIO_ARTIFACT_DIR` (mặc định `data/artifacts`).

**Workspace ở thanh bên trái** tự cập nhật mỗi 2 giây, liệt kê mọi tác vụ đang chờ/chạy/đang dừng
và 20 tác vụ kết thúc gần đây. Bấm **Dừng tác vụ** để hủy tác vụ trong hàng đợi hoặc ngắt
tiến trình riêng của tác vụ đang chạy. Trạng thái `cancelling` chỉ chuyển `cancelled` sau
khi tiến trình đã được dừng; dữ liệu đã commit vẫn được giữ lại. Tác vụ đã kết thúc
hiển thị trạng thái kết quả, không có nút kill vì không còn tiến trình chạy.
Bấm vào tên tác vụ để mở đúng nguồn/tiến trình ở Phase 1 hoặc nội dung ở Phase 2.
Nút **Xóa** đưa tác vụ đã kết thúc vào thùng rác; **Hoàn tác xóa** khôi phục dữ liệu.
Tác vụ đang chạy phải được dừng trước khi xóa. Nút **Nội dung mới** mở luồng tạo mới.

## Dùng clip làm nguồn hình

Phase 3 hỗ trợ **Ảnh / Clip**, tải file và tái sử dụng nguồn đã lưu. Clip ngắn tự lặp
cho đủ lời đọc; clip dài được cắt theo thời lượng đầu ra. Có lựa chọn giữ đủ hình
hoặc crop giữa; tiếng gốc được thay bằng lời đọc. Cần FFprobe trên PATH (thuộc gói
FFmpeg hệ thống), rồi chạy `uv run alembic upgrade head`.

File lưu trên đĩa local; SQLite chỉ lưu metadata và ID. API nhận file theo từng khối,
worker dựng tuần tự, có giới hạn dung lượng/CPU và dọn các lượt dựng cũ không còn
được tham chiếu. Xem [thiết kế, giới hạn, API và debug local media](docs/local-media.md).
Streamlit vẫn giữ file upload trong RAM trước khi gửi API; dùng API streaming cho
batch lớn và giữ file tải qua UI nhỏ.

## PostgreSQL

```powershell
docker compose up -d postgres
```

Đổi `STUDIO_DATABASE_URL` trong `.env` thành
`postgresql+psycopg://studio:localdev@localhost:5432/studio`, rồi chạy migration.
Dữ liệu SQLite không tự chuyển sang PostgreSQL. Compose dùng mật khẩu local mặc định;
có thể đặt `POSTGRES_PASSWORD` và cập nhật URL tương ứng.

## Kiểm tra

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Test trình duyệt thật bằng Playwright:

```powershell
./scripts/test-e2e.ps1
./scripts/test-e2e.ps1 -LiveWeb
```

Chi tiết phạm vi, dữ liệu mẫu AI và ảnh/video/trace: [e2e/README.md](e2e/README.md).

Test dùng database tạm và chạy migration thật. Dependencies được khóa trong `uv.lock`.
API dùng header `Idempotency-Key` để gửi lại an toàn; cùng key khác nội dung trả 409.
Đặt `STUDIO_API_KEY` để yêu cầu `X-API-Key` cho API và UI; mặc định dành cho localhost.

## Phạm vi hiện tại

- Ba nhánh dùng chung schema, có nguồn, ghi chú quyền sử dụng và tham chiếu nguồn từng cảnh.
- Worker chạy crawl → lưu nguồn → AI analysis → chờ duyệt cho URL; preflight cho nội dung nhập tay.
- Job: queued → running → awaiting_review → approved/rejected; lỗi → failed, retry tối đa 3 lần.
- Worker và audit dùng cùng database; UI gọi API, không ghi database trực tiếp.
- Crawler chung HTTP/HTTPS + Trafilatura; chặn mạng nội bộ, giữ kiểm tra TLS, xác thực redirect, giới hạn dữ liệu.
- Trang cần JavaScript/đăng nhập/CAPTCHA có thể chưa đọc được; trả lỗi thay vì báo thành công giả.
- Có adapter AI theo cấu hình; chưa cấu hình model/key và chưa kiểm thử AI trả phí thực tế.
- Có giọng đọc, phụ đề, dựng MP4 và duyệt video. Chưa có tự sinh hình minh họa hoặc nhạc nền.
- Crawl4AI/render trình duyệt, OCR, search, RAG, n8n và xuất bản chưa tích hợp.
- Chạy **một supervisor local**; mỗi job thực thi trong một tiến trình con riêng. Supervisor
  kiểm tra yêu cầu dừng mỗi 0,2 giây, terminate/kill đúng tiến trình con do nó tạo.
  Khởi động lại supervisor phục hồi trạng thái job bị ngắt thành failed/cancelled.
  Chưa hỗ trợ nhiều supervisor đồng thời hoặc lease phân tán.
- PostgreSQL có cấu hình và migration; cần Docker đang hoạt động để kiểm thử thực tế.

Xem [backlog](docs/backlog.md) và [quyết định kiến trúc](docs/architecture.md).

Automatic styles: new renders choose a content-specific preset and burn styled ASS captions with FFmpeg/libass. See [automatic styles](docs/auto-styles.md) for catalog sync, pinned versions and phrase-timing limitations.
