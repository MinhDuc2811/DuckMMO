"""Explicit test-layer selection; offline runs never silently invoke live TTS."""

from pathlib import Path

import pytest

LAYERS = ("unit", "api", "integration", "screen_flow", "e2e")
FEATURES = Path(__file__).parent / "features"


def pytest_addoption(parser):
    group = parser.getgroup("feature suites")
    group.addoption(
        "--test-layer",
        action="append",
        choices=LAYERS,
        default=[],
        help="Select a layer in test_suite; repeat to combine layers.",
    )
    group.addoption(
        "--feature",
        action="append",
        default=[],
        help="Select a feature folder in test_suite; repeat to combine features.",
    )
    group.addoption("--run-e2e", action="store_true", help="Include new Playwright feature suites.")
    group.addoption(
        "--run-live-tts",
        action="store_true",
        help="Call the real free Edge service; failures are reported as failures.",
    )


def pytest_configure(config):
    for layer in LAYERS:
        config.addinivalue_line("markers", f"{layer}: {layer} feature test layer")
    config.addinivalue_line("markers", "live_tts: calls the real free speech provider")


def pytest_ignore_collect(collection_path, config):
    try:
        parts = collection_path.relative_to(FEATURES).parts
    except ValueError:
        return None
    if len(parts) >= 2 and parts[1] == "e2e":
        return not (config.getoption("--run-e2e") or "e2e" in config.getoption("--test-layer"))
    return None


def pytest_collection_modifyitems(config, items):
    layers, features = config.getoption("--test-layer"), config.getoption("--feature")
    selected, deselected = [], []
    for item in items:
        try:
            parts = Path(item.path).relative_to(FEATURES).parts
        except ValueError:
            parts = ()
        feature, layer = parts[:2] if len(parts) >= 2 else ("", "")
        if layer in LAYERS:
            item.add_marker(getattr(pytest.mark, layer))
        if (layers and layer not in layers) or (features and feature not in features):
            deselected.append(item)
            continue
        if item.get_closest_marker("live_tts") and not config.getoption("--run-live-tts"):
            item.add_marker(
                pytest.mark.skip(reason="Live TTS unrun; enable --run-live-tts explicitly")
            )
        selected.append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
