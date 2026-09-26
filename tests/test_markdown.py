"""Finding math in Markdown: input -> expected output."""

import pytest

from mathunicode import collapse_math_blocks, convert_math_spans


def _table(cases: dict[str, str]):
    return pytest.mark.parametrize(("tex", "expected"), list(cases.items()), ids=list(cases))


@_table({
    "pay $5 or $6": "pay $5 or $6", "costs $5-$10": "costs $5-$10", "pay $5 or $x$ now": "pay $5 or x now",
    "The $ sign is used a lot, $x$": "The $ sign is used a lot, x", "0.20$\\pm$0.26": "0.20±0.26",
    "an $ r $ -dim": "an r -dim", "$(K - 1) $ -stage": "(K − 1) -stage", "a $ $ b": "a $ $ b",
    r"cost is \$5 and \$10": r"cost is \$5 and \$10", "$$ \\alpha $$": "α",
    "see `$HOME` and $x$": "see `$HOME` and x", "```ls $HOME``` then $x^2$": "```ls $HOME``` then x²",
    "```\n$a$\n```\n$b^2$": "```\n$a$\n```\nb²",
    "1. ```bash\n   echo $A\n   ```\n$b_1$": "1. ```bash\n   echo $A\n   ```\nb₁",
    "```\r\n$a$\r\n```\r\nthen $x^2$\r\n": "```\r\n$a$\r\n```\r\nthen x²\r\n",
    "## Inline ($...$) and ($$ ... $$), $x_1$": "## Inline ($...$) and ($$ ... $$), x₁",
    "t\n$$\na +\nb\n$$\nu": "t\na + b\nu", "\x010\x01 and $x$": "\x010\x01 and x",
})
def test_convert_math_spans(tex, expected):
    assert convert_math_spans(tex) == expected


@_table({
    "before\n$$\nx_i\n$$\nafter": "before\n$$ x_i $$\nafter",
    "$$\nline one\nline two\n$$": "$$ line one line two $$", "$$\na\n\nb\n$$": "$$ a b $$",
    "- item\n  $$\n  x\n  $$\n": "- item\n  $$ x $$\n", "a\r\n$$\r\nx\r\n$$\r\nb\r\n": "a\r\n$$ x $$\r\nb\r\n",
    "$$\n$$\nprose line\n$$\nmore": "$$\n$$\nprose line\n$$\nmore",  # empty block: no mispairing
    "$$\nx % c\n+ y\n$$": "$$\nx % c\n+ y\n$$", "$$\n50\\%\n$$": "$$ 50\\% $$",
    "```\n$$\nx\n$$\n```\n$$\ny\n$$": "```\n$$\nx\n$$\n```\n$$ y $$", "$$\na\n```\n$$\n```": "$$\na\n```\n$$\n```",
    "$$\nunclosed": "$$\nunclosed", "$$ x $$": "$$ x $$",
})
def test_collapse_math_blocks(tex, expected):
    assert collapse_math_blocks(tex) == expected


def test_no_pathological_slowdown():
    import time

    start = time.perf_counter()
    convert_math_spans(" ".join("`" * k for k in range(1, 400)))
    assert time.perf_counter() - start < 2.0
