"""Learning library and one-focus authoring, using only HTTP client dependencies."""

import json

import streamlit as st

from ui.client.api import request
from ui.state.workspace import select_workspace

KINDS = {
    "vocabulary": "Từ vựng · từng nghĩa",
    "patterns": "Cấu trúc",
    "samples": "Sample",
    "exercises": "Bài tập",
}
EXAMPLES = {
    "vocabulary": {
        "lemma": "adapt",
        "part_of_speech": "verb",
        "sense": "change to suit a new situation",
        "ipa_uk": "/əˈdæpt/",
        "definition": "to change your behaviour to suit a new situation",
        "examples": ["Students need time to adapt to a new school."],
    },
    "patterns": {
        "form": "Although + clause, clause",
        "function": "contrast",
        "explanation": "Introduce a contrasting idea.",
        "examples": ["Although online lessons are convenient, I prefer a classroom."],
    },
    "samples": {
        "skill": "speaking",
        "prompt": "Describe a place where you study.",
        "response": (
            "I usually study in a small library near my home. "
            "It is quiet and has plenty of natural light."
        ),
        "annotations": [
            {"quote": "plenty of natural light", "note": "A useful phrase for describing a room."}
        ],
    },
    "exercises": {
        "question": "She is interested ___ science.",
        "options": ["in", "on", "at"],
        "answer": "in",
        "explanation": "Use interested in + noun.",
    },
}


def render(opened=None, active=True, jobs_snapshot=None):
    st.subheader("Thư viện IELTS")
    st.caption(
        "Một mục = một nghĩa từ, một cấu trúc, một sample hoặc một câu hỏi. "
        "Ví dụ tự viết không có band IELTS đã chấm."
    )
    if not active:
        return
    topics = request("GET", "/api/ielts/topics")
    if topics is None:
        return
    names = {t["id"]: t["name"] for t in topics}
    with st.expander("Thêm topic"):
        with st.form("ielts-topic"):
            name = st.text_input("Tên topic", max_chars=200)
            parent = st.selectbox(
                "Topic cha", [None, *names], format_func=lambda v: names.get(v, "Không có")
            )
            add = st.form_submit_button("Lưu topic")
        if add and request("POST", "/api/ielts/topics", json={"name": name, "parent_id": parent}):
            st.rerun()
    kind = st.selectbox("Loại nội dung", list(KINDS), format_func=KINDS.get, key="ielts-kind")
    with st.expander("Thêm nội dung / nhập JSON"):
        st.caption(
            "Mẫu dưới đây do dự án tự viết, chỉ minh họa schema. Sửa và kiểm tra trước khi lưu."
        )
        with st.form(f"ielts-create-{kind}"):
            title = st.text_input("Tên mục học", max_chars=200)
            selected = st.multiselect("Topic của nội dung", list(names), format_func=names.get)
            label = st.text_input("Nguồn nội dung", max_chars=300)
            url = st.text_input("Link nguồn")
            rights = st.text_area("Quyền sử dụng nội dung", max_chars=2000)
            raw = st.text_area(
                "Dữ liệu nội dung (JSON)",
                value=json.dumps(EXAMPLES[kind], ensure_ascii=False, indent=2),
                height=250,
            )
            save = st.form_submit_button("Lưu bản nháp")
        if save:
            try:
                data = json.loads(raw)
            except ValueError:
                st.error("JSON chưa hợp lệ.")
            else:
                if request(
                    "POST",
                    f"/api/ielts/{kind}",
                    json={
                        "title": title,
                        "topic_ids": selected,
                        "source": {"label": label, "url": url or None, "rights_note": rights},
                        "data": data,
                    },
                ):
                    st.rerun()
        batch = st.file_uploader(
            "Nhập batch JSON (tối đa 100 mục)", type=["json"], max_upload_size=1, key="ielts-import"
        )
        preview = st.button("Kiểm tra batch", disabled=batch is None)
        apply = st.button("Nhập batch", disabled=batch is None)
        if preview or apply:
            try:
                payload = json.loads(batch.getvalue())
            except (ValueError, UnicodeDecodeError):
                st.error("File JSON chưa hợp lệ.")
            else:
                result = request("POST", "/api/ielts/imports/preview", json=payload)
                if result:
                    st.json(result)
                    if apply and result["valid"]:
                        if request("POST", "/api/ielts/imports", json=payload):
                            st.rerun()
    q = st.text_input(
        "Tìm trong thư viện",
        max_chars=200,
        help="Tìm gần đúng trong tối đa 1.000 mục mới nhất của bộ lọc; không tự gộp các nghĩa.",
    )
    topic_filter = st.selectbox(
        "Lọc topic", [None, *names], format_func=lambda v: names.get(v, "Tất cả")
    )
    status_filter = st.selectbox(
        "Trạng thái nội dung",
        [None, "draft", "reviewed"],
        format_func=lambda v: {None: "Tất cả", "draft": "Bản nháp", "reviewed": "Đã duyệt"}[v],
    )
    page = st.number_input("Trang thư viện", min_value=1, value=1, step=1)
    result = request(
        "GET",
        f"/api/ielts/{kind}",
        params={
            "q": q,
            "limit": 20,
            "offset": (page - 1) * 20,
            **({"topic_id": topic_filter} if topic_filter else {}),
            **({"status": status_filter} if status_filter else {}),
        },
    )
    if not result:
        return
    if result["search_truncated"]:
        st.info("Tìm gần đúng giới hạn ở 1.000 mục; lọc topic để thu hẹp.")
    if not result["items"]:
        st.info("Chưa có mục phù hợp. Thêm topic rồi lưu nội dung đầu tiên.")
        return
    for item in result["items"]:
        with st.expander(f"{item['title']} · {item['status']}"):
            st.caption("Topic: " + ", ".join(names.get(t, t) for t in item["topic_ids"]))
            st.json(item["data"])
            st.write(item["source"])
            with st.form(f"ielts-edit-{item['id']}"):
                st.caption("Sửa nội dung hoặc nguồn sẽ đưa mục về bản nháp và giữ revision cũ.")
                edit_title = st.text_input("Sửa tên mục", value=item["title"], max_chars=200)
                edit_data = st.text_area(
                    "Sửa dữ liệu (JSON)",
                    value=json.dumps(item["data"], ensure_ascii=False, indent=2),
                )
                edit_source = st.text_area(
                    "Sửa nguồn và quyền (JSON)",
                    value=json.dumps(item["source"], ensure_ascii=False, indent=2),
                )
                edited = st.form_submit_button("Lưu sửa mục học")
            if edited:
                try:
                    payload = {
                        "title": edit_title,
                        "data": json.loads(edit_data),
                        "source": json.loads(edit_source),
                        "topic_ids": item["topic_ids"],
                        "expected_version": item["version"],
                    }
                except ValueError:
                    st.error("JSON chỉnh sửa chưa hợp lệ.")
                else:
                    if request("PUT", f"/api/ielts/items/{item['id']}", json=payload):
                        st.rerun()
            with st.form(f"ielts-review-{item['id']}"):
                reviewer = st.text_input("Người duyệt")
                note = st.text_area("Ghi chú kiểm tra kiến thức và quyền sử dụng")
                reviewed = st.form_submit_button("Duyệt mục học")
            if reviewed and request(
                "POST",
                f"/api/ielts/items/{item['id']}/review",
                json={"expected_version": item["version"], "reviewer": reviewer, "note": note},
            ):
                st.rerun()
            with st.form(f"ielts-brief-{item['id']}"):
                focus = st.text_area("Lời đọc cho một Short (một ý, tối đa 85 từ)", max_chars=650)
                create = st.form_submit_button(
                    "Tạo Short từ mục này", disabled=item["status"] != "reviewed"
                )
            if create:
                brief = request(
                    "POST",
                    f"/api/ielts/items/{item['id']}/brief",
                    json={"expected_version": item["version"], "focus_text": focus},
                )
                if brief:
                    # Stable idempotency key prevents duplicate jobs after an uncertain response.
                    import hashlib

                    signature = hashlib.sha256(
                        json.dumps(brief, sort_keys=True).encode()
                    ).hexdigest()
                    job = request(
                        "POST",
                        "/api/jobs",
                        json={"package": brief["package"]},
                        extra_headers={"Idempotency-Key": f"ielts-{signature}"},
                    )
                    if job:
                        select_workspace(job["id"], job["status"])
                        st.session_state["submission_notice"] = (
                            "Đã tạo kịch bản English một ý. "
                            "Tiếp tục kiểm duyệt rồi dựng khung trắng."
                        )
                        st.rerun()
