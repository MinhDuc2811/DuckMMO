PAYLOAD = {
    "keyword": "FC Online cập nhật",
    "target_date": "2026-10-23",
    "topic_path": ["news", "esport", "fifa-online"],
}


def test_topic_default_is_persisted_and_snapshotted_into_queued_job(client):
    preferences = {
        "profiles": [
            {
                "branch": "research",
                "topic_path": PAYLOAD["topic_path"],
                "preferred_url": "https://official.example/news",
            }
        ]
    }
    saved = client.put("/api/settings/research", json=preferences)
    assert saved.status_code == 200
    assert client.get("/api/settings/research").json() == saved.json()
    response = client.post("/api/import/keyword", json=PAYLOAD)
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "queued" and job["package"]["scenes"] == []
    assert job["package"]["research"]["preferred_url"] == "https://official.example/news"
    assert "23/10/2026" in job["package"]["title"]


def test_keyword_request_validation_and_source_requirement(client):
    assert client.post("/api/import/keyword", json={**PAYLOAD, "keyword": " "}).status_code == 422
    assert (
        client.post("/api/import/keyword", json={**PAYLOAD, "search_web": False}).status_code == 422
    )
    assert (
        client.post("/api/import/keyword", json={**PAYLOAD, "max_sources": 11}).status_code == 422
    )
    assert (
        client.post(
            "/api/import/keyword", json={**PAYLOAD, "preferred_url": "http://10.0.0.1"}
        ).status_code
        == 422
    )


def test_legacy_idempotency_key_survives_optional_research_fields(client):
    import hashlib
    import json

    from app.db import Job
    from tests.test_pipeline import PACKAGE

    headers = {"Idempotency-Key": "legacy-replay"}
    first = client.post("/api/jobs", json={"package": PACKAGE}, headers=headers).json()
    legacy_package = {
        k: v for k, v in first["package"].items() if k not in {"research", "discovery"}
    }
    with client.app.state.sessions() as session:
        job = session.get(Job, first["id"])
        job.request_hash = hashlib.sha256(
            json.dumps(legacy_package, sort_keys=True).encode()
        ).hexdigest()
        session.commit()
    replay = client.post("/api/jobs", json={"package": PACKAGE}, headers=headers)
    assert replay.status_code == 201
    assert replay.json()["id"] == first["id"]
