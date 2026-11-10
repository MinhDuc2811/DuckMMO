# Tự tạo và đăng YouTube Shorts theo lịch

Tab **Tự động hóa** nối hàng đợi bài học, worker dựng video, QA và YouTube API.
Không cần bấm tạo/duyệt/upload cho từng video sau khi đã bật lịch. Thông báo lỗi chỉ
hiện trong dashboard; không gửi Telegram/email. Không tự bật lịch hoặc đăng thử khi cài đặt.

## Kết nối kênh thật

1. Trong Google Cloud project của bạn, bật **YouTube Data API v3** và **YouTube Analytics API**.
   Thiết lập OAuth consent screen, thêm tài khoản của bạn vào test users nếu app đang Testing.
2. Tạo **OAuth client loại Web application**. Thêm Authorized redirect URI trùng chính xác
   `STUDIO_YOUTUBE_REDIRECT_URI`. Mặc định local là:
   `http://127.0.0.1:8000/api/youtube/oauth/callback`.
   Nếu chạy server từ xa, dùng URL HTTPS của API mà trình duyệt của bạn truy cập được,
   không dùng localhost của một máy khác. URL UI và URL API có thể khác nhau.
3. Trong tab Tự động hóa hoặc Phase 5, mở **Kết nối / kiểm tra YouTube**, lưu client ID/secret,
   bấm **Kết nối bằng Google**, đăng nhập và chọn đúng tài khoản/kênh.
4. Sau callback, quay lại tool và bấm **Kiểm tra kết nối kênh**. Tool dùng API `channels.list`
   để xác minh ID/tên kênh, không coi có chuỗi token là đã kiểm tra kết nối.

Không gửi credentials vào chat hoặc Git. Cấu hình/refresh token ở `data/settings/youtube.json`
(nằm cạnh thư mục artifacts), được ghi atomic, file mode 0600 trên POSIX. Đây là lưu cục bộ,
không phải kho bí mật được mã hóa. API/UI vẫn là ứng dụng single-user, không triển khai public
mà không có TLS và API authentication. Callback public dùng state ngẫu nhiên một lần, TTL
10 phút và PKCE S256. Chỉ một phiên OAuth mới nhất có hiệu lực. Access token không lưu ra UI.
Env OAuth cũ vẫn dùng được nếu chưa có cấu hình cục bộ; đổi client sẽ yêu cầu kết nối lại.

Quyền: youtube.upload, youtube.readonly, yt-analytics.readonly. OAuth app ở Testing có thể
có refresh token hết hạn sớm theo chính sách Google. API project chưa qua kiểm định có thể
bị giới hạn video upload ở chế độ private: kết nối thành công không tự gỡ giới hạn này.
Phải xử lý trong Google Cloud/YouTube, không thể vượt bằng code của tool.

## Tạo hàng đợi

- Chọn các mục **đã duyệt** trong thư viện IELTS: vocabulary, patterns, samples, exercises.
- Bấm **Chuẩn bị nội dung hàng đợi** sau khi chọn bài. Mỗi mục tạo một video, một nội dung đọc tối đa 85 từ/650 ký tự. UI gợi ý từ dữ liệu có sẵn;
  xem/sửa một lần trước khi lưu. Không tự bịa bài bằng AI hoặc trộn tất cả nội dung vào một Short.
- Chọn ảnh thật, giờ đăng đầu theo Việt Nam (UTC+7), khoảng cách 6–168 giờ, tối đa 60 video/lịch.
  Lần đầu cách hiện tại ít nhất 35 phút. Không tự thêm bài khi hàng đợi hết.
- Lịch mới ở trạng thái dừng. Checkbox và **Bật lịch tự động** là ủy quyền cho auto-review
  và publish toàn bộ hàng đợi đó, gắn với ID kênh đã xác minh. Không áp dụng cho job thủ công.
- Mặc định chỉ tự duyệt khi FFmpeg đạt và các bước render không có fail/warn. Có tùy chọn
  chấp nhận warning; unknown như phát âm/độ đúng ngữ nghĩa vẫn chưa được tự xác minh.

Video dùng giọng miễn phí **en-GB-SoniaNeural**, layout dọc, khung trắng và ảnh thật đã chọn,
không thêm nhạc mặc định. Nguồn bài và credit ảnh được ghi trong mô tả YouTube.
Bản hiện tại tự tạo từ hàng đợi bài học đã chuẩn bị/duyệt; chưa có chiến dịch tự research
và sinh bài vô hạn, chưa có auto-chọn footage MPT cho từng bài hay vòng tối ưu theo retention.

## Vận hành

Chạy migration, API, UI và worker như bình thường:

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
uv run streamlit run ui/studio.py
uv run python -m app.worker
```

Worker cần chạy liên tục để tạo/upload; đóng trình duyệt không dừng worker. Điều phối chạy
trong supervisor hiện tại, có lock liên process, tối đa 10 lượt mỗi tick. Job/render vẫn dùng
supervisor, checkpoint, quota và cancel guards hiện có. Không thêm broker hoặc worker thứ hai.

Bắt đầu chuẩn bị 30 phút trước giờ đăng. Video dọc ≤60 giây mới được đăng tự động. Khi đạt
QA, auto-review được audit dưới tên **Automation policy** (không giả là người đã xem/nghe).
Upload resumable dùng `privacyStatus=private` và `publishAt`; YouTube chịu trách nhiệm
công khai đúng lịch sau khi đã nhận video. Tool kiểm tra processing/privacy mỗi 5 phút,
phân biệt `scheduled` với `published`; lỗi xử lý, thiếu lịch hoặc chậm công khai >15 phút
hiện trong dashboard. Trạng thái thực tế phải do API trả về, không suy từ thời gian local.

Lịch được lưu trong migration 0007: `automation_plans`, `automation_runs`. Snapshot nguồn/
version bảo vệ thay đổi thư viện; idempotency key theo slot tránh tạo job trùng sau restart.
Upload tận dụng session/offset và unique artifact hiện có để đối soát, không tạo upload mới
khi kết quả cũ chưa rõ. Lỗi upload 5xx tối đa ba lượt với backoff; lỗi content/render/QA hoặc
lỡ thời gian không tự đăng bù. Kiểm tra lỗi và tạo lịch mới khi đã sửa, không đăng dồn backlog.

**Dừng lịch** ngăn bước tiếp theo ở local; request upload đang chạy có thể hoàn tất. Video
đã hẹn giờ trên YouTube vẫn còn lịch, phải hủy/đổi trong YouTube Studio. Tắt worker cũng
không hủy lịch mà YouTube đã nhận. Dashboard chỉ tự refresh khi mở, không gửi thông báo ngoài.

## Kiểm chứng và giới hạn

Test API/DB/worker/FFmpeg dùng thật; Google HTTP và TTS là fixture được khai báo. Playwright
kiểm tra kết nối, callback state và bật/dừng lịch trong dashboard. Không giả lập việc user đã
đăng nhập Google thật; không có tài khoản/credentials ở môi trường này, chưa upload/công khai
bất kỳ video nào trên kênh thật. Cần OAuth và mở mạng Google để xác minh live.

Không suy kiểm tra kỹ thuật thành phát âm chuẩn, fact-check hoặc khả năng video hấp dẫn.
Chưa benchmark lịch lớn/throughput, chưa có heartbeat/supervisor service installer hay hỗ trợ
multi-user/multi-channel. Dùng process manager của máy chủ để giữ API/worker hoạt động.
