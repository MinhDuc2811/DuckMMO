"""ASGI entry point; application wiring lives in bootstrap."""

from app.bootstrap import create_app

__all__ = ["create_app", "app"]

app = create_app()
