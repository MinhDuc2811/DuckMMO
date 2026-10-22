# Review trước commit và đánh giá ảnh hưởng v1

Điểm càng cao nghĩa là ảnh hưởng tiềm năng càng ít. Đây là điểm riêng với reuse score.
Không có API AI trả phí. Công cụ phân tích diff; tác giả vẫn phải thật sự đọc diff và lý giải.

## Trước commit: đọc diff và mô tả từng file

```bash
git diff
git add <các-file-thuộc-thay-đổi>
git diff --cached
uv run python scripts/commit_review.py --prepare
```

Lệnh cuối in đường dẫn JSON trong Git common directory, không đưa report vào codebase.
Điền `summary`, `reason`, và `what`/`why` cho **từng file**. Không xóa fingerprint, không
bỏ file. Chạy `uv run python scripts/check_quality.py commit` để xem phần review được in ra.
Sau đó `git commit -m "Mô tả ngắn thay đổi"`.

`commit-msg` tự thêm bản mô tả đã kiểm tra vào nội dung commit, không phải comment bị Git
xóa: Summary, What changed, Where (trạng thái + đường dẫn), Why (chung + từng file), Impact,
core paths, fingerprint. Dùng `git show --format=full <commit>` để biết commit làm gì trước
khi quyết định revert. Hook không tự thực hiện revert hoặc khẳng định migration revert an toàn.

Review dùng `HEAD → STAGED`, không dùng các byte chưa stage. Nội dung, quyền executable,
symlink hoặc baseline đổi thì fingerprint đổi, phải xem lại diff và tạo review mới.
Pre-commit hiện vẫn chặn partial-stage Python để lint và code staged không lệch nhau.
Empty commit/message-only amend chưa được hỗ trợ bởi luồng review này.

Ví dụ record (template thật sẽ có fingerprint và toàn bộ đường dẫn chính xác):

```json
{
  "fingerprint": "<được tạo tự động>",
  "summary": "Thêm cache audio dùng chung cho các lượt render",
  "reason": "Tránh gọi lại TTS khi chỉ đổi hình và giữ nguyên kịch bản.",
  "files": [
    {
      "path": "app/infrastructure/media/speech.py",
      "what": "Tái sử dụng WAV đã kiểm tra theo nội dung, giọng và tốc độ.",
      "why": "Giảm số lần gọi provider và giữ cache độc lập với bản audio bị trim."
    }
  ]
}
```

## Công thức v1

Gọi N là số file **tracked của baseline** (không tính .git, file ignored, report local).
Dùng N=1 nếu repo rỗng để tránh chia 0. Mọi loại file tracked đều được tính, kể cả docs/tests.

- Tỷ lệ yêu cầu ban đầu: `R = số file created/modified / N × 100`.
  "Append" được hiểu v1 là file được sửa, không phải số dòng thêm.
- Để không bỏ sót xóa/rename: `E = số đường dẫn changed (A/M/D) / N × 100`.
  Rename được tính bảo thủ là xóa + thêm; đây là giới hạn v1, không giả vờ nhận diện semantic rename.
- Core penalty: 30 nếu chạm contracts/modules/pipeline/services/infrastructure hoặc
  schemas/config/db/worker/bootstrap/main, auth dependencies hoặc uv.lock; 0 nếu không.
  Adapter publishing cũng được tính là core.
- Dependency penalty: `min(20, 2 × số file app/ui khác import trực tiếp module bị đổi)`.
  Kiểm tra cả baseline và code mới; chưa phải call graph, không phát hiện dynamic import đầy đủ.
- Policy penalty: 30 nếu sửa hook/workflow/scripts/rule/test discovery/pyproject hoặc
  conftest/AGENTS ở bất kỳ thư mục nào; 0 nếu không.
- `Score = round(max(0, 100 − min(100,E) − core_penalty − dependency_penalty − policy_penalty), 2)`.

Mẫu số lấy từ baseline, nên thêm file rỗng vào cùng PR không làm loãng tỷ lệ. File core chỉ
đổi một dòng vẫn cần review: tool không tự suy luận dòng đó chắc chắn vô hại.
Coefficients có version=1, là khởi điểm để hiệu chỉnh bằng dữ liệu lỗi/thời gian review.
Không hạ trọng số/ngưỡng trong cùng thay đổi chỉ để được push.

| Điểm | Phân loại | Trước push |
| --- | --- | --- |
| >80 | Ảnh hưởng ít | Qua cửa điểm ảnh hưởng; vẫn phải qua các kiểm tra khác |
| 50..80 (gồm cả 50 và 80) | Ảnh hưởng trung bình | Human review có xác nhận hợp lệ |
| <50 | Ảnh hưởng nhiều | Human review có xác nhận hợp lệ |

Xem trước: `uv run python scripts/review_impact.py --base origin/main`.
Trước push đánh giá `baseline → HEAD`, độc lập với điểm nhỏ của từng commit.
Nhiều commit nhỏ không chia nhỏ được mức ảnh hưởng tổng của nhánh.

## Human review trước push

Không cần SSH key, chữ ký hoặc request ký. User có thể xác nhận ngay trong chat.
Record phải ghi: `username`, `status` (approved/rejected/pending), `review_date`
(YYYY-MM-DD), `scope` và nội dung/nguồn xác nhận. Tool tự gắn fingerprint, điểm,
phân loại và toàn bộ đường dẫn đã đổi. Chỉ trạng thái approved mới cho qua gate.
Thiếu trường, ngày tương lai, pending/rejected hoặc code/baseline khác đều không hợp lệ.

Ví dụ sau khi đã được user xác nhận phạm vi cụ thể:

```bash
uv run python scripts/review_impact.py --base origin/main --head HEAD \
  --confirm-user MinhDuc2811 --status approved --review-date 2026-10-22 \
  --scope "Commit descriptions và impact review; xác nhận user thay cho SSH" \
  --confirmation "User xác nhận trong Codex chat: ok cho phép, xong tự merge vào main" \
  --enforce
```

Dùng ngày review thực tế, không sao chép ngày ví dụ cho những lần sau. Record nằm tại
Git common directory `change-reviews/confirmations/<fingerprint>.json`; lịch sử quyết
định được append vào `history.jsonl`. Có thể chạy lại với rejected để thu hồi approval.
Không tự nhận dạng/kiểm chứng người sở hữu username bằng mật mã: đây là nhật ký xác
nhận theo yêu cầu user, không phải cơ chế xác thực danh tính. Agent chỉ được ghi nhận
lời xác nhận thật; không tự viết approval cho thay đổi chưa được user duyệt.

Approval còn hiệu lực với đúng phạm vi/code đã duyệt, không áp dụng cho chỉnh sửa mới
không liên quan. Approval không đổi điểm hoặc bỏ qua test lỗi. Hook dùng merge-base
với main cho nhánh tính năng hoặc remote main khi push main; phải dùng đúng base.
Local hook có thể bị bỏ qua; enforcement trên GitHub vẫn cần ruleset riêng.

## Luồng nghiệp vụ: dựa trên test, không suy từ score

Pre-push chạy offline tests, migration và (khi chạm code/test/policy) hai smoke suites:

```bash
uv run pytest -q e2e/test_media_upload.py test_suite/features/speech/e2e --run-e2e \
  --tracing retain-on-failure --screenshot only-on-failure
```

Phải cài Chromium và dependency của Playwright. Chạy lỗi, thiếu browser, thiếu dependency
đều chặn push và lưu report `change-reviews/reports/<fingerprint>.json` trong Git common dir.
Report phân biệt test failed/unavailable, chưa chạy, đã đạt trong scope được test, và thiếu
human approval. Approval không biến test đỏ thành xanh. Không dùng retry/skip để che lỗi.
Hai smoke suites chưa bao phủ mọi workflow; khi feature mới cần luồng khác, thêm test tương ứng.
Live Edge/YouTube vẫn là kiểm tra opt-in riêng, không được báo đã đạt khi bị chặn.

CI hiện tại chạy impact report ở bước core và Playwright ở bước browser riêng. User confirmation
được enforce tại local pre-push, không tuyên bố có server-side enforcement. Việc tạo approval
trên GitHub/auto-merge nằm ngoài phạm vi thay đổi này.
