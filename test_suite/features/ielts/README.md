# IELTS: database checks và Playwright

## Phạm vi hiện tại

Đã có thư viện IELTS runtime đầu tiên (Alembic 0006); schema thử vẫn độc lập. Bộ test không tạo API/UI giả để chứng minh
tính năng đã hoàn thành. Có các phần độc lập:

1. **Database**: schema/seed thật trên SQLite tạm; kiểm tra quan hệ, một focus, reject dữ liệu sai.
2. **Video baseline**: browser thật → Streamlit → FastAPI → database migrated → test worker →
   FFmpeg thật → phát/tải MP4 + SRT → duyệt video → sửa script hủy approval/video cũ.
3. **Readiness**: kiểm tra các API IELTS được thiết kế và tab thư viện. Thiếu implementation là
   **failure**, không skip/xfail; readiness pass cũng chưa chứng minh hành trình thư viện hoàn chỉnh.

4. **Library flow**: UI tạo topic/từ → duyệt → soạn một ý → job → white-card MP4 → tải file,
   kiểm tra dữ liệu và checksum thật; TTS là PCM fixture được khai báo. API test bao phủ import,
   hai nghĩa riêng, revision/source invalidation và query count.

Baseline lấy một cụm từ trong prototype làm input, nhập qua UI thủ công hiện hữu. Nó không import
kho vào app, không kiểm tra IELTS branch và không đại diện cho tính năng thư viện đã được tích hợp.
Legacy branch vẫn là novel; test ghi nhận điều này, không ánh xạ giả thành IELTS.

## Setup

Từ root repository, Python 3.12+, uv:

```bash
uv sync --frozen --group dev --python 3.12
uv run playwright install --with-deps chromium
```

Cần FFmpeg hệ thống có `ffprobe` trên PATH để kiểm tra stream video/audio sau tải.
Trên máy đã có Chromium, không cần tải browser thứ hai:

```bash
uv run python scripts/test_ielts_e2e.py --browser-executable /usr/bin/chromium
```

Trong môi trường cloud hiện tại, cache uv mặc định không ghi được. Dùng cache user-owned:

```bash
UV_CACHE_DIR=/tmp/duckmmo-uv-cache uv sync --frozen --group dev --python 3.12
.venv/bin/python scripts/test_ielts_e2e.py --browser-executable /usr/bin/chromium
```

PowerShell sau setup: `uv run python scripts/test_ielts_e2e.py`.
`--browser-executable` chỉ nhận file Chromium, không nhận URL/database ứng dụng của người dùng.
Nếu không chỉ định, fixture dùng `/usr/bin/chromium` qua PATH khi có, hoặc browser Playwright đã cài.
Không tự thêm `--no-sandbox` hay sửa chính sách máy để browser chạy.

## Các lệnh

```bash
# Toàn bộ: database + baseline + readiness, có exit code khác 0 khi IELTS chưa có.
uv run python scripts/test_ielts_e2e.py

# Chỉ kiểm tra video flow hiện tại, không khẳng định IELTS library đã hoạt động.
uv run python scripts/test_ielts_e2e.py --suite baseline

# Chỉ schema/seed SQLite.
uv run python scripts/test_ielts_e2e.py --suite database

# Chỉ gate kiểm tra API/UI IELTS.
uv run python scripts/test_ielts_e2e.py --suite readiness

# Có màn hình/display thì có thể xem browser.
uv run python scripts/test_ielts_e2e.py --suite baseline --headed
```

Chạy trực tiếp qua convention repository:

```bash
uv run pytest --feature ielts --test-layer e2e --browser chromium \
  --tracing on --screenshot on --video off --output test-results/ielts/manual -q
uv run pytest --feature ielts --test-layer integration -q
```

Không sửa discovery, skip, expected results hay thresholds để readiness xanh khi chưa có tính năng.
Mặc định `pytest -q` vẫn theo quy tắc repository: browser opt-in; prototype integration được chạy offline.
Suite `all` bao gồm cả readiness gate và library flow; không bỏ gate khi API thiếu. Không dùng `baseline` rồi báo toàn tính năng pass.

## Fixture và giới hạn

- API/UI là các process thật, migration Alembic thật, database/ports/artifacts riêng cho từng test.
- Dùng `e2e.conftest.Stack`, lifecycle và evidence hiện có; cleanup process do fixture sở hữu.
- Worker test dùng claim/pipeline/render thật qua dependency injection; **không kiểm tra supervisor
  production**. Provider speech tạo PCM tone có tín hiệu, không gọi Microsoft và không phải giọng nói.
- Không mock route UI/API, không dùng HTML giả. AI/crawler trong worker offline phải fail nếu bị gọi.
- Chọn Aria trong UI và assert config đến renderer; điều này không xác nhận chất lượng phát âm Aria.
- Chỉ nội dung tự biên soạn để test; không thực hiện upload/xuất bản YouTube. Kiểm tra publish list rỗng.
- TTS thật, bilingual, pause từng cảnh, overlay đáp án, tìm kho, import, review học thuật và quyền
  sử dụng chưa được baseline chứng minh; xem cases.md cho coverage còn chờ.

## Evidence

Runner tạo thư mục riêng `test-results/ielts/<UTC timestamp>-<random>/`:

- `results.xml`: JUnit gồm test pass/fail/error, không tự chuyển failure thành pass.
- `run.json`: suite, browser path, provider fixture, exit code và thời điểm.
- `browser/<test>/trace.zip`, screenshots: hành trình browser thật.
- Baseline có `english-short.mp4`, `english-short.srt`, `video-review.png`: output ứng dụng
  tải qua browser và screenshot khung video, giữ cùng lần chạy.
- Log API/UI/worker và screenshot cuối do Stack lưu tại `artifacts/e2e/<test-name>/`.
  Logs ở tên cố định được ghi đè khi chạy lại; trace/JUnit timestamped mới là mốc phân biệt lần chạy.

Không bật video recording mặc định vì Chromium hệ thống không bảo đảm có FFmpeg recorder
đi kèm Playwright. MP4 do ứng dụng dựng vẫn được test phát/tải/FFprobe trong baseline.

```bash
uv run playwright show-trace test-results/ielts/<run>/browser/<test>/trace.zip
```

## Bổ sung khi code tính năng

Readiness chỉ là điều kiện tiên quyết. Khi M1–M4 được code, thêm browser tests thực tế cho các case
planned; chốt accessible labels/test IDs cùng UI. Giữ readiness và baseline, không thay chúng bằng
một test mô phỏng feature. Full library acceptance chỉ được báo pass sau khi các case này chạy thật.
Chưa thêm IELTS gate vào CI mặc định vì app chưa có feature; đây là suite opt-in có thể chạy ngay,
không phải required CI đã xanh. Khi tính năng hoàn thiện, thêm CI với artifact upload on failure.

## Kết quả đã chạy trong môi trường này

Ngày 2026-11-08, Python 3.12.14, Playwright 1.64.0, Chromium hệ thống 154.0.8037.57:

- Dependencies cài theo `uv.lock`; không thay dependency hoặc lockfile.
- Tải browser bundled từ cdn.playwright.dev bị network policy chặn (403); Chromium hệ thống chạy được.
- Lịch sử trước khi triển khai runtime: `--suite all` có **16 passed, 1 failed**, exit code 1.
- 15 database checks và video baseline pass; readiness fail vì thiếu 11 API operations IELTS.
- Trace/JUnit/MP4/SRT: `test-results/ielts/20261108T125837Z-624eaa0a/`.
- Lint/format các file Python mới và diff whitespace checks đạt.
- Có warning deprecation FastAPI/Starlette TestClient; không thay dependencies để che warning.

Trong lúc thiết lập, trace phát hiện widget cũ/mới tạm cùng tồn tại và popup chọn giọng đóng
trong rerender. Test chờ Streamlit idle/unique editor và dùng keyboard chọn giọng; vẫn giữ
assert đúng Aria, config worker, output codec/hash và lifecycle. Không tăng timeout để che failure,
không skip/xfail readiness hoặc thay kỳ vọng nghiệp vụ.

Chưa chạy full legacy regression, PostgreSQL hoặc live TTS; chưa chứng minh IELTS library-to-video
vì phần ứng dụng đó chưa có. Không có thay đổi production code, commit, push hay publish.

Kết quả tích hợp hiện tại và lỗi live còn chặn push: [toolkit validation](../../../docs/research/shorts-toolkit/validation.md).
