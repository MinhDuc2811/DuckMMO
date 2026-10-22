"""Reuse existing isolated settings and migrated SQLite fixtures."""

from tests.conftest import isolate_local_settings  # noqa: F401
from tests.test_pipeline import client  # noqa: F401
