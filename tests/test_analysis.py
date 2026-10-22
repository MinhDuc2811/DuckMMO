import json

import httpx
import pytest

from app.schemas import ContentPackage
from app.services.analysis import AnalysisFailure, analyse
from app.worker import process_one
from tests.test_pipeline import client  # noqa: F401


def package():
    return ContentPackage(
        title="Story",
        branch="novel",
        sources=[{"label": "Source", "rights_note": "Test"}],
        scenes=[{"narration": "Original", "source_indices": [0]}],
        source_documents=[
            {
                "title": "Source",
                "source_url": "https://any.example/story",
                "content": "Original source text",
            }
        ],
    )


def test_ai_missing_configuration_is_explicit(monkeypatch):
    for name in ("BASE_URL", "MODEL", "API_KEY"):
        monkeypatch.setenv(f"STUDIO_ANALYSIS_{name}", "")
    with pytest.raises(AnalysisFailure, match="chưa phân tích AI"):
        analyse(package())


def test_ai_validated_output_and_source_payload(monkeypatch):
    monkeypatch.setenv("STUDIO_ANALYSIS_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("STUDIO_ANALYSIS_MODEL", "configured-model")
    monkeypatch.setenv("STUDIO_ANALYSIS_API_KEY", "test-placeholder")
    calls = []

    def post(self, url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Summary",
                                    "key_points": ["Point"],
                                    "video_content": "Narration",
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    result = analyse(package())
    assert result["video_content"] == "Narration"
    assert result["ai_generated"]
    assert calls[0][0] == "https://provider.example/v1/chat/completions"
    assert "Original source text" in calls[0][1]["json"]["messages"][1]["content"]


def test_analysis_failure_keeps_sources_and_blocks_review(client, monkeypatch):  # noqa: F811
    calls = []

    def imported(url):
        calls.append(url)
        return {"title": "Source", "source_url": url, "content": "Raw source preserved"}

    monkeypatch.setattr("app.worker.import_url", imported)

    def failed(_):
        raise AnalysisFailure("AI unavailable")

    monkeypatch.setattr("app.worker.analyse", failed)
    job = client.post("/api/import/web", json={"url": "https://any.example/story"}).json()
    process_one(client.app.state.sessions)
    saved = client.get(f"/api/jobs/{job['id']}").json()
    assert saved["status"] == "failed"
    assert saved["package"]["source_documents"][0]["content"] == "Raw source preserved"
    assert saved["error"] == "AI unavailable"
    assert (
        client.post(
            f"/api/jobs/{job['id']}/review",
            json={"reviewer": "User", "note": "Checked", "decision": "approve"},
        ).status_code
        == 409
    )
    monkeypatch.setattr(
        "app.worker.analyse",
        lambda _: {
            "type": "ai",
            "ai_generated": True,
            "summary": "Summary",
            "key_points": ["Point"],
            "video_content": "Actual analysis output",
        },
    )
    client.post(f"/api/jobs/{job['id']}/retry")
    process_one(client.app.state.sessions)
    ready = client.get(f"/api/jobs/{job['id']}").json()
    assert ready["status"] == "awaiting_review"
    assert ready["package"]["video_content"] == "Actual analysis output"
    assert len(calls) == 1  # Retry analysis reuses the raw source, does not recrawl.
