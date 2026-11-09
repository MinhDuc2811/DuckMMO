import hashlib
import json
import subprocess

from tests.test_video import approved_script


def test_actual_mpt_download_assembly_import_and_render_selection(mpt_http, client, tmp_path):
    job_id, digest = approved_script(client)
    payload = {
        "provider": "pexels",
        "terms": ["green city"],
        "seconds": 5,
        "ratio": "9:16",
        "rights_note": "Original HTTP test fixture; not production footage",
        "expected_content_hash": digest,
    }
    response = client.post(f"/api/jobs/{job_id}/moneyprinter/footage", json=payload)
    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset["kind"] == "video" and 5 <= asset["duration"] <= 6
    assert (asset["width"], asset["height"]) == (1080, 1920)
    provenance = asset["provenance"]
    assert provenance["engine"] == "MoneyPrinterTurbo" and provenance["version"] == "1.3.10"
    assert provenance["sources"][0]["source_page"] == "https://www.pexels.com/video/101/"
    assert "fixture-only" not in json.dumps(provenance)
    downloaded = client.get(f"/api/jobs/{job_id}/assets/{asset['id']}/file")
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == asset["sha256"]
    file = tmp_path / "prepared.mp4"
    file.write_bytes(downloaded.content)
    streams = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(file)]
        )
    )["streams"]
    assert not any(s["codec_type"] == "audio" for s in streams)
    queued = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": digest,
            "video_asset_id": asset["id"],
            "visual": {"preset": "lesson-card"},
        },
    )
    assert queued.status_code == 200, queued.text
    assert queued.json()["render_config"]["video_file"] == "input-clip"
    assert client.get(f"/api/jobs/{job_id}").json()["package"]["scenes"]
    assert not list((tmp_path / "moneyprinter").glob("prepare-*/request.json"))
    assert "fixture-only" not in (tmp_path / "moneyprinter" / "config.toml").read_text()
