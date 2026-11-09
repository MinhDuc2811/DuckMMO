# Kiểm tra chất lượng video thành phẩm

Mỗi lần render mới tự chạy FFmpeg/FFprobe trên **file MP4 cuối cùng**, sau khi trộn
âm thanh và dựng phụ đề/khung trắng. Không cần API key, model AI hay dependency mới.
Bộ này kiểm tra kỹ thuật; chưa bảo đảm phát âm chuẩn, bài học đúng hoặc video hấp dẫn.

## Luồng sử dụng

Dựng video như trước. Nếu có lỗi chặn, tác vụ chuyển `failed`, không tạo video sẵn sàng
để duyệt; xem evidence trong **Theo dõi tác vụ → Chất lượng**. Nếu đạt hoặc chỉ có cảnh
báo, màn hình duyệt video hiện kết quả FFmpeg và cho tải **báo cáo chất lượng JSON**.
Cảnh báo cần xem/nghe lại trước khi quyết định duyệt. Quyết định duyệt/đăng vẫn thủ công.

Báo cáo `output-quality.json` gắn SHA-256 của đúng MP4 được quét và nằm trong manifest
`video.quality.output`, checkpoint QA và endpoint có xác thực:
`GET /api/jobs/{job_id}/artifacts/quality_report`. Phiên bản evaluator: `ffmpeg-output-v1`.
Job cũ không được tự gán kết quả; dựng lại để có kiểm tra mới.

## Các kiểm tra

| Kiểm tra | Xử lý |
| --- | --- |
| Thiếu stream hình/tiếng, sai kích thước, thời lượng stream/file lệch lời đọc >0,3 giây | Chặn |
| Không giải mã hoàn tất toàn bộ hình và tiếng, thiếu FFprobe, timeout hoặc thiếu kết quả đo | Chặn |
| True peak không hữu hạn hoặc nhỏ hơn −50 dBTP (toàn bộ đầu ra gần như im lặng) | Chặn |
| Gần như toàn bộ video đen (≥95% thời lượng theo blackdetect) | Chặn |
| Có đoạn đen ≥0,5 giây | Cảnh báo và mốc thời gian |
| Có khoảng im lặng ≥1 giây dưới −50 dB | Cảnh báo và mốc thời gian |
| Integrated loudness ngoài khoảng −24 đến −12 LUFS | Cảnh báo |
| True peak trên −1 dBTP | Cảnh báo headroom; không khẳng định clipping/méo tiếng |

Khoảng LUFS là tiêu chí biên tập ban đầu, không phải yêu cầu của YouTube. Blackdetect
đánh dấu frame có ≥98% pixel dưới ngưỡng độ sáng 0,1; nền đen sau khung trắng có chữ
có thể không bị phát hiện. Nền ảnh tĩnh hợp lệ, không chạy freeze detector để chặn ảnh.

Đo loudnorm dùng **input_i/input_tp** của âm thanh AAC đã giải mã, không dùng kết quả
normalization dự kiến; toàn bộ đầu ra phân tích đi vào null sink, không sửa MP4 gốc.
Không tự normalize lại giọng/nhạc và không tự sửa nội dung.

## Giới hạn và vận hành

Quét thêm một lượt toàn bộ MP4 làm tăng thời gian render. Dùng command runner hiện có,
thread limit theo settings, timeout probe 30 giây và decode `max(60, 3 × thời lượng)`.
Subprocess được quản lý/dọn như các bước render hiện tại, checkpoint giữ cancel guards.
Chỉ ghi báo cáo nhỏ; tính hash streaming, không nạp toàn bộ MP4 vào RAM. Chưa có benchmark
throughput/peak RAM cho video dài; không tuyên bố đạt một SLA tốc độ cụ thể.

Chưa đánh giá độ nét/chính tả chữ trên frame, đồng bộ từng từ, phát âm Anh–Anh, nhạc lấn
giọng, độ liên quan background hay hiệu quả giữ người xem. Kiểm tra phụ đề và audio PCM
trước render vẫn được giữ. Im lặng/đen ngắn có thể có chủ ý, nên mặc định chỉ cảnh báo.

## Kiểm chứng

Feature tests tại `test_suite/features/output_quality`: MP4 thật cho ảnh tĩnh, im lặng,
đen, thiếu tiếng, sai thời lượng/kích thước, file hỏng và khoảng im lặng có timecode.
API/worker kiểm tra lưu evidence, hash, authentication và chặn duyệt khi đầu ra lỗi.
Playwright tải báo cáo từ màn hình duyệt và đối chiếu đúng MP4; speech là PCM fixture
được khai báo, không phải thử giọng Edge trực tiếp. Không gọi dịch vụ ngoài/đăng bài.

Nguồn: [FFmpeg](https://github.com/FFmpeg/FFmpeg),
[filter documentation](https://ffmpeg.org/ffmpeg-filters.html).
