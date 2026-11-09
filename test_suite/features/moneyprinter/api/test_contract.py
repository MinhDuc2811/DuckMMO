from app.contracts.content import content_hash
from tests.test_video import approved_script


def test_missing_configuration_stale_content_and_disabled_providers(client):
    job_id, digest = approved_script(client)
    payload = {
        "terms": ["green city"],
        "seconds": 5,
        "rights_note": "Review source terms",
        "expected_content_hash": "0" * 64,
    }
    assert client.post(f"/api/jobs/{job_id}/moneyprinter/footage", json=payload).status_code == 409
    payload["expected_content_hash"] = digest
    from pydantic import SecretStr

    client.app.state.settings.pexels_api_key = SecretStr("")
    assert client.post(f"/api/jobs/{job_id}/moneyprinter/footage", json=payload).status_code == 409
    payload["provider"] = "openai_image"
    assert client.post(f"/api/jobs/{job_id}/moneyprinter/footage", json=payload).status_code == 422
    payload["provider"] = "pexels"
    payload["terms"] = ["a", "b", "c", "d"]
    assert client.post(f"/api/jobs/{job_id}/moneyprinter/footage", json=payload).status_code == 422
    assert content_hash(client.get(f"/api/jobs/{job_id}").json()["package"]) == digest
