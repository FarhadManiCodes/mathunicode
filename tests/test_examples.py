"""The expected renderings written in examples/*.md, checked -- so an example
file can't silently drift from what the code does.

Each '<!-- expect: A / B -->' comment gives the rendering of the math on its
line (or, on a line of its own, of the block just above it), span by span.
'expect: no math' means nothing there may be converted."""

import re
from pathlib import Path

import pytest

from mathunicode import convert_math_spans
from mathunicode.convert import _MATH_SPAN

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.md"))
EXPECT = re.compile(r"(?P<source>.*?)\s*<!-- expect: (?P<expected>.*?) -->\s*$")


def _cases(path: Path):
    lines = path.read_text(encoding="utf-8").split("\n")
    for number, line in enumerate(lines, 1):
        m = EXPECT.match(line)
        if not m:
            continue
        source = m.group("source")
        if not source.strip():
            # A comment on its own line describes the block just above it.
            block: list[str] = []
            for above in reversed(lines[: number - 1]):
                if not above.strip():
                    if block:
                        break
                    continue
                block.insert(0, above)
            source = "\n".join(block)
        yield pytest.param(source, m.group("expected"), id=f"{path.name}:{number}")


@pytest.mark.parametrize(("source", "expected"), [c for p in EXAMPLES for c in _cases(p)])
def test_example_renders_as_expected(source, expected):
    if expected == "no math":
        assert convert_math_spans(source) == source
        return
    spans = [m.group(0) for m in _MATH_SPAN.finditer(source)]
    assert [convert_math_spans(s) for s in spans] == expected.split(" / ")


def test_examples_have_expectations():
    assert EXAMPLES
    assert all(list(_cases(p)) for p in EXAMPLES)
