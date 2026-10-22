# Kế hoạch harness đánh giá và cải thiện toàn bộ pipeline DuckMMO

Trạng thái: kế hoạch triển khai; các hạng mục dưới đây chưa phải tính năng đã hoàn thành.
Mục tiêu: mỗi lần sản xuất tạo dữ liệu có thể đánh giá; thay đổi prompt, routing, style hoặc
tham số chỉ được dùng mặc định sau khi có bằng chứng tốt hơn. Người dùng đưa nguồn/ảnh,
duyệt nội dung và video, phản hồi ngắn; hệ thống thực hiện đánh giá và thử nghiệm phía sau.
Không bảo đảm từng video sau luôn tốt hơn; đo chất lượng theo nhóm nội dung tương đương.

## 1. Phạm vi và khoảng trống hiện tại

Đã có: Job/JobEvent, source_documents, AI analysis, sửa/duyệt nội dung, TTS, FFmpeg/libass,
style snapshot, render run, content/video hash, log, retry/cancel và duyệt video cuối.
Chưa có: revision lịch sử cho toàn bộ bước, đánh giá chất lượng có bằng chứng, phản hồi có
cấu trúc, bộ benchmark, experiment/promotion, outcome từ nền tảng, dataset hay fine-tuning.
Publish và analytics chưa được tích hợp: phải xây adapter thực trước khi đánh giá hai bước này.

Harness là lớp chung chạy xuyên suốt các phase, không phải một phase riêng sau khi làm video.
Fine-tuning là nhánh triển khai sau, không là điều kiện để bắt đầu cải thiện sản phẩm.

## 2. Flow mục tiêu

Nguồn -> lấy dữ liệu -> phân tích/kịch bản -> duyệt nội dung -> chia cảnh/style/ảnh ->
giọng đọc -> phụ đề -> dựng/QA -> duyệt video -> xuất bản -> đo kết quả.
Mỗi bước: đầu vào có phiên bản -> thực thi -> lưu artifact -> kiểm tra -> ghi kết quả.
Lỗi chắc chắn: chặn chuyển bước và đưa bằng chứng. Điểm đánh giá bằng AI: cảnh báo hoặc
so sánh, không tự tuyên bố nội dung đúng. Sửa hoặc thử lại chỉ bước liên quan, có giới hạn.
Duyệt nội dung và duyệt video vẫn bắt buộc; hệ thống không tự đăng khi thiếu phê duyệt.

## 3. Kế hoạch theo từng bước

| Bước | Dữ liệu cần lưu | Kiểm tra và điều kiện chuyển bước | Cách cải thiện tự động |
| --- | --- | --- | --- |
| Khởi tạo | mục đích, branch, ngôn ngữ, nền tảng đích, thời lượng đích, nguồn, cấu hình snapshot | schema hợp lệ; tham chiếu nguồn; mặc định rõ khi chưa có mục tiêu | chọn cấu hình đã kiểm chứng theo loại nội dung; học sở thích từ phản hồi, cho phép reset |
| Lấy nguồn | URL cuối, thời điểm, hash raw/extracted, bản extractor, lỗi và thời gian | HTTP/encoding; trang chặn/đăng nhập/rỗng; trùng nội dung; độ bao phủ trên bộ nguồn có đáp án | so extractor bằng benchmark đa nguồn; không dùng độ dài văn bản đơn thuần làm tiêu chí thắng; không cài selector riêng cho một trang để che lỗi |
| Phân tích/kịch bản | source snapshot, prompt/model/provider, request/response hash, chi phí/usage, đoạn kịch bản gắn bằng chứng | JSON đúng; đúng ngôn ngữ; nguồn được tham chiếu; phát hiện thiếu nguồn, số liệu/tên sai, lặp và vượt thời lượng | so prompt và model trên cùng input; giảm lỗi dựa trên sửa của người duyệt; không học từ output chưa duyệt |
| Duyệt nội dung | revision trước/sau, diff, approve/reject, lý do có cấu trúc | phê duyệt đúng content hash; chỉnh sửa làm mất duyệt bản cũ | phân loại lỗi nội dung/giọng văn/thiếu ý; tạo ví dụ tốt từ bản đã được duyệt; không coi mọi chỉnh sửa là sửa factual |
| Chia cảnh/style/ảnh | storyboard, scene-text/source mapping, asset hash, style/version, crop/motion | ảnh giải mã được, phù hợp khung hình; thiếu ảnh; thời lượng cảnh; text safe area; độ liên quan ảnh cần xác nhận | ưu tiên style có kết quả tốt trong cùng nhóm; thử variant ở chế độ shadow; chỉ tự chọn từ thư viện đã kiểm tra; nguồn CapCut chưa hỗ trợ phải ghi rõ |
| Giọng đọc | engine/voice/version, văn bản đọc, WAV, duration, loudness, lỗi phát âm được gắn nhãn | không im lặng/clipping, thiếu đoạn, ngôn ngữ sai; so transcript với script khi có ASR phù hợp | so voice và tốc độ; từ điển phát âm có phiên bản, chỉ thêm từ sửa đã xác nhận; không sửa nguyên bản script để giấu lỗi TTS |
| Phụ đề | cue/word timings, nguồn timing, SRT/ASS, style snapshot | timestamp tăng; không chồng bất hợp lý; không vượt audio; tốc độ đọc, wrap, tràn khung, Unicode | tối ưu ngắt câu, số từ/dòng và vùng hiển thị; phrase estimate phải ghi nhãn; chỉ bật karaoke sau khi word timing được kiểm chứng |
| Dựng và QA | render plan, cấu hình FFmpeg, artifact/hash, frame samples, streams, logs | decode đầu/giữa/cuối và quanh điểm cắt; lệch audio/video, đen hình, phụ đề bị cắt; phân biệt nền đen chủ ý | cache theo hash từng bước; điều chỉnh encoder/motion từ benchmark chất lượng-thời gian; sửa lỗi có giới hạn, không tự đổi nội dung đã duyệt |
| Duyệt video | artifact hash, nhận xét theo cảnh/timecode, điểm thành phần, lý do từ chối | phê duyệt đúng video hiện tại; sửa script/ảnh/style làm mất hiệu lực phê duyệt liên quan | tìm bước gây lỗi và dựng lại phần cần thiết; ghi sở thích đã xác nhận; không tái dùng quyết định duyệt cho variant mới |
| Xuất bản | platform/account, approved hash, caption/thumbnail, publish id và response | adapter thật; format/quyền tài khoản hợp lệ; idempotency; thiếu review thì chặn; trạng thái nền tảng chưa chắc chắn phải đối soát trước retry | tối ưu metadata bằng dữ liệu có kiểm soát; không retry mù gây đăng trùng; upload failure là lỗi vận hành, không là lỗi chất lượng video |
| Đo sau đăng | metrics theo mốc thời gian, denominator, platform và cohort | chỉ số thiếu không được coi là 0; phân biệt chưa có dữ liệu và lỗi API | so retention/completion/engagement theo cùng nền tảng, tuổi bài, độ dài/chủ đề; tương quan không là bằng chứng nhân quả; A/B khi nền tảng và dữ liệu cho phép |

## 4. Hợp đồng dữ liệu và migration

Giữ Job.status phục vụ UI cũ. Bổ sung bảng mới bằng Alembic; không chuyển toàn bộ lịch sử
vào JSON của JobEvent. JobEvent tiếp tục là log dễ đọc, liên kết run/evaluation khi cần.

- PipelineRevision: job_id, revision_id, parent_revision_id, input hashes, mục tiêu, created_at.
- StepRun: revision_id, step, attempt, state, config_snapshot, input/output hashes, timestamps,
  provider/model/version, latency, usage/cost (nullable nếu provider không cung cấp), error_code.
- ArtifactRecord: run_id, kind, đường dẫn nội bộ, hash, size, metadata; không nhận path tùy ý từ UI.
- Evaluation: run_id/artifact_hash, evaluator_id/version, rubric_version, dimension, score hoặc
  pass/fail/unknown, confidence nếu có ý nghĩa, evidence (source span hoặc timecode), limitations.
- ReviewFeedback: reviewer, revision/hash, scope/scene/timecode, label, note, decision, edit_diff.
- ConfigVersion: family (extractor/prompt/model_route/voice/subtitle/style/render), immutable
  config, parent, provenance, activation state và hash; không chứa API key.
- Experiment: baseline/candidate, dataset_version, cohort, budget, kết quả, quyết định promote.
- PublishAttempt / OutcomeSnapshot: approved artifact, platform id, idempotency key, metrics,
  sampled_at và denominators. Triển khai cùng adapter publish/analytics, không tạo số liệu giả.
- DatasetExample / DatasetVersion: nguồn revision/review, split, quyền sử dụng và eligibility.

Tách mã lỗi provider/quota/timeout khỏi lỗi semantic và review rejection. Không lưu key,
Authorization headers hay toàn bộ request chứa credential vào log/dataset. Không dùng
credential đăng bài để huấn luyện. Dữ liệu huấn luyện có provenance và chính sách xóa.
Bản cũ chỉ backfill metadata có thật; thiếu dữ liệu giữ unknown, không suy đoán điểm.

## 5. Harness và đánh giá

Một interface chung: evaluate(step_run, artifacts, context) -> evaluations + proposed_actions.
Evaluator chạy deterministic trước, model-based sau khi cần. Mỗi evaluator có version và
bộ test riêng. Evidence phải trỏ tới revision/artifact đang đánh giá.

Các dimension độc lập: factual/source coverage, script clarity, visual relevance, speech,
subtitle readability/sync, technical render, human preference, cost và latency.
Không gộp thành một điểm tổng duy nhất để che lỗi nghiêm trọng. Chỉ tính điểm tổng cho
so sánh khi đủ thành phần; hiển thị phần nào chưa đánh giá. Model judge không thay thế
người duyệt và không dùng một model vừa tạo vừa tự chấm làm bằng chứng duy nhất.

Hành động có thể đề xuất: retry cùng bước, sửa có phạm vi, đổi candidate đã cho phép,
request_review, hoặc fail. Bắt đầu với tối đa 2 lần sửa mỗi bước mỗi revision và tối đa
3 lời gọi AI sửa tự động mỗi job; có budget thời gian/token/chi phí. Đây là giá trị đề xuất,
được benchmark lại; hết budget thì dừng và hiện lý do. Network/provider retry là budget riêng.
Không tự tăng quota hay chuyển sang dịch vụ trả phí khác để làm bước đó qua.

## 6. Vòng học và cập nhật

1. Ghi nhận run, evaluation và feedback ở mọi job.
2. Chỉ thu mẫu có review và nguồn rõ; phân biệt sửa sở thích với sửa sự thật.
3. Sinh candidate có phiên bản (prompt, routing, style, subtitle rules, pronunciation).
4. Chạy offline với baseline trên cùng bộ input; không tác động job đang chạy.
5. Đánh giá, ghi bằng chứng, chi phí và sai số; judge chỉ đọc dữ liệu cần thiết.
6. Chạy shadow, sau đó canary có giới hạn; cả hai vẫn giữ review của người dùng.
7. Promote khi đạt gate; thay đổi chất lượng nội dung/model cần duyệt promotion ban đầu.
   Có thể bật tự promote cho loại thay đổi đã được người dùng cho phép bằng policy riêng.
8. Rollback mặc định cho job mới khi vi phạm gate; job đang chạy giữ config đã pin.

Cập nhật thư viện style -> kiểm tra schema -> render smoke test -> baseline eval -> activate.
Không tải code tùy ý từ template, không tự git pull/pip upgrade ở production.
Nguồn preset và phiên bản model thay đổi không đồng nghĩa candidate tốt hơn.

## 7. Benchmark, promotion gate và fine-tuning

Seed benchmark đề xuất: 30 case (10 novel, 10 comic, 10 research), gồm tiếng Việt có dấu,
nguồn dài/ngắn, nhiều nguồn, trang lỗi, ảnh dọc/ngang, tên riêng/số liệu và prompt injection.
Comic/OCR hay capability chưa triển khai phải là unsupported/skip có lý do, không tính pass.
Tách train/dev/test theo nguồn/câu chuyện để tránh leakage; thêm holdout đánh giá thủ công.
Giữ một core set cố định để so phiên bản, một tập mới phản ánh dữ liệu gần đây.

Gate ban đầu (đề xuất; cần hiệu chỉnh từ baseline):
- Không phát sinh lỗi chặn mới; các case vi phạm nguồn/hash/review phải bị chặn đúng.
- Không giảm điểm factual, speech/sub sync và technical trong tập kiểm thử trọng yếu.
- Cải thiện dimension mục tiêu, không giảm dimension khác quá ngưỡng được khai báo trước.
- Báo cả số mẫu, phân phối, thiếu dữ liệu và bất định; ít mẫu thì chưa promote tự động.
- p95 latency và chi phí không vượt budget đã định cho experiment; thiếu usage ghi unknown.
- Có canary và đường rollback trước khi thay mặc định.

Fine-tuning chỉ mở sau khi có dataset đã duyệt, đánh giá mức đủ/đa dạng theo nhiệm vụ,
provider/model cho phép, và thử tối ưu prompt/retrieval trước. Không ấn định số mẫu tối thiểu
như bảo đảm chất lượng. Training chạy riêng; không train trong worker đang dựng video.
Model mới phải qua cùng benchmark/holdout/promotion gate. Không tự ghi đè model gốc.

## 8. UI/UX

Giữ Workspace ở trái. Bảng phải: Tiến trình / Log / Chất lượng.
Mỗi bước hiển thị đang chạy, đã kiểm tra, cần duyệt, gặp lỗi hoặc chưa hỗ trợ; số đo thật và
phiên bản cấu hình. Có bằng chứng ở nguồn/timecode, không chỉ điểm số hay thông báo thành công.

Phase 2: phản hồi nhanh sai ý/thiếu ý/dài/giọng văn; lưu diff, người dùng vẫn sửa trực tiếp.
Phase 4: phản hồi giọng đọc/sub/ảnh/nhịp dựng/nội dung, gắn cảnh hoặc timecode; nút sửa bước
liên quan, hiển thị ảnh hưởng tới phê duyệt. Không bắt người dùng nhập bảng cấu hình kỹ thuật.
Trang Cải thiện: baseline vs candidate, số mẫu, chỉ số, ngân sách, trạng thái và rollback.
Metrics sau đăng chỉ xuất hiện khi connector thực có dữ liệu.

## 9. Backlog và thứ tự thực hiện

| Đợt | Ticket | Deliverable | Phụ thuộc / nghiệm thu |
| --- | --- | --- | --- |
| A | H01 | schema StepRun/revision/config/artifact/evaluation/feedback, migration | DB rỗng/cũ migrate được; hồi quy review/cancel/retry giữ nguyên |
| A | H02 | recorder và hook worker/API theo từng bước | run có hash và phiên bản; retry/cancel không ghi sai revision; log không có key |
| A | H03 | feedback Phase 2/4, lưu edit diff và timecode | phản hồi gắn đúng content/video hash; sửa làm mất duyệt đúng phạm vi |
| B | H04 | evaluator nguồn/kịch bản + taxonomy lỗi | H01–H02; bộ nguồn đa dạng, phát hiện crawl failure và claim thiếu evidence |
| B | H05 | evaluator voice/sub/render và QA frame sampling | H01–H02; bắt silence/clipping/tràn sub/desync ở fixture có chủ đích |
| B | H06 | tab Chất lượng và repair policy có budget | H03–H05; thấy evidence; dừng vòng sửa; không tự duyệt hay tự đăng |
| C | H07 | dataset version + benchmark runner + report | H03–H05; baseline reproducible, không trộn holdout, ghi case unsupported |
| C | H08 | experiment, shadow/canary/promotion/rollback | H07; candidate tệ bị chặn; pin run cũ; rollback áp dụng job mới |
| C | H09 | candidate prompt/style/subtitle/voice routing | H06–H08; có improvement evidence, không chỉ tự cập nhật JSON |
| D | H10 | publish adapter và publish gate | H01–H03; chỉ approved hash, idempotency, đối soát khi timeout, test sandbox |
| D | H11 | analytics adapter, outcome snapshots/cohort report | H10; metrics thiếu là unknown, refresh có quota/backoff, không bịa kết quả |
| E | H12 | dataset export và fine-tune pilot nếu đủ điều kiện | H07–H11 và provider hỗ trợ; holdout/gate/canary; có baseline so sánh |

Ưu tiên triển khai: A -> B -> C để hệ thống bắt đầu cải thiện trước khi publish được nối.
D có thể chuẩn bị hợp đồng sau A, nhưng chỉ chạy thật khi có tài khoản/quyền từ người dùng.
E là quyết định dựa trên dữ liệu, không mặc định phải train. Không ước lượng lịch hoàn thành
trước khi chốt baseline thời gian/chi phí và capability của provider hiện tại.

## 10. Ranh giới module và điểm tích hợp

- app/quality/: contracts, recorder, evaluators, policy và report (module mới).
- app/learning/: datasets, benchmark, experiments, promotion (module mới).
- app/publishing/: adapters, idempotency/outcomes (module mới, hiện chưa có capability).
- app/db.py + migrations/: bảng mới; app/schemas.py: API contracts.
- app/worker.py: ghi StepRun/checkpoint, evaluate trước chuyển trạng thái, repair budget.
- web_import.py: evidence/raw-extraction metadata; analysis.py: prompt/model/usage snapshots.
- video.py/styles.py: tách scene/voice/sub/render, artifact và kiểm tra từng bước.
- app/main.py: feedback/evaluations/experiments APIs; giữ content/video hash checks hiện tại.
- ui/studio.py: chất lượng, feedback, evidence và candidate comparison.
- tests/: policy, evaluator, migrations, cancellation và leakage; e2e/: toàn luồng có review.

API dự kiến: GET /jobs/{id}/quality; POST /jobs/{id}/feedback; GET /jobs/{id}/runs;
POST /experiments; GET /experiments/{id}; POST /experiments/{id}/promote; POST /configs/{id}/rollback.
Các API ghi phải dùng cùng cơ chế auth và kiểm tra revision như flow hiện tại.

## 11. Definition of done cho phiên bản đầu

Một job thực đi qua nguồn -> AI -> duyệt nội dung -> render -> duyệt video, có StepRun và
đánh giá từng capability đã thực hiện. Người dùng từ chối một lỗi sub có timecode; hệ thống
ghi feedback, tạo candidate, benchmark, chỉ dựng lại sau gate, và yêu cầu duyệt video mới.
Có báo cáo baseline/candidate; cấu hình tệ không được promote; rollback có test thực.
Test bằng Playwright trên UI, API/worker/FFmpeg thực; model fixture được ghi rõ trong CI,
cộng một smoke test provider thật khi có key/quota. Không dùng fixture để tuyên bố AI thật.
Publish/analytics chỉ được đánh dấu done sau test adapter thực; thiếu connector ghi chưa có.
