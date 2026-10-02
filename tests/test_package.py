"""Tests for the package's public surface."""

import subprocess
import sys
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


def _modules_loaded_by(statement: str) -> set[str]:
    code = f"{statement}; import sys; print(*sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return set(out.stdout.split())


@pytest.mark.parametrize("statement", [
    "import mathunicode",
    "import mathunicode.cli",
    "from mathunicode import collapse_math_blocks, convert_math_spans",
    "import mathunicode.markdown",
])
def test_import_stays_light(statement):
    # nvim starts a CLI per formula: the parser (latex2mathml ~40 ms) and importlib.metadata (~15 ms)
    # are loaded by the code that needs them, not by `import mathunicode`.
    heavy = {"latex2mathml", "importlib.metadata", "xml.sax.saxutils", "argparse"}
    assert not heavy & _modules_loaded_by(statement)


def test_public_names_load_lazily():
    ns: dict = {}
    exec("from mathunicode import *", ns)
    assert {"latex_to_unicode", "convert_math_spans", "collapse_math_blocks", "__version__"} <= ns.keys()
    with pytest.raises(AttributeError):
        mathunicode.no_such_name  # noqa: B018
