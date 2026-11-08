"""Real migrated SQLite and HTTP contracts, no fake learning repository."""

from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.infrastructure.persistence.database import LearningItem, LearningReview
from app.schemas import ContentPackage


def topic(client, name="Education", parent=None):
    response = client.post("/api/ielts/topics", json={"name": name, "parent_id": parent})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def vocabulary(topic_id, sense="change to suit a new situation"):
    return {
        "title": "adapt · change",
        "topic_ids": [topic_id],
        "source": {"label": "Original test", "rights_note": "Original fixture; not official IELTS"},
        "data": {
            "lemma": "adapt",
            "part_of_speech": "verb",
            "sense": sense,
            "ipa_uk": "/əˈdæpt/",
            "definition": "to change to suit a new situation",
            "examples": ["Students adapt to a new school."],
        },
    }


def test_separate_senses_topic_filter_fuzzy_and_reviewed_brief(client):
    parent = topic(client)
    child = topic(client, "School", parent)
    one = client.post("/api/ielts/vocabulary", json=vocabulary(child))
    assert one.status_code == 201, one.text
    one = one.json()
    second = vocabulary(parent, "change a book into a film")
    second["title"] = "adapt · film"
    assert client.post("/api/ielts/vocabulary", json=second).status_code == 201
    assert client.post("/api/ielts/vocabulary", json=vocabulary(child)).status_code == 409
    found = client.get("/api/ielts/vocabulary", params={"topic_id": child, "q": "adpat"}).json()
    assert [i["id"] for i in found["items"]] == [one["id"]]
    assert found["items"][0]["data"]["ipa_uk"] == "/əˈdæpt/"
    brief = {
        "expected_version": one["version"],
        "focus_text": "Adapt means to change. Students adapt to a new school.",
    }
    assert client.post(f"/api/ielts/items/{one['id']}/brief", json=brief).status_code == 409
    review = client.post(
        f"/api/ielts/items/{one['id']}/review",
        json={
            "expected_version": one["version"],
            "reviewer": "Teacher",
            "note": "Checked meaning, example and original rights",
        },
    )
    assert review.status_code == 200, review.text
    assert review.json()["version"] == 2
    assert client.post(f"/api/ielts/items/{one['id']}/brief", json=brief).status_code == 409
    brief["expected_version"] = 2
    response = client.post(f"/api/ielts/items/{one['id']}/brief", json=brief)
    assert response.status_code == 200, response.text
    package = ContentPackage.model_validate(response.json()["package"])
    assert package.language == "en" and len(package.scenes) == 1
    assert package.sources[0].rights_note == "Original fixture; not official IELTS"
    brief["focus_text"] = "word " * 86
    assert client.post(f"/api/ielts/items/{one['id']}/brief", json=brief).status_code == 422
    with client.app.state.sessions() as session:
        audit = session.scalar(select(LearningReview))
        assert audit.item_id == one["id"] and audit.reviewer == "Teacher"


def test_import_is_atomic_preview_detects_batch_and_existing_duplicates(client):
    education = topic(client)
    entry = vocabulary(education)
    payload = {"kind": "vocabulary", "items": [entry, entry]}
    assert not client.post("/api/ielts/imports/preview", json=payload).json()["valid"]
    assert client.post("/api/ielts/imports", json=payload).status_code == 409
    assert client.get("/api/ielts/vocabulary").json()["items"] == []
    payload["items"] = [entry, {**entry, "topic_ids": [str(uuid4())]}]
    assert client.post("/api/ielts/imports", json=payload).status_code == 422
    assert client.get("/api/ielts/vocabulary").json()["items"] == []
    payload["items"] = [entry]
    assert client.post("/api/ielts/imports/preview", json=payload).json()["valid"]
    assert client.post("/api/ielts/imports", json=payload).json()["count"] == 1
    assert not client.post("/api/ielts/imports/preview", json=payload).json()["valid"]
    assert client.post("/api/ielts/imports", json=payload).status_code == 409


@pytest.mark.parametrize(
    "kind,data",
    [
        (
            "patterns",
            {
                "form": "Although + clause, clause",
                "function": "contrast",
                "explanation": "Contrast two ideas",
                "examples": ["Although it is sunny, it is cold."],
            },
        ),
        (
            "samples",
            {
                "skill": "speaking",
                "prompt": "Describe your city.",
                "response": "My city has many parks.",
                "annotations": [{"quote": "many parks", "note": "A place feature"}],
            },
        ),
        (
            "exercises",
            {
                "question": "interested ___ music",
                "options": ["in", "at"],
                "answer": "in",
                "explanation": "interested in",
            },
        ),
    ],
)
def test_typed_collections_roundtrip_and_reject_wrong_type(client, kind, data):
    payload = {**vocabulary(topic(client)), "data": data}
    saved = client.post(f"/api/ielts/{kind}", json=payload)
    assert saved.status_code == 201, saved.text
    assert saved.json()["data"] == data
    assert client.get(f"/api/ielts/{kind}").json()["items"][0]["id"] == saved.json()["id"]
    assert client.post("/api/ielts/vocabulary", json=payload).status_code == 422


def test_batched_list_does_not_add_queries_for_each_item(client):
    education = topic(client)
    payload = {
        "kind": "vocabulary",
        "items": [vocabulary(education, f"Distinct meaning {i}") for i in range(30)],
    }
    assert client.post("/api/ielts/imports", json=payload).status_code == 201
    counts = []
    for limit in (1, 30):
        selects = []

        def count(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        event.listen(client.app.state.engine, "before_cursor_execute", count)
        try:
            response = client.get("/api/ielts/vocabulary", params={"limit": limit})
            assert response.status_code == 200 and len(response.json()["items"]) == limit
        finally:
            event.remove(client.app.state.engine, "before_cursor_execute", count)
        counts.append(len(selects))
    assert counts == [2, 2]


def test_validation_and_pagination(client):
    education = topic(client)
    assert (
        client.post(
            "/api/ielts/topics", json={"name": "Missing parent", "parent_id": str(uuid4())}
        ).status_code
        == 422
    )
    assert client.post("/api/ielts/topics", json={"name": "Education"}).status_code == 409
    entry = vocabulary(education)
    for bad in (
        {"topic_ids": []},
        {"topic_ids": [education, education]},
        {"source": {"label": "x", "rights_note": ""}},
    ):
        assert client.post("/api/ielts/vocabulary", json={**entry, **bad}).status_code == 422
    entry["data"] = {
        "skill": "writing",
        "prompt": "P",
        "response": "A short response",
        "annotations": [{"quote": "missing", "note": "invalid"}],
    }
    assert client.post("/api/ielts/samples", json=entry).status_code == 422
    entry["data"] = {"question": "Q", "options": ["a", "b"], "answer": "c", "explanation": "E"}
    assert client.post("/api/ielts/exercises", json=entry).status_code == 422
    assert client.get("/api/ielts/vocabulary?limit=101").status_code == 422
    assert client.get("/api/ielts/vocabulary?offset=-1").status_code == 422
    with client.app.state.sessions() as session:
        assert session.scalar(select(LearningItem)) is None


def test_edit_invalidates_review_preserves_snapshot_and_rejects_stale_changes(client):
    payload = vocabulary(topic(client))
    item = client.post("/api/ielts/vocabulary", json=payload).json()
    item_id = item["id"]
    assert (
        client.post(
            f"/api/ielts/items/{item_id}/review",
            json={
                "expected_version": 1,
                "reviewer": "Teacher",
                "note": "Meaning and rights checked",
            },
        ).status_code
        == 200
    )
    changed = {**payload, "expected_version": 1, "title": "Updated adapt"}
    assert client.put(f"/api/ielts/items/{item_id}", json=changed).status_code == 409
    changed["expected_version"] = 2
    changed["source"] = {"label": "New source", "rights_note": "Needs rights review"}
    updated = client.put(f"/api/ielts/items/{item_id}", json=changed)
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "draft" and updated.json()["version"] == 3
    history = client.get(f"/api/ielts/items/{item_id}/revisions").json()
    assert [r["version"] for r in history] == [1, 2, 3]
    assert history[1]["snapshot"]["status"] == "reviewed"
    assert history[1]["snapshot"]["source"]["label"] == "Original test"
    assert history[2]["snapshot"]["source"]["label"] == "New source"
    assert (
        client.post(
            f"/api/ielts/items/{item_id}/brief",
            json={"expected_version": 3, "focus_text": "Adapt means change."},
        ).status_code
        == 409
    )
