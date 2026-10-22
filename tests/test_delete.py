from app.db import Job
from app.worker import process_one
from tests.test_pipeline import client, submit  # noqa: F401


def test_delete_and_restore_retains_content(client):  # noqa: F811
    job_id = submit(client).json()["id"]
    assert client.delete(f"/api/jobs/{job_id}").status_code == 409
    client.post(f"/api/jobs/{job_id}/cancel")
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get("/api/jobs").json() == []
    assert client.get("/api/workspace/jobs").json() == []
    assert not process_one(client.app.state.sessions)
    with client.app.state.sessions() as session:
        assert session.get(Job, job_id).package["title"]
    restored = client.post(f"/api/jobs/{job_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "cancelled"
    assert len(client.get("/api/workspace/jobs").json()) == 1
