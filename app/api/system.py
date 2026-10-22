import os

from sqlalchemy import text

from app.modules.errors import ApplicationError


def health(engine):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM jobs LIMIT 1"))
    except Exception:
        raise ApplicationError(503, "Database unavailable or migrations not applied")
    return {"status": "ok", "stage": "foundation"}


def capabilities():
    return {
        "preflight": "ready",
        "human_review": "ready",
        "crawl": "http_html",
        "analysis": "structural",
        "tts": "local_sapi_or_edge" if os.name == "nt" else "edge",
        "video": "ffmpeg",
        **dict.fromkeys(["ai_gateway", "ocr", "search"], "not_configured"),
    }
