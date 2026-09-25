"""LaTeX -> readable Unicode approximation, built on pylatexenc.

pylatexenc's default macro table silently drops or mishandles a handful of
common math macros -- not cosmetically, but as real content loss (e.g.
``\\|x\\|^2`` becomes ``x^2``, losing the norm entirely; ``\\det(A)`` becomes
``(A)``, losing the operator name). The fixes below were found by
systematically testing every macro that actually appears across a real paper
library (149 unique macro names), not guessed.
"""

import re
from bisect import bisect_left
from collections import defaultdict, deque

from pylatexenc import latexwalker, macrospec
from pylatexenc.latex2text import (
    LatexNodes2Text,
    MacroTextSpec,
    get_default_latex_context_db,
)


def _build_parse_db():
    """Parser-side specs for fixed macros that take arguments -- without one,
    pylatexenc parses '\\pmod{n}' as an argument-less macro followed by a
    separate '{n}' group, and the text spec below never sees the 'n'."""
    db = latexwalker.get_default_latex_context_db()
    db.add_context_category(
        "mathunicode-fixes",
        prepend=True,
        macros=[
            macrospec.std_macro("pmod", False, 1),
            *(macrospec.std_macro(name, False, 2) for name in ("binom", "dbinom", "tbinom")),
        ],
    )
    return db


def _labelled_arrow(arrow: str, label_first: bool):
    """Text for '\\xrightarrow[below]{above}': the 'above' label drawn on the
    arrow's tail, '-f→' (or '←f-' for a left arrow); a bare arrow without
    one. The rarer 'below' label is dropped."""

    def repl(node, l2tobj) -> str:  # pylatexenc passes l2tobj by that name
        above = node.nodeargd.argnlist[1]
        label = l2tobj.nodelist_to_text([above]).strip() if above is not None else ""
        if not label:
            return arrow
        return f"-{label}{arrow}" if label_first else f"{arrow}{label}-"

    return repl


def _build_context_db():
    db = get_default_latex_context_db()
    # Wide accents drawn like their narrow forms, as combining marks on each
    # character ('\\overline{AB}' -> 'A̅B̅'); pylatexenc drops the accent.
    wide_accents = [
        MacroTextSpec(wide, simplify_repl=db.get_macro_spec(narrow).simplify_repl)
        for wide, narrow in (("overline", "bar"), ("widetilde", "tilde"), ("widehat", "hat"))
    ]
    db.add_context_category(
        "mathunicode-fixes",
        prepend=True,
        macros=[
            MacroTextSpec("|", simplify_repl="‖"),
            MacroTextSpec("coloneqq", simplify_repl=":="),
            MacroTextSpec("land", simplify_repl="∧"),
            MacroTextSpec("arg", simplify_repl="arg"),
            MacroTextSpec("Pr", simplify_repl="Pr"),
            MacroTextSpec("circledR", simplify_repl="®"),
            MacroTextSpec("cot", simplify_repl="cot"),
            MacroTextSpec("csc", simplify_repl="csc"),
            MacroTextSpec("det", simplify_repl="det"),
            # Operator names and symbols pylatexenc drops entirely.
            MacroTextSpec("sec", simplify_repl="sec"),
            MacroTextSpec("coth", simplify_repl="coth"),
            MacroTextSpec("lg", simplify_repl="lg"),
            MacroTextSpec("ker", simplify_repl="ker"),
            MacroTextSpec("dim", simplify_repl="dim"),
            MacroTextSpec("deg", simplify_repl="deg"),
            MacroTextSpec("gcd", simplify_repl="gcd"),
            MacroTextSpec("hom", simplify_repl="hom"),
            MacroTextSpec("mod", simplify_repl="mod"),
            MacroTextSpec("bmod", simplify_repl="mod"),
            MacroTextSpec("pmod", simplify_repl="(mod %s)"),
            MacroTextSpec("lor", simplify_repl="∨"),
            MacroTextSpec("neg", simplify_repl="¬"),
            MacroTextSpec("iff", simplify_repl="⟺"),
            MacroTextSpec("implies", simplify_repl="⟹"),
            MacroTextSpec("impliedby", simplify_repl="⟸"),
            MacroTextSpec("gets", simplify_repl="←"),
            MacroTextSpec("colon", simplify_repl=":"),
            MacroTextSpec("colonequals", simplify_repl=":="),
            MacroTextSpec("coloneq", simplify_repl=":="),
            MacroTextSpec("eqqcolon", simplify_repl="=:"),
            MacroTextSpec("eqcolon", simplify_repl="=:"),
            MacroTextSpec("Coloneqq", simplify_repl="::="),
            MacroTextSpec("models", simplify_repl="⊨"),
            MacroTextSpec("vDash", simplify_repl="⊨"),
            MacroTextSpec("bot", simplify_repl="⊥"),
            MacroTextSpec("Box", simplify_repl="□"),
            MacroTextSpec("Diamond", simplify_repl="◇"),
            MacroTextSpec("checkmark", simplify_repl="✓"),
            MacroTextSpec("ddagger", simplify_repl="‡"),
            MacroTextSpec("llbracket", simplify_repl="⟦"),
            MacroTextSpec("rrbracket", simplify_repl="⟧"),
            MacroTextSpec("S", simplify_repl="§"),
            MacroTextSpec("P", simplify_repl="¶"),
            *wide_accents,
            MacroTextSpec("xrightarrow", simplify_repl=_labelled_arrow("→", label_first=True)),
            MacroTextSpec("xleftarrow", simplify_repl=_labelled_arrow("←", label_first=False)),
            *(
                MacroTextSpec(name, simplify_repl="C(%s,%s)")
                for name in ("binom", "dbinom", "tbinom")
            ),
            # amsmath's italic capital Greek; plain Unicode has only upright.
            *(
                MacroTextSpec("var" + name, simplify_repl=char)
                for name, char in zip(
                    "Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega".split(),
                    "ΓΔΘΛΞΠΣΥΦΨΩ",
                )
            ),
        ],
    )
    return db


_PARSE_DB = _build_parse_db()
_CONTEXT_DB = _build_context_db()


# A '_'/'^' script marker. The escaped '\_' (literal underscore) and the
# accent macro '\^' ('\^{o}' -> 'ô') are not script markers; '\\_' (a line
# break, then a real subscript) is.
_MARKER = r"(?<!(?<!\\)\\)[_^]"

# Whitespace before a marker is kept when it is a control space ('\ '). A match
# only starts at the beginning of a whitespace run: starting inside long runs
# too made this quadratic.
_SPACED_MARKER = re.compile(rf"(?:(?<![\s\\])\s+)?({_MARKER})\s*")
_SPACED_GROUP = re.compile(rf"({_MARKER}\{{)([^{{}}]*)\}}")
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


# pylatexenc drops the whitespace after a macro, gluing its output to what
# follows: '\sin x' -> 'sinx', 'a \to b' -> 'a →b'. For operator names and
# relation/arrow/binary-operator symbols, where that space matters, it's kept
# by ending the macro name with '{}' ('\sin{} x' -> 'sin x'). Other macros
# (Greek letters, \nabla, ...) stay tight: '\Delta t' -> 'Δt' reads better
# than 'Δ t' in OCR output that spaces every token.
_WORD_OPERATORS = (
    "sin cos tan cot sec csc sinh cosh tanh coth arcsin arccos arctan "
    "arg deg det dim exp gcd hom inf ker lg lim liminf limsup ln log max min "
    "Pr sup mod bmod"
)
_RELATIONS = (
    "to gets mapsto rightarrow leftarrow leftrightarrow Rightarrow Leftarrow "
    "Leftrightarrow longrightarrow longleftarrow Longrightarrow Longleftarrow "
    "implies impliedby iff in notin ni subset subseteq supset supseteq "
    "le leq ge geq ne neq ll gg approx equiv sim simeq cong propto perp mid "
    "parallel coloneqq colonequals coloneq eqqcolon eqcolon Coloneqq models vDash "
    "land lor wedge vee cdot times div pm mp circ cup cap "
    "setminus oplus otimes"
)
# Both lookaheads start with whitespace, so only whole macro names match
# ('\in' never matches inside '\int').
_SPACED_MACRO = re.compile(
    # A word operator before a letter, digit or macro -- '\sin x', '\log \alpha'
    # but not '\exp (x)' or '\sin \left(', where the space is OCR noise.
    rf"\\(?:{'|'.join(_WORD_OPERATORS.split())})"
    r"(?=\s+(?:[A-Za-z0-9]|\\\||\\(?!left|right|[bB]igg?[lr]?\b)[A-Za-z]))"
    # A relation spaced on both sides, before anything but a script marker or
    # closing brace. A tight 'a\leq b' stays 'a≤b': the space after '\leq'
    # there only ends the macro name. An alignment '&' or a spacing macro
    # ('\quad', '\,', '~', ...) counts as the space before.
    rf"|(?:(?<=[\s&~])|(?<=\\[,;:])|(?<=\\quad)|(?<=\\qquad)|^)\\(?:{'|'.join(_RELATIONS.split())})(?=\s+[^\s_^}}])"
)


# '\colon' is set like punctuation, 'f: X': no space before it, and one after
# (as a control space '\ ') unless nothing follows. A control space before it
# is kept.
_SPACED_COLON = re.compile(r"(?:(?<!(?<!\\)\\)\s+)?\\colon(?![A-Za-z])\s*(?P<next>[^\s}]?)")

# In math mode LaTeX ignores spaces around the thin/medium/thick/negative
# space macros, but pylatexenc prints them next to theirs: 'x\,\to\, y' ->
# 'x →  y'. An escaped backslash ('\\,': line break, comma) isn't one, and a
# control space '\ ' before one is kept. Leading whitespace is matched only
# from the start of its run, which keeps this linear.
_SPACE_AROUND_SPACING_MACRO = re.compile(r"(?:(?<![\s\\])\s+)?(?<!(?<!\\)\\)(\\[,;:!])\s*")


def _keep_space_after_macros(tex: str) -> str:
    tex = _SPACE_AROUND_SPACING_MACRO.sub(r"\1", tex)
    tex = _SPACED_COLON.sub(
        lambda m: "\\colon" + ("\\ " + m.group("next") if m.group("next") else ""), tex
    )
    return _SPACED_MACRO.sub(lambda m: m.group(0) + "{}", tex)


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
_BRACED_SCRIPT = re.compile(rf"(?P<prefix>\\[a-zA-Z]+)?(?P<marker>{_MARKER})\{{(?P<content>[^{{}}]*)\}}")
_BARE_SCRIPT = re.compile(rf"(?P<prefix>\\[a-zA-Z]+)?(?P<marker>{_MARKER})(?P<content>[0-9A-Za-z+\-=()])")
_SCRIPT_GROUP = re.compile(rf"{_MARKER}\{{[^{{}}]*\}}")
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


_PROSE_WORD = re.compile(r"[A-Za-z]{2,}")


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
    return len(_PROSE_WORD.findall(content)) >= 3


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
        return _convert(tex)
    except Exception:
        return tex


def _convert(tex: str) -> str:
    """The conversion pipeline without the prose guard or the fallback, for
    callers that apply both themselves."""
    tex = _normalize_math_spacing(tex)
    tex = _keep_space_after_macros(tex)
    tex = _unicode_scripts(tex)
    # A fresh LatexNodes2Text per call, not a shared one: inside math nodes it
    # temporarily overwrites its own strict_latex_spaces, so concurrent calls
    # on one instance can leave it permanently wrong.
    converter = LatexNodes2Text(latex_context=_CONTEXT_DB)
    return converter.latex_to_text(tex, latex_context=_PARSE_DB)


# Math spans, tried in order at each position. '\x01' is excluded from span
# bodies so a span never reaches into a masked code region (see _mask_code).
_MATH_SPAN = re.compile(
    # $$...$$ display math, possibly multi-line.
    r"(?<!\\)\$\$(?P<display>[^\x01]+?)(?<!\\)\$\$"
    # $...$ inline math by Pandoc's rule: no whitespace just inside either
    # '$', and -- when the body starts with a digit, as currency does -- the
    # closing '$' not followed by a digit, so '$5-$10' never pairs up while
    # '$\pm$0.26' still does.
    r"|(?<!\\)\$(?=(?P<num>\d)?)(?P<inline>(?=[^\s$])[^\n$\x01]*?[^\s\\$\x01])\$(?(num)(?!\d))"
    # ...or whitespace just inside the opening '$', as OCR tools (e.g. MinerU)
    # write inline spans: '$ r $', '$ x _ {i} $', sometimes '$ t\in[0,1]$'.
    # A currency '$' is followed by the amount, never by a space.
    r"|(?<!\\)\$[ \t]+(?P<padded>[^\s$\x01](?:[^\n$\x01]*?[^\s\\$\x01])?)[ \t]*\$"
    # ...or whitespace just inside the closing '$' only ('$(x) \to y $'),
    # accepted only when the body is clearly LaTeX: prose like '$5 or $' can
    # look just like this.
    r"|(?<!\\)\$(?P<tail>(?=[^\s$\d])(?=[^\n$\x01]*?(?:\\[A-Za-z]|[_^]\{))[^\n$\x01]*?[^\s\\$\x01])[ \t]+\$"
)

# What may precede a fence on its line: any indentation, and list-item or
# blockquote markers ('1. ```bash', '> ```'). The goal is masking, not
# rendering, so this is looser than CommonMark's 0-3 spaces.
_FENCE_OPEN_PREFIX = r"[ \t]*(?:(?:[-*+]|\d+[.)])[ \t]+|>[ \t]?)*"
_FENCE_CLOSE_PREFIX = r"[ \t]*(?:>[ \t]?)*"

# A fenced code block: opened by 3+ backticks or tildes (a backtick fence's
# info string can't itself contain a backtick -- '```ls``' on one line is an
# inline code span, not a fence), closed by a fence of the same character at
# least as long, or running to the end of the text if unclosed.
_FENCED_CODE = re.compile(
    rf"^{_FENCE_OPEN_PREFIX}(?P<fence>(?P<bt>`{{3,}})(?=[^`\n]*$)|~{{3,}}).*?"
    rf"(?:^{_FENCE_CLOSE_PREFIX}(?P=fence)(?(bt)`*|~*)[ \t]*$|\Z)",
    flags=re.MULTILINE | re.DOTALL,
)
_BACKTICKS = re.compile(r"`+")
_BLANK_LINE = re.compile(r"\n[ \t]*\n")
_CODE_PLACEHOLDER = re.compile(r"\x01(\d+)\x01")


def _code_span_ranges(text: str) -> list[tuple[int, int]]:
    """(start, end) of each inline code span: a backtick run closed by the
    next run of the same length in the same paragraph (CommonMark). A linear
    scan -- the equivalent regex backtracks badly on many unmatched runs."""
    runs = [(m.start(), m.end()) for m in _BACKTICKS.finditer(text)]
    later_runs: defaultdict[int, deque[int]] = defaultdict(deque)
    for i, (start, end) in enumerate(runs):
        later_runs[end - start].append(i)
    breaks = [m.start() for m in _BLANK_LINE.finditer(text)]
    spans = []
    i = 0
    while i < len(runs):
        start, end = runs[i]
        same_length = later_runs[end - start]
        while same_length and same_length[0] <= i:
            same_length.popleft()
        if same_length:
            j = same_length[0]
            k = bisect_left(breaks, end)
            if k == len(breaks) or breaks[k] >= runs[j][0]:
                spans.append((start, runs[j][1]))
                i = j + 1
                continue
        i += 1  # no closer in this paragraph: a literal backtick run
    return spans


def _mask_code(text: str, saved: list[str]) -> str:
    """Replace Markdown code, whose '$'s are never math, with '\x01N\x01'
    placeholders (originals appended to saved). Text that already contains
    '\x01' is returned unmasked, since its placeholders would be ambiguous."""
    if "\x01" in text:
        return text

    def _mask(code: str) -> str:
        saved.append(code)
        return f"\x01{len(saved) - 1}\x01"

    text = _FENCED_CODE.sub(lambda m: _mask(m.group(0)), text)
    out = []
    pos = 0
    for start, end in _code_span_ranges(text):
        out.append(text[pos:start])
        out.append(_mask(text[start:end]))
        pos = end
    out.append(text[pos:])
    return "".join(out)


def convert_math_spans(text: str) -> str:
    """Find $...$/$$...$$ spans in a larger text and convert each in place.

    $$...$$ may span multiple lines (display equations do); $...$ is
    restricted to one line -- real inline math never spans a paragraph
    break, but two unrelated dollar amounts in the same paragraph
    ("costs $50 ... $100") easily could, and matching across them would
    feed nonsense into the converter instead of failing loudly. Within a
    line, $...$ follows Pandoc's rule, or is padded with spaces the way OCR
    output writes it (see _MATH_SPAN for the exact rules).

    A '$' escaped as '\\$' (the standard Markdown escape for a literal dollar)
    never opens or closes a span -- the '(?<!\\)' guards keep escaped currency
    like "\\$5 ... \\$10" from being read as one span and mangled. Nor does a
    '$' inside Markdown code (`...` spans, ```/~~~ fences), e.g. `echo $HOME`.
    """
    saved: list[str] = []
    text = _mask_code(text, saved)
    out: list[str] = []
    pos = 0
    while m := _MATH_SPAN.search(text, pos):
        content = m.group("display") or m.group("inline") or m.group("padded") or m.group("tail")
        if _looks_like_prose(content):
            # Not math, so leave it. An inline match is left only up to its
            # opening '$': its closing '$' may open a real span ('The $ sign
            # is common, $x$ is not'), so the search resumes right there.
            resume = m.end() if m.group("display") is not None else m.start() + 1
            out.append(text[pos:resume])
            pos = resume
            continue
        try:
            converted = _convert(content.strip())
        except Exception:
            # Leave the span exactly as written, delimiters included.
            converted = m.group(0)
        out.append(text[pos : m.start()])
        out.append(converted)
        pos = m.end()
    out.append(text[pos:])
    text = "".join(out)
    if not saved:
        return text
    return _CODE_PLACEHOLDER.sub(lambda m: saved[int(m.group(1))], text)


_BARE_DOLLARS_LINE = re.compile(r"^(\s*)\$\$\s*$")
_FENCE = re.compile(rf"^{_FENCE_OPEN_PREFIX}(`{{3,}}(?=[^`]*$)|~{{3,}})")
_TEX_COMMENT = re.compile(r"(?<!\\)%")


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

    The collapsed line keeps the opening '$$' line's indentation (so a block
    inside a list item stays in it) and its CRLF ending, if any. Blank content
    lines are dropped. Left unchanged: blocks inside fenced code, blocks with
    no closing '$$', empty blocks, and blocks with a '%' comment -- joining
    their lines would comment out the rest of the equation.
    """
    lines = text.split("\n")
    result: list[str] = []
    fence: str | None = None  # the opening fence while inside fenced code
    i = 0
    while i < len(lines):
        line = lines[i]
        if fence is not None:
            if re.match(rf"^{_FENCE_CLOSE_PREFIX}{re.escape(fence[0])}{{{len(fence)},}}\s*$", line):
                fence = None
        elif fence_match := _FENCE.match(line):
            fence = fence_match.group(1)
        elif opener := _BARE_DOLLARS_LINE.match(line):
            j = i + 1
            while j < len(lines) and not _BARE_DOLLARS_LINE.match(lines[j]):
                j += 1
            if j < len(lines):
                content = [c.strip() for c in lines[i + 1 : j] if c.strip()]
                if content and not any(_TEX_COMMENT.search(c) for c in content):
                    eol = "\r" if lines[j].endswith("\r") else ""
                    result.append(f"{opener.group(1)}$$ {' '.join(content)} $${eol}")
                else:
                    result.extend(lines[i : j + 1])
                i = j + 1
                continue
        result.append(line)
        i += 1
    return "\n".join(result)
