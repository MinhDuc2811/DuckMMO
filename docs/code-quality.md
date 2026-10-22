# Kiểm tra code trước commit và push

`review_code.py` chấm **phần thay đổi**, không chấm chất lượng toàn bộ sản phẩm.
Không gọi AI/API, không phát sinh phí dịch vụ. Điểm là heuristic AST có thể bỏ sót
logic tương tự nhưng viết khác; người review vẫn phải kiểm tra thiết kế và common owner.

## Chạy và bật kiểm tra

```bash
uv sync --frozen --group dev
uv run python scripts/install_quality_hooks.py
uv run python scripts/review_code.py --base origin/main --output /tmp/reuse-review.json
uv run python scripts/check_quality.py commit
uv run python scripts/check_quality.py ci --base origin/main
```

Review mặc định đọc working tree, gồm file Python chưa tracked. Để kiểm tra commit:

```bash
uv run python scripts/review_code.py --base origin/main --head HEAD
```

- Pre-commit: lint, format, diff whitespace và review staged diff theo [change-impact.md](change-impact.md).
  Commit-msg lưu mô tả what/where/why và điểm ảnh hưởng vào commit body. Không tự stage file.
- Pre-push: yêu cầu working tree sạch và checkout đúng commit đang push; chạy review,
  toàn bộ test offline (gồm architecture/query count/media) và migration trên DB tạm.
- Migration kiểm tra cả DB mới và nâng schema baseline lên schema mới; không dùng DB thật.
- Nhánh tính năng so với merge-base của `origin/main`; main so với remote main đang push.
  Chạy `git fetch origin main` trước push để baseline cập nhật. Không lấy commit cũ bất kỳ
  làm baseline chỉ để tăng điểm.
- CI chạy lại các kiểm tra từ PR base hoặc commit main trước push và browser upload clip.
  CI browser bao phủ upload clip và chọn giọng/tốc độ đọc; khi thay UI/workflow khác,
  bổ sung browser test tương ứng. Không tuyên bố toàn bộ UI đã được kiểm thử từ các smoke test.
- Thay đổi trên cây staged phải là code đã lint; không partial-stage phiên bản khác
  working tree. CI/pre-push kiểm tra lại bản commit cuối cùng.

## Điểm tái sử dụng

Bắt đầu 100; chỉ trừ **phát hiện mới** trong file `app/**/*.py`, `ui/**/*.py` thay đổi.
Nợ cũ không tự động chặn mọi PR, nhưng thêm cùng kiểu lỗi vẫn bị tính thêm.
Tổng điểm thấp nhất là 0.

| Nhóm | Mức trừ mỗi phát hiện | Tối đa mỗi nhóm |
| --- | --- | --- |
| Ranh giới kiến trúc | Import sai tầng: 20; syntax: 40 | 40 |
| Trùng lặp | Function AST giống nhau ở hai file, tối thiểu 40 AST node: 15 | 35 |
| Bỏ qua common | HTTP trong screen: 10; tạo engine/session sai tầng hoặc subprocess trong screen/router: 15 | 25 |
| Tài nguyên | Đọc toàn bộ MP4/WAV/media_path vào RAM bằng `read_bytes`: 15 | 30 |

Hàm trùng được so không tính tên hàm/docstring; chưa chuẩn hóa biến hay phát hiện
semantic clone. Rule tài nguyên chỉ nhận một số biểu thức media rõ ràng; không thay benchmark.
Không ép thêm abstraction chỉ để tăng điểm. Code mỏng, dùng đúng module có thể đạt 100;
điểm đó không chứng minh correctness, performance hay test coverage.

**Điểm > 70:** qua cửa điểm. **Điểm <= 70:** chặn, trừ khi có giải trình hợp lệ.
Lint/test/migration lỗi vẫn chặn dù điểm cao hay có giải trình. Boundary test hiện có
vẫn độc lập và bắt buộc. Không giảm test hay sửa scorer để hợp thức hóa feature.

## Ngoại lệ có giải trình

Sau khi code đã được commit, chạy review với `--head HEAD`, lấy `fingerprint` từ report,
thêm entry vào `code-review-exceptions.json`, rồi commit file giải trình. Đối với worktree,
chỉ dùng fingerprint xem trước; nếu còn thay code thì cần tạo lại report.
File giải trình không tham gia fingerprint để tránh vòng lặp. Nội dung app/ui và hai script
review/check ở cả baseline lẫn đích đều tham gia: đổi code hoặc baseline sẽ làm ngoại lệ cũ hết hiệu lực.

```json
{
  "exceptions": [
    {
      "fingerprint": "<fingerprint chính xác trong report>",
      "owner": "<người chịu trách nhiệm>",
      "expires": "<YYYY-MM-DD, không quá 30 ngày từ hôm chạy>",
      "reason": "<bối cảnh thay đổi và lý do cần ngoại lệ, tối thiểu 40 ký tự>",
      "common_considered": "<đường dẫn common đã tìm hiểu và giới hạn cụ thể của nó>",
      "why_not_reuse": "<vì sao dùng lại hoặc mở rộng common chưa phù hợp với ca này>",
      "risk_and_validation": "<rủi ro, test hoặc benchmark cụ thể và kết quả đã kiểm tra>"
    }
  ]
}
```

Mỗi trường lý giải cần tối thiểu 40 ký tự, owner không rỗng, thời hạn từ hôm chạy đến
30 ngày sau. Công cụ chỉ kiểm tra tính đầy đủ, fingerprint và hạn; **không xác minh được
lý giải đúng hay người khai owner có quyền phê duyệt**. Reviewer phải đọc nội dung này.
Điểm không được nâng lên khi có ngoại lệ; report giữ nguyên điểm và in toàn bộ giải trình.
Không có cờ `--force`/`--skip-score` trong công cụ.

## Trách nhiệm của tác giả và người review

1. Tìm common trước khi viết helper: contracts, modules, infrastructure, ui/client và components.
2. PR nêu component đã dùng lại; nếu tạo mới, nêu owner và vì sao common hiện tại chưa đủ.
3. Sửa shared behavior phải test các caller liên quan. Giữ transaction, audit, cancel và hash guard.
4. Giữ Workspace 3 SELECT với 1 và 101 job; endpoint mới phải kiểm tra N+1 khi phù hợp.
5. Thay media/worker phải kiểm tra file lớn, peak RAM (gồm process con), giới hạn đồng thời,
   cancel và disk-full. Benchmark dùng fixture/runner cố định; chưa có baseline thì báo thiếu,
   không tự gán ngưỡng thời gian hay tuyên bố đã đạt performance.
6. Thay rule, hook, workflow, test kiến trúc hoặc ngoại lệ cần maintainer review.

Git hook có thể bị bỏ qua bằng `--no-verify`, và workflow chỉ hoạt động sau khi push lên GitHub.
Để chặn code lỗi vào main thực sự, cấu hình GitHub ruleset: bắt buộc PR, required status
`quality` của workflow `Code quality`, required review, dismiss stale review và không cho bypass.
Việc thêm các file này **không tự bật branch protection**. Nếu cho phép direct push main,
CI chỉ báo lỗi sau khi code đã lên main. Checkout/máy khác phải cài hook riêng.

Điểm ảnh hưởng và human review trước push là gate độc lập: xem [change-impact.md](change-impact.md).
