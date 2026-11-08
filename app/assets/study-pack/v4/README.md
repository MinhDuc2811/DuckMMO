# Upbeat music v4

Ba bản không lời nguyên gốc theo hướng vui và dễ nhớ hơn. Dùng màu sắc pop groove,
country-pop và acoustic pop làm định hướng; không dùng giai điệu hoặc bản thu của bài hát cụ thể.
Các bản phối bằng nhạc cụ ảo GeneralUser GS/FluidSynth, không phải bản thu ban nhạc thật.

| Tên hiển thị | ID tương thích | Độ dài | Nhạc cụ / nhịp |
| --- | --- | --- | --- |
| Sunny Steps | quiet-pages | 32s · 90 BPM | Electric piano, guitar clean mang giai điệu, guitar nylon, bass và kick/snare/clap nhẹ |
| Open Road | soft-focus | 40s · 120 BPM | Guitar steel strum/picking, banjo nhỏ, bass acoustic, hi-hat/tambourine |
| Good Mood | morning-air | 32s · 120 BPM | Guitar nylon/steel, piano motif, bass, rim/shaker |

Thay đổi chính so với v3: cụm giai điệu được soạn rõ thành 4 câu lặp có biến thể,
nhịp đệm offbeat và bass pickup, không chỉ rải nốt của hợp âm. Ít khoảng nghỉ dài.
Reverb/chorus vẫn tắt; gain dưới lời đọc gợi ý 8–10%, ducking bật.
WAV là nguồn loop; MP3 có thể thêm encoder padding nên chỉ dùng để nghe thử.

**Đã bị người dùng từ chối về chất lượng âm nhạc.** Thẻ trắng hiện mặc định tắt nhạc;
v4 chỉ còn là lựa chọn thử nghiệm chủ động. Lựa chọn đã lưu vẫn được giữ.
Catalog presentation v6, manifest pack v4; các task đã pin file cũ không bị thay nội dung.
Ảnh chụp thật/credit v3 tiếp tục dùng; bản cập nhật này chỉ đổi nhạc và mặc định chọn nhạc.

Generator `scripts/generate_upbeat_music.py` tái sử dụng engine `generate_chamber_music.py`.
Cần soundfont GeneralUser GS và libfluidsynth để tái tạo; file WAV tạo sẵn dùng trong app
không cần cài các công cụ đó. Giấy phép soundfont được giữ trong SOUNDFONT-LICENSE.txt.

Kiểm tra tín hiệu: 32/40/32s, không sample clipping, chênh lệch điểm nối nhỏ hơn p99 biến thiên
sample trong bài. Các con số này không đánh giá mức độ hay/vui; có bản nghe thử để người dùng chọn.

Lịch sử bước v4 (đã được thay bằng mặc định tắt nhạc): chỉ cập nhật nhãn chọn nhạc và kỳ vọng mặc định thẻ trắng từ ambient sang
quiet-pages theo yêu cầu mới. Giữ kiểm tra ảnh/credit, ID track, volume 10%, ducking và job queue;
thêm assert chọn mặc định Sunny Steps ở screen-flow. Browser xác nhận Sunny Steps mặc định,
sau đó người dùng chủ động đổi sang Open Road và kiểm tra soft-focus tới queue. Trace ban đầu
cho thấy ArrowDown trong test cũ đi sang option kế tiếp khi Sunny Steps đã là mặc định;
thay bằng thao tác mở menu/chọn đúng tên, không nới assertion hoặc timeout.

Các script sinh nhạc đã dừng, được chuyển cùng bản thử vào `/workspace/archive/rejected-study-assets/generators/`; không cài vào runtime mới.
