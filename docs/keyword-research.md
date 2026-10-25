# Nghiên cứu từ keyword

Phase 1 có luồng **Tạo nội dung từ keyword** bên cạnh URL và nhập tay.

1. Trong **Nguồn nghiên cứu mặc định theo chủ đề**, lưu nhánh `research`, đường dẫn `news/esport/fifa-online` và URL trang cập nhật chính thức. Không điền sẵn một URL giả hoặc suy đoán trang chính thức.
2. Chọn lần lượt các cấp chủ đề, nhập yêu cầu như “Tổng hợp những thay đổi quan trọng của FC Online”, chọn ngày cần nghiên cứu và bấm **Tìm nguồn và tổng hợp**. Có thể ghi đè website cho riêng lần này.
3. Worker tìm liên kết bài viết liên quan trên website mặc định, bổ sung tìm kiếm `site:` và tìm thêm trên web nếu được bật. Tắt tìm web thì chỉ truy cập website ưu tiên, không gọi search provider. Tối đa 10 nguồn; URL trùng và địa chỉ nội bộ bị loại. Website yêu cầu JavaScript/đăng nhập/CAPTCHA có thể không crawl được.
4. Worker lưu danh sách URL và nội dung nguồn trước khi gọi AI. Một số nguồn crawl lỗi được báo rõ; không có nguồn đọc được thì job thất bại. Retry AI dùng lại dữ liệu đã lưu, không âm thầm đổi nguồn.
5. Phase 2 hiển thị bản thảo có dẫn nguồn `[1]`, `[2]` và danh sách bài gốc, kèm cảnh báo tìm/crawl thiếu nguồn. Người dùng đọc, sửa và duyệt như trước. Dẫn nguồn hợp lệ về chỉ số không chứng minh mọi nhận định đúng; vẫn cần fact-check.

## Tìm kiếm và AI

Mặc định `STUDIO_SEARCH_PROVIDER=duckduckgo` dùng trang HTML công khai, không cần key; có thể bị rate limit hoặc CAPTCHA. Đây không phải Google.

Để chọn Google Programmable Search, cấu hình local `.env`:

```dotenv
STUDIO_SEARCH_PROVIDER=google
STUDIO_GOOGLE_SEARCH_ENGINE_ID=your-search-engine-id
STUDIO_GOOGLE_SEARCH_API_KEY=your-key
```

Google cần tài khoản/API tương ứng và chịu chính sách/quota của nhà cung cấp; không mặc định coi đây là dịch vụ miễn phí hoặc khả dụng cho mọi tài khoản. Không scrape Google HTML và không vượt CAPTCHA. Chọn search provider sai, thiếu cấu hình hoặc không có nguồn sẽ báo lỗi thật.

AI vẫn dùng **Kết nối AI** hiện có. Khi thiếu kết nối, job giữ nguồn đã lấy và báo lỗi để cấu hình rồi retry; không giả lập kết quả tổng hợp. Search và AI cần mạng khả dụng trên máy chạy worker.

Ngày yêu cầu được gửi vào truy vấn và prompt, nhưng không tự chứng minh ngày đăng bài hoặc ngày sự kiện. Crawler lưu `published_at` từ metadata ngày xuất bản mà website khai báo và `retrieved_at` từ thời điểm lấy dữ liệu. Không thay ngày xuất bản bằng ngày sửa bài hoặc ngày crawl. Khi thiếu metadata hỗ trợ, ngày đăng được đánh dấu chưa xác định. Phase 2 cảnh báo nguồn khác ngày yêu cầu hoặc chưa xác định ngày; AI cũng nhận các cảnh báo này. Metadata do website khai báo chưa được xác minh độc lập. Prompt yêu cầu AI phân biệt các ngày, không tự gọi nội dung cũ là cập nhật mới, và nêu thiếu bằng chứng. Phiên bản này chưa lọc cứng ngày xuất bản hay xác minh độc lập mọi nhận định.

## Lưu trữ và API

Cấu hình chủ đề lưu tại `data/settings/research.json` (theo thư mục cha của `STUDIO_ARTIFACT_DIR`). `GET/PUT /api/settings/research` đọc/ghi danh sách profile; PUT thay cả danh sách, UI giữ lại các profile khác. Các endpoint dùng bảo vệ API hiện có. Không thay schema SQL: request, provenance và snapshot nằm trong JSON ContentPackage.

`POST /api/import/keyword` nhận `keyword`, `branch`, `language`, `topic_path`, `target_date` (YYYY-MM-DD), `preferred_url` tùy chọn, `search_web`, `max_sources`. Website mặc định được chốt vào job khi submit; đổi cấu hình sau đó không làm đổi job cũ. `GET /api/jobs/{id}` trả `package.research`, `package.discovery` và `source_documents` để truy vết.

## Kiểm tra

```bash
uv run pytest --feature keyword_research -q
uv run playwright install chromium
uv run pytest --feature keyword_research --test-layer e2e --browser chromium -q
```

Test offline dùng search/crawl/AI fixture; browser kiểm tra nhập liệu, lưu nguồn mặc định và tạo job thật, không gọi search/AI ngoài Internet.
