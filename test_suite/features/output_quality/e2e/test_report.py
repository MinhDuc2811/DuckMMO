"""Real browser/API/worker/FFmpeg; speech is explicitly a synthetic PCM fixture."""

import hashlib
import json

import httpx
from playwright.sync_api import expect


def test_rendered_video_exposes_matching_quality_report_before_approval(page, studio):
    studio.env["IELTS_E2E_ISOLATED_DIRECTORY"] = str(studio.directory.resolve())
    studio.worker = studio.spawn("worker", ["-m", "test_suite.support.ielts_fixture_worker"])
    response = httpx.post(
        studio.api_url + "/api/jobs",
        json={
            "package": {
                "branch": "novel",
                "language": "en",
                "title": "Output quality fixture",
                "sources": [{"label": "Original fixture", "rights_note": "Test only"}],
                "scenes": [
                    {
                        "narration": "A short English lesson with one clear example.",
                        "source_indices": [0],
                    }
                ],
            }
        },
    )
    response.raise_for_status()
    job = response.json()
    studio.wait_status(job["id"], "awaiting_review")
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/review",
        json={"decision": "approve", "reviewer": "Fixture", "note": "Original fixture"},
    ).raise_for_status()
    package = studio.job(job["id"])["package"]
    text = package.get("video_content") or "\n\n".join(s["narration"] for s in package["scenes"])
    httpx.post(
        studio.api_url + f"/api/jobs/{job['id']}/render",
        json={
            "voice": "en-US-AriaNeural",
            "expected_content_hash": hashlib.sha256(text.encode()).hexdigest(),
            "visual": {"preset": "lesson-card"},
        },
    ).raise_for_status()
    studio.wait_status(job["id"], "awaiting_video_review")
    rendered = studio.job(job["id"])
    page.goto(studio.ui_url)
    page.get_by_role("button", name="Output quality fixture", exact=True).click()
    expect(
        page.get_by_role("button", name="Tải báo cáo chất lượng JSON", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_text("Phát âm và nội dung bài học vẫn cần người duyệt.", exact=True)
    ).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("button", name="Tải báo cáo chất lượng JSON", exact=True).click()
    report = json.loads(download.value.path().read_text())
    assert report == rendered["video"]["quality"]["output"]
    assert report["sha256"] == rendered["video"]["sha256"]
    assert report["status"] in ("pass", "warn")
    assert any(
        e["dimension"] == "output_full_decode" and e["outcome"] == "pass"
        for e in report["evaluations"]
    )
    assert studio.job(job["id"])["status"] == "awaiting_video_review"
    assert httpx.get(studio.api_url + f"/api/jobs/{job['id']}/youtube").json() == []
