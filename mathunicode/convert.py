"""LaTeX -> readable Unicode approximation, built on pylatexenc.

pylatexenc's default macro table silently drops or mishandles a handful of
common math macros -- not cosmetically, but as real content loss (e.g.
``\\|x\\|^2`` becomes ``x^2``, losing the norm entirely; ``\\det(A)`` becomes
``(A)``, losing the operator name). The fixes below were found by
systematically testing every macro that actually appears across a real paper
library (149 unique macro names), not guessed.
"""

import re

from pylatexenc.latex2text import (
    LatexNodes2Text,
    MacroTextSpec,
    get_default_latex_context_db,
)


def _build_context_db():
    db = get_default_latex_context_db()
    db.add_context_category(
        "mathunicode-fixes",
        prepend=True,
        macros=[
            MacroTextSpec("|", simplify_repl="‖"),
            MacroTextSpec("coloneqq", simplify_repl=":= "),
            MacroTextSpec("land", simplify_repl="∧ "),
            MacroTextSpec("arg", simplify_repl="arg"),
            MacroTextSpec("Pr", simplify_repl="Pr"),
            MacroTextSpec("circledR", simplify_repl="®"),
            MacroTextSpec("cot", simplify_repl="cot"),
            MacroTextSpec("csc", simplify_repl="csc"),
            MacroTextSpec("det", simplify_repl="det"),
        ],
    )
    return db


_CONTEXT_DB = _build_context_db()


def _normalize_math_spacing(tex: str) -> str:
    """Undo OCR tools' inconsistent spacing around subscripts/superscripts,
    e.g. 'x _ {i}' -> 'x_{i}' and 'u _ {p h y}' -> 'u_{phy}'."""
    tex = re.sub(r"\s*([_^])\s*", r"\1", tex)

    def _collapse(m: "re.Match") -> str:
        return (
            m.group(1)
            + re.sub(r"(?<=[A-Za-z])\s+(?=[A-Za-z])", "", m.group(2))
            + "}"
        )

    return re.sub(r"([_^]\{)([^{}]*)\}", _collapse, tex)


def latex_to_unicode(tex: str) -> str:
    """Convert one bare LaTeX math expression (no $ delimiters) to a
    readable Unicode approximation. Falls back to the original text on any
    parse failure rather than raising, so one malformed expression never
    breaks a larger document/answer being converted."""
    try:
        return LatexNodes2Text(latex_context=_CONTEXT_DB).latex_to_text(
            _normalize_math_spacing(tex)
        )
    except Exception:
        return tex


def convert_math_spans(text: str) -> str:
    """Find $...$/$$...$$ spans in a larger text and convert each in place.

    $$...$$ may span multiple lines (display equations do); $...$ is
    restricted to one line -- real inline math never spans a paragraph
    break, but two unrelated dollar amounts in the same paragraph
    ("costs $50 ... $100") easily could, and matching across them would
    feed nonsense into the converter instead of failing loudly.
    """

    def _sub(m: "re.Match") -> str:
        return latex_to_unicode(m.group(1) or m.group(2))

    return re.sub(r"\$\$(.+?)\$\$|\$([^\n$]+?)\$", _sub, text, flags=re.DOTALL)
