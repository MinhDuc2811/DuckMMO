"""A separate project space, never an IELTS preset or background job."""

import json

import streamlit as st

from ui.client.api import request

STYLES = {
    "B1": "B1 · Minimal Line Art",
    "B2": "B2 · Colorful Hand-Drawn",
    "B3": "B3 · Retro TV",
    "B4": "B4 · Survival Thriller",
}
DIRECTOR = {
    "A1": "Classic Black & White",
    "A2": "Modern Pop",
    "A3": "Prehistoric Cave",
    "A4": "Cozy Storytelling",
    "A5": "Historical Cartoon",
    "A6": "Amber Noir",
}


def render():
    st.header("Stickman Studio")
    st.caption(
        "Không gian riêng · kaomei/stickman-video-director · dự án và đầu ra tách khỏi IELTS."
    )
    mode = st.radio(
        "Chế độ Stickman", ["Autopilot · Dựng video", "Director · Brief & prompt"], horizontal=True
    )
    if mode.startswith("Director"):
        director()
        return
    with st.expander("Kiểm tra renderer và hướng dẫn"):
        st.write(
            "Cần Node.js ≥20, FFprobe và gói canvas. Nhập lời đọc/hình đã có quyền dùng; "
            "app không tự gọi dịch vụ sinh ảnh hoặc TTS."
        )
        st.code("npm ci --prefix integrations/stickman-video-director --ignore-scripts")
        if st.button("Kiểm tra Stickman runtime"):
            if result := request("GET", "/api/stickman/doctor", timeout=30):
                st.json(result)
    with st.expander("Tạo dự án Stickman", expanded=True):
        with st.form("stickman-create"):
            title = st.text_input("Tên dự án Stickman", max_chars=160)
            style = st.selectbox("Style Stickman", list(STYLES), format_func=STYLES.get)
            ratio = st.selectbox("Tỉ lệ Stickman", ["9:16", "16:9"])
            submit = st.form_submit_button("Tạo dự án riêng")
        if submit:
            if created := request(
                "POST",
                "/api/stickman/projects",
                json={"title": title, "style": style, "ratio": ratio},
            ):
                st.session_state["stickman-project"] = created["id"]
                st.rerun()
    projects = request("GET", "/api/stickman/projects")
    if not projects:
        st.info("Tạo một dự án để bắt đầu. Kho IELTS và tác vụ video hiện có vẫn giữ riêng.")
        return
    names = {p["id"]: p["title"] for p in projects}
    if st.session_state.get("stickman-project") not in names:
        st.session_state["stickman-project"] = next(iter(names))
    selected = st.selectbox(
        "Dự án Stickman", list(names), format_func=names.get, key="stickman-project"
    )
    item = request("GET", f"/api/stickman/projects/{selected}")
    if not item:
        return
    st.caption(f"Phiên bản {item['version']} · {item['state']} · {item['project']['style']}")
    st.caption(
        "Giới hạn local: lời đọc 120 giây, video 720p, 12–30 fps. "
        "Render giữ nguyên tốc độ file lời đọc."
    )
    with st.expander("1. Lời đọc, hình và âm thanh", expanded=True):
        st.caption(
            "Tải file đã chuẩn bị. B2/B3/B4 cần hình/storyboard đúng style; "
            "B4 giữ yêu cầu voice riêng của upstream."
        )
        with st.form(f"stickman-upload-{selected}"):
            asset = st.file_uploader(
                "File nguồn Stickman",
                type=["wav", "mp3", "flac", "ogg", "m4a", "png", "jpg", "jpeg"],
                max_upload_size=20,
            )
            rights = st.text_input("Nguồn và quyền dùng file", max_chars=1000)
            upload = st.form_submit_button("Lưu file vào dự án")
        if upload and asset:
            if request(
                "POST",
                f"/api/stickman/projects/{selected}/assets",
                params={"filename": asset.name, "rights_note": rights},
                content=asset.getvalue(),
                timeout=130,
            ):
                st.rerun()
        for asset in item["assets"]:
            st.code(asset["path"], language=None)
            st.caption(f"{asset['name']} · {asset['kind']} · {asset['rights_note']}")
    audio = {a["path"]: a["name"] for a in item["assets"] if a["kind"] == "audio"}
    if audio and item["project"]["style"] == "B1":
        with st.expander("Tạo timeline B1 minh họa nhanh"):
            st.caption(
                "Một caption trên toàn đoạn audio: chỉ là điểm bắt đầu, "
                "chưa phải căn lời hay storyboard AI."
            )
            with st.form(f"stickman-starter-{selected}"):
                source = st.selectbox("Lời đọc Stickman", list(audio), format_func=audio.get)
                caption = st.text_input("Caption ngắn cho đoạn minh họa", max_chars=58)
                starter = st.form_submit_button("Tạo timeline B1")
            if starter and request(
                "POST",
                f"/api/stickman/projects/{selected}/starter",
                json={
                    "expected_version": item["version"],
                    "audio_path": source,
                    "caption": caption,
                },
            ):
                st.rerun()
    with st.expander("2. Chỉnh storyboard / timeline JSON"):
        st.caption(
            "Sửa timing, captions và các lớp hình theo lời đọc. "
            "Lưu sửa sẽ hủy duyệt preview và ẩn đầu ra cũ."
        )
        with st.form(f"stickman-timeline-{selected}-{item['version']}"):
            raw = st.text_area(
                "Timeline Stickman",
                value=json.dumps(item["project"], ensure_ascii=False, indent=2),
                height=400,
            )
            save = st.form_submit_button("Lưu timeline Stickman")
        if save:
            try:
                data = json.loads(raw)
            except ValueError:
                st.error("Timeline JSON chưa hợp lệ.")
            else:
                if request(
                    "PUT",
                    f"/api/stickman/projects/{selected}",
                    json={"expected_version": item["version"], "project": data},
                ):
                    st.rerun()
    st.subheader("3. Preview → duyệt → xuất MP4")
    seconds = st.number_input("Độ dài preview (giây)", min_value=1, max_value=60, value=20)
    for label, command in [("Kiểm tra timeline", "validate"), ("Dựng preview Stickman", "preview")]:
        if st.button(label, key=f"stickman-{command}"):
            with st.spinner("Đang xử lý Stickman local…"):
                result = request(
                    "POST",
                    f"/api/stickman/projects/{selected}/actions/{command}",
                    json={"expected_version": item["version"], "seconds": seconds},
                    timeout=620,
                )
            if result:
                if command == "preview":
                    st.rerun()
                st.success("Timeline đã qua kiểm tra kỹ thuật; vẫn cần xem và nghe preview.")
    if item.get("preview_version") == item["version"]:
        preview = request(
            "GET", f"/api/stickman/projects/{selected}/artifacts/preview", raw=True, timeout=60
        )
        if preview:
            st.video(preview)
            st.download_button("Tải preview Stickman", preview, file_name="stickman-preview.mp4")
        with st.form(f"stickman-approval-{selected}-{item['version']}"):
            note = st.text_input("Nhận xét sau khi xem và nghe preview", max_chars=1000)
            approve = st.form_submit_button("Duyệt preview Stickman")
        if approve and request(
            "POST",
            f"/api/stickman/projects/{selected}/actions/approve",
            json={
                "expected_version": item["version"],
                "note": note,
                "preview_sha256": item.get("preview_sha256"),
            },
        ):
            st.rerun()
    if st.button("Render MP4 Stickman", disabled=item["state"] != "approved"):
        with st.spinner("Đang render video Stickman…"):
            if request(
                "POST",
                f"/api/stickman/projects/{selected}/actions/render",
                json={"expected_version": item["version"]},
                timeout=620,
            ):
                st.rerun()
    if item.get("film_version") == item["version"]:
        film = request(
            "GET", f"/api/stickman/projects/{selected}/artifacts/film", raw=True, timeout=60
        )
        if film:
            st.video(film)
            st.download_button("Tải MP4 Stickman", film, file_name="stickman-film.mp4")
        subtitles = request(
            "GET", f"/api/stickman/projects/{selected}/artifacts/film-srt", raw=True
        )
        if subtitles:
            st.download_button("Tải phụ đề Stickman", subtitles, file_name="stickman-film.srt")


def director():
    st.write("Director chuẩn bị brief và tài liệu cho trợ lý AI, không giả lập video đã sinh.")
    with st.form("stickman-director"):
        source = st.text_area("Nội dung / ý tưởng Stickman", max_chars=20000, height=180)
        style = st.selectbox(
            "Style Director", list(DIRECTOR), format_func=lambda k: f"{k} · {DIRECTOR[k]}"
        )
        ratio = st.selectbox("Tỉ lệ Director", ["9:16", "16:9"])
        seconds = st.number_input(
            "Thời lượng Director", min_value=10, max_value=300, value=60, step=10
        )
        submit = st.form_submit_button("Chuẩn bị gói Director")
    if submit:
        kit = request(
            "POST",
            "/api/stickman/director-kit",
            raw=True,
            json={"source": source, "style": style, "ratio": ratio, "seconds": seconds},
        )
        if kit:
            st.download_button(
                "Tải brief và tài liệu Director", kit, file_name="stickman-director-kit.zip"
            )
