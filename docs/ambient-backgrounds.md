# Ambient background và xuất HD

Phase 3 thêm **Chất lượng xuất**:

| Profile | Kích thước dọc | FPS | H.264 | Phạm vi |
| --- | --- | --- | --- | --- |
| preview (mặc định API/UI cũ) | 720×1280 | 24 | CRF 23, veryfast | Tất cả layout |
| final | 1080×1920 | 30 | CRF 19, medium | Khung trắng |

Bản Final ngang dùng 1920×1080. Wallpaper ảnh lớn được crop từ bản gốc rồi resize
LANCZOS về khung Final, tránh thu nhỏ ảnh ngang trước rồi phóng lại phần crop dọc.
Giới hạn upload/20 megapixel vẫn giữ nguyên.

 Final giới hạn cho Khung trắng để không âm thầm đổi tỷ lệ
font/phụ đề của các preset cũ. Khung trắng đã chứa toàn bộ chữ trong `motion.mp4`, nên
bước ghép AAC vào `video.mp4` dùng video stream copy, không nén H.264 lần thứ hai. Các
preset cần overlay ASS vẫn giữ đường encode hiện có. Final chừa 16% bên phải khung
trắng cho vùng điều khiển Shorts; cần xem thử trên thiết bị thật vì UI YouTube thay đổi.

Lịch tự động **mới tạo** dùng Final; lịch cũ không có lựa chọn này giữ preview. Không tự
bật hay sửa lịch đang lưu. Giọng đọc, kiểm tra chất lượng, audit và quyền đăng giữ nguyên.

## Clip nền

Chọn **Clip**, upload/chọn file như trước và bật **Tối ưu clip nền cho Khung trắng**.
Nhập điểm bắt đầu và cửa sổ 3–20 giây. Chỉ dùng clip thuộc job, đã qua kiểm tra upload.
Worker:

1. Phân tích cửa sổ đã chọn bằng FFmpeg scene filter ở 320px/4fps, ngưỡng 0,3.
2. Chọn cảnh liên tục dài nhất trong cửa sổ. Dưới 3 giây thì báo lỗi, không ghép bừa.
3. Giải mã theo FPS profile, crossfade đuôi với phần đầu trong khoảng 0,35 giây.
4. Bỏ phần đầu đã dùng để blend ở chu kỳ tiếp theo để không nhảy ngược sau điểm nối.

Không tạo video nền nén trung gian. Decoder đọc lại đoạn nguồn mỗi chu kỳ và luôn được
đóng/thu hồi khi renderer dừng. Chỉ giữ phần đầu để blend, tối đa 64 MB RGB; cộng thêm
các frame đang xử lý và bộ đệm của FFmpeg. Đây không phải số peak RAM toàn process.
Clip nguồn ngắn hơn 3 giây hoặc điểm bắt đầu ra ngoài clip bị từ chối khi dựng.

Báo cáo `background-analysis.json` lưu hash nguồn, khoảng chọn, các cut đo được, FPS,
chu kỳ, số frame blend và ngân sách buffer; được đưa vào `video.quality.background`,
hiện ở màn hình duyệt. Không bật tối ưu thì giữ hành vi lặp clip cũ. Tùy chọn API:

```json
{
  "render_quality": "final",
  "visual": {"preset": "lesson-card"},
  "video_asset_id": "<owned asset UUID>",
  "background_options": {
    "start_seconds": 0,
    "duration_seconds": 8,
    "auto_scene": true,
    "smooth_loop": true
  }
}
```

Các trường narration hash và voice của RenderOptions vẫn cần như trước. API từ chối
background_options khi thiếu video asset hoặc dùng layout khác. Không tải video mạng
mới, không đưa tiếng của clip nguồn vào narration và không thay thông tin quyền sử dụng.

## Đánh giá và giới hạn

Test dùng MP4/FFmpeg thật: giảm jump trên clip gradient có seam, tránh hard cut, giữ buffer
bounded, đóng decoder, render Full HD, xác minh packet hash của H.264 trước/sau mux và
vùng phải ngoài card. Browser chọn Final và tối ưu clip, dựng/tải MP4 thật. TTS trong test
là tone fixture được khai báo, không xác minh phát âm thực tế.

Mẫu so sánh ngoài repo tại `/workspace/research/ambient-quality-2026-11-10/`: baseline
commit `9ce048c`, nguồn ảnh CC0 Bells Beach có pan giả lập, không phải cảnh quay mới.
Có baseline 720p/hai lần nén, control 720p/một lần nén và Final 1080p/crossfade.
SSIM đo final với intermediate của từng case chỉ đo mất mát lượt nén cuối, không là điểm
thẩm mỹ. Pixel jump ở ROI nền chỉ là chỉ báo kỹ thuật, không là điểm độ mượt cảm nhận.

Crossfade có thể ghosting khi chủ thể di chuyển mạnh; scene detector có thể bỏ sót cut
hoặc nhầm thay đổi sáng. Thuật toán chưa xếp hạng ngữ nghĩa, chưa tự chọn background theo
topic, không biến nguồn thấp phân giải thành chi tiết thật. Có thể tắt tối ưu hoặc chọn
cửa sổ khác. HD/medium có thể tốn CPU và dung lượng hơn; chưa có benchmark tải lớn/Windows.
