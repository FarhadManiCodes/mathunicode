"""Tests for the package's public surface."""

import tomllib
from pathlib import Path

import mathunicode


def test_version_matches_pyproject():
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    expected = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert mathunicode.__version__ == expected
