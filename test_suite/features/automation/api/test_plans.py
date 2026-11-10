def test_plan_is_off_until_explicit_authorization_and_verified_channel(
    client, plan_payload, google_http
):
    made = client.post("/api/automation/plans", json=plan_payload)
    assert made.status_code == 201, made.text
    assert made.json()["enabled"] is False
    plan_id = made.json()["id"]
    assert client.put(f"/api/automation/plans/{plan_id}", json={"enabled": True}).status_code == 422
    enabled = client.put(
        f"/api/automation/plans/{plan_id}", json={"enabled": True, "authorize_auto_publish": True}
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["channel_id"] == "fixture-channel"
    assert len(client.get("/api/automation/plans").json()[0]["runs"]) == 1
    assert (
        client.put(f"/api/automation/plans/{plan_id}", json={"enabled": False}).json()["enabled"]
        is False
    )


def test_reject_naive_time_stale_library_and_overfull_short(client, plan_payload):
    payload = {**plan_payload, "first_publish_at": "2030-01-01T12:00:00"}
    assert client.post("/api/automation/plans", json=payload).status_code == 422
    plan_payload["episodes"][0]["expected_version"] = 999
    assert client.post("/api/automation/plans", json=plan_payload).status_code == 409
    plan_payload["episodes"][0]["focus_text"] = "word " * 86
    assert client.post("/api/automation/plans", json=plan_payload).status_code in (409, 422)


def test_vietnam_time_is_saved_as_the_same_utc_instant(client, plan_payload):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    expected = datetime.fromisoformat(plan_payload["first_publish_at"])
    plan_payload["first_publish_at"] = expected.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat()
    response = client.post("/api/automation/plans", json=plan_payload)
    assert response.status_code == 201, response.text
    actual = client.get("/api/automation/plans").json()[0]["runs"][0]["publish_at"]
    assert datetime.fromisoformat(actual) == expected
