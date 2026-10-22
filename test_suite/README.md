# Feature test suites

Thư mục này là nơi cấu hình và viết test mới. Cấu trúc ưu tiên tìm theo feature:

```text
test_suite/
├── pytest_plugin.py         # chọn feature/tầng, cấu hình live và browser
├── conftest.py              # dùng lại SQLite migration/settings fixtures
├── support/                 # audio fixtures, đường dẫn và helper dùng chung
├── create_feature.py        # tạo khung feature, không sinh test pass giả
└── features/
    ├── speech/
    │   ├── unit/
    │   ├── api/
    │   ├── integration/
    │   ├── screen_flow/
    │   ├── e2e/
    │   └── cases.md
    └── test_harness/        # xác minh discovery, opt-in và exit status
```

## Quy ước từng tầng

| Tầng | Kiểm tra | Dependency |
| --- | --- | --- |
| unit | phân đoạn text, validation, chính sách proxy | không gọi dịch vụ ngoài |
| api | HTTP contract, auth, status/body và lifecycle preview | FastAPI TestClient + SQLite tạm; TTS fixture được ghi rõ |
| integration | cache/PCM/ghép audio, render MP4, kết nối các component | filesystem/FFmpeg thật; fixture audio cho offline |
| screen_flow | thao tác màn hình và state nghiệp vụ | Streamlit AppTest, API/DB thật trong process; provider fixture |
| e2e | browser → UI → API → database/worker | Playwright browser và process thật; test offline dừng worker trước bước TTS |

`integration/test_live_edge.py` là nhánh kiểm thử live riêng: gọi Edge thật, không
cache, không thay audio bằng fixture, rồi dựng MP4 thật nếu provider trả audio.
Nó kiểm tra cả hai giọng Việt với script liền mạch và script có dấu câu. Mức tự nhiên,
phát âm và độ phù hợp khán giả vẫn cần người nghe đánh giá; không suy ra từ FFT/PID.

## Lệnh chạy

Chạy ở root repository, dùng Python của venv hoặc `uv run`:

```bash
# Toàn bộ regression offline cũ + feature mới; browser không được collect mặc định.
uv run pytest -q

# Một feature, mặc định không gọi dịch vụ ngoài.
uv run pytest --feature speech -q

# Từng tầng (có thể lặp --test-layer để chọn nhiều tầng).
uv run pytest --feature speech --test-layer unit -q
uv run pytest --feature speech --test-layer api -q
uv run pytest --feature speech --test-layer integration -q
uv run pytest --feature speech --test-layer screen_flow -q

# Browser thật: cài Chromium + system dependencies trước theo hướng dẫn Playwright.
uv run playwright install chromium
uv run pytest --feature speech --test-layer e2e --browser chromium \
  --tracing retain-on-failure --screenshot only-on-failure \
  --output test-results/speech/e2e -q

# Chỉ khi muốn gọi dịch vụ Edge miễn phí thật; lỗi mạng/provider vẫn là FAILED.
uv run pytest test_suite/features/speech/integration/test_live_edge.py \
  --run-live-tts --junitxml=test-results/speech/live-results.xml -q

# Bao gồm browser feature suites trong một lần chạy tổng.
uv run pytest --run-e2e --browser chromium -q

# Tạo feature mới, đủ năm tầng, không ghi đè feature đang tồn tại.
uv run python -m test_suite.create_feature local_media
```

Có thể gọi trực tiếp một file hoặc test node ID để debug. Không đổi command filter
hoặc bỏ test đang fail rồi báo là full suite đã đạt. `--feature` chỉ chọn feature
trong thư mục mới; test regression cũ bị deselect trong lệnh này. Tên feature sai
phải ra exit code 5, không phải zero-test success.

## Cấu hình và báo cáo

- Pyproject `testpaths` gồm `tests` và `test_suite/features`. Root `conftest.py` chỉ
  nạp plugin chung. Cấu hình mới nằm trong thư mục này, không cài thêm dependency.
- `--test-layer`, `--feature`, `--run-e2e`, `--run-live-tts` là lựa chọn scope công khai.
- Offline mặc định: test live TTS được báo skipped với lý do rõ; E2E không collect.
  Đây là scope mặc định, không phải bằng chứng browser hoặc provider đã đạt.
- Live đã opt-in mà mất mạng/quota thì báo failed, không tự skip/xfail hay dùng voice giả.
- Audio/video/report live lưu dưới `test-results/speech/live/<run-id>/` khi có kết quả;
  mỗi lần chạy có ID mới để không lấy nhầm bằng chứng cũ. Khi lỗi vẫn có `result.json`.
- Playwright logs/screenshots dùng lại `artifacts/e2e/`; trace ở output directory.
- Test không sử dụng DB/artifact đang chạy của người dùng và không in key/token/URL ký.
- Feature `test_harness` dùng một project pytest tạm để chứng minh opt-in lỗi thật
  vẫn trả nonzero; các test giả trong project tạm chỉ là fixture kiểm tra runner.

## Giữ regression và tính trung thực

Đọc [AGENTS.md](AGENTS.md). Không sửa expected/assertion/threshold/mock/skip để khớp
code lỗi. Sửa application trước. Chỉ sửa test khi chứng minh test bị sai hoặc yêu cầu
thay đổi, kèm lý do và review; không dùng rule này để giữ một assertion đọc sai DOM.
Mỗi feature nên có `cases.md`: ID, điều kiện, thao tác, kết quả mong đợi và test node.

Các test speech mới đã được chuyển từ file tạm `tests/test_speech.py` sang các tầng,
giữ nguyên assertion. Các test cũ trong `tests/` và `e2e/` chưa di chuyển; lệnh offline
tổng vẫn chạy `tests/`, browser legacy vẫn dùng `pytest e2e ...`. Việc chuyển feature
cũ sẽ thực hiện riêng để không thay đổi test của task khác hoặc mất regression.
