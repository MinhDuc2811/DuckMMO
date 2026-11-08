import io

from PIL import Image

from app.schemas import RenderOptions


def test_british_voices_and_white_card_are_available(client):
    catalog = client.get("/api/voices").json()
    voices = {voice["id"]: voice for voice in catalog["voices"]}
    for voice_id in ("en-GB-SoniaNeural", "en-GB-RyanNeural"):
        assert voices[voice_id]["locale"] == "en-GB"
        assert voices[voice_id]["provider"] == "edge"
        assert voices[voice_id]["available"]
        assert RenderOptions(voice=voice_id, expected_content_hash="0" * 64).voice == voice_id
    assert catalog["english_default_voice"] == "en-GB-SoniaNeural"
    response = client.post("/api/production/style-preview", json={"preset": "lesson-card"})
    assert response.status_code == 200, response.text
    with Image.open(io.BytesIO(response.content)) as preview:
        assert preview.size == (240, 426)
        assert preview.getpixel((22, 90)) is not None
