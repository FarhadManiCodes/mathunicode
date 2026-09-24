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


_CONVERTER = LatexNodes2Text(latex_context=_build_context_db())


_SPACED_MARKER = re.compile(r"\s*([_^])\s*")
_SPACED_GROUP = re.compile(r"([_^]\{)([^{}]*)\}")
_LETTER_GAP = re.compile(r"(?<=[A-Za-z])\s+(?=[A-Za-z])")


def _normalize_math_spacing(tex: str) -> str:
    """Undo OCR tools' inconsistent spacing around subscripts/superscripts,
    e.g. 'x _ {i}' -> 'x_{i}' and 'u _ {p h y}' -> 'u_{phy}'.

    Two steps with deliberately different scopes:
    1. The first substitution strips whitespace -- including newlines --
       around *every* '_'/'^' in the input, not only script groups. This is
       intentional: it operates on a single already-isolated math expression,
       where any space adjacent to a script marker is an OCR artifact.
    2. The letter-spacing collapse ('p h y' -> 'phy') is then scoped to
       '_{...}'/'^{...}' groups only, since 'a b' in the body could be
       intentional (implicit multiplication)."""
    tex = _SPACED_MARKER.sub(r"\1", tex)

    def _collapse(m: re.Match[str]) -> str:
        return m.group(1) + _LETTER_GAP.sub("", m.group(2)) + "}"

    return _SPACED_GROUP.sub(_collapse, tex)


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


# Script-marker patterns for _unicode_scripts. 'prefix' captures a bare macro
# name immediately before the marker (see the protecting-space note there).
_BRACED_SCRIPT = re.compile(r"(?P<prefix>\\[a-zA-Z]+)?(?P<marker>[_^])\{(?P<content>[^{}]*)\}")
_BARE_SCRIPT = re.compile(r"(?P<prefix>\\[a-zA-Z]+)?(?P<marker>[_^])(?P<content>[0-9A-Za-z+\-=()])")
_SCRIPT_GROUP = re.compile(r"[_^]\{[^{}]*\}")
_MASK_PLACEHOLDER = re.compile(r"\x00(\d+)\x00")


def _scriptify(content: str, mapping: dict[str, str]) -> str | None:
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

    def _replace(m: re.Match[str]) -> str:
        prefix = m.group("prefix") or ""
        content = m.group("content")
        mapping = _SUB_MAP if m.group("marker") == "_" else _SUP_MAP
        converted = None if "\\" in content else _scriptify(content, mapping)
        if converted is None:
            return m.group(0)
        sep = " " if prefix else ""
        return prefix + sep + converted

    tex = _BRACED_SCRIPT.sub(_replace, tex)

    # Any '_{...}'/'^{...}' group still present here failed the braced pass
    # (a backslash, or a character with no Unicode script form) and must be
    # left whole -- mask it so the bare pass below can't reach *inside* it and
    # do a partial conversion, e.g. the '_j' of a surviving '^{i_j}' becoming
    # '^{iⱼ}'. The '\x00N\x00' placeholder can't appear in real LaTeX and
    # contains no '_'/'^', so it's inert to the bare regex.
    saved: list[str] = []

    def _mask(m: re.Match[str]) -> str:
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    tex = _SCRIPT_GROUP.sub(_mask, tex)
    tex = _BARE_SCRIPT.sub(_replace, tex)
    return _MASK_PLACEHOLDER.sub(lambda m: saved[int(m.group(1))], tex)


_WORD = re.compile(r"[A-Za-z]{2,}")


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
    return len(_WORD.findall(content)) >= 3


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
        return _CONVERTER.latex_to_text(tex)
    except Exception:
        return tex


_MATH_SPAN = re.compile(
    r"(?<!\\)\$\$(.+?)(?<!\\)\$\$|(?<!\\)\$([^\n$]+?)(?<!\\)\$",
    flags=re.DOTALL,
)


def convert_math_spans(text: str) -> str:
    """Find $...$/$$...$$ spans in a larger text and convert each in place.

    $$...$$ may span multiple lines (display equations do); $...$ is
    restricted to one line -- real inline math never spans a paragraph
    break, but two unrelated dollar amounts in the same paragraph
    ("costs $50 ... $100") easily could, and matching across them would
    feed nonsense into the converter instead of failing loudly.

    A '$' escaped as '\\$' (the standard Markdown escape for a literal dollar)
    never opens or closes a span -- the '(?<!\\)' guards keep escaped currency
    like "\\$5 ... \\$10" from being read as one span and mangled.
    """

    def _sub(m: re.Match[str]) -> str:
        # group(1) is the $$-display body, group(2) the $-inline body. The
        # prose guard is applied here (not inside latex_to_unicode) so the
        # exact original delimiter level -- '$$' vs '$' -- can be restored on
        # a false positive, rather than always collapsing to a single '$'.
        display = m.group(1) is not None
        content = m.group(1) if display else m.group(2)
        if _looks_like_prose(content):
            delim = "$$" if display else "$"
            return f"{delim}{content}{delim}"
        return latex_to_unicode(content)

    return _MATH_SPAN.sub(_sub, text)


_BARE_DOLLARS_LINE = re.compile(r"^\s*\$\$\s*$")


def collapse_math_blocks(text: str) -> str:
    """Collapse $$ / content / $$ blocks (a bare '$$' line, one or more
    content lines, another bare '$$' line) into a single line
    '$$ content $$'.

    Some Markdown renderers (confirmed directly for render-markdown.nvim's
    LaTeX handler: position="center" is the only mode that actually conceals
    the raw source, and it's silently overridden to a non-concealing mode
    whenever the equation's node spans more than one buffer line) only hide
    the raw $$...$$ source and show the rendered replacement when the
    equation is written on a single source line. A multi-line block, even
    though it's the same equation, ends up showing both the raw text and
    the render side by side with no config fix available -- rewriting it
    onto one line is the only way to get concealment for that equation.
    """
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        if _BARE_DOLLARS_LINE.match(lines[i]):
            content: list[str] = []
            j = i + 1
            while j < len(lines) and not _BARE_DOLLARS_LINE.match(lines[j]):
                content.append(lines[j].strip())
                j += 1
            if j < len(lines) and content:
                result.append("$$ " + " ".join(content) + " $$")
                i = j + 1
                continue
            # no matching closing $$ (or an empty $$/$$ block) -- unchanged
            result.append(lines[i])
            i += 1
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)
