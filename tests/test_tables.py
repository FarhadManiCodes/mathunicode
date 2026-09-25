"""The generated character tables match what _build_tables derives from the current data."""

import unicodedata
from importlib.metadata import version
from pathlib import Path

import pytest

from mathunicode import _build_tables, _tables


def test_tables_match_their_source_data():
    # Each Python carries its own Unicode version, so only the matching one checks; latex2mathml is
    # locked, so a bump without regenerating fails here.
    if _tables.UNICODE_VERSION != unicodedata.unidata_version:
        pytest.skip(f"tables generated with Unicode {_tables.UNICODE_VERSION}")
    assert _tables.LATEX2MATHML_VERSION == version("latex2mathml"), "run `python -m mathunicode._build_tables`"
    assert Path(_tables.__file__).read_text(encoding="utf-8") == _build_tables.source(), (
        "stale tables: run `python -m mathunicode._build_tables`"
    )
