"""Actual API with only the MPT child's external HTTP transport replaced for E2E."""

from pathlib import Path

from app.infrastructure.media import moneyprinter
from app.main import app

moneyprinter.BRIDGE = Path(__file__).with_name("mpt_http_fixture.py")
__all__ = ["app"]
