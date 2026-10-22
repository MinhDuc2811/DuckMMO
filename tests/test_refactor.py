"""Behavior and architectural boundaries introduced by the modular refactor."""

import ast
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.config import Settings
from app.db import Job, JobEvent
from app.main import create_app
from app.services.ai_connection import load_connection
from tests.test_pipeline import PACKAGE, client, submit  # noqa: F401


def test_workspace_query_count_does_not_grow_with_job_count(client):  # noqa: F811
    first = submit(client).json()["id"]
    engine = client.app.state.engine
    statements = []

    def count(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        response = client.get("/api/workspace/jobs")
        assert response.status_code == 200
        initial_count = len(statements)
        with client.app.state.sessions() as session:
            session.add_all(
                [
                    Job(package=PACKAGE, request_hash=str(index), status="queued")
                    for index in range(100)
                ]
            )
            session.add(JobEvent(job_id=first, status="queued", message="Most recent event"))
            session.commit()
        statements.clear()
        rows = client.get("/api/workspace/jobs").json()
        assert len(rows) == 101  # Active jobs remain visible beyond list pagination.
        assert next(row for row in rows if row["id"] == first)["stage"] == "Most recent event"
        assert len(statements) == initial_count == 3
    finally:
        event.remove(engine, "before_cursor_execute", count)


def test_settings_api_preserves_key_without_returning_it(client):  # noqa: F811
    payload = {"base_url": "https://provider.example/v1", "model": "test", "api_key": "private"}
    saved = client.put("/api/settings/ai", json=payload)
    assert saved.status_code == 200
    assert "api_key" not in saved.json()
    assert "private" not in saved.text
    payload.update(model="replacement", api_key="")
    assert client.put("/api/settings/ai", json=payload).status_code == 200
    connection = load_connection(client.app.state.settings)
    assert connection.api_key.get_secret_value() == "private"
    assert connection.model == "replacement"
    read = client.get("/api/settings/ai")
    assert "api_key" not in read.json()
    assert read.json()["model"] == "replacement"
    payload.update(base_url="file:///invalid", api_key="do-not-echo")
    rejected = client.put("/api/settings/ai", json=payload)
    assert rejected.status_code == 422
    assert "do-not-echo" not in rejected.text
    assert load_connection(client.app.state.settings).model == "replacement"


def test_settings_api_uses_app_configuration_and_authentication(client, tmp_path):  # noqa: F811
    settings = Settings(
        database_url=str(client.app.state.engine.url),
        api_key="protected",
        artifact_dir=tmp_path / "another-app" / "artifacts",
        analysis_base_url="",
        analysis_model="",
        analysis_api_key="",
    )
    with TestClient(create_app(settings)) as other:
        assert other.get("/api/settings/ai").status_code == 401
        assert other.put("/api/settings/ai", json={}).status_code == 401
        response = other.put(
            "/api/settings/ai",
            headers={"X-API-Key": "protected"},
            json={
                "base_url": "https://provider.example/v1",
                "model": "other",
                "api_key": "other-key",
            },
        )
        assert response.status_code == 200
    assert load_connection(settings).model == "other"
    assert not (
        client.app.state.settings.artifact_dir.parent / "settings" / "analysis.json"
    ).exists()


def test_dependency_boundaries():
    root = Path(__file__).resolve().parents[1]
    rules = [
        ("ui", ("app",)),
        ("app/modules", ("fastapi", "app.api", "ui")),
        ("app/contracts", ("fastapi", "sqlalchemy", "streamlit", "app.infrastructure")),
    ]
    violations = []
    for folder, forbidden in rules:
        for path in (root / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                for module in modules:
                    if any(
                        module == prefix or module.startswith(prefix + ".") for prefix in forbidden
                    ):
                        violations.append(
                            f"{path.relative_to(root)}:{node.lineno} imports {module}"
                        )
    assert not violations, "\n".join(violations)


def test_ui_approved_content_keeps_draft_when_switching_to_production(client, monkeypatch):  # noqa: F811
    import httpx
    from streamlit.testing.v1 import AppTest

    from app.worker import process_one

    job = submit(client).json()
    process_one(client.app.state.sessions)
    client.post(
        f"/api/jobs/{job['id']}/review",
        json={
            "decision": "approve",
            "reviewer": "Tester",
            "note": "Reviewed",
        },
    ).raise_for_status()

    def local_request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", local_request)
    app = AppTest.from_file(Path(__file__).parents[1] / "ui/studio.py").run()
    assert not app.exception
    editor = next(area for area in app.text_area if area.label == "Nội dung video của bạn")
    assert editor.value == PACKAGE["scenes"][0]["narration"]
    next(button for button in app.button if button.label == "Tiếp tục dựng video").click().run()
    assert not app.exception
    assert not app.error
    assert app.session_state["workflow_phase"] == "Phase 3 · Sản xuất video"
