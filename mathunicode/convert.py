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


# Unicode has no dedicated subscript/superscript glyph for every character --
# notably missing: b,c,d,f,g,q,w,y,z (subscript), any uppercase letter, and
# any Greek letter (either script). These maps cover exactly what exists.
_SUB_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
    "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}
_SUP_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ",
    "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
    "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
}


def _scriptify(content: str, mapping: dict) -> "str | None":
    """Convert content to true Unicode sub/superscript chars if every
    character has one; None if not (caller keeps the current '_word' text --
    no partial conversions, e.g. 'phy' stays 'phy', never 'ₚhy')."""
    if not content or any(c not in mapping for c in content):
        return None
    return "".join(mapping[c] for c in content)


def _unicode_scripts(tex: str) -> str:
    """Replace _{...}/^{...} groups (and bare _x/^x) with true Unicode
    sub/superscript characters when every character in the group has one,
    e.g. '_{int}' -> 'ᵢₙₜ', '_1' -> '₁'. Left untouched (pylatexenc's own
    '_word' fallback applies later) when not fully representable, and
    skipped entirely if the group contains a macro (backslash) -- that
    needs pylatexenc's own expansion first, and Greek letters have no
    Unicode subscript forms anyway, so it would never apply to them
    regardless.

    A macro name immediately followed by the substituted Unicode
    characters (e.g. '\\sum_{i=1}' with no space before the underscore)
    would otherwise glue onto it -- pylatexenc reads '\\sumᵢ₌₁' as one
    (unknown, dropped) macro name, silently losing the \\sum entirely. When
    a bare macro name (\\[a-zA-Z]+) immediately precedes the match, a
    protecting space is inserted before the substitution; LaTeX itself
    already treats a space there as insignificant (a control word always
    consumes one trailing space), so this never changes the parsed
    meaning, only guards tokenization.
    """

    def _braced(m: "re.Match", mapping: dict) -> str:
        prefix, content = m.group(1) or "", m.group(2)
        if "\\" in content:
            return m.group(0)
        converted = _scriptify(content, mapping)
        if converted is None:
            return m.group(0)
        sep = " " if prefix else ""
        return prefix + sep + converted

    def _bare(m: "re.Match", mapping: dict) -> str:
        prefix, ch = m.group(1) or "", m.group(2)
        converted = mapping.get(ch)
        if converted is None:
            return m.group(0)
        sep = " " if prefix else ""
        return prefix + sep + converted

    tex = re.sub(r"(\\[a-zA-Z]+)?_\{([^{}]*)\}", lambda m: _braced(m, _SUB_MAP), tex)
    tex = re.sub(r"(\\[a-zA-Z]+)?\^\{([^{}]*)\}", lambda m: _braced(m, _SUP_MAP), tex)
    tex = re.sub(r"(\\[a-zA-Z]+)?_([0-9A-Za-z+\-=()])", lambda m: _bare(m, _SUB_MAP), tex)
    tex = re.sub(r"(\\[a-zA-Z]+)?\^([0-9A-Za-z+\-=()])", lambda m: _bare(m, _SUP_MAP), tex)
    return tex


def _looks_like_prose(content: str) -> bool:
    """Guard against $...$ span detection (both this package's own
    convert_math_spans and, confirmed directly via treesitter, tree-sitter-
    markdown's own inline-math grammar) pairing the first '$' with
    whichever '$' comes next, regardless of what's between them -- e.g.
    "costs $50 ... $100" gets read as one math span "50 ... $100"->"50 ...".
    Real LaTeX almost always has a macro (backslash) or a sub/superscript
    marker; multi-word prose with neither is almost certainly a false
    positive, not an equation."""
    if "\\" in content or "_" in content or "^" in content:
        return False
    return len(re.findall(r"[A-Za-z]{2,}", content)) >= 3


def latex_to_unicode(tex: str) -> str:
    """Convert one bare LaTeX math expression (no $ delimiters) to a
    readable Unicode approximation. Falls back to the original text on any
    parse failure rather than raising, so one malformed expression never
    breaks a larger document/answer being converted."""
    try:
        if _looks_like_prose(tex):
            # Restore the $ signs a caller (or tree-sitter-markdown) already
            # stripped, so the display ends up identical to the untouched
            # original text instead of silently losing the currency marks.
            return f"${tex}$"
        tex = _normalize_math_spacing(tex)
        tex = _unicode_scripts(tex)
        return LatexNodes2Text(latex_context=_CONTEXT_DB).latex_to_text(tex)
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
