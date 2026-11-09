"""Present the exact rendered artifact's quality evidence, including explicit limitations."""

import json

import streamlit as st

LABELS = {
    "output_streams": "Kích thước và thời lượng hình/tiếng",
    "output_full_decode": "Giải mã toàn bộ video",
    "output_audio_signal": "Tín hiệu âm thanh",
    "output_loudness": "Âm lượng tổng thể",
    "output_audio_peak": "Đỉnh âm thanh",
    "output_silence": "Khoảng im lặng",
    "black_frames": "Đoạn hình đen",
}


def output_quality_panel(meta):
    report = meta.get("quality", {}).get("output")
    if not report or report.get("sha256") != meta.get("sha256"):
        st.info("Video này chưa có báo cáo kiểm tra FFmpeg mới; dựng lại để kiểm tra.")
        return
    if report["status"] == "pass":
        st.success("FFmpeg: Đạt kiểm tra kỹ thuật đầu ra")
    elif report["status"] == "warn":
        st.warning("FFmpeg: Có cảnh báo cần xem/nghe lại trước khi duyệt")
    else:
        st.error("FFmpeg: Video không đạt kiểm tra kỹ thuật")
    with st.expander("Chi tiết kiểm tra chất lượng đầu ra"):
        for item in report["evaluations"]:
            icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}[item["outcome"]]
            st.write(f"{icon} {LABELS.get(item['dimension'], item['dimension'])}")
            st.json(item["evidence"], expanded=False)
        for limitation in report["limitations"]:
            st.caption(limitation)
    st.caption("Phát âm và nội dung bài học vẫn cần người duyệt.")
    st.download_button(
        "Tải báo cáo chất lượng JSON",
        json.dumps(report, ensure_ascii=False, indent=2),
        file_name="output-quality.json",
        mime="application/json",
        key=f"output-quality-{meta['sha256']}",
    )
