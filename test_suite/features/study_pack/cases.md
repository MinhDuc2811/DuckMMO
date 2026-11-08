# Study pack — coverage

| Case | Layer | Test |
| --- | --- | --- |
| WAV không clipping, đủ thời lượng và boundary không có spike bất thường | unit | test_assets.py::test_instrumentals_have_headroom_and_no_exceptional_loop_jump |
| IDs có allowlist, nguồn ảnh loại trừ nhau | unit | test_assets.py::test_render_rejects_ambiguous_backgrounds_and_unlisted_ids |
| File bị thay đổi phải reject | unit | test_assets.py::test_changed_bundled_file_is_rejected |
| Catalog, PNG/WAV download, unknown ID, pin digest/duration | api | test_library.py::test_catalog_downloads_and_pinning |
| API thư viện giữ authentication hiện hữu | api | test_library.py::test_library_downloads_require_existing_api_auth |
| Background + nhạc bundle qua encoder/mixer thật | integration | test_render.py |
| Browser chọn ảnh/nhạc có sẵn, cấu hình tới queue thật | e2e | test_select.py |

Audio integration dùng speech PCM fixture, không mock bundle/encoder/mixer. E2E dừng worker
trước TTS; không khẳng định đã nghe giọng thật. Chất lượng nghe nhạc chủ quan cần người dùng nghe.
Screen_flow chưa thêm case riêng; các UI controls được kiểm tra bằng browser thật và regression
presentation/lesson-card đã có, không thêm test giả để lấp thư mục.
