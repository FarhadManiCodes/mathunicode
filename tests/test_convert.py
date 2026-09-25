"""The rendering rules, one table each: input -> expected output."""

import pytest

from mathunicode import collapse_math_blocks, convert_math_spans, latex_to_unicode


def _table(cases: dict[str, str]):
    return pytest.mark.parametrize(("tex", "expected"), list(cases.items()), ids=list(cases))


@_table({
    # Unicode sub/superscripts when every character has one
    "x_{i}": "xᵢ", "x^2": "x²", "10^{-3}": "10⁻³", "\\sum_{i=1}^{n} x_i^2": "∑ᵢ₌₁ⁿ xᵢ²",
    "x^{n + 1}": "xⁿ⁺¹", "A^{T} x": "Aᵀx", "f^{\\prime}(x)": "f′(x)", "90^{\\circ}": "90°",
    # otherwise: one token as is, more than one parenthesized
    "u_{phy}": "u_phy", "\\mathbf{u}_{syn}": "𝐮_syn", "x^{i_j}": "x^(iⱼ)", "e^{-x^2}": "e^(−x²)",
    "e^{-i\\omega t}": "e^(−iωt)", "\\min_{\\Theta, \\Lambda} f": "min_(Θ, Λ) f", "a^{b^c}": "a^(bᶜ)",
    "\\mathbb{R}^{n \\times m}": "ℝ^(n × m)", "\\lim_{n \\to \\infty} a_n": "lim_(n → ∞) aₙ",
    "\\underbrace{a+b}_{n}": "(a + b)ₙ",
})
def test_scripts(tex, expected):
    assert latex_to_unicode(tex) == expected


@_table({
    "\\frac{a+b}{c}": "(a + b)/c", "\\sqrt{x^2+1}": "√(x² + 1)", "\\frac{1}{2}": "1/2",
    "\\binom{n}{k}": "(n; k)", "\\hat{x}_1": "x̂₁", "\\overline{AB}": "A̅B̅", "\\dot{x}(t)": "ẋ(t)",
})
def test_fractions_roots_accents(tex, expected):
    assert latex_to_unicode(tex) == expected


@_table({
    # rows joined by '; ', cells by ', ' -- one line whatever surrounds them
    "A = \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}": "A = (1, 2; 3, 4)",
    "f(x) = \\begin{cases} 1 & x > 0 \\\\ 0 & \\text{else} \\end{cases}": "f(x) = {1, x > 0; 0, else",
    "\\begin{aligned} a &= b \\\\ c &= d \\end{aligned}": "a = b; c = d",
    "\\sum_{\\substack{i<j \\\\ k}} x": "∑_(i < j; k) x",
    "\\left\\{ \\begin{array}{ll} 1 & x > 0 \\\\ 0 & \\text{else} \\end{array} \\right.": "{1, x > 0; 0, else",
    "a \\\\ b": "a; b",
})
def test_rows(tex, expected):
    assert latex_to_unicode(tex) == expected


@_table({
    # infix operators spaced, prefix and fences tight, words spaced
    "a \\to b": "a → b", "a\\leq b": "a ≤ b", "x \\in [0, 1]": "x ∈ [0, 1]", "-x + y": "−x + y",
    "\\det(A) = 0": "det(A) = 0", "\\sin x + \\cos y": "sin x + cos y", "2 \\sin x": "2 sin x",
    "\\operatorname{tr}(A)": "tr(A)", "\\|x\\|^2": "‖x‖²", "|a| + |b|": "|a| + |b|",
    "\\det \\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix} = ad - bc": "det |a, b; c, d| = ad − bc",
    "\\int_0^1 f(x)\\,dx": "∫₀¹ f(x) dx", "\\mathrm{if} x > t": "if x > t",
})
def test_spacing(tex, expected):
    assert latex_to_unicode(tex) == expected


@_table({
    # LaTeX's semantics: source whitespace, comments, fonts; nothing dropped
    "a +\nb": "a + b", "x % note\n+ y": "x + y", "u_{p h y}": "u_phy",
    "\\mathrm{a r g m i n}_x f": "argminₓ f", "\\mathrm{a\\ b}": "a b", "\\foo x": "foo x",
    "\\mathbb{R}": "ℝ", "\\text{is\\_ok}": "is_ok", "50\\%": "50%", "\\left. x \\right|": "x|",
    "\\boldsymbol{u}_{syn}": "𝒖_syn", "\\boldsymbol{\\theta}": "𝜽", "\\mathbf{x}": "𝐱",
})
def test_latex_semantics(tex, expected):
    assert latex_to_unicode(tex) == expected


@_table({
    "5 and": "$5 and $", "50 to train, compared to": "$50 to train, compared to $",
    "...": "$...$", "\\left( unbalanced": "\\left( unbalanced", "2 x": "2x",
})
def test_prose_and_fallback(tex, expected):
    # currency paired as math comes back with its '$'s; what doesn't parse, as it was
    assert latex_to_unicode(tex) == expected


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
    latex_to_unicode("x^{a " * 2000)
    assert time.perf_counter() - start < 2.0
