# Crawler: nguyên nhân và xác minh sửa lỗi

## Kết quả điều tra code

- Trước sửa, `SUPPORTED_HOSTS` từ chối mọi host ngoài một website. Đây là lỗi chủ động
  trong validation, không phải các website khác đều hỏng.
- Parser XPath `vungdoc/truyen` chỉ dành riêng một layout. Bộ extractor chung Trafilatura
  đã có nhưng chỉ được dùng làm fallback, trong khi allowlist chặn các host khác trước đó.
- HTTP request mặc định từng nhận 403; cùng URL với headers trình duyệt nhận 200.
  Đây là bằng chứng về cách server phản hồi request trong lần kiểm tra, không chứng minh
  mọi lỗi 403 đều do User-Agent hay mọi website đều hỗ trợ HTTP crawler.
- Crawl4AI không có trong dependency hoặc đường thực thi; không có cơ sở nói đã debug
  một integration Crawl4AI sẵn có. Integration cũ là HTTPX.
- UI fetch nguồn trong Phase 2; worker chỉ chạy preflight đếm từ. Không có AI analysis.

## Đường thực thi sau sửa

Phase 1 nhận nhiều URL → queued → worker fetch/extract → commit source_documents →
AI analysis theo model/provider cấu hình → validate output → awaiting_review.
Phase 2 chỉ đọc/chỉnh sửa/duyệt/tải kết quả. Crawl/analysis lỗi không lọt vào Phase 2.
Lỗi được phân biệt validate_url, dns, http_status, redirect, timeout, content_type,
size, extract, network và analysis. Không log API key hoặc toàn bộ nội dung nguồn.

## Xác minh

Đã chạy cùng crawler/parser chung, không selector riêng, trên ba website:

| Nguồn | Kết quả văn bản |
| --- | --- |
| metruyenchu.com.vn/hoa-son-tai-khoi/chuong-80-LQ_6GUMpZ0Bv | 13.295 ký tự |
| docs.python.org/3/tutorial/introduction.html | 16.645 ký tự |
| trafilatura.readthedocs.io/en/latest/quickstart.html | 3.819 ký tự |

Test tự động bao gồm redirect khác host, redirect về mạng nội bộ, DNS nội bộ,
403, content-type sai, HTML rỗng/JS shell, nhiều nguồn, analysis lỗi, retry dùng nguồn
đã lưu, gating API/UI và kiểm duyệt sau Phase 1.

AI provider tests dùng response giả có kiểm tra schema; chưa gọi provider thực tế vì
workspace chưa cấu hình endpoint/model/key. Không coi test giả là kết quả AI thực tế.
JavaScript-rendered sites, login và CAPTCHA chưa hỗ trợ; không cam kết đọc được mọi website.
