"""Real, isolated application stack; system Chromium is an explicit fallback."""

import pytest

from e2e.conftest import browser_evidence, studio  # noqa: F401
from test_suite.support.browser import browser_type_launch_args  # noqa: F401


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1440, "height": 1100}}
