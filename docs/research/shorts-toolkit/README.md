# Thư viện cho IELTS YouTube Shorts — khảo sát 2026-11-08

Đã đọc metadata/README của 59 repository truy cập được và 56 root license; 61 địa chỉ đã thử. Đây là khảo sát tài liệu tĩnh, không phải benchmark hay xác nhận mọi repo chạy được. Catalog và sources kèm URL, ngày kiểm tra, hash của bản tài liệu đã đọc. Điều kiện API/model/assets cần kiểm lại khi triển khai.

## Quyết định cho ứng dụng hiện tại

| Nhu cầu | Chọn | Cách tích hợp |
| --- | --- | --- |
| Render thẻ trắng 9:16 | FFmpeg + Pillow hiện có | Giữ worker, cancellation, checksum, duyệt video; không nhân đôi renderer |
| Phụ đề | pysubs2 (MIT) | Ghi/đọc SRT chuẩn, giữ libass và bộ kiểm tra layout hiện tại; timing vẫn ước lượng theo cụm, chưa word alignment |
| Kho IELTS | SQLAlchemy/Alembic + RapidFuzz (MIT) | Topic cha/con, nội dung có loại riêng, nghĩa từ vựng, cấu trúc, sample và bài tập; tìm gần đúng không tự gộp các nghĩa |
| Ảnh/video thật | Pexels REST + Openverse REST qua httpx sẵn có | Tìm theo từ khóa ảnh/video/audio, hiển thị tác giả/source/license; người dùng chọn, tải và upload qua media owner có giới hạn hiện tại |
| Nhạc | Upload bản đã nghe và có quyền dùng | Dùng mixer/loop/crossfade/ducking hiện có, mặc định tắt; không tạo thêm MIDI |
| Voice UK | Edge Sonia/Ryan hiện có | Nghe thử bắt buộc về mặt biên tập; không thêm dịch vụ trả phí. Mạng môi trường này đang chặn Edge |
| YouTube | Giữ adapter resumable upload/OAuth hiện có | Không thay bằng SDK chỉ để bọc cùng HTTP; không đăng video trong tác vụ này |
| Kiểm thử | Playwright hiện có | Browser thật, DB tạm, FFmpeg thật; TTS fixture ghi rõ |

Không cài tất cả repo. Phụ thuộc mới phải có caller thực tế; FFmpeg đã có loudnorm nên không thêm pyloudnorm/ffmpeg-normalize chỉ để làm cùng việc.

## Các lựa chọn tốt nhưng chưa đưa vào runtime

- **Remotion**: phù hợp preview timeline và bài quiz động, nhưng kéo thêm React/Node/Chromium vào backend Python. License hiện tại không phải MIT: miễn phí cho các nhóm đủ điều kiện, doanh nghiệp lớn hơn phải kiểm điều khoản. Chỉ dùng khi chuyển frontend/timeline thực sự.
- **Kokoro**: local TTS 82M, Apache-2.0, có British `lang_code='b'`. Cần tải checkpoint, chọn voice và nghe IPA/tên riêng trước. Chưa tải model/chưa audition, không quảng cáo đã đạt phát âm chuẩn. Piper successor GPL-3.0, license từng voice khác nhau.
- **ACE-Step 1.5**: MIT code, có REST tạo nhạc bất đồng bộ. Nên chạy service/GPU riêng và duyệt bản demo trước; chưa cài, chưa chạy, chưa nghe. Không bảo đảm nhạc hay hay được cấp quyền với mọi checkpoint.
- **WhisperX/faster-whisper**: khi có audio ngoài cần nhận dạng/căn lời. Chưa cần tải Torch/model nặng cho script-to-TTS; diarization không cần với một narrator.
- **pgvector/sentence-transformers/Meilisearch**: chỉ sau khi đo thấy SQL+filter+fuzzy chưa đủ; license model/edition riêng. Không thay phân loại dữ liệu bằng vector search.
- **RQ/Prefect**: chỉ khi có nhu cầu nhiều worker/lease phân tán. Supervisor local hiện có vẫn là owner.

## Repo gần sản phẩm nhất

1. [short-video-maker](https://github.com/gyoridavid/short-video-maker): tham khảo REST/MCP + Kokoro + Whisper + Pexels + Remotion. MIT của wrapper không thay license Remotion; dependency fluent-ffmpeg đã deprecated/archived. Không fork nguyên bộ.
2. [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo): Python, đủ script/stock/TTS/caption/music/render; nhiều provider có phí và quyền assets riêng. Hợp tham khảo flow và lỗi triển khai.
3. [AI-Youtube-Shorts-Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator): hợp cắt bài giảng dài, crop theo mặt; default cloud MuAPI và ranking API không phải miễn phí hoàn toàn.

## Nguồn nhạc phù hợp hơn việc tự tổng hợp

Ưu tiên YouTube Audio Library được tải/chọn thủ công và lưu điều khoản của từng track; hoặc catalog được cấp phép như Epidemic Sound/Artlist/Jamendo nếu phù hợp ngân sách. Không giả định các dịch vụ này đều có public API hoặc mọi bài đều dùng được trên mọi kênh. Openverse (đã nối tìm audio) / Freesound hữu ích cho audio CC/ambience/loop, không bảo đảm kho nhạc pop hoàn chỉnh dễ nghe. Music picker trong Shorts khác với quyền đính nhạc vào MP4 qua upload API. Tách vocal hoặc cover không tự cấp quyền ca khúc.

AudioCraft: code MIT nhưng **weights CC-BY-NC-4.0**, không chọn mặc định cho kênh kiếm tiền. stable-audio-tools: code MIT nhưng model có điều khoản riêng. Demucs, stable-ts, youtube/api-samples, Openverse API repo cũ và OAuth repo cũ có trạng thái archived/moved cần tránh dùng làm dependency mới.

## Chuẩn bị data và biên tập

- Mỗi mục có nguồn, quyền sử dụng, topic, loại, trạng thái draft/reviewed, phiên bản. Từ vựng lưu một nghĩa một mục (lemma/POS/IPA/definition/examples), không gộp đồng âm/đa nghĩa.
- Pattern lưu form/function/explanation/examples; sample lưu prompt/skill/response/annotations; exercise lưu question/options/answer/explanation. Quan hệ topic nhiều-nhiều.
- Không gán band IELTS cho ví dụ tự viết; không coi word frequency là CEFR/band; không sao chép đề/sách bản quyền vào seed. Seed nghiên cứu vẫn draft và chưa xác minh quyền.
- JSON import: preview schema + topic + duplicate trước; ghi nguyên batch trong transaction; fuzzy chỉ gợi ý, exact duplicate không tạo bản thứ hai.
- Một Short chỉ chọn một nghĩa/một cấu trúc/một đoạn sample/một câu hỏi. Hook ngắn → ví dụ → giải thích/đáp án → nhắc lại. Không nhét cả vocabulary, pattern, sample vào cùng video.
- Assets: lưu provider ID/source URL/author/license/rights note/topic và hash file upload. Chọn ảnh thật ít chi tiết sau thẻ trắng, không chọn chỉ vì từ khóa khớp.
- Nhạc: nghe ít nhất ba vòng loop, nghe trên loa điện thoại và dưới voice; kiểm seam, bass, clipping. LUFS và ducking không đánh giá được giai điệu hay.

## YouTube và giới hạn kiểm chứng

Official Data API discovery revision 20261019 không có trường `isShort` trong videos.insert/Video. Xuất 9:16 không có nghĩa API cam kết phân loại Shorts; điều kiện hiện hành của YouTube cần đối chiếu trước đăng. Không có API đính bài trending từ music picker được xác minh trong khảo sát. Không dùng số sao GitHub hay lời README làm bằng chứng trending/viral.

## Catalog đầy đủ


| Nhóm | Repo | Dùng cho | Điều kiện / giới hạn |
| --- | --- | --- | --- |
| Dự án hoàn chỉnh | [gyoridavid/short-video-maker](https://github.com/gyoridavid/short-video-maker) | REST/MCP; Kokoro + Whisper + Pexels + Remotion + music | MIT repo; Remotion có license riêng; Sửa template thẻ trắng, chọn UK voice, kiểm music assets; có dependency fluent-ffmpeg deprecated. |
| Dự án hoàn chỉnh | [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | Luồng script → stock assets → TTS → captions → video | MIT; Nhiều provider/cấu hình; không fork toàn bộ vào app; quyền assets/API tách license code. |
| Dự án hoàn chỉnh | [SamurAIGPT/AI-Youtube-Shorts-Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator) | Video dài → chọn đoạn → crop 9:16 | MIT; Hợp cắt bài giảng; API/LLM mode có thể tốn tiền; không có bảo đảm viral. |
| Dự án hoàn chỉnh | [FujiwaraChoki/MoneyPrinterV2](https://github.com/FujiwaraChoki/MoneyPrinterV2) | Automation nhiều mục đích | AGPL-3.0; Workflow Twitter/affiliate/cold outreach không sát kho IELTS; không lấy toàn dự án làm lõi. |
| Dựng video | [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg) | Encode/crop/loop/mix/duck/ASS | LGPL/GPL tuỳ build; Đã có trong project; font/layout và đầu vào vẫn cần biên tập; xem license build binary. |
| Dựng video | [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | Template thẻ trắng, timer, quiz, preview theo timeline | License Remotion riêng; License hiện ghi cá nhân/công ty <=3 nhân viên có free eligibility; không mặc định MIT; không mặc định nhanh hơn FFmpeg. |
| Dựng video | [Zulko/moviepy](https://github.com/Zulko/moviepy) | Composition bằng Python | MIT; Có breaking changes v2; không nên chạy thêm engine trùng lặp nếu renderer hiện tại đã đủ. |
| Dựng video | [PyAV-Org/PyAV](https://github.com/PyAV-Org/PyAV) | Decode/frame/audio theo stream | BSD-style; FFmpeg riêng; Hợp khi cần tối ưu xử lý frame thật sự; không cung cấp template đẹp sẵn. |
| Dựng video | [motion-canvas/motion-canvas](https://github.com/motion-canvas/motion-canvas) | Animation giải thích/đồ hoạ timeline | MIT; Hợp sơ đồ, so sánh; cạnh tranh lựa chọn renderer với Remotion, không cần cả hai. |
| Dựng video | [mifi/editly](https://github.com/mifi/editly) | Video composition khai báo | MIT; Cần thử dependencies native; không tự giải quyết thiết kế card hoặc nội dung IELTS. |
| Dựng video | [ManimCommunity/manim](https://github.com/ManimCommunity/manim) | Animation biểu đồ/quy trình | MIT; Hợp một số bài Writing Task 1; quá nặng cho card chữ thông thường. |
| Dựng video | [Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Phát hiện điểm đổi cảnh | BSD-3-Clause; Dùng khi ingest clip dài; không tự chọn đoạn có giá trị học tập. |
| Phụ đề | [libass/libass](https://github.com/libass/libass) | Render ASS/SSA | ISC; Đã được FFmpeg renderer hiện có sử dụng; không cần xây engine caption mới. |
| Phụ đề | [tkarabela/pysubs2](https://github.com/tkarabela/pysubs2) | Đọc/ghi/sửa SRT/ASS và timing | MIT; Tích hợp nhẹ; không tự căn từng từ bằng audio. |
| Phụ đề | [m-bain/whisperX](https://github.com/m-bain/whisperX) | ASR + forced alignment | BSD-2-Clause code; models riêng; Dùng alignment cho script đã biết; không cần diarization cho một narrator; kiểm model license/deps. |
| Phụ đề | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Transcribe audio có sẵn | MIT code; models riêng; Không tự sinh TTS; không thay thế bộ máy forced alignment trong mọi trường hợp. |
| Phụ đề | [MontrealCorpusTools/Montreal-Forced-Aligner](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner) | Căn audio với transcript đã biết | MIT code; models/dictionaries riêng; Phụ thuộc nặng hơn; chọn dictionary/acoustic model phù hợp English. |
| Phụ đề | [jianfch/stable-ts](https://github.com/jianfch/stable-ts) | Chỉnh timestamp, alignment | MIT; Repo archived; README nói development indefinitely paused. |
| Giọng đọc | [hexgrad/kokoro](https://github.com/hexgrad/kokoro) | TTS có British English lang_code b | Apache-2.0; README mô tả weights Apache; Chưa nghe benchmark trong dự án; phải audition đúng voice, từ học thuật và phiên bản model. |
| Giọng đọc | [rany2/edge-tts](https://github.com/rany2/edge-tts) | Giọng en-GB có sẵn trong app | LGPLv3 phần lớn; một file MIT; service terms riêng; Client không chính thức; lỗi policy mạng 403 trước đây không được chữa bằng đổi SDK. |
| Giọng đọc | [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | Local TTS, HTTP/CLI/Python API | GPL-3.0 code; voice model riêng; Đây là repo kế nhiệm; kiểm license và chất lượng từng voice en_GB. |
| Giọng đọc | [rhasspy/piper](https://github.com/rhasspy/piper) | Piper cũ | MIT repo cũ; Archived; README chuyển sang OHF-Voice/piper1-gpl. |
| Giọng đọc | [idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS) | TTS nhiều model | MPL-2.0 code; model riêng; Không gộp license XTTS/checkpoints vào MPL; không cần voice cloning cho yêu cầu hiện tại. |
| Giọng đọc | [Azure-Samples/cognitive-services-speech-sdk](https://github.com/Azure-Samples/cognitive-services-speech-sdk) | TTS chính thức với giọng UK | MIT samples; dịch vụ có điều khoản/chi phí; Chỉ là phương án nghiên cứu nếu đổi chính sách chi phí; chưa nối provider trả phí. |
| Xử lý audio | [csteinmetz1/pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) | Đo/chuẩn hoá loudness LUFS | MIT; Chọn công cụ này hoặc ffmpeg-normalize theo nhu cầu; không tạo ra giai điệu hay hơn. |
| Xử lý audio | [slhck/ffmpeg-normalize](https://github.com/slhck/ffmpeg-normalize) | Batch EBU R128 loudness normalization | MIT; Tái dùng FFmpeg sẵn có; giữ file gốc và kiểm đầu ra. |
| Xử lý audio | [jiaaro/pydub](https://github.com/jiaaro/pydub) | Cắt/fade/crossfade/gain | MIT; Phù hợp tiện ích; project đã có nhiều thao tác tương tự qua FFmpeg. |
| Xử lý audio | [librosa/librosa](https://github.com/librosa/librosa) | BPM/onset/beat/silence analysis | ISC; Hỗ trợ chọn đoạn/điểm nối, không bảo đảm loop nghe tự nhiên hoặc nhạc hợp gu. |
| Xử lý audio | [spotify/pedalboard](https://github.com/spotify/pedalboard) | Effects/EQ/compression/plugin processing | GPL-3.0; Không cần nếu mục tiêu là nhạc khô, ít vang và mixer hiện tại đủ. |
| Xử lý audio | [nomadkaraoke/python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | Tách vocal/instrumental từ file được cung cấp | MIT wrapper; model weights riêng; Không cấp quyền dùng bài hát; có thể có artefact; không thay kho nhạc hoàn chỉnh. |
| Xử lý audio | [facebookresearch/demucs](https://github.com/facebookresearch/demucs) | Music source separation | MIT; Repo archived; xem wrapper/model đang được duy trì nếu cần tách stem. |
| Sinh nhạc | [ace-step/ACE-Step-1.5](https://github.com/ace-step/ACE-Step-1.5) | Music model + REST async API | MIT repo; kiểm model card checkpoint; Đã đọc API /release_task và /query_result; chưa chạy, chưa nghe; claims chất lượng/tốc độ là từ tác giả. |
| Sinh nhạc | [ace-step/ACE-Step](https://github.com/ace-step/ACE-Step) | Music generation | Apache-2.0 repo; checkpoint riêng; Ưu tiên đánh giá 1.5 trước, không cần triển khai hai phiên bản. |
| Sinh nhạc | [Stability-AI/stable-audio-tools](https://github.com/Stability-AI/stable-audio-tools) | Audio generation/training/inference | MIT code; model license riêng; Kiểm chính xác model/EULA; không suy ra free commercial từ license code. |
| Sinh nhạc | [facebookresearch/audiocraft](https://github.com/facebookresearch/audiocraft) | MusicGen/AudioGen | MIT code; weights CC-BY-NC-4.0; Trọng số mặc định noncommercial; dependencies cần môi trường riêng. |
| Nguồn tài sản | [MTG/freesound-python](https://github.com/MTG/freesound-python) | Tìm sound/ambience/loop qua Freesound | MIT client; audio license từng file; Không phải kho bài pop hoàn chỉnh được cấp phép hàng loạt; lưu license/credit mỗi file. |
| Nguồn tài sản | [WordPress/openverse](https://github.com/WordPress/openverse) | Search ảnh và audio có metadata giấy phép | MIT service code; media license riêng; Gọi API, không cần tự host toàn bộ search engine; kiểm nguồn/quality từng asset. |
| Nguồn tài sản | [WordPress/openverse-api](https://github.com/WordPress/openverse-api) | Openverse API cũ | MIT repo cũ; Archived; code chuyển vào WordPress/openverse/api. |
| Nguồn tài sản | [pexels/pexels-javascript](https://github.com/pexels/pexels-javascript) | Ảnh/clip stock theo topic | MIT theo package.json; Pexels terms riêng; Python app nên dùng httpx có sẵn; API key/quota và terms phải kiểm trước tích hợp. |
| Nguồn tài sản | [unsplash/unsplash-js](https://github.com/unsplash/unsplash-js) | Ảnh chụp thật | MIT SDK; Unsplash/API terms riêng; Kiểm attribution, hotlink/download tracking requirements; không mặc định mass-mirror ảnh. |
| Nguồn tài sản | [mwclient/mwclient](https://github.com/mwclient/mwclient) | Wikimedia Commons, nguồn lịch sử/học thuật | MIT client; media license riêng; Truy license/author/credit ở từng file, không coi toàn Commons là public domain. |
| Thiết kế chữ | [google/fonts](https://github.com/google/fonts) | Chữ card, IPA, dấu tiếng Việt | Theo từng font: OFL/Apache/...; Đọc license từng family và kiểm glyph; không cài toàn repo. |
| YouTube | [googleapis/google-api-python-client](https://github.com/googleapis/google-api-python-client) | Data API và Analytics API | Apache-2.0; Tái dùng approval/publish adapter hiện có; OAuth/quota; không có isShort trong discovery đã đọc. |
| YouTube | [googleapis/google-cloud-python](https://github.com/googleapis/google-cloud-python/tree/main/packages/google-auth-oauthlib) | OAuth/refresh token | Apache-2.0; Chỉ dùng packages/google-auth-oauthlib; không cài toàn Google Cloud SDK. |
| YouTube | [googleapis/google-auth-library-python-oauthlib](https://github.com/googleapis/google-auth-library-python-oauthlib) | OAuth repo cũ | Apache-2.0; Archived; README chuyển package sang google-cloud-python. |
| YouTube | [youtube/api-samples](https://github.com/youtube/api-samples) | Ví dụ upload/analytics | License toàn repo chưa xác minh ở khảo sát; Archived; không coi là SDK hiện hành. |
| Import video | [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) | Import nguồn video người dùng có quyền dùng | Unlicense code; phần đóng gói/third-party riêng; Không cấp quyền reupload hoặc lấy nhạc; không phải API xuất bản YouTube. |
| Kho IELTS | [rapidfuzz/RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | Phát hiện tên/đoạn gần trùng | MIT; Chỉ gợi ý duplicate; không tự merge hai nghĩa từ khác nhau. |
| Kho IELTS | [explosion/spaCy](https://github.com/explosion/spaCy) | Lemma/POS/sentence segmentation | MIT code; model license riêng; Giúp chuẩn hoá và gắn nhãn; không phải nguồn định nghĩa hay bộ chấm IELTS. |
| Kho IELTS | [jxmorris12/language_tool_python](https://github.com/jxmorris12/language_tool_python) | Grammar checking, có thể chọn en-GB | GPL-3.0 wrapper; Human review vẫn cần; không quy đổi số lỗi thành IELTS band. |
| Kho IELTS | [rspeer/wordfreq](https://github.com/rspeer/wordfreq) | Word frequency để ưu tiên từ | Apache-2.0 code; data CC BY-SA; README nói data chủ yếu snapshot tới khoảng 2021; không dùng làm CEFR/IELTS band hay trend hiện tại. |
| Kho IELTS | [UKPLab/sentence-transformers](https://github.com/UKPLab/sentence-transformers) | Semantic search/near-duplicate | Apache-2.0 code; model riêng; Chỉ thêm khi truy vấn semantic cần thiết; kiểm benchmark và model license. |
| Tìm kiếm | [pgvector/pgvector](https://github.com/pgvector/pgvector) | Vector index trong Postgres | PostgreSQL License; Full-text/filters trước; không cần vector DB riêng từ đầu. |
| Tìm kiếm | [meilisearch/meilisearch](https://github.com/meilisearch/meilisearch) | Full-text, facets, typo tolerance | CE MIT; EE BUSL/commercial; Thêm service và đồng bộ index; chỉ khi Postgres search không đáp ứng. |
| Batch jobs | [rq/rq](https://github.com/rq/rq) | Queue/retry workers | BSD-2-Clause; Hiện đã có queue/cancel/audit; không thay nếu chưa có nhu cầu đa worker. |
| Batch jobs | [PrefectHQ/prefect](https://github.com/PrefectHQ/prefect) | DAG/batch/retry/observability | Apache-2.0; Không cần thay lifecycle app chỉ để tạo vài Short. |
| Kiểm thử | [microsoft/playwright-python](https://github.com/microsoft/playwright-python) | Browser E2E và screenshots | Apache-2.0; Đã thiết lập; test pass không thay thế nghe/xem đánh giá chất lượng nội dung. |
| Dependency cần tránh | [fluent-ffmpeg/node-fluent-ffmpeg](https://github.com/fluent-ffmpeg/node-fluent-ffmpeg) | FFmpeg wrapper | MIT; Archived/deprecated; README nói không được duy trì, có vấn đề FFmpeg mới; short-video-maker đang phụ thuộc nó. |
| Ngoài phạm vi | [moeru-ai/airi](https://github.com/moeru-ai/airi) | AI companion | MIT; Không sát công cụ sản xuất bài học tiếng Anh/Shorts; không thêm vào stack. |

## Runtime và kiểm chứng tích hợp

Xem [hướng dẫn kho IELTS](../../ielts-shorts/runtime.md) và [ảnh/nhạc](../../study-pack.md).
Snapshot `summary.json` mô tả pha nghiên cứu trước coding, không phải tuyên bố hiện tại chưa tích hợp.
Openverse routes đã đối chiếu [cấu hình URL upstream](https://github.com/WordPress/openverse/blob/main/api/conf/urls/__init__.py): `v1/images/` và `v1/audio/`.

[Kết quả kiểm thử và điểm chặn Git push](validation.md).
