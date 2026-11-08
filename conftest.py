"""Load the shared test configuration for legacy and feature suites."""

from test_suite.support.browser import browser_type_launch_args  # noqa: F401

pytest_plugins = ["test_suite.pytest_plugin"]
