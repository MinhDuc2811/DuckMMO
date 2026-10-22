import copy

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.config import Settings
from app.db import Job
from app.main import create_app
from app.worker import process_one

PACKAGE = {
    "branch": "novel",
    "title": "Chuyến đi đầu tiên",
    "language": "vi",
    "sources": [{"label": "Bản thảo tự viết", "rights_note": "Tác giả sở hữu"}],
    "scenes": [{"narration": "Một buổi sáng, nhân vật bắt đầu hành trình.", "source_indices": [0]}],
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("STUDIO_DATABASE_URL", url)
    monkeypatch.setenv("STUDIO_API_KEY", "")
    monkeypatch.setenv("STUDIO_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    command.upgrade(Config("alembic.ini"), "head")
    api = create_app(Settings(database_url=url, api_key=""))
    with TestClient(api) as client:
        yield client


def submit(client, package=None, key=None):
    return client.post(
        "/api/jobs",
        json={"package": package or PACKAGE},
        headers={"Idempotency-Key": key} if key else {},
    )


@pytest.mark.parametrize("branch", ["novel", "comic", "research"])
def test_complete_review_flow(client, branch):
    package = {**PACKAGE, "branch": branch}
    response = submit(client, package)
    assert response.status_code == 201
    job_id = response.json()["id"]
    assert process_one(client.app.state.sessions)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "awaiting_review"
    assert job["result"]["word_count"] > 0
    assert job["attempts"] == 1
    reviewed = client.post(
        f"/api/jobs/{job_id}/review",
        json={"decision": "approve", "reviewer": "Duc", "note": "Đã kiểm tra bản thảo gốc"},
    )
    assert reviewed.json()["status"] == "approved"
    assert [e["status"] for e in client.get(f"/api/jobs/{job_id}/events").json()] == [
        "queued",
        "running",
        "running",
        "awaiting_review",
        "approved",
    ]
    assert not process_one(client.app.state.sessions)


def test_idempotency_and_conflict(client):
    first = submit(client, key="stable").json()
    assert submit(client, key="stable").json()["id"] == first["id"]
    changed = {**PACKAGE, "title": "Khác"}
    assert submit(client, changed, "stable").status_code == 409
    assert len(client.get("/api/jobs").json()) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"title": "  "},
        {"scenes": []},
        {"sources": []},
        {"branch": "game"},
        {"scenes": [{"narration": "Test", "source_indices": [9]}]},
        {"branch": "research", "scenes": [{"narration": "Unreferenced claim"}]},
    ],
)
def test_invalid_packages_rejected(client, change):
    assert submit(client, {**copy.deepcopy(PACKAGE), **change}).status_code == 422


def test_review_gate_and_retry_gate(client):
    job_id = submit(client).json()["id"]
    payload = {"decision": "approve", "reviewer": "Duc", "note": "Reviewed"}
    assert client.post(f"/api/jobs/{job_id}/review", json=payload).status_code == 409
    assert client.post(f"/api/jobs/{job_id}/retry").status_code == 409
    process_one(client.app.state.sessions)
    payload["decision"] = "reject"
    assert client.post(f"/api/jobs/{job_id}/review", json=payload).json()["status"] == "rejected"
    assert client.post(f"/api/jobs/{job_id}/review", json=payload).status_code == 409


def test_failure_retry_limit(client, monkeypatch):
    job_id = submit(client).json()["id"]

    def fail(_):
        raise RuntimeError("provider secrets must not reach API responses")

    monkeypatch.setattr("app.worker.preflight", fail)
    for attempt in range(1, 4):
        assert process_one(client.app.state.sessions)
        job = client.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "failed"
        assert job["attempts"] == attempt
        assert "secrets" not in job["error"]
        response = client.post(f"/api/jobs/{job_id}/retry")
        assert response.status_code == (200 if attempt < 3 else 409)


def test_persistence_and_schema(client):
    job_id = submit(client).json()["id"]
    with client.app.state.sessions() as other_session:
        assert other_session.get(Job, job_id).package["title"] == PACKAGE["title"]
    assert {"jobs", "job_events", "alembic_version"} <= set(
        inspect(client.app.state.engine).get_table_names()
    )
    assert client.get("/health").status_code == 200


def test_authentication(client):
    api = create_app(Settings(database_url=str(client.app.state.engine.url), api_key="test-key"))
    with TestClient(api) as secured:
        assert secured.get("/api/jobs").status_code == 401
        assert secured.get("/api/jobs", headers={"X-API-Key": "wrong"}).status_code == 401
        assert secured.get("/api/jobs", headers={"X-API-Key": "test-key"}).status_code == 200


def test_filters_and_errors(client):
    submit(client)
    assert len(client.get("/api/jobs?status=queued").json()) == 1
    assert client.get("/api/jobs?status=approved").json() == []
    assert client.get("/api/jobs?offset=1").json() == []
    assert client.get("/api/jobs?limit=999").status_code == 422
    assert client.get("/api/jobs/not-a-uuid").status_code == 422
    assert client.get("/api/jobs/00000000-0000-0000-0000-000000000000").status_code == 404


def test_stale_review_cannot_overwrite(client):
    from sqlalchemy.orm.exc import StaleDataError

    job_id = submit(client).json()["id"]
    process_one(client.app.state.sessions)
    with client.app.state.sessions() as first, client.app.state.sessions() as second:
        a, b = first.get(Job, job_id), second.get(Job, job_id)
        a.status = "approved"
        first.commit()
        b.status = "rejected"
        with pytest.raises(StaleDataError):
            second.commit()
