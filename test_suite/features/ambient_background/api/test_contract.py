from tests.test_video import approved_script


def test_final_requires_card_and_clip_options_require_owned_clip(client):
    job_id, digest = approved_script(client)
    payload = {"expected_content_hash": digest, "render_quality": "final"}
    assert client.post(f"/api/jobs/{job_id}/render", json=payload).status_code == 422
    payload["visual"] = {"preset": "lesson-card"}
    response = client.post(f"/api/jobs/{job_id}/render", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["render_config"]["render_quality"] == "final"
    payload["background_options"] = {"duration_seconds": 8}
    assert client.post(f"/api/jobs/{job_id}/render", json=payload).status_code == 422


def test_final_crops_original_wallpaper_before_resizing(client):
    import io

    from PIL import Image, ImageDraw, ImageOps

    from app.config import Settings

    original = Image.new("RGB", (3840, 2160), "#112233")
    draw = ImageDraw.Draw(original)
    for x in range(1400, 2440, 5):
        draw.line((x, 0, x, 2159), fill="white", width=2)
    source = io.BytesIO()
    original.save(source, format="PNG")
    job_id, digest = approved_script(client)
    upload = client.post(f"/api/jobs/{job_id}/assets?kind=image", content=source.getvalue())
    assert upload.status_code == 201, upload.text
    queued = client.post(
        f"/api/jobs/{job_id}/render",
        json={
            "expected_content_hash": digest,
            "render_quality": "final",
            "visual": {"preset": "lesson-card"},
            "image_asset_ids": [upload.json()["id"]],
        },
    )
    assert queued.status_code == 200, queued.text
    config = queued.json()["render_config"]
    path = Settings().artifact_dir / job_id / config["run_id"] / config["image_files"][0]
    with Image.open(path) as pinned:
        assert pinned.size == (1080, 1920)
        expected = ImageOps.fit(original, (1080, 1920), method=Image.Resampling.LANCZOS)
        assert pinned.tobytes() == expected.tobytes()
