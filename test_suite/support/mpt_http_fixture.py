"""Child-process HTTP provider fixture only; native MPT search/download/render stay real."""

import io
import json
import os
import runpy
import sys
from pathlib import Path

import requests

root = Path(os.environ["MPT_FIXTURE_ROOT"]).resolve()
if os.environ.get("STUDIO_DATABASE_URL") not in (
    f"sqlite:///{root / 'test.db'}",
    f"sqlite:///{root / 'studio.db'}",
):
    raise RuntimeError("MPT HTTP fixture requires an explicitly isolated test database")
video = root / "provider.mp4"


def fixture_get(url, *args, **kwargs):
    response = requests.Response()
    response.status_code, response.url = 200, url
    if url.startswith("https://api.pexels.com/v1/videos/search?"):
        assert kwargs.get("headers", {}).get("Authorization") == "fixture-only"
        data = json.dumps(
            {
                "videos": [
                    {
                        "id": 101,
                        "url": "https://www.pexels.com/video/101/",
                        "duration": 6,
                        "width": 1080,
                        "height": 1920,
                        "user": {
                            "id": 7,
                            "name": "Fixture author",
                            "url": "https://www.pexels.com/@fixture/",
                        },
                        "video_files": [
                            {
                                "id": 201,
                                "file_type": "video/mp4",
                                "width": 1080,
                                "height": 1920,
                                "link": "https://videos.pexels.com/fixture.mp4",
                            }
                        ],
                    }
                ]
            }
        ).encode()
        content_type = "application/json"
    elif url == "https://videos.pexels.com/fixture.mp4":
        data, content_type = video.read_bytes(), "video/mp4"
    else:
        raise AssertionError("Unexpected outbound HTTP request in isolated MPT fixture")
    response._content = data
    response.raw = io.BytesIO(data)
    response.headers.update({"Content-Type": content_type, "Content-Length": str(len(data))})
    return response


requests.get = fixture_get
bridge = Path(__file__).resolve().parents[2] / "integrations/moneyprinter-turbo/bridge.py"
sys.argv = [str(bridge), sys.argv[1]]
runpy.run_path(str(bridge), run_name="__main__")
