"""Create empty feature test folders without overwriting existing files or fake passing tests."""

import argparse
import re
from pathlib import Path

from test_suite.pytest_plugin import LAYERS


def create_feature(name):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("Use a lowercase Python feature name, for example local_media")
    root = Path(__file__).parent / "features" / name
    if root.exists():
        raise FileExistsError(f"Feature already exists: {root}")
    root.mkdir()
    (root / "__init__.py").touch()
    for layer in LAYERS:
        directory = root / layer
        directory.mkdir()
        (directory / "__init__.py").touch()
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature")
    print(create_feature(parser.parse_args().feature))


if __name__ == "__main__":
    main()
