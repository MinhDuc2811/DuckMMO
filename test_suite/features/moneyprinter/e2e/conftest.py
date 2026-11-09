import shutil

import pytest

from e2e.conftest import Stack, browser_evidence  # noqa: F401
from tests.test_media import clip  # noqa: F401


@pytest.fixture
def studio(tmp_path, clip):  # noqa: F811
    shutil.copyfile(clip, tmp_path / "provider.mp4")
    stack = Stack(tmp_path)
    stack.env.update(
        {
            "MPT_FIXTURE_ROOT": str(tmp_path),
            "STUDIO_MPT_DIR": str(tmp_path / "moneyprinter"),
            "STUDIO_PEXELS_API_KEY": "fixture-only",
        }
    )
    original_spawn = stack.spawn

    def spawn(name, args):
        if name == "api":
            args = [
                "test_suite.support.mpt_fixture_api:app" if a == "app.main:app" else a for a in args
            ]
        return original_spawn(name, args)

    stack.spawn = spawn
    try:
        stack.start()
        yield stack
    finally:
        stack.close()
