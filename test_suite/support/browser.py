"""Use an explicitly configured/system Chromium when the bundled browser is absent."""

import os
import shutil
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, browser_name):
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if browser_name == "chromium":
        executable = executable or shutil.which("chromium")
    if executable:
        if browser_name != "chromium" or not Path(executable).is_file():
            raise pytest.UsageError(f"Invalid Chromium executable: {executable}")
        return {**browser_type_launch_args, "executable_path": executable}
    return browser_type_launch_args
