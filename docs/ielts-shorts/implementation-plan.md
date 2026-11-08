# Kế hoạch coding IELTS Shorts

## Đích đến và thứ tự

Tạo kho kiến thức có thể tìm theo topic, nghĩa, cấu trúc, sample; từ đó chọn một mục tiêu
để soạn và dựng một Short. Xây một lát cắt hoạt động xuyên suốt trước khi nhập dữ liệu lớn.
Ưu tiên Academic Writing/Speaking ở lát cắt đầu vì không cần phụ thuộc bộ audio/đề có bản quyền;
taxonomy vẫn hỗ trợ các kỹ năng và General Training. Đây là thứ tự triển khai đề xuất,
không phải loại bỏ Listening/Reading.

| Mốc | Công việc | Điều kiện hoàn thành |
| --- | --- | --- |
| M0 — thiết kế/data | Schema thử, dictionary, seed, quy tắc nhập | Đi qua được topic → nghĩa/cấu trúc → sample → bài tập → brief; seed không có approval giả |
| M1 — persistence/import | SQLAlchemy models, Alembic additive, import preview/commit | SQLite và PostgreSQL: DB mới + upgrade từ baseline; reimport không trùng; lỗi rollback cả lô |
| M2 — thư viện | API và UI duyệt topic, từ/nghĩa, cấu trúc, sample | Bộ lọc đúng, phân trang ổn định, không N+1, sửa có version và audit |
| M3 — soạn Short | Brief một focus, script revisions, cảnh độc lập lời đọc/chữ | Không chọn hai focus; review chốt đúng revision; đo/ước lượng thời lượng phân biệt rõ |
| M4 — nối video | Adapter content/render, giọng theo cảnh, text overlay, pause | Video thật đúng thứ tự, đủ khoảng nghỉ, đáp án không hiện sớm; sửa script hủy approval |
| M5 — mở rộng kho | Reading/Listening sets, ý tưởng, series/ôn tập, search | Bộ câu hỏi nhiều dạng và provenance hoạt động; nhập lô có quan sát/khôi phục |
| M6 — hiệu quả nội dung | Nối video với style version và outcome snapshots hiện có | Truy được script/source snapshot của video; so sánh có tuổi video và thời điểm số liệu |

Bản kế hoạch này là thiết kế mục tiêu ban đầu. Đã có lát cắt M1/M2 và luồng một mục → video;
đối chiếu [runtime.md](runtime.md) để biết schema/API thật và phần còn thiếu.
Chưa tuyên bố hoàn tất M1–M6 theo toàn bộ tiêu chí, đặc biệt PostgreSQL, segment links và quiz timeline.
Không ước lượng thời gian cứng trước khi thử migration, renderer và dữ liệu mẫu.

## M1 — schema và import

- Namespace bảng mới `ielts_*` khi tích hợp; không dùng tên trùng bảng hiện hữu.
- Models đặt tại `app/infrastructure/persistence/ielts.py`, dùng lại `Base`, engine,
  Session, FK setup từ `database.py`; không tạo engine/session riêng trong use case.
- Application owner: `app/modules/ielts/`, chia taxonomy, vocabulary, patterns, samples,
  exercises, briefs theo trách nhiệm khi độ lớn thực tế cần. Không generic repository/event bus.
- Schema/API contracts dùng Pydantic, cấm trường lạ, giới hạn độ dài/số lượng và validate JSON theo format.
- Migration revision mới tiếp sau **head thực tế lúc triển khai**, không sửa các revision cũ.
- UUID nội bộ; `dataset_id + external_key` duy nhất làm định danh import. Dùng bảng import batches
  và mapping có FK được khai báo trong migration production, không dùng ID nhập làm quyền ghi đè tùy ý.
- Import preview trả lỗi theo dòng; normalize Unicode NFC, khoảng trắng và key tìm kiếm, không xóa bản gốc.
- Reimport cùng key/cùng dữ liệu là no-op. Cùng key/khác dữ liệu tạo revision hoặc conflict theo
  expected version; không ghi đè bản đã duyệt. Idempotency key ràng buộc payload digest.
- Validate và ghi trong một transaction của batch; reviewer approval và audit commit cùng transaction.
- Ban đầu nhận JSON/CSV có template; chưa crawl hàng loạt/PDF OCR. Import file có giới hạn dung lượng,
  số dòng, MIME/schema và không tự tải URL/media ngoài khi preview.
- Pilot nhiều file vẫn là một dataset để phát hiện FK thiếu trước khi commit.

## M2 — API/UI thư viện

Endpoints đề xuất, chưa tồn tại:

- `GET/POST /api/ielts/topics`, `GET/PATCH /api/ielts/topics/{id}`.
- `GET/POST /api/ielts/vocabulary`; detail trả entry + senses, không trộn nghĩa.
- `GET/POST /api/ielts/patterns`, `/prompts`, `/samples`, `/exercises`.
- Sample API tạo version/segment/annotation có ràng buộc; không sửa ngầm annotation bản cũ.
- `POST /api/ielts/imports/preview`, `/api/ielts/imports/{id}/commit`.
- Review endpoints nhận expected version/digest, reviewer và ghi chú.

Query dùng keyset pagination ổn định `(sort_key, id)`, trả tối đa số bản ghi quy định.
Filter topic con dùng recursive CTE; anti-cycle trong taxonomy service cùng transaction,
xử lý concurrent move bằng khóa phù hợp trên PostgreSQL. Không tự coi prototype đã chặn mọi chu kỳ.
Index chiều ngược bảng nối; đo query plan với dữ liệu tổng hợp, không chỉ seed vài dòng.

UI: thêm thư viện IELTS qua `ui/client`, không import backend/DB trong screen.
Màn hình topic tổng hợp các tab Vocabulary / Structures / Samples / Practice / Shorts.
Trang từ: nghĩa, topic, ví dụ, phát âm, quan hệ, nơi đã dùng.
Trang sample: phiên bản, đoạn, liên kết từ/cấu trúc và nhận xét.
Không nhân bản text để thể hiện cùng nội dung ở nhiều topic.

## M3 — một Short, một mục tiêu

- `short_briefs`: một objective và đúng một focus có kiểu FK; tài liệu liên quan là hỗ trợ.
- Mặc định biên tập thử 30–60 giây; prototype cho 15–90 giây để khám phá. Đây không phải
  giới hạn chính sách YouTube, cũng không phải thời lượng thực đo.
- Có thể thêm một bài thực hành cho cùng mục tiêu; không tự thêm điểm kiến thức thứ hai.
- UI báo word count/time estimate; nội dung dài phải sửa hoặc tách brief. Human review vẫn
  kiểm tra độ nguyên tử: một FK không chứng minh văn bản chỉ dạy một ý.
- Snapshot chứa text nguồn được dùng, IDs + versions, giải thích, đáp án, annotations,
  provenance/rights, scenes, locale/voice, pause, style version và toàn bộ cấu hình ảnh hưởng output.
- Canonical JSON + SHA-256 cho snapshot. Chỉ approved snapshot bất biến được export;
  thay đổi tạo revision mới. Quyền sử dụng bị thu hồi chặn export mới dù còn snapshot cũ.
- Duyệt kiến thức không đồng nghĩa duyệt kịch bản, và duyệt kịch bản không đồng nghĩa duyệt video.
- AI chỉ tạo draft. Không tự duyệt đáp án/nguồn, không bịa band hoặc biến dữ liệu mẫu thành đề thật.

## M4 — tích hợp pipeline hiện có

| Thành phần hiện tại | Tái sử dụng / thay đổi cần thiết |
| --- | --- |
| `app/modules/jobs/service.py` | Tạo job qua owner hiện có; giữ idempotency, cancel, audit, transaction |
| `app/modules/content/service.py` | Giữ review/optimistic locking; mở rộng fingerprint khi thêm dữ liệu ảnh hưởng output |
| `app/contracts/content.py` | Hiện hash chỉ narration: không dùng hash cũ làm chứng cứ display/answer/pause không đổi |
| `app/schemas.py` | Thêm branch IELTS với compatibility tests; không gán giả IELTS vào Research/Novel |
| `app/services/styles.py`, `styles.json` | Catalog hiện bắt buộc ba branch; cập nhật validation, preset, learned-style lookup và regression cùng lúc |
| `app/infrastructure/media/` | Tái sử dụng adapter speech/FFmpeg/probe/storage; bổ sung cảnh, overlay và khoảng nghỉ |
| `app/contracts/voices.py` | Có Aria en-US, Sonia/Ryan en-GB và giọng Việt; en-GB đã đăng ký nhưng live bị policy mạng chặn 403, cần nghe kiểm tra |
| `PipelineRevision`, `StepRun`, feedback | Lưu snapshot/hash, input/output, review; không thêm hệ audit video song song |
| `MediaAsset`, media module | Tài sản job dùng owner cũ; tài sản thư viện có owner riêng và mapping sang job |
| `PublishAttempt`, `OutcomeSnapshot` | Tái sử dụng về sau; không viết hệ đăng YouTube thứ hai |

Kho thư viện và content package là hai contract khác nhau. Adapter export phải serialize snapshot
đầy đủ vào revision hoặc bảng liên kết FK job thật; prototype không tạo job_id mồ côi.
Thêm fields có version cho scenes (display/narration/locale/pause) và pin contract version;
giữ job cũ đọc và dựng được, không thay đổi thuật toán hash cũ cho dữ liệu cũ.
Content/video fingerprint mới phải bao gồm mọi input có tác động tương ứng và reject stale approvals.

Ảnh hưởng renderer lớn: đo audio từng cảnh, khoảng lặng thật, overlay answer theo timeline,
thời lượng FFprobe và QA; không mô phỏng pause bằng dấu chấm. Giọng theo cảnh là tính năng mới,
không thể hứa rằng backend một giọng hiện tại đã hỗ trợ bilingual/multi-speaker.

## Kiểm thử và điều kiện phát hành

Khi thêm test đọc `test_suite/AGENTS.md`, `test_suite/README.md`; feature `ielts` đủ năm tầng:

- Unit: nghĩa trùng, annotation sai, một focus, MCQ/answer shape, normalization, snapshot digest,
  topic cycle, module/skill/part combinations và criterion hợp kỹ năng.
- API: auth hiện có, duplicate import, wrong FK, expected version conflict, quyền chưa rõ,
  không có nội dung approved, pagination/filter, import rollback, payload/media limits.
- Integration: migrate SQLite/PostgreSQL mới và upgrade; import lặp; concurrent edit/move topic;
  immutability đã duyệt; search query count; indexing và dữ liệu tổng hợp có báo cáo quy mô.
- Screen flow: chọn topic → chọn đúng nghĩa → sample → brief → sửa → duyệt; lỗi API không mất draft.
- E2E/browser: hành trình thật với DB/API; tạo Short một mục tiêu. Provider fixture ghi rõ ở offline;
  live Edge/bilingual pronunciation là kiểm thử riêng, không báo pass nếu provider bị chặn.
- Media: overlay không lộ đáp án sớm, pause/audio duration đúng; cancel, RAM với file lớn,
  disk-full/cleanup; bảo toàn legacy render, review và Workspace query count.

Chạy lint/format, tests phù hợp, migration checks và quality checks theo AGENTS khi triển khai.
Không hạ threshold, sửa expected/skip để cho tính năng qua. PostgreSQL/browser/live TTS chưa chạy
phải được báo chưa xác minh; thiếu verification cần thiết không đủ điều kiện push.

Triển khai additive theo feature flag, backup DB trước migration, thử restore. Tắt flag là rollback
luồng UI; không tự downgrade xóa thư viện đã có dữ liệu. Destructive migration phải có kế hoạch riêng.
Không commit/push/publish trong bước chuẩn bị này.
