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
| 50..80 (gồm cả 50 và 80) | Ảnh hưởng trung bình | Human review có chữ ký hợp lệ |
| <50 | Ảnh hưởng nhiều | Human review có chữ ký hợp lệ |

Xem trước: `uv run python scripts/review_impact.py --base origin/main`.
Trước push đánh giá `baseline → HEAD`, độc lập với điểm nhỏ của từng commit.
Nhiều commit nhỏ không chia nhỏ được mức ảnh hưởng tổng của nhánh.

## Human review trước push

Không chấp nhận JSON tự điền `approved=true`. Reviewer dùng SSH private key của họ để ký
payload gắn fingerprint của hai cây code, score, level và hạn tối đa 7 ngày.
AI/agent **không được tự tạo/sign approval**, mượn SSH agent, hoặc coi yêu cầu triển khai
chung trong chat là approval cho một fingerprint cụ thể.

Cấu hình một lần: human đưa public key vào `allowed_signers` trong thư mục Git common
`change-reviews/` (lấy bằng `git rev-parse --git-common-dir`). Định dạng OpenSSH:

```text
maintainer@example.com ssh-ed25519 AAAA...public-key...
```

Không đưa private key vào repo, không gửi private key vào chat. Public key local này là
trust configuration do human quản lý. Tool cũng hỗ trợ `reviewers.allowed_signers` từ
**baseline**; key thêm/sửa trong chính diff đang duyệt không thể tự cấp quyền cho diff đó.
Git owner kiểm soát được máy local nên vẫn có thể thay trust config/bỏ qua hook; enforcement
trên GitHub cần ruleset và workflow tin cậy riêng, chưa được cấu hình trong thay đổi này.

Sau khi commit hoàn tất và nhánh đã cố định:

```bash
uv run python scripts/review_impact.py --base origin/main --head HEAD \
  --request-for maintainer@example.com
```

Tool in đường dẫn request JSON. **Request chưa có chữ ký không phải approval.** Human đọc
diff, commit description, điểm và test report; kiểm tra payload rồi ký chính file đó:

```bash
ssh-keygen -Y sign -f /path/to/human_private_key \
  -n duckmmo-impact-review /path/to/request.json
```

File `.json.sig` phải nằm cạnh JSON gốc, trong Git common `change-reviews/`. Sau đó chạy
`uv run python scripts/review_impact.py --base origin/main --head HEAD --enforce`.
Key không tin cậy, chữ ký sai, code/baseline thay đổi hoặc hết hạn đều bị chặn.
Đừng ký request khi code vẫn còn thay. Baseline thực tế của hook là merge-base với main
cho nhánh tính năng, hoặc remote main khi push main; dùng đúng SHA base khi tạo request.
Chưa cấu hình public key thì medium/high **không được push**.

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

CI hiện tại chạy impact report ở bước core và Playwright ở bước browser riêng. Human signature
được enforce tại local pre-push, không tuyên bố có server-side enforcement. Việc tạo approval
trên GitHub/auto-merge nằm ngoài phạm vi thay đổi này.
