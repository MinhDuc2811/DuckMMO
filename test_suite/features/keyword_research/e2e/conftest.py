import os

import pytest

from e2e.conftest import browser_evidence, studio  # noqa: F401
from test_suite.support.paths import PROJECT_ROOT


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    executable = os.getenv("TEST_CHROMIUM_EXECUTABLE")
    return {**browser_type_launch_args, **({"executable_path": executable} if executable else {})}


@pytest.fixture(autouse=True)
def research_trace(page, request):
    page.context.tracing.start(screenshots=True, snapshots=True)
    yield
    directory = PROJECT_ROOT / "artifacts" / "e2e" / request.node.name
    directory.mkdir(parents=True, exist_ok=True)
    page.context.tracing.stop(path=str(directory / "research-trace.zip"))
