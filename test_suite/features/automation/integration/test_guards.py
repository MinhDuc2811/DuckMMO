from datetime import timedelta

from sqlalchemy import select

from app.infrastructure.persistence.database import AutomationPlan, AutomationRun
from app.modules.automation.runner import tick
from app.modules.automation.service import utc


def test_paused_plan_and_missed_slot_never_create_jobs(client, plan_payload, google_http):
    made = client.post("/api/automation/plans", json=plan_payload).json()
    sessions, settings = client.app.state.sessions, client.app.state.settings
    with sessions() as session:
        run = session.scalar(select(AutomationRun))
        clock = utc(run.publish_at)
    tick(sessions, settings, clock)
    assert client.get("/api/automation/plans").json()[0]["runs"][0]["job_id"] is None
    client.put(
        f"/api/automation/plans/{made['id']}",
        json={"enabled": True, "authorize_auto_publish": True},
    ).raise_for_status()
    tick(sessions, settings, clock + timedelta(hours=1))
    result = client.get("/api/automation/plans").json()[0]["runs"][0]
    assert result["state"] == "error" and result["job_id"] is None
    assert "Lỡ thời điểm" in result["error"]
    assert not any(r.url.path == "/upload/youtube/v3/videos" for r in google_http)


def test_changed_channel_blocks_before_content_creation(client, plan_payload, google_http):
    made = client.post("/api/automation/plans", json=plan_payload).json()
    with client.app.state.sessions() as session:
        plan = session.get(AutomationPlan, made["id"])
        plan.channel_id, plan.enabled = "different-channel", True
        run = session.scalar(select(AutomationRun))
        clock = utc(run.publish_at) - timedelta(minutes=25)
        session.commit()
    tick(client.app.state.sessions, client.app.state.settings, clock)
    result = client.get("/api/automation/plans").json()[0]["runs"][0]
    assert result["state"] == "error" and result["job_id"] is None
    assert "Kênh YouTube" in result["error"]
