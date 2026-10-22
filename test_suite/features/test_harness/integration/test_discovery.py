"""Test discovery must not turn explicit failures into successful empty runs."""

import os
import shutil
import subprocess
import sys

import pytest

from test_suite.support.paths import PROJECT_ROOT


@pytest.fixture
def harness_project(tmp_path):
    shutil.copyfile(PROJECT_ROOT / "test_suite/pytest_plugin.py", tmp_path / "suite_plugin.py")
    (tmp_path / "conftest.py").write_text('pytest_plugins = ["suite_plugin"]\n')
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = features\n")
    cases = {
        "unit": "def test_unit_case():\n    assert True\n",
        "integration": (
            "import pytest\n@pytest.mark.live_tts\ndef test_live_case():\n"
            '    raise RuntimeError("expected live-service fixture failure")\n'
        ),
        "e2e": (
            'def test_browser_case():\n    raise RuntimeError("expected browser fixture failure")\n'
        ),
    }
    for layer, source in cases.items():
        root = tmp_path / "features" / "speech" / layer
        root.mkdir(parents=True)
        (root / f"test_{layer}_fixture.py").write_text(source)
    return tmp_path


def run_harness(project, *args):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *args],
        cwd=project,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_default_offline_scope_is_explicit(harness_project):
    result = run_harness(harness_project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 1 skipped" in result.stdout
    assert "test_browser_case" not in result.stdout


def test_feature_layer_selection_collects_only_requested_layer(harness_project):
    result = run_harness(
        harness_project, "--feature", "speech", "--test-layer", "unit", "--collect-only"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "test_unit_case" in result.stdout
    assert "test_live_case" not in result.stdout
    assert "test_browser_case" not in result.stdout


def test_explicit_live_failure_cannot_be_skipped(harness_project):
    result = run_harness(
        harness_project, "--feature", "speech", "--test-layer", "integration", "--run-live-tts"
    )
    assert result.returncode == 1
    assert "expected live-service fixture failure" in result.stdout
    assert "1 failed" in result.stdout
    assert "skipped" not in result.stdout


def test_explicit_browser_failure_cannot_be_omitted(harness_project):
    result = run_harness(harness_project, "--feature", "speech", "--test-layer", "e2e")
    assert result.returncode == 1
    assert "expected browser fixture failure" in result.stdout
    assert "1 failed" in result.stdout


def test_unknown_feature_is_not_zero_test_success(harness_project):
    result = run_harness(harness_project, "--feature", "does_not_exist")
    assert result.returncode == 5
    assert "deselected" in result.stdout
