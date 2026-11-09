"""Actual upstream Node/canvas/FFmpeg; audio is an explicit synthetic fixture."""

import copy
import io
import zipfile

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from test_suite.support.stickman import project_with_audio


def test_doctor_and_director_export_are_truthful_and_protected(client):
    doctor = client.get("/api/stickman/doctor")
    assert doctor.status_code == 200 and doctor.json()["ready"], doctor.text
    assert doctor.json()["runtime"]["network_checked"] is False
    response = client.post(
        "/api/stickman/director-kit",
        json={
            "source": "A learner discovers a better study habit.",
            "style": "A3",
            "ratio": "9:16",
            "seconds": 30,
        },
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "SKILL.md" in archive.namelist() and "LICENSE" in archive.namelist()
        brief = archive.read("director-request.md").decode()
        assert "A3" in brief and "30 seconds" in brief and "9:16" in brief
        assert "A learner discovers" in brief
    assert client.get("/api/jobs").json() == []
    with TestClient(
        create_app(Settings(database_url=str(client.app.state.engine.url), api_key="fixture-only"))
    ) as protected:
        assert protected.get("/api/stickman/projects").status_code == 401
        assert protected.get("/api/stickman/doctor").status_code == 401


def test_media_paths_are_confined_and_optimistic_edits_are_enforced(client):
    item = project_with_audio(client)
    endpoint = f"/api/stickman/projects/{item['id']}"
    for path in (
        "/etc/passwd",
        "../../outside.wav",
        "https://example.org/audio.wav",
        "inputs/" + "f" * 64 + ".wav",
    ):
        project = copy.deepcopy(item["project"])
        project["voice"]["path"] = path
        assert (
            client.put(
                endpoint, json={"expected_version": item["version"], "project": project}
            ).status_code
            == 422
        )
    project = copy.deepcopy(item["project"])
    project["font"] = "/etc/passwd"
    assert (
        client.put(
            endpoint, json={"expected_version": item["version"], "project": project}
        ).status_code
        == 422
    )
    assert (
        client.put(endpoint, json={"expected_version": 1, "project": item["project"]}).status_code
        == 409
    )
    assert (
        client.post(
            endpoint + "/actions/shell", json={"expected_version": item["version"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            endpoint + "/assets?filename=bad.sh&rights_note=fixture", content=b"echo unsafe"
        ).status_code
        == 422
    )
    assert (
        client.post(
            endpoint + "/assets?filename=empty.wav&rights_note=fixture", content=b""
        ).status_code
        == 422
    )
    assert client.get("/api/jobs").json() == []


def test_other_runtime_styles_validate_without_aliasing_b1_or_generating_paid_voice(client):
    item = project_with_audio(client)
    endpoint = f"/api/stickman/projects/{item['id']}"
    for style in ("B2", "B3", "B4"):
        project = copy.deepcopy(item["project"])
        project["style"] = style
        project["shots"][0]["layers"] = [
            {"type": "line", "points": [[10, 10], [100, 100]], "x": 100, "y": 100}
        ]
        if style == "B3":
            project["television"] = {"enabled": True, "intensity": 0.45}
        if style == "B4":
            project["voice"].update(
                name="Explicit test fixture",
                id="fixture-pcm",
                user_override="Test-only PCM fixture, explicitly not Brian",
                contains_sfx=True,
            )
        saved = client.put(endpoint, json={"expected_version": item["version"], "project": project})
        assert saved.status_code == 200, saved.text
        item = saved.json()
        validated = client.post(
            endpoint + "/actions/validate", json={"expected_version": item["version"], "seconds": 1}
        )
        assert validated.status_code == 200, validated.text
        assert validated.json()["project"]["project"]["style"] == style
        # Start the next iteration from the original B1 shape, avoiding cross-style-only fields.
        item["project"].pop("television", None)
    assert client.get("/api/jobs").json() == []
