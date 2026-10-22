import hashlib
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import streamlit as st
from dotenv import load_dotenv

# Streamlit executes this file with ui/ on sys.path when launched from its CLI.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.ai_connection import load_connection, save_connection  # noqa: E402
from ui.media_inputs import upload_media  # noqa: E402

load_dotenv()
st.set_page_config(page_title="AI Content Studio", page_icon="🦆", layout="wide")
API_URL = os.getenv("STUDIO_API_URL", "http://127.0.0.1:8000").rstrip("/")
HEADERS = {"X-API-Key": os.getenv("STUDIO_API_KEY", "")}


def request(method, path, extra_headers=None, **kwargs):
    try:
        response = httpx.request(
            method,
            f"{API_URL}{path}",
            headers={**HEADERS, **(extra_headers or {})},
            timeout=kwargs.pop("timeout", 15),
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        st.error(
            detail
            if isinstance(detail, str)
            else "Chưa xử lý được yêu cầu. Kiểm tra nội dung nhập."
        )
    except httpx.RequestError:
        st.error("Không kết nối được API. Hãy chạy migration và khởi động FastAPI.")
    return None


def select_workspace(job_id, status, phase="content"):
    st.session_state["pending_workspace"] = (job_id, status, phase)


if pending := st.session_state.pop("pending_workspace", None):
    st.session_state["workspace_selection"] = pending[0]
    st.session_state["selected_content"] = pending[0]
    st.session_state["selected_render_job"] = pending[0]
    st.session_state["selected_video_job"] = pending[0]
    phase = pending[2] if len(pending) > 2 else "content"
    st.session_state["workflow_phase"] = (
        "Phase 3 · Sản xuất video"
        if phase == "production"
        else "Phase 4 · Duyệt video"
        if phase == "video_review"
        else "Phase 2 · Kiểm duyệt"
        if phase == "content_review" or pending[1] in ("awaiting_review", "approved", "rejected")
        else "Phase 1 · Nguồn & phân tích"
    )

if deleted := st.session_state.pop("pending_delete", None):
    if st.session_state.get("workspace_selection") == deleted:
        st.session_state.pop("workspace_selection", None)
        st.session_state.pop("selected_content", None)
        st.session_state["workflow_phase"] = "Phase 1 · Nguồn & phân tích"


st.title("🦆 AI Content Studio")
st.caption("Soạn, chỉnh sửa và tải nội dung video")
if notice := st.session_state.pop("submission_notice", None):
    st.success(notice)


@st.fragment(run_every="2s")
def render_workspace():
    st.header("Workspace")
    if st.button("＋ Nội dung mới", use_container_width=True):
        st.session_state.pop("workspace_selection", None)
        st.session_state["workflow_phase"] = "Phase 1 · Nguồn & phân tích"
        st.rerun()
    if deleted_id := st.session_state.get("last_deleted"):
        st.caption("Đã xóa khỏi Workspace.")
        if st.button("Hoàn tác xóa", use_container_width=True):
            if request("POST", f"/api/jobs/{deleted_id}/restore"):
                st.session_state.pop("last_deleted", None)
                st.rerun()
    items = request("GET", "/api/workspace/jobs")
    if items is None:
        return
    active_statuses = ("queued", "running", "cancelling")
    active = [j for j in items if j["status"] in active_statuses]
    recent = [j for j in items if j["status"] not in active_statuses]
    labels = {
        "queued": "Chờ xử lý",
        "running": "Đang xử lý",
        "cancelling": "Đang dừng…",
        "cancelled": "Đã dừng",
        "failed": "Gặp lỗi",
        "awaiting_review": "Chờ kiểm duyệt",
        "approved": "Đã duyệt",
        "rejected": "Đã từ chối",
        "awaiting_video_review": "Video chờ duyệt",
        "video_approved": "Video đã duyệt",
        "video_rejected": "Video cần chỉnh sửa",
    }
    st.caption(f"{len(active)} tác vụ đang hoạt động · Tự cập nhật")
    if not active:
        st.info("Không có tác vụ đang chạy.")
    for item in active:
        with st.container(border=True, key=f"workspace-job-{item['id']}"):
            if st.button(
                item["title"],
                key=f"open-{item['id']}",
                on_click=select_workspace,
                args=(item["id"], item["status"], item.get("phase", "content")),
                use_container_width=True,
            ):
                st.rerun()
            st.caption(f"{item['branch'].upper()} · {labels[item['status']]}")
            stage = item["stage"]
            if "Voice and visuals" in stage:
                st.caption("Tạo giọng đọc và hình ảnh: " + stage.rsplit(" ", 1)[-1])
            elif "Encoding MP4" in stage:
                st.caption("Đang dựng video MP4")
            elif "Checking video" in stage:
                st.caption("Kiểm tra video và âm thanh")
            elif item.get("phase") == "production":
                st.caption("Chuẩn bị video")
            elif "Analysis started" in stage:
                st.caption("Đang phân tích nội dung")
            elif "Crawl completed" in stage:
                st.caption("Đã lấy dữ liệu nguồn")
            elif item["status"] == "running":
                st.caption("Đang lấy dữ liệu và xử lý nguồn")
            if st.button(
                "Dừng tác vụ",
                key=f"stop-{item['id']}",
                disabled=item["status"] == "cancelling",
                use_container_width=True,
            ):
                if request("POST", f"/api/jobs/{item['id']}/cancel"):
                    st.rerun()
            st.button(
                "Xóa",
                key=f"delete-{item['id']}",
                disabled=True,
                help="Dừng tác vụ trước khi xóa.",
                use_container_width=True,
            )
    with st.expander(f"Gần đây ({len(recent)})", expanded=True):
        for item in recent:
            with st.container(border=True, key=f"workspace-job-{item['id']}"):
                if st.button(
                    item["title"],
                    key=f"open-{item['id']}",
                    on_click=select_workspace,
                    args=(item["id"], item["status"], item.get("phase", "content")),
                    use_container_width=True,
                ):
                    st.rerun()
                st.caption(labels.get(item["status"], item["status"]))
                if item["error"]:
                    st.caption(item["error"])
                if st.button("Xóa", key=f"delete-{item['id']}", use_container_width=True):
                    if request("DELETE", f"/api/jobs/{item['id']}"):
                        st.session_state["last_deleted"] = item["id"]
                        st.session_state["pending_delete"] = item["id"]
                        st.rerun()
    if st.button("Làm mới Workspace", use_container_width=True):
        st.rerun()


@st.fragment(run_every="2s")
def render_production_progress(job_id):
    job = request("GET", f"/api/jobs/{job_id}")
    if not job:
        return
    if job["status"] not in ("queued", "running", "cancelling"):
        st.rerun()
    items = request("GET", "/api/workspace/jobs") or []
    stage = next((item["stage"] for item in items if item["id"] == job_id), "")
    count = re.search(r"Voice and visuals (\d+)/(\d+)", stage)
    if count:
        current, total = map(int, count.groups())
        st.progress(current / total, text=f"Tạo giọng đọc và hình ảnh: {current}/{total} đoạn")
    elif "Encoding MP4" in stage:
        st.info("Đang xuất file MP4. Kịch bản dài có thể cần vài phút.")
    elif "Checking video" in stage:
        st.info("Đang kiểm tra hình ảnh và âm thanh của video.")
    elif "Combining narration" in stage:
        st.info("Đang ghép giọng đọc.")
    else:
        st.info(
            "Đang dừng video…" if job["status"] == "cancelling" else "Đang chuẩn bị dựng video…"
        )
    st.caption("Tiến trình tự cập nhật. Bạn có thể dừng tác vụ trong Workspace bên trái.")


def stage_label(message):
    labels = {
        "Video production started": "Bắt đầu dựng video",
        "Combining narration": "Ghép giọng đọc",
        "Encoding MP4": "Xuất file MP4",
        "Checking video and audio": "Kiểm tra hình và tiếng",
        "Video ready for final review": "Video đã sẵn sàng để duyệt",
        "Phase 1 started": "Bắt đầu lấy dữ liệu nguồn",
        "Analysis started": "Phân tích nội dung",
        "Phase 1 complete; ready for Phase 2 review": "Nội dung sẵn sàng để duyệt",
    }
    if count := re.fullmatch(r"Voice and visuals (\d+)/(\d+)", message):
        return f"Tạo giọng đọc và hình ảnh: {count[1]}/{count[2]} đoạn"
    if message.startswith("Auto style:"):
        return message.replace("Auto style:", "Đã tự chọn style:", 1)
    return labels.get(message, message)


@st.fragment(run_every="2s")
def render_activity_log():
    st.subheader("Theo dõi tác vụ")
    job_id = st.session_state.get("workspace_selection")
    if not job_id:
        st.info("Chọn một nội dung trong Workspace để xem tiến trình và log.")
        return
    job = request("GET", f"/api/jobs/{job_id}")
    events = request("GET", f"/api/jobs/{job_id}/events")
    if not job or events is None:
        return
    st.caption(job["package"]["title"])
    progress_tab, log_tab, quality_tab, learning_tab = st.tabs(
        ["Tiến trình", "Log", "Chất lượng", "Cải thiện"]
    )
    with progress_tab:
        latest = events[-1]["message"] if events else "Chờ xử lý"
        st.write(stage_label(latest))
        if job.get("error"):
            st.error(job["error"])
        elif job["status"] in ("cancelled", "cancelling"):
            st.warning("Đã dừng tác vụ" if job["status"] == "cancelled" else "Đang dừng…")
        if job.get("render_config"):
            starts = [
                i
                for i, event in enumerate(events)
                if event["message"] == "Video production started"
            ]
            run = events[starts[-1] :] if starts else []
            messages = [event["message"] for event in run]
            done = bool(job.get("video"))
            stages = [
                ("Tạo giọng đọc và hình ảnh", "Voice and visuals"),
                ("Ghép giọng đọc", "Combining narration"),
                ("Xuất MP4", "Encoding MP4"),
                ("Kiểm tra hình và tiếng", "Checking video and audio"),
            ]
            current = max(
                (i for i, (_, token) in enumerate(stages) if any(token in m for m in messages)),
                default=-1,
            )
            for i, (label, _) in enumerate(stages):
                icon = "✅" if done or i < current else "⏳" if i == current else "○"
                st.write(f"{icon} {i + 1}. {label}")
            counts = [re.fullmatch(r"Voice and visuals (\d+)/(\d+)", m) for m in messages]
            counts = [c for c in counts if c]
            if counts:
                count = counts[-1]
                st.progress(
                    int(count[1]) / int(count[2]),
                    text=f"Giọng đọc và hình ảnh: {count[1]}/{count[2]} đoạn",
                )
            if done:
                st.success("Hoàn tất · Video sẵn sàng")
                if st.button("Xem video", key="activity-open-video", use_container_width=True):
                    select_workspace(job_id, job["status"], "video_review")
                    st.rerun()
        st.caption("Tự cập nhật mỗi 2 giây. Các bước xuất và kiểm tra hiển thị trạng thái thực tế.")
    with log_tab:
        st.caption(f"{len(events)} sự kiện · Mới nhất ở trên · Giờ Việt Nam")
        lines = []
        for event in reversed(events):
            timestamp = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            local = timestamp.astimezone(timezone(timedelta(hours=7)))
            lines.append(f"{local:%H:%M:%S} [{event['status']}] {stage_label(event['message'])}")
        with st.container(height=540):
            st.code("\n".join(lines) or "Chưa có sự kiện", language=None, wrap_lines=True)
        st.download_button(
            "Tải log",
            "\n".join(lines),
            file_name=f"log-{job_id[:8]}.txt",
            mime="text/plain",
            key=f"log-download-{job_id}",
        )

    with quality_tab:
        quality = request("GET", f"/api/jobs/{job_id}/quality")
        if quality:
            current = [e for e in quality["evaluations"] if e["current"]]
            st.caption(f"{len(quality['runs'])} lượt xử lý · {len(current)} kiểm tra hiện tại")
            if not current:
                st.info("Chưa có đánh giá cho phiên bản này. Job cũ không được gán điểm hồi tố.")
            for item in current:
                icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "unknown": "○"}[item["outcome"]]
                with st.expander(f"{icon} {item['dimension']}"):
                    st.json(item["evidence"])
            with st.expander("Lịch sử từng bước"):
                st.dataframe(
                    [
                        {"Bước": r["step"], "Trạng thái": r["state"], "Hiện tại": r["current"]}
                        for r in quality["runs"]
                    ],
                    hide_index=True,
                )
            st.caption("Độ đúng sự thật, phát âm và khớp từng từ vẫn cần người duyệt.")
    with learning_tab:
        experiments = request("GET", "/api/learning/experiments") or []
        if not experiments:
            st.info("Chưa có thử nghiệm. Gắn nhãn lỗi phụ đề khi duyệt video để tạo candidate.")
        for experiment in experiments[:5]:
            report = experiment["report"]
            with st.expander(f"{experiment['state']} · {experiment['id'][:8]}"):
                st.write(
                    f"Điểm bố cục: {report['baseline']['score']:.1f} → "
                    f"{report['candidate']['score']:.1f}"
                )
                st.caption(
                    f"{report['supporting_jobs']}/{report['required_jobs']} job phản hồi độc lập"
                )
                st.write(report["reason"])
                st.caption(
                    "Benchmark bố cục offline; chưa chứng minh tăng chất lượng "
                    "nội dung hay lượt xem."
                )
                if st.button("Chạy benchmark lại", key=f"benchmark-{experiment['id']}"):
                    if request("POST", f"/api/learning/experiments/{experiment['id']}/benchmark"):
                        st.rerun()
                if experiment["state"] == "eligible" and st.button(
                    "Áp dụng cho video mới", key=f"promote-{experiment['id']}"
                ):
                    if request("POST", f"/api/learning/experiments/{experiment['id']}/promote"):
                        st.rerun()
                if experiment["state"] in ("canary", "promoted") and st.button(
                    "Quay về style mặc định", key=f"rollback-{experiment['id']}"
                ):
                    if request(
                        "POST", f"/api/learning/configs/{experiment['candidate_id']}/rollback"
                    ):
                        st.rerun()


with st.sidebar:
    with st.container(key="workspace-panel"):
        render_workspace()

opened = None
if selection := st.session_state.get("workspace_selection"):
    opened = request("GET", f"/api/jobs/{selection}")
    if opened:
        st.subheader(opened["package"]["title"])

main_column, activity_column = st.columns([3, 1.25], gap="large")
with activity_column:
    with st.container(border=True, key="activity-panel"):
        render_activity_log()

with main_column:
    create_tab, jobs_tab, production_tab, video_tab, youtube_tab = st.tabs(
        [
            "Phase 1 · Nguồn & phân tích",
            "Phase 2 · Kiểm duyệt",
            "Phase 3 · Sản xuất video",
            "Phase 4 · Duyệt video",
            "Phase 5 · YouTube",
        ],
        key="workflow_phase",
        on_change="rerun",
    )
    with create_tab:
        st.subheader("Lấy dữ liệu từ nguồn")
        try:
            connection = load_connection()
        except (ValueError, OSError):
            connection = None
        with st.expander("Kết nối AI", expanded=connection is None):
            if connection:
                st.caption(f"Đã cấu hình model: {connection.model}")
            else:
                st.warning("Chưa kết nối AI. Cấu hình một lần để phân tích các nguồn web.")
            with st.form("ai-connection"):
                ai_url = st.text_input(
                    "URL API AI",
                    value=connection.base_url if connection else "",
                    placeholder="https://your-provider.example/v1",
                )
                ai_model = st.text_input("Model AI", value=connection.model if connection else "")
                ai_key = st.text_input(
                    "API key AI", type="password", help="Để trống để giữ key đã lưu."
                )
                st.caption("Key được lưu cục bộ trên máy chạy DuckMMO. Không cần gửi key vào chat.")
                save_ai = st.form_submit_button("Lưu kết nối AI")
            if save_ai:
                secret = ai_key or (connection.api_key.get_secret_value() if connection else "")
                try:
                    save_connection(
                        ai_url,
                        ai_model,
                        secret,
                        structured_output=connection.structured_output if connection else False,
                        timeout_seconds=connection.timeout_seconds if connection else 120,
                    )
                except (ValueError, OSError):
                    st.error("Chưa lưu được. Kiểm tra URL HTTP/HTTPS, tên model và API key.")
                else:
                    st.session_state["submission_notice"] = (
                        "Đã lưu kết nối AI. Bấm Thử lại ở tác vụ lỗi để tiếp tục phân tích."
                    )
                    st.rerun()
        with st.form("phase1-web"):
            website_urls = st.text_area(
                "Link nguồn (mỗi dòng một URL)", placeholder="https://website.com/bai-viet"
            )
            source_branch = st.selectbox("Loại nội dung", ["novel", "comic", "research"])
            fetch = st.form_submit_button("Bắt đầu Phase 1", type="primary")
        if fetch:
            urls = list(
                dict.fromkeys(line.strip() for line in website_urls.splitlines() if line.strip())
            )
            if not urls:
                st.error("Nhập ít nhất một link nguồn.")
            elif len(urls) > 10:
                st.error("Mỗi nội dung tối đa 10 link nguồn.")
            else:
                imported = request(
                    "POST", "/api/import/web", json={"urls": urls, "branch": source_branch}
                )
                if imported:
                    st.session_state["submission_notice"] = (
                        "Đã nhận nguồn. Đang chờ lấy dữ liệu và phân tích ở Phase 1."
                    )
                    select_workspace(imported["id"], imported["status"])
                    st.rerun()
        st.caption(
            "Nguồn được lấy trước rồi phân tích AI. "
            "Chỉ nội dung phân tích thành công mới sang Phase 2."
        )
        with st.expander("Hoặc nhập nội dung thủ công"):
            st.subheader("Nội dung đầu vào")
            st.write("Nhập kịch bản đã chuẩn bị. Bước này kiểm tra cấu trúc, không tự sinh recap.")
            with st.form("package"):
                left, right = st.columns(2)
                branch = left.selectbox("Nhánh", ["novel", "comic", "research"])
                language = right.selectbox("Ngôn ngữ", ["vi", "en", "zh", "ja", "ko"])
                title = st.text_input("Tiêu đề", max_chars=200)
                source = st.text_input("Tên nguồn", max_chars=300)
                source_url = st.text_input("URL nguồn (không bắt buộc)")
                rights = st.text_area("Ghi chú quyền sử dụng / giấy phép", max_chars=2000)
                narration = st.text_area(
                    "Lời dẫn (mỗi đoạn cách nhau một dòng trống là một cảnh)", height=220
                )
                visual = st.text_input("Gợi ý hình ảnh cho các cảnh", max_chars=2000)
                submit = st.form_submit_button("Đưa vào hàng đợi", type="primary")
            if submit:
                paragraphs = [p.strip() for p in narration.split("\n\n") if p.strip()]
                if not all([title.strip(), source.strip(), rights.strip(), paragraphs]):
                    st.error("Điền tiêu đề, tên nguồn, quyền sử dụng và lời dẫn.")
                else:
                    package = {
                        "schema_version": "1.0",
                        "branch": branch,
                        "title": title,
                        "language": language,
                        "sources": [
                            {"label": source, "url": source_url or None, "rights_note": rights}
                        ],
                        "scenes": [
                            {"narration": p, "visual_note": visual, "source_indices": [0]}
                            for p in paragraphs
                        ],
                    }
                    if "submission_key" not in st.session_state:
                        st.session_state.submission_key = str(uuid4())
                    # Keep the key on transport failure so resubmission cannot duplicate the job.
                    payload_signature = repr(package)
                    if st.session_state.get("submission_payload") != payload_signature:
                        st.session_state.submission_key = str(uuid4())
                    st.session_state.submission_payload = payload_signature
                    result = request(
                        "POST",
                        "/api/jobs",
                        json={"package": package},
                        extra_headers={"Idempotency-Key": st.session_state.submission_key},
                    )
                    if result:
                        st.session_state["submission_notice"] = f"Đã tạo job: {result['id']}"
                        st.session_state.pop("submission_key", None)
                        select_workspace(result["id"], result["status"])
                        st.rerun()
        phase1_jobs = request("GET", "/api/jobs")
        if phase1_jobs:
            phase1_jobs = [item for item in phase1_jobs if not item.get("render_config")]
        if phase1_jobs and opened:
            phase1_jobs = [item for item in phase1_jobs if item["id"] == opened["id"]]
        if phase1_jobs:
            st.subheader("Tiến trình Phase 1")
            for item in phase1_jobs:
                if item["status"] in ("queued", "running", "cancelling", "cancelled", "failed"):
                    with st.container(border=True):
                        st.write(item["package"]["title"])
                        st.caption(
                            {
                                "queued": "Chờ xử lý",
                                "running": "Đang xử lý",
                                "failed": "Xử lý thất bại",
                                "cancelling": "Đang dừng",
                                "cancelled": "Đã dừng",
                            }[item["status"]]
                        )
                        for source in item["package"]["sources"]:
                            if source.get("url"):
                                st.write(source["url"])
                        if item["error"]:
                            st.error(item["error"])
                        if item["status"] == "failed" and st.button(
                            "Thử lại", key=f"retry-{item['id']}"
                        ):
                            if request("POST", f"/api/jobs/{item['id']}/retry"):
                                st.rerun()
                else:
                    st.caption(f"{item['package']['title']} — Đã sẵn sàng kiểm duyệt ở Phase 2")

    with jobs_tab:
        st.subheader("Nội dung video")
        jobs = request("GET", "/api/jobs")
        if jobs is not None:
            jobs = [
                job
                for job in jobs
                if job["status"]
                in (
                    "awaiting_review",
                    "approved",
                    "rejected",
                    "awaiting_video_review",
                    "video_approved",
                    "video_rejected",
                )
            ]
        if opened:
            jobs = (
                [opened]
                if opened["status"]
                in (
                    "awaiting_review",
                    "approved",
                    "rejected",
                    "awaiting_video_review",
                    "video_approved",
                    "video_rejected",
                )
                else []
            )
        if jobs:
            by_id = {j["id"]: j for j in jobs}
            if st.session_state.get("selected_content") not in by_id:
                st.session_state["selected_content"] = jobs[0]["id"]
            selected = st.selectbox(
                "Chọn nội dung",
                list(by_id),
                key="selected_content",
                format_func=lambda job_id: (
                    f"{by_id[job_id]['package']['title']} · "
                    f"{by_id[job_id]['package']['branch'].upper()}"
                ),
            )
            job = by_id[selected]
            package = job["package"]
            saved_content = package.get("video_content") or "\n\n".join(
                scene["narration"] for scene in package["scenes"]
            )
            st.caption("Nội dung đã qua Phase 1. Đọc, chỉnh sửa và duyệt bên dưới.")
            if job["result"] and job["result"].get("analysis"):
                analysis = job["result"]["analysis"]
                st.caption(
                    f"{job['result']['word_count']} từ · "
                    f"{analysis['source_count']} nguồn · "
                    + (
                        "Đã phân tích AI"
                        if analysis.get("ai_generated")
                        else "Nội dung nhập thủ công"
                    )
                )
            # Bind each editor to its loaded revision to prevent stale overwrites.
            editor_key = f"editor-{selected}"
            revision_key = f"revision-{selected}"
            if editor_key not in st.session_state:
                st.session_state[editor_key] = saved_content
                st.session_state[revision_key] = hashlib.sha256(saved_content.encode()).hexdigest()
            content = st.text_area(
                "Nội dung video của bạn", height=420, max_chars=200000, key=editor_key
            )
            save, download = st.columns(2)
            if save.button("Lưu nội dung", type="primary", use_container_width=True):
                if not content.strip():
                    st.error("Nội dung không được để trống.")
                else:
                    result = request(
                        "PUT",
                        f"/api/jobs/{selected}/content",
                        json={
                            "content": content,
                            "expected_content_hash": st.session_state[revision_key],
                        },
                    )
                    if result:
                        st.session_state[revision_key] = hashlib.sha256(
                            content.strip().encode()
                        ).hexdigest()
                        st.success("Đã lưu nội dung.")
            filename = re.sub(r"[^\w\- ]", "", package["title"]).strip()[:80] or "content"
            download.download_button(
                "Tải file content (.txt)",
                data=content,
                file_name=f"{filename}.txt",
                mime="text/plain; charset=utf-8",
                use_container_width=True,
            )
            st.caption("File tải về chứa đúng nội dung đang hiển thị trong ô soạn thảo.")
            if job["status"] in (
                "approved",
                "awaiting_video_review",
                "video_approved",
                "video_rejected",
            ):
                st.success("Nội dung đã được duyệt.")
                if st.button("Tiếp tục dựng video", type="primary"):
                    if content.strip() != saved_content.strip():
                        st.error("Lưu và duyệt lại phần chỉnh sửa trước khi dựng video.")
                    else:
                        st.session_state["pending_workspace"] = (
                            selected,
                            job["status"],
                            "production",
                        )
                        st.rerun()
            elif job["status"] == "awaiting_review":
                with st.expander("Phản hồi nội dung"):
                    content_labels = st.multiselect(
                        "Lý do cần sửa",
                        ["incorrect_fact", "missing_content", "wording", "other"],
                        format_func=lambda x: {
                            "incorrect_fact": "Sai thông tin",
                            "missing_content": "Thiếu ý",
                            "wording": "Cách diễn đạt",
                            "other": "Khác",
                        }[x],
                    )
                    content_note = st.text_area("Nhận xét nội dung", max_chars=4000)
                    if st.button("Yêu cầu sửa nội dung"):
                        if not content_note.strip():
                            st.error("Nhập nội dung cần sửa.")
                        elif request(
                            "POST",
                            f"/api/jobs/{selected}/review",
                            json={
                                "decision": "reject",
                                "reviewer": "Người dùng workspace",
                                "note": content_note,
                                "labels": content_labels,
                                "expected_content_hash": st.session_state[revision_key],
                            },
                        ):
                            st.rerun()
                if st.button("Duyệt nội dung", use_container_width=True):
                    if content.strip() != saved_content.strip():
                        st.error("Hãy lưu phần chỉnh sửa trước khi duyệt.")
                    else:
                        if request(
                            "POST",
                            f"/api/jobs/{selected}/review",
                            json={
                                "decision": "approve",
                                "reviewer": "Người dùng workspace",
                                "note": content_note.strip()
                                or "Đã kiểm duyệt nội dung trong Phase 2.",
                                "labels": content_labels,
                                "expected_content_hash": st.session_state[revision_key],
                            },
                        ):
                            st.rerun()
        elif jobs == []:
            st.info("Chưa có nội dung sẵn sàng. Hoàn tất Phase 1 trước khi kiểm duyệt.")

    with production_tab:
        st.subheader("Bước 5–6 · Chuẩn bị và dựng video")
        st.write("Hệ thống tự chọn style theo nội dung, căn phụ đề và dựng video từ ảnh của bạn.")
        st.info(
            "Style tự động: kể chuyện điện ảnh, truyện tranh nổi bật hoặc thông tin rõ ràng. "
            "Không cần chỉnh font và hiệu ứng từng video."
        )
        candidates = request("GET", "/api/jobs") or []
        if opened and opened["id"] not in [item["id"] for item in candidates]:
            candidates.append(opened)
        candidates = [
            item
            for item in candidates
            if item["status"]
            in ("approved", "awaiting_video_review", "video_approved", "video_rejected")
            or item.get("render_config")
        ]
        if opened:
            candidates = [item for item in candidates if item["id"] == opened["id"]]
        if candidates:
            render_jobs = {item["id"]: item for item in candidates}
            if st.session_state.get("selected_render_job") not in render_jobs:
                st.session_state["selected_render_job"] = candidates[0]["id"]
            render_id = st.selectbox(
                "Chọn kịch bản đã duyệt",
                list(render_jobs),
                key="selected_render_job",
                format_func=lambda value: render_jobs[value]["package"]["title"],
            )
            render_job = render_jobs[render_id]
            if render_job["status"] in ("queued", "running", "cancelling"):
                render_production_progress(render_id)
            else:
                if render_job.get("video"):
                    st.success("Đã dựng xong video.")
                    if st.button("Mở video để xem và duyệt", type="primary"):
                        select_workspace(render_id, render_job["status"], "video_review")
                        st.rerun()
                if render_job.get("error"):
                    st.error(render_job["error"])
                media_mode = st.radio(
                    "Nguồn hình", ["Ảnh", "Clip"], horizontal=True, key=f"media-mode-{render_id}"
                )
                saved_assets = request("GET", f"/api/jobs/{render_id}/assets") or []
                kind = "video" if media_mode == "Clip" else "image"
                available = [a for a in saved_assets if a["kind"] == kind]
                reused = st.multiselect(
                    "File đã tải lên",
                    available,
                    format_func=lambda a: f"{a['id'][:8]} · {a['size'] / 1_000_000:.1f} MB",
                    key=f"media-reuse-{render_id}-{kind}",
                )
                with st.expander("Quản lý file nguồn"):
                    for asset in saved_assets:
                        if st.button(
                            f"Xóa file {asset['id'][:8]}", key=f"delete-asset-{asset['id']}"
                        ):
                            if request("DELETE", f"/api/jobs/{render_id}/assets/{asset['id']}"):
                                st.rerun()
                with st.form(f"render-{render_id}"):
                    voices = {
                        "local-vi": "Tiếng Việt · giọng trên máy",
                        "local-en": "English · giọng trên máy",
                        "vi-VN-HoaiMyNeural": "Tiếng Việt · Hoài My (Edge online)",
                        "vi-VN-NamMinhNeural": "Tiếng Việt · Nam Minh (Edge online)",
                        "en-US-AriaNeural": "English · Aria (Edge online)",
                    }
                    voice = st.selectbox("Giọng đọc", list(voices), format_func=voices.get)
                    layout = st.selectbox(
                        "Khung hình",
                        ["portrait", "landscape"],
                        format_func=lambda value: (
                            "Dọc 9:16 · 720×1280"
                            if value == "portrait"
                            else "Ngang 16:9 · 1280×720"
                        ),
                    )
                    if media_mode == "Clip":
                        pictures = st.file_uploader(
                            "Clip cho video",
                            type=["mp4", "mov", "webm"],
                            accept_multiple_files=False,
                            max_upload_size=100,
                        )
                        video_fit = st.selectbox(
                            "Cách đặt clip",
                            ["pad", "crop"],
                            format_func=lambda v: (
                                "Giữ đủ hình, thêm viền" if v == "pad" else "Cắt giữa cho đầy khung"
                            ),
                        )
                        st.caption(
                            "Một clip tối đa 100 MB, 120 giây, Full HD, 60 fps. "
                            "Clip tự lặp theo lời đọc; tắt tiếng gốc."
                        )
                    else:
                        pictures = st.file_uploader(
                            "Ảnh cho video (không bắt buộc)",
                            type=["png", "jpg", "jpeg"],
                            accept_multiple_files=True,
                            max_upload_size=3,
                        )
                        video_fit = "pad"
                        st.caption("Tối đa 10 ảnh, mỗi ảnh 3 MB. Không thêm ảnh: dùng nền chữ.")
                    st.caption("File lưu local, tái sử dụng được. Trên Linux hãy chọn giọng Edge.")
                    build = st.form_submit_button("Dựng video", type="primary")
                if build:
                    uploads = ([pictures] if pictures else []) if kind == "video" else pictures
                    limit = 100_000_000 if kind == "video" else 3_000_000
                    count_limit = 1 if kind == "video" else 10
                    if len(uploads) + len(reused) > count_limit or any(
                        p.size > limit for p in uploads
                    ):
                        st.error("Vượt số lượng file hoặc giới hạn dung lượng.")
                    else:
                        uploaded_ids = upload_media(request, render_id, uploads, kind)
                        if uploaded_ids is None:
                            st.stop()
                        asset_ids = [a["id"] for a in reused] + uploaded_ids
                        if kind == "video" and not asset_ids:
                            st.error("Chọn một clip để dựng video.")
                            st.stop()
                        script = render_job["package"].get("video_content") or "\n\n".join(
                            scene["narration"] for scene in render_job["package"]["scenes"]
                        )
                        result = request(
                            "POST",
                            f"/api/jobs/{render_id}/render",
                            json={
                                "voice": voice,
                                "layout": layout,
                                "image_asset_ids": asset_ids if kind == "image" else [],
                                "video_asset_id": asset_ids[0] if kind == "video" else None,
                                "video_fit": video_fit,
                                "expected_content_hash": hashlib.sha256(
                                    script.encode()
                                ).hexdigest(),
                            },
                        )
                        if result:
                            st.session_state["pending_workspace"] = (
                                render_id,
                                "queued",
                                "production",
                            )
                            st.rerun()
        else:
            st.info("Duyệt kịch bản ở Phase 2 để bắt đầu dựng video.")

    with video_tab:
        st.subheader("Bước 7 · Xem và duyệt video cuối")
        ready = request("GET", "/api/jobs") or []
        if opened and opened["id"] not in [item["id"] for item in ready]:
            ready.append(opened)
        ready = [
            item
            for item in ready
            if item["status"] in ("awaiting_video_review", "video_approved", "video_rejected")
            and item.get("video")
        ]
        if opened:
            ready = [item for item in ready if item["id"] == opened["id"]]
        if ready:
            videos = {item["id"]: item for item in ready}
            if st.session_state.get("selected_video_job") not in videos:
                st.session_state["selected_video_job"] = ready[0]["id"]
            video_id = st.selectbox(
                "Chọn video",
                list(videos),
                key="selected_video_job",
                format_func=lambda value: videos[value]["package"]["title"],
            )
            video_job = videos[video_id]
            meta = video_job["video"]
            if style := meta.get("style"):
                st.caption(f"Style tự động: {style['name']} · Thư viện v{style['catalog_version']}")
                st.caption("Phụ đề căn theo thời lượng đoạn đọc; chưa căn chính xác từng từ.")
            st.caption(
                f"{meta['width']}×{meta['height']} · {meta['duration']:.1f} giây · "
                f"{meta['caption_count']} đoạn phụ đề · Đã kiểm tra hình và tiếng"
            )
            if video_tab.open:
                try:
                    media = httpx.get(
                        f"{API_URL}/api/jobs/{video_id}/artifacts/video",
                        headers=HEADERS,
                        timeout=60,
                    )
                    media.raise_for_status()
                    st.video(media.content, format="video/mp4", width=420)
                    st.download_button(
                        "Tải video MP4",
                        media.content,
                        file_name=f"video-{video_id[:8]}.mp4",
                        mime="video/mp4",
                    )
                    srt = httpx.get(
                        f"{API_URL}/api/jobs/{video_id}/artifacts/subtitles",
                        headers=HEADERS,
                        timeout=15,
                    )
                    if srt.status_code == 200:
                        st.download_button(
                            "Tải phụ đề SRT",
                            srt.content,
                            file_name=f"subtitles-{video_id[:8]}.srt",
                            mime="application/x-subrip",
                        )
                    if meta.get("style"):
                        styled_subtitles = httpx.get(
                            f"{API_URL}/api/jobs/{video_id}/artifacts/styled_subtitles",
                            headers=HEADERS,
                            timeout=15,
                        )
                        if styled_subtitles.status_code == 200:
                            st.download_button(
                                "Tải phụ đề có style ASS",
                                styled_subtitles.content,
                                file_name=f"subtitles-{video_id[:8]}.ass",
                                mime="text/plain",
                            )
                except httpx.HTTPError:
                    st.error("Chưa mở được file video. Hãy thử tải lại.")
            if video_job["status"] == "video_approved":
                st.success("Video đã được duyệt. Sẵn sàng cho bước đăng bài.")
            elif video_job["status"] == "video_rejected":
                st.warning("Video cần chỉnh sửa. Sửa kịch bản hoặc dựng lại ở Phase 3.")
            else:
                with st.form(f"video-review-{video_id}"):
                    feedback = st.text_area(
                        "Nhận xét video",
                        max_chars=4000,
                        placeholder="Kiểm tra giọng đọc, hình ảnh, phụ đề và nhịp dựng…",
                    )
                    feedback_labels = st.multiselect(
                        "Vấn đề cần cải thiện",
                        [
                            "subtitle_overflow",
                            "subtitle_pacing",
                            "subtitle_sync",
                            "pronunciation",
                            "visual_relevance",
                            "editing_pace",
                            "incorrect_fact",
                            "missing_content",
                            "other",
                        ],
                        format_func=lambda x: {
                            "subtitle_overflow": "Phụ đề tràn/nhiều dòng",
                            "subtitle_pacing": "Phụ đề quá nhanh",
                            "subtitle_sync": "Phụ đề lệch tiếng",
                            "pronunciation": "Phát âm",
                            "visual_relevance": "Ảnh không phù hợp",
                            "editing_pace": "Nhịp dựng",
                            "incorrect_fact": "Sai thông tin",
                            "missing_content": "Thiếu nội dung",
                            "other": "Khác",
                        }[x],
                    )
                    feedback_time = st.number_input(
                        "Vị trí lỗi (giây)",
                        min_value=0.0,
                        max_value=float(meta["duration"]),
                        value=0.0,
                    )
                    approve_video = st.form_submit_button("Duyệt video", type="primary")
                    reject_video = st.form_submit_button("Yêu cầu chỉnh sửa")
                if approve_video or reject_video:
                    if reject_video and not feedback.strip():
                        st.error("Nhập nội dung cần chỉnh sửa để lưu kết quả.")
                    else:
                        if request(
                            "POST",
                            f"/api/jobs/{video_id}/video-review",
                            json={
                                "decision": "approve" if approve_video else "reject",
                                "reviewer": "Người dùng workspace",
                                "note": feedback.strip() or "Đã xem và duyệt video.",
                                "expected_video_hash": meta["sha256"],
                                "labels": feedback_labels,
                                "timecode": feedback_time if feedback_labels else None,
                            },
                        ):
                            st.rerun()
            if st.button("Sửa kịch bản của video này"):
                st.session_state["pending_workspace"] = (
                    video_id,
                    "awaiting_review",
                    "content_review",
                )
                st.rerun()
            if st.button("Dựng lại video"):
                st.session_state["pending_workspace"] = (video_id, "approved", "production")
                st.rerun()
        else:
            st.info("Chưa có video để duyệt. Hoàn tất bước dựng ở Phase 3 trước.")

    with youtube_tab:
        st.subheader("Đăng YouTube và theo dõi hiệu quả")
        connection = request("GET", "/api/youtube/status")
        if connection and not connection["connected"]:
            st.info("Chưa kết nối YouTube. Cần OAuth của kênh; không dùng key Gemini.")
            with st.expander("Kết nối một lần"):
                st.write(
                    "Thiết lập Google OAuth với quyền youtube.upload và yt-analytics.readonly. "
                    "Lưu client ID, client secret và refresh token trong cấu hình cục bộ."
                )
                st.code(
                    "STUDIO_YOUTUBE_CLIENT_ID\nSTUDIO_YOUTUBE_CLIENT_SECRET\nSTUDIO_YOUTUBE_REFRESH_TOKEN"
                )
                st.caption("Không gửi token hoặc client secret vào chat.")
        if opened:
            publish_job = request("GET", f"/api/jobs/{opened['id']}")
            if publish_job and publish_job["status"] == "video_approved":
                with st.form(f"youtube-publish-{opened['id']}"):
                    upload_title = st.text_input(
                        "Tiêu đề YouTube",
                        value=publish_job["package"]["title"][:100],
                        max_chars=100,
                    )
                    upload_description = st.text_area("Mô tả YouTube", max_chars=5000)
                    upload_privacy = st.selectbox(
                        "Chế độ hiển thị", ["private", "unlisted", "public"]
                    )
                    made_for_kids = st.checkbox("Nội dung dành cho trẻ em")
                    start_upload = st.form_submit_button(
                        "Đăng / tiếp tục upload YouTube",
                        disabled=not connection or not connection["connected"],
                    )
                if start_upload:
                    result = request(
                        "POST",
                        f"/api/jobs/{opened['id']}/youtube",
                        timeout=90,
                        json={
                            "title": upload_title,
                            "description": upload_description,
                            "privacy": upload_privacy,
                            "made_for_kids": made_for_kids,
                            "expected_video_hash": publish_job["video"]["sha256"],
                        },
                    )
                    if result:
                        st.success(
                            "Đã gửi lượt upload. Trạng thái được lưu để tiếp tục; không đăng trùng."
                        )
            else:
                st.info("Duyệt video cuối ở Phase 4 trước khi đăng.")
            attempts = request("GET", f"/api/jobs/{opened['id']}/youtube") or []
            for attempt in attempts:
                st.write(f"YouTube: {attempt['state']} · Đã gửi {attempt['offset']:,} byte")
                if attempt["platform_id"]:
                    st.link_button(
                        "Mở video YouTube",
                        f"https://www.youtube.com/watch?v={attempt['platform_id']}",
                    )
                    if st.button("Cập nhật Analytics", key=f"analytics-{attempt['id']}"):
                        request("POST", f"/api/youtube/{attempt['id']}/analytics", timeout=60)
                    snapshots = request("GET", f"/api/youtube/{attempt['id']}/analytics") or []
                    if snapshots:
                        metrics = snapshots[0]["metrics"]
                        if metrics["data_available"]:
                            st.json(metrics["values"])
                        else:
                            st.info("YouTube chưa trả dữ liệu. Không coi là 0 lượt xem.")
                        st.caption("Chỉ số quan sát; chưa chứng minh style mới làm tăng hiệu quả.")
        else:
            st.info("Chọn video trong Workspace trước.")
