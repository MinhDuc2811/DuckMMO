# Từ điển dữ liệu và quy tắc

Schema có FK thật cho các quan hệ, không dùng `entity_type + entity_id` cho kiến thức.
Mọi trạng thái review trong prototype mặc định draft. Tên bảng production sẽ thêm `ielts_`.
SQL tại đây chỉ thử tính đúng của quan hệ; validation nghiệp vụ được nêu rõ bên dưới.

## 1. Nguồn và taxonomy

| Bảng | Khóa/quan hệ | Ý nghĩa |
| --- | --- | --- |
| sources | PK id | Đầu sách/website/bộ nội dung gốc; edition tách các phiên bản sách |
| source_items | FK source_id; unique(source_id, locator) | Trang/test/URL/đoạn nguồn; quyền sử dụng ở cấp nhỏ |
| topics | FK parent_id; unique code | Cây chủ đề; mỗi node có một cha; nội dung gắn nhiều node |
| labels | unique(dimension, code) | Skill, question type, function, criterion, register, CEFR, cách phân loại bài dạy |

Không nhập “band 8 vocabulary” như sự thật. Band của sample và nhóm người học hướng tới là hai khái niệm.
Không biến dạng bài sư phạm (opinion/discussion) thành danh mục chính thức khi nguồn chưa xác nhận.
Module/part và skill là thuộc tính có contract riêng, không free-text tag thay thế kiểm tra nghiệp vụ.

Ví dụ taxonomy ban đầu: Education → Online learning, Access to education; Work → Remote work;
Environment → Pollution. Danh mục mở rộng dùng code ổn định, có từ đồng nghĩa tìm kiếm về sau.
Seed chỉ có ít label đủ minh họa, không tuyên bố đã bao trùm IELTS.

`rights_status`:
- unknown: chưa biết, chặn tái sử dụng nguyên tài sản.
- reference_only: chỉ dùng tham khảo theo phạm vi đã ghi nhận; không tự cho phép sao chép.
- permission_granted: có bằng chứng và phạm vi quyền, cần kiểm tra hết hạn/thu hồi tại export.
- original_pending_review: nội dung mới biên soạn nhưng chưa được người phụ trách duyệt.

Production thêm rights evidence, permitted uses, checked_by/at, expiry/revocation và provenance
riêng cho nội dung phái sinh. Một FK nguồn trong prototype là nguồn chính; cần bảng nối có FK kiểu
cụ thể cho nhiều nguồn khi nhập nội dung tổng hợp, không nhét danh sách nguồn vào một chuỗi.

## 2. Từ vựng

| Bảng | Quan hệ | Trường đáng chú ý |
| --- | --- | --- |
| lexical_entries | 1:N lexical_senses | headword giữ bản gốc; normalized_key để tìm/dedup; kind phân biệt từ/cụm |
| lexical_senses | FK entry, source_item | sense_number, POS, definition_en, meaning_vi, usage_note, version |
| sense_topics | N:M sense/topic | Gắn theo nghĩa, không tự gắn mọi nghĩa của một từ vào cùng topic |
| sense_labels | N:M sense/label | Register/skill/CEFR có căn cứ khi được dùng |
| lexical_relations | sense → sense | Near synonym không đồng nghĩa hoàn toàn; note bắt buộc |
| word_forms | entry → forms | Biến hình của từ; word family nối các entry qua nghĩa với note |
| pronunciations | sense → IPA/audio | Theo nghĩa để tránh trộn cách đọc; locale, nguồn audio/IPA |
| vocabulary_examples | sense → examples | Text Anh, dịch Việt, nguồn và review riêng |

Collocation là một lexical entry loại collocation có nghĩa riêng. Các thành phần liên kết bằng
`lexical_relations.collocation_component`. Không tạo bản sao collocation trong từng topic.
Normalized key không đủ để phân xử mọi homograph: importer hiển thị gợi ý merge và yêu cầu người duyệt;
không tự gộp hai nghĩa vì giống chữ. Nếu sau này cần tách homograph thành entry riêng, bổ sung
homograph_key và migration unique constraint có kế hoạch, không mất sense IDs.

## 3. Cấu trúc

| Bảng | Ý nghĩa |
| --- | --- |
| patterns | kind = grammar / expression / discourse; template, explanation, usage_limits |
| pattern_topics | N:M; optional, nhiều cấu trúc dùng xuyên topic |
| pattern_labels | N:M; function, skill… phải validate dimension được phép |
| pattern_examples | Câu đúng, dịch, câu sai tùy chọn và giải thích |

Ba subtype dùng chung bảng vì cùng vòng đời và bộ field hiện tại. Không tạo generic content blob;
nếu xuất hiện field/constraint khác biệt thực tế, tách subtype có FK về pattern.
Production có thể thêm pattern_relations để nối expression với grammar point, và lỗi độc lập
khi một pattern có nhiều cặp lỗi; không phải nhân bản pattern.

## 4. Prompt, sample và annotations

| Bảng | Ý nghĩa |
| --- | --- |
| prompts, prompt_topics | Đề/câu hỏi tự biên soạn hay có nguồn; module, skill, task_part |
| samples | Danh tính sample; prompt optional cho câu/đoạn bổ trợ |
| sample_versions | Phiên bản và parent; source sample cố định trong prototype |
| sample_segments | Nhiều đoạn/câu/lượt nói theo thứ tự; nội dung và bản dịch |
| sample_topics | N:M sample/topic |
| sample_annotations | Quote + occurrence trong segment; đúng một FK sense hoặc pattern |
| sample_assessments | Criterion, assessor kind/name, estimated band tùy chọn, feedback và nguồn |

Text của sample được dựng từ các segment theo thứ tự, không giữ hai bản full text độc lập để tránh lệch.
Annotation dùng quote + lần xuất hiện; service kiểm tra khớp chính xác trong segment bất biến.
Nếu sửa text phải tạo version + segment/annotation mới. Prototype chưa có trigger khóa update.
Parent version phải thuộc cùng sample và không có vòng; SQL chỉ kiểm tra FK tồn tại,
service/migration production cần bổ sung composite FK và kiểm tra cycle.

Assessment chỉ nhận label có dimension criterion; criterion phù hợp skill. IELTS Writing Task 1
dùng Task Achievement, Task 2 dùng Task Response; Speaking có bộ tiêu chí riêng. Nhận xét một
đoạn không trở thành overall band của cả bài. Seed không có band/assessment giả.

## 5. Bài tập và Shorts

| Bảng | Ý nghĩa |
| --- | --- |
| exercises | Một target sense/pattern/segment; response spec, key, explanation và evidence |
| short_briefs | Một objective và đúng một focus sense/pattern/segment/exercise |
| script_revisions | Phiên bản kịch bản, snapshot input và hash; chưa hash không đủ điều kiện export |
| script_scenes | Thứ tự, role, spoken_text/locale, display_text, dịch, pause và visual brief |

JSON trong prototype chỉ CHECK cú pháp JSON. Service phải kiểm tra schema theo format: MCQ
có lựa chọn duy nhất và đáp án hợp lệ; gap fill có max_words/biến thể; correction có thao tác rõ;
TFNG chỉ ba giá trị; rewrite có rubric/biến thể, không tự chấm sai mọi câu ngoài một đáp án mẫu.
Một focus ở DB không chứng minh nội dung không nhồi nhiều kiến thức; đó còn là việc review objective/script.

Snapshot mẫu chỉ là dữ liệu minh họa, `snapshot_sha256=NULL`, export=false.
Production snapshot phải đầy đủ như implementation-plan; approved snapshot bất biến.
Target duration không phải audio duration. Mặc định toàn Short English narration, dịch Việt hiển thị;
đổi locale theo cảnh cần tính năng media mới và nghe kiểm tra, không mặc định đã hỗ trợ.

## 6. Ràng buộc hiện có và chưa có

| Được kiểm tra bằng SQL prototype | Phải kiểm tra ở application/migration production |
| --- | --- |
| FK tham chiếu tồn tại, unique keys, position > 0 | Reviewer, evidence, review state transitions, audit |
| Một focus/target; annotation một kiểu | Nội dung thật sự chỉ có một mục tiêu |
| JSON hợp cú pháp | Shape JSON, đáp án/evidence hợp lý, quote nằm trong segment |
| Module enum; both chỉ dành Listening/Speaking | Tất cả tổ hợp skill/module/task-part hợp lệ |
| Không làm cha trực tiếp của chính mình | Chu kỳ nhiều node, concurrent move |
| Parent version tồn tại | Parent cùng sample, không cycle, revision approved bất biến |
| Band trong khoảng 0..9 nếu có | Nguồn chấm, bước điểm, criterion, không gọi ước lượng là chính thức |
| Hash dài 64 nếu có | Hex/canonicalization, fingerprint đúng nội dung, stale approval |

## 7. Mở rộng có chủ đích ở giai đoạn sau

- Listening assets/transcripts theo turn và time range; Reading passages theo đoạn.
- Question sets + ordered questions + answer keys nhiều loại, maps/tables và evidence offsets.
- Idea bank: claim, support, counterargument, fact/hypothesis, nguồn kiểm chứng; không đưa
  số liệu tự tạo vào ví dụ như fact.
- Series, prerequisites, review schedule ở cấp nội dung; chưa có tài khoản người học hay SRS cá nhân.
- Target audience/band range ở brief/lesson khi thực sự cần; không suy ra từ một từ.
- Production FKs, timestamps UTC, soft archive, optimistic version, revision audit cho mọi nội dung chỉnh sửa được.
- Revision chốt provenance và quyền sử dụng; nhiều nguồn cho một nội dung, nhiều assessment cho một version.
- Tìm kiếm full-text PostgreSQL trước; embedding/vector chỉ thêm khi có truy vấn và benchmark cụ thể.
- Partition metrics/logs theo nhu cầu thực đo, không partition sớm toàn kho từ vựng.

Prototype không thay thế schema production đầy đủ. Chưa có đo hiệu năng PostgreSQL hoặc bằng chứng
khả năng phục vụ số lượng lớn; seed chỉ xác minh luồng liên kết và ràng buộc cấu trúc.
