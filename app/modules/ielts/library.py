"""Transactional typed library, bounded fuzzy discovery and one-focus briefs."""

import hashlib
import json
from uuid import uuid4

from rapidfuzz.fuzz import WRatio
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.contracts.ielts import Exercise, Pattern, Sample, Vocabulary
from app.infrastructure.persistence.database import (
    GrammarPattern,
    LearningExercise,
    LearningItem,
    LearningItemTopic,
    LearningReview,
    LearningRevision,
    LearningSample,
    LearningTopic,
    VocabularySense,
)
from app.modules.errors import ApplicationError

TYPES = {
    "vocabulary": (Vocabulary, VocabularySense),
    "patterns": (Pattern, GrammarPattern),
    "samples": (Sample, LearningSample),
    "exercises": (Exercise, LearningExercise),
}


def commit(session):
    try:
        session.commit()
    except (IntegrityError, StaleDataError) as exc:
        session.rollback()
        raise ApplicationError(
            409, "Dữ liệu trùng hoặc phiên bản đã đổi. Tải lại thư viện."
        ) from exc


def list_topics(*, session):
    return [
        {"id": t.id, "name": t.name, "parent_id": t.parent_id}
        for t in session.scalars(select(LearningTopic).order_by(LearningTopic.name))
    ]


def create_topic(payload, *, session):
    if len(payload.name) > 200:
        raise ApplicationError(422, "Tên topic tối đa 200 ký tự.")
    if payload.parent_id and not session.get(LearningTopic, str(payload.parent_id)):
        raise ApplicationError(422, "Topic cha không tồn tại.")
    topic = LearningTopic(
        name=payload.name, parent_id=str(payload.parent_id) if payload.parent_id else None
    )
    session.add(topic)
    commit(session)
    return {"id": topic.id, "name": topic.name, "parent_id": topic.parent_id}


def fingerprint(kind, payload):
    schema, _ = TYPES[kind]
    if not isinstance(payload.data, schema):
        raise ApplicationError(422, f"Payload không đúng loại {kind}.")
    canonical = json.dumps(payload.data.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((kind + "\n" + canonical).encode()).hexdigest()


def validate_topics(payloads, *, session):
    wanted = {str(t) for p in payloads for t in p.topic_ids}
    found = set(session.scalars(select(LearningTopic.id).where(LearningTopic.id.in_(wanted))))
    if wanted != found:
        raise ApplicationError(422, "Một hoặc nhiều topic không tồn tại.")


def preview_import(payload, *, session):
    validate_topics(payload.items, session=session)
    hashes = [fingerprint(payload.kind, p) for p in payload.items]
    existing = set(
        session.scalars(
            select(LearningItem.fingerprint).where(LearningItem.fingerprint.in_(hashes))
        )
    )
    seen, rows = set(), []
    for index, (item, digest) in enumerate(zip(payload.items, hashes, strict=True)):
        duplicate = digest in existing or digest in seen
        rows.append(
            {"index": index, "title": item.title, "duplicate": duplicate, "fingerprint": digest}
        )
        seen.add(digest)
    return {"valid": not any(r["duplicate"] for r in rows), "rows": rows, "count": len(rows)}


def add_item(kind, payload, *, session):
    validate_topics([payload], session=session)
    digest = fingerprint(kind, payload)
    item = LearningItem(
        id=str(uuid4()),
        kind=kind,
        title=payload.title,
        source=payload.source.model_dump(mode="json"),
        fingerprint=digest,
    )
    _, model = TYPES[kind]
    session.add(item)
    session.flush()
    session.add(model(item_id=item.id, **payload.data.model_dump(mode="json")))
    session.add_all(LearningItemTopic(item_id=item.id, topic_id=str(t)) for t in payload.topic_ids)
    record_revision(
        item,
        payload.data.model_dump(mode="json"),
        [str(t) for t in payload.topic_ids],
        session=session,
    )
    return item


def record_revision(item, data, topics, *, session):
    session.add(
        LearningRevision(
            item_id=item.id,
            version=item.version,
            snapshot={
                "kind": item.kind,
                "title": item.title,
                "source": item.source,
                "status": item.status,
                "data": data,
                "topic_ids": topics,
            },
        )
    )


def update_item(item_id, payload, *, session):
    item = session.get(LearningItem, str(item_id))
    if not item:
        raise ApplicationError(404, "Không tìm thấy mục học.")
    if item.version != payload.expected_version:
        raise ApplicationError(409, "Phiên bản đã đổi. Tải lại trước khi sửa.")
    validate_topics([payload], session=session)
    digest = fingerprint(item.kind, payload)
    # Finish reads before mutation to avoid partial autoflush on a duplicate fingerprint.
    detail = session.get(TYPES[item.kind][1], item.id)
    session.execute(delete(LearningItemTopic).where(LearningItemTopic.item_id == item.id))
    item.title = payload.title
    item.source = payload.source.model_dump(mode="json")
    item.fingerprint = digest
    item.status = "draft"
    item.version += 1
    for key, value in payload.data.model_dump(mode="json").items():
        setattr(detail, key, value)
    session.add_all(LearningItemTopic(item_id=item.id, topic_id=str(t)) for t in payload.topic_ids)
    record_revision(
        item,
        payload.data.model_dump(mode="json"),
        [str(t) for t in payload.topic_ids],
        session=session,
    )
    commit(session)
    return read_item(item.id, session=session)


def create_item(kind, payload, *, session):
    try:
        item = add_item(kind, payload, session=session)
        commit(session)
    except IntegrityError as exc:
        session.rollback()
        raise ApplicationError(409, "Nội dung này đã có trong thư viện.") from exc
    return read_item(item.id, session=session)


def import_items(payload, *, session):
    preview = preview_import(payload, session=session)
    if not preview["valid"]:
        raise ApplicationError(409, "Batch có nội dung trùng. Kiểm tra preview trước khi nhập.")
    try:
        items = [add_item(payload.kind, item, session=session) for item in payload.items]
        commit(session)
    except IntegrityError as exc:
        session.rollback()
        raise ApplicationError(409, "Nội dung vừa được nhập bởi yêu cầu khác.") from exc
    return {"ids": [item.id for item in items], "count": len(items)}


def item_dict(item, detail, topic_ids):
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "source": item.source,
        "status": item.status,
        "version": item.version,
        "topic_ids": topic_ids,
        "data": {
            c.name: getattr(detail, c.name) for c in detail.__table__.columns if c.name != "item_id"
        },
    }


def read_item(item_id, *, session):
    item = session.get(LearningItem, str(item_id))
    if not item:
        raise ApplicationError(404, "Không tìm thấy mục học.")
    _, model = TYPES[item.kind]
    topics = list(
        session.scalars(
            select(LearningItemTopic.topic_id).where(LearningItemTopic.item_id == item.id)
        )
    )
    return item_dict(item, session.get(model, item.id), topics)


def list_items(kind, q, topic_id, status, limit, offset, *, session):
    _, model = TYPES[kind]
    query = (
        select(LearningItem, model)
        .join(model, model.item_id == LearningItem.id)
        .where(LearningItem.kind == kind)
    )
    if topic_id:
        query = query.where(
            LearningItem.id.in_(
                select(LearningItemTopic.item_id).where(LearningItemTopic.topic_id == str(topic_id))
            )
        )
    if status:
        query = query.where(LearningItem.status == status)
    # Fuzzy search is explicitly bounded; exact SQL/topic pagination has no scan cap.
    query = query.order_by(LearningItem.created_at.desc(), LearningItem.id)
    candidates = list(
        session.execute(query.limit(1001) if q else query.offset(offset).limit(limit))
    )
    truncated = bool(q and len(candidates) > 1000)
    if q:
        scored = [
            (WRatio(q.casefold(), (i.title + " " + str(getattr(d, "lemma", ""))).casefold()), i, d)
            for i, d in candidates[:1000]
        ]
        candidates = [
            (i, d)
            for score, i, d in sorted(scored, key=lambda r: r[0], reverse=True)
            if score >= 55
        ][offset : offset + limit]
    ids = [i.id for i, _ in candidates]
    links = (
        session.execute(
            select(LearningItemTopic).where(LearningItemTopic.item_id.in_(ids))
        ).scalars()
        if ids
        else []
    )
    topics = {}
    for link in links:
        topics.setdefault(link.item_id, []).append(link.topic_id)
    return {
        "items": [item_dict(i, d, topics.get(i.id, [])) for i, d in candidates],
        "search_truncated": truncated,
        "limit": limit,
        "offset": offset,
    }


def review_item(item_id, payload, *, session):
    item = session.get(LearningItem, str(item_id))
    if not item:
        raise ApplicationError(404, "Không tìm thấy mục học.")
    if item.version != payload.expected_version:
        raise ApplicationError(409, "Phiên bản đã đổi. Tải lại trước khi duyệt.")
    current = read_item(item.id, session=session)
    item.status = "reviewed"
    item.version += 1
    record_revision(item, current["data"], current["topic_ids"], session=session)
    session.add(
        LearningReview(
            item_id=item.id, version=item.version, reviewer=payload.reviewer, note=payload.note
        )
    )
    commit(session)
    return read_item(item.id, session=session)


def prepare_brief(item_id, payload, *, session):
    item = read_item(item_id, session=session)
    if item["version"] != payload.expected_version:
        raise ApplicationError(409, "Phiên bản đã đổi.")
    if item["status"] != "reviewed":
        raise ApplicationError(409, "Duyệt nội dung và quyền sử dụng trước khi tạo Short.")
    # The author selects one excerpt/question/example, instead of stuffing the whole item.
    if len(payload.focus_text.split()) > 85:
        raise ApplicationError(422, "Một Short tối đa 85 từ. Chọn một ý hoặc một đoạn ngắn hơn.")
    source = item["source"]
    return {
        "package": {
            "branch": "novel",
            "language": "en",
            "title": item["title"],
            "sources": [
                {
                    "label": source["label"],
                    "rights_note": source["rights_note"],
                    **({"url": source["url"]} if source.get("url") else {}),
                }
            ],
            "scenes": [{"narration": payload.focus_text, "source_indices": [0]}],
        },
        "library_item_id": item["id"],
        "library_version": item["version"],
        "word_count": len(payload.focus_text.split()),
    }


def revisions(item_id, *, session):
    read_item(item_id, session=session)
    return [
        {"version": r.version, "snapshot": r.snapshot}
        for r in session.scalars(
            select(LearningRevision)
            .where(LearningRevision.item_id == str(item_id))
            .order_by(LearningRevision.version)
        )
    ]
