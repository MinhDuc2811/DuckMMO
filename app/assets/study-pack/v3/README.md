# Study Pack v3 — ảnh chụp thật

Ảnh/credit bên dưới vẫn dùng. Nhạc v3 đã bị từ chối và chuyển ra ngoài Git tại
`/workspace/archive/rejected-study-assets/v3/music/`. Mô tả nhạc dưới đây là lịch sử,
không phải khuyến nghị hoặc tài sản đang được chọn mặc định.

Theo lựa chọn đã chốt: một pop ballad, một acoustic pop, một R&B nhẹ. Ba giai điệu tự soạn,
không sử dụng giai điệu, bản thu hoặc phần hát của bài hit cụ thể. Nhạc cụ ảo GeneralUser GS
được render bằng FluidSynth, reverb/chorus tắt; bass và trống nhẹ để dùng dưới lời đọc.

| File nhạc | Style | Độ dài / nhịp |
| --- | --- | --- |
| music/quiet-pages.wav | Pop ballad: guitar nylon, electric piano, piano lead, bass và trống nhẹ | 32s / 60 BPM |
| music/soft-focus.wav | Acoustic pop: guitar steel/nylon, piano, bass acoustic, nhịp nhẹ | 40s / 96 BPM |
| music/morning-air.wav | R&B nhẹ: electric piano, guitar clean, fingered bass, hi-hat hơi swing | 32s / 90 BPM |

WAV PCM mono 16-bit 22050 Hz là nguồn loop; bản nghe thử MP3 lặp ba vòng nằm trong gói tải về.
Các kiểm tra tín hiệu không thay thế việc nghe đánh giá âm nhạc. Mức nhạc trong video gợi ý 8–10%, ducking bật.
Generator v3 tái sử dụng renderer v2 qua event factory/instrument programs, không nhân bản synth engine.

## Ảnh là ảnh chụp, không phải ảnh AI

| Ảnh | Nguồn / tác giả | License | Độ phân giải gốc |
| --- | --- | --- | --- |
| Gia vị | Riyaad Minty, Flickr; bản phân phối trong scikit-image tutorials | CC BY 2.0 | 1024×683 |
| Di tích Petra | Francois Malan, dataset Petra 2014 | CC BY 3.0 | 3000×1987 |
| Bells Beach | scikit-image tutorial contributors, repository CC0 | CC0 1.0 | 1280×960 |

Ảnh gốc JPEG được giữ trong originals/. Bản backgrounds/ chỉ đổi container sang PNG,
không thay bố cục/màu, không generative fill, không nâng chi tiết bằng AI. Khi làm video,
renderer crop/fit theo khung; độ nét giới hạn bởi độ phân giải ảnh gốc, không giả là ảnh 4K.

Nguồn giấy phép/credit được tải và lưu trong LICENSE-tutorials.txt, LICENSE-panoramas.txt,
spices_credits.txt và CREDITS.txt. CC BY yêu cầu ghi công; khi dùng trong video, chép credit
tương ứng vào mô tả. App hiển thị credit và có nút tải TXT ở lựa chọn ảnh.

- Gia vị: https://www.flickr.com/photos/riym/3326786046
- Petra: https://github.com/scikit-image/skimage-tutorials/blob/main/images/pano/DFM_4209.jpg
- Bells Beach: https://github.com/scikit-image/skimage-tutorials/blob/main/images/Bells-Beach.jpg

Không tự tải ảnh từ URL bất kỳ hoặc tự đăng YouTube. Giữ v1/v2 ngoài Git để đối chiếu; manifest hiện tại
chọn ảnh v3, nhạc mặc định tắt. ID thư viện cũ là alias tương thích API; nhãn/topic phản ánh nội dung mới.
Task đã pin ảnh/nhạc cũ vẫn giữ file và hash của phiên bản đó.

Tái tạo nhạc:

```bash
python scripts/generate_90s_music.py --soundfont /path/GeneralUser-GS.sf2 --output /tmp/90s-originals
```

GeneralUser GS license được kèm trong SOUNDFONT-LICENSE.txt; soundfont không nằm trong gói tải về.

Các script sinh nhạc đã dừng, được chuyển cùng bản thử vào `/workspace/archive/rejected-study-assets/generators/`; không cài vào runtime mới.
