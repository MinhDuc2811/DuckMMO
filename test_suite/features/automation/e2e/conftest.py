import pytest

from e2e.conftest import Stack, browser_evidence  # noqa: F401


@pytest.fixture
def studio(tmp_path):
    stack = Stack(tmp_path)
    stack.env["AUTOMATION_FIXTURE_ROOT"] = str(tmp_path)
    original_spawn = stack.spawn

    def spawn(name, args):
        if name == "api":
            args = [
                "test_suite.support.automation_fixture_api:app" if a == "app.main:app" else a
                for a in args
            ]
        return original_spawn(name, args)

    stack.spawn = spawn
    try:
        stack.start()
        yield stack
    finally:
        stack.close()
