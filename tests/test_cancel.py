import os
import subprocess
import sys
import time

from app.db import Job
from app.worker import claim_one, process_one, recover_interrupted, run_isolated, supervise_job
from tests.test_pipeline import client, submit  # noqa: F401


def test_cancel_queued_is_immediate_and_idempotent(client):  # noqa: F811
    job_id = submit(client).json()["id"]
    assert client.post(f"/api/jobs/{job_id}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/jobs/{job_id}/cancel").json()["status"] == "cancelled"
    assert not process_one(client.app.state.sessions)
    assert client.post(f"/api/jobs/{job_id}/retry").status_code == 409
    events = client.get(f"/api/jobs/{job_id}/events").json()
    assert [e["status"] for e in events] == ["queued", "cancelled"]


def test_cancel_actually_terminates_only_its_child(client):  # noqa: F811
    job_id = submit(client).json()["id"]
    other_id = submit(client).json()["id"]
    sessions = client.app.state.sessions
    with sessions() as session:
        session.get(Job, job_id).status = "running"
        session.commit()
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        assert child.poll() is None
        response = client.post(f"/api/jobs/{job_id}/cancel")
        assert response.json()["status"] == "cancelling"
        started = time.monotonic()
        supervise_job(sessions, job_id, child)
        assert child.poll() is not None
        assert time.monotonic() - started < 5
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "cancelled"
        assert client.get(f"/api/jobs/{other_id}").json()["status"] == "queued"
        assert process_one(sessions)
        assert client.get(f"/api/jobs/{other_id}").json()["status"] == "awaiting_review"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_cancel_during_crawl_cannot_publish_result(client, monkeypatch):  # noqa: F811
    job_id = client.post("/api/import/web", json={"url": "https://any.example/a"}).json()["id"]

    def crawl(url):
        assert client.post(f"/api/jobs/{job_id}/cancel").json()["status"] == "cancelling"
        return {"title": "Should not publish", "content": "Raw text", "source_url": url}

    def forbidden_analysis(_):
        raise AssertionError("Analysis must not run after cancellation")

    monkeypatch.setattr("app.worker.import_url", crawl)
    monkeypatch.setattr("app.worker.analyse", forbidden_analysis)
    process_one(client.app.state.sessions)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "cancelled"
    assert job["result"] is None


def test_workspace_and_restart_recovery(client):  # noqa: F811
    job_id = submit(client).json()["id"]
    with client.app.state.sessions() as session:
        session.get(Job, job_id).status = "cancelling"
        session.commit()
    active = client.get("/api/workspace/jobs").json()
    assert active[0]["id"] == job_id
    assert active[0]["status"] == "cancelling"
    recover_interrupted(client.app.state.sessions)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "cancelled"


def test_finished_job_has_no_process_to_kill(client):  # noqa: F811
    job_id = submit(client).json()["id"]
    process_one(client.app.state.sessions)
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 409


def test_production_worker_executes_in_isolated_process(client):  # noqa: F811
    job_id = submit(client).json()["id"]
    sessions = client.app.state.sessions
    assert claim_one(sessions) == job_id
    run_isolated(sessions, job_id)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "awaiting_review"
