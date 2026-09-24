"""Tests for the package's public surface."""

import tomllib
from pathlib import Path

import pytest

import mathunicode


def test_version_matches_pyproject():
    if mathunicode.__version__ == "0+unknown":
        pytest.skip("mathunicode is not installed; no package metadata to read")
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    expected = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert mathunicode.__version__ == expected, (
        "installed metadata is stale; reinstall (uv sync / pip install -e .)"
    )
