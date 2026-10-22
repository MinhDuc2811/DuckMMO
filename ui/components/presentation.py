"""Presentation controls share the API catalog and never import backend code."""

import streamlit as st


def _select_style(key, preset):
    st.session_state[key] = preset


def visual_controls(request, job_id, saved):
    catalog = request("GET", "/api/production/catalog") or {"presets": [], "tracks": []}
    names = {"auto": "Tự động chọn", **{p["id"]: p["name"] for p in catalog["presets"]}}
    options = saved.get("visual", {})
    st.markdown("### 1. Chọn phong cách")
    st.caption("Mọi phong cách đều dùng được cho nội dung của bạn.")
    with st.expander("Khám phá các phong cách", expanded=True):
        columns = st.columns(3)
        descriptions = {
            "collage": "Ảnh xếp lớp, chuyển động nhẹ như tạp chí",
            "panels": "Chia khung hình thành nhiều ô sinh động",
            "quote": "Gọn gàng, tập trung vào câu chữ",
            "full": "Hình toàn màn hình, chữ lớn nổi bật",
        }
        for index, item in enumerate(catalog["presets"]):
            with columns[index % 3].container(border=True):
                st.markdown(f"**{item['name']}**")
                st.caption(descriptions.get(item.get("layout"), ""))
                st.button(
                    f"Dùng {item['name']}",
                    key=f"choose-{job_id}-{item['id']}",
                    on_click=_select_style,
                    args=(f"style-preset-{job_id}", item["id"]),
                )
    preset = st.selectbox(
        "Phong cách",
        list(names),
        format_func=names.get,
        index=list(names).index(options.get("preset")) if options.get("preset") in names else 0,
        key=f"style-preset-{job_id}",
    )
    st.caption("Bấm “Xem mẫu style” để xem chuyển động trước khi lựa chọn.")
    with st.expander("Tùy chỉnh thêm · bố cục, chuyển động và màu sắc"):
        st.caption("Bạn có thể giữ nguyên các thiết lập này để bắt đầu.")
        layouts = {
            "preset": "Theo phong cách đã chọn",
            "mix": "Phối nhiều bố cục",
            "full": "Toàn màn hình",
            "collage": "Ảnh xếp lớp",
            "panels": "Chia nhiều ô",
            "quote": "Tập trung vào câu chữ",
        }
        layout = st.selectbox(
            "Bố cục",
            list(layouts),
            format_func=layouts.get,
            index=list(layouts).index(options.get("layout", "preset")),
        )
        intensities = {"gentle": "Nhẹ", "medium": "Vừa", "strong": "Mạnh"}
        intensity = st.select_slider(
            "Mức chuyển động",
            list(intensities),
            value=options.get("intensity", "medium"),
            format_func=intensities.get,
        )
        transitions = {"cut": "Cắt", "fade": "Hòa tan", "slide": "Trượt"}
        transition = st.selectbox(
            "Chuyển cảnh",
            list(transitions),
            format_func=transitions.get,
            index=list(transitions).index(options.get("transition", "fade")),
            key=f"transition-{job_id}",
        )
        custom = st.checkbox("Đổi màu nhấn", value=bool(options.get("accent")))
        accent = st.color_picker("Màu nhấn", options.get("accent") or "#ffb454") if custom else None
        seed = int(
            st.number_input(
                "Biến thể bố cục",
                min_value=0,
                max_value=2147483647,
                value=options.get("seed", 0),
                step=1,
            )
        )
    visual = dict(
        preset=preset,
        layout=layout,
        intensity=intensity,
        transition=transition,
        accent=accent,
        seed=seed,
    )
    if preset != "auto" and st.button("Xem mẫu style", key=f"preview-style-{job_id}"):
        preview = request("POST", "/api/production/style-preview", raw=True, json=visual)
        if preview:
            st.image(preview, caption="Mẫu minh họa chuyển động; chưa phải preview toàn video.")
    if preset == "auto":
        st.caption(
            "Hệ thống sẽ chọn cách trình bày mặc định. Chọn một phong cách để tự chỉnh chuyển động."
        )
    return visual, catalog


def music_controls(catalog, assets, saved, job_id):
    st.markdown("### 2. Thêm nhạc nền")
    st.caption("Không bắt buộc. Giọng đọc luôn được giữ riêng với nhạc nền.")
    old = saved.get("music", {})
    sources = {"off": "Không dùng", "library": "Nhạc có sẵn", "upload": "File của bạn"}
    default = "library" if old.get("track") else "upload" if old.get("asset_id") else "off"
    mode = st.radio(
        "Nguồn nhạc nền",
        list(sources),
        format_func=sources.get,
        index=list(sources).index(default),
        horizontal=True,
        key=f"music-mode-{job_id}",
    )
    track, asset_id, uploaded = None, None, None
    if mode == "library":
        tracks = {t["id"]: t["name"] for t in catalog["tracks"]}
        if tracks:
            track = st.selectbox(
                "Bản nhạc",
                list(tracks),
                format_func=tracks.get,
                index=list(tracks).index(old.get("track") or "ambient"),
            )
        st.caption("Hai bản nền đơn giản có sẵn miễn phí. Bạn cũng có thể tải nhạc của mình lên.")
    elif mode == "upload":
        available = {
            a["id"]: f"{a['id'][:8]} · {a['duration']:.1f} giây"
            for a in assets
            if a["kind"] == "audio"
        }
        choices = [None, *available]
        asset_id = st.selectbox(
            "Nhạc đã tải",
            choices,
            index=choices.index(old.get("asset_id")) if old.get("asset_id") in choices else 0,
            format_func=lambda v: available.get(v, "Chọn file mới"),
        )
        uploaded = st.file_uploader(
            "Upload nhạc nền",
            type=["wav", "mp3", "flac", "ogg", "m4a"],
            max_upload_size=20,
            key=f"music-upload-{job_id}",
        )
        st.caption("Tối đa 20 MB, 10 phút. Chỉ dùng nhạc bạn có quyền sử dụng.")
    if mode == "off":
        st.caption("Video sẽ chỉ có giọng đọc, không có nhạc nền.")
    volume = st.slider(
        "Âm lượng nhạc (%)",
        0,
        50,
        round(old.get("volume", 0.16) * 100),
        disabled=mode == "off",
        key=f"music-volume-{job_id}",
        help="Bắt đầu khoảng 10–20% để nhạc không lấn giọng đọc.",
    )
    ducking = st.checkbox(
        "Tự giảm nhạc khi có lời",
        value=old.get("ducking", True),
        disabled=mode == "off",
        key=f"music-ducking-{job_id}",
        help="Nhạc nhỏ xuống khi có người đọc và tăng lại ở khoảng nghỉ.",
    )
    with st.expander("Chọn đoạn nhạc bắt đầu"):
        offset = st.number_input(
            "Bắt đầu nhạc tại giây",
            min_value=0.0,
            max_value=600.0,
            value=float(old.get("start_seconds", 0)),
            step=1.0,
            disabled=mode == "off",
            key=f"music-offset-{job_id}",
            help="0 là đầu bài. Hai bản nhạc có sẵn dài 8 giây và sẽ tự lặp.",
        )

    return (
        dict(
            track=track,
            asset_id=asset_id,
            volume=volume / 100,
            ducking=ducking,
            start_seconds=offset,
        ),
        uploaded,
        mode,
    )
