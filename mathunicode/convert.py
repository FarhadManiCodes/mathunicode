"""LaTeX math -> one line of Unicode: latex2mathml parses it into MathML (the W3C math structure), and
_render gives each element one rule. Public: latex_to_unicode, convert_math_spans, collapse_math_blocks."""

import html
import re
import unicodedata
from importlib.resources import files
from itertools import groupby
from xml.etree.ElementTree import Element

from latex2mathml.converter import convert_to_element

# Unicode's sub/superscript characters; a script uses them only if all have one.
_SUB = dict(zip("0123456789+-−=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ", strict=True))
_SUP = dict(zip("0123456789+-−=()abcdefghijklmnoprstuvwxyzABDEGHIJKLMNOPRTUVW∘",  # raised ∘ is a degree
                "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ°", strict=True))
_RAISED = set("′″‴°*")  # already raised: appended as they are
# Marks over/under a base -> combining characters ("" for braces: dropped).
_ACCENTS = {"^": "̂", "ˆ": "̂", "‾": "̅", "―": "̅", "¯": "̅", "~": "̃",
            "˜": "̃", "˙": "̇", "¨": "̈", "→": "⃗", "ˇ": "̌", "˘": "̆",
            "⏟": "", "⏞": "", "︸": "", "︷": ""}
_SCRIPTS = ("msub", "msup", "msubsup", "munder", "mover", "munderover")

# TeX's atom class of each symbol, from latex2mathml's copy of unimathsymbols
# (plain TeX's own mathcodes for the four ASCII characters where they differ).
_CLASS = {"/": "Ord", ":": "Rel", "!": "Close"}
_TEX = dict(B="Bin", V="Bin", R="Rel", L="Op", O="Open", C="Close", P="Punct")  # unicode-math class letters
for _line in (files("latex2mathml") / "unimathsymbols.txt").read_text(encoding="utf-8").splitlines():
    _f = _line.split("^")
    if len(_f) > 4 and len(_f[1]) == 1 and not _line.startswith("#"):
        _CLASS.setdefault(_f[1], _TEX.get(_f[4], "Ord"))
# TeX's inter-atom spacing (The TeXbook, ch. 18): '1' where a space goes between a left atom (row)
# and a right atom (column), in the order of _ORDER -- but never before punctuation, as in text.
_ORDER = ("Ord", "Op", "Bin", "Rel", "Open", "Close", "Punct", "Inner")
_SPACING = dict(zip(_ORDER, ("01110001", "11010001", "11001001", "11001001", "00000000", "01110001",
                             "11011101", "11111001"), strict=True))
_SPACING["Sign"] = _SPACING["Ord"]  # a prefix sign is an Ord (and attaches to what follows)
# Unicode's styled letters by (style words, base letter): 𝐱 bold x, ℝ double-struck R.
_STYLED = {(frozenset(re.split(r"[- ]", m[1].replace("BLACK-LETTER", "FRAKTUR"))), unicodedata.normalize("NFKC", c)): c
           for c in map(chr, [*range(0x1D400, 0x1D800), *range(0x2100, 0x2150)])
           if (m := re.match(r"(?:MATHEMATICAL )?(.+?) (?:CAPITAL|SMALL|DIGIT)\b", unicodedata.name(c, "")))}


def _text(node) -> str:
    """A token's text: entities decoded, '~' as '∼' (latex2mathml writes \\sim as an ASCII '~'), and
    an unknown macro's backslash dropped -- it prints its name, never nothing."""
    text = html.unescape(node.text or "")
    return "∼" if text == "~" else text.lstrip("\\")


def _upright_word(node) -> str | None:
    """Letters of an upright identifier or a group of them ('\\mathrm{if}')."""
    if node.tag == "mi" and node.get("mathvariant") == "normal" and (node.text or "").isalpha():
        return node.text
    letters = [_upright_word(c) for c in node] if node.tag in ("mrow", "mstyle") else []
    return "".join(letters) if letters and all(letters) else None


def _class(node) -> str:
    """TeX's atom class: a scripted atom has its nucleus's, a fraction or table is Inner, a
    word (sin, \\mathrm{argmin}) is Op, a group opened by a fence ('\\left(') is Inner."""
    text = _text(node)  # an unknown macro ('\\sech') is an operator name
    if node.get("form") in ("prefix", "postfix"):  # a fence, as MathML marks '\\left', '\\right'
        return "Open" if node.get("form") == "prefix" else "Close"
    if len(_upright_word(node) or "") > 1 or (len(text) > 1 and text.isalpha()):
        return "Op"
    if node.tag in _SCRIPTS and len(node):
        return _class(node[0])
    if node.tag in ("mfrac", "mtable") or (node.tag == "mrow" and len(node) > 1 and _class(node[0]) == "Open"):
        return "Inner"
    if node.tag in ("mrow", "mstyle") and len(node) == 1:
        return _class(node[0])
    return _CLASS.get(text, "Ord") if len(text) == 1 else "Ord"


def _unit(node, script: bool = False) -> bool:
    """Reads as one unit without parentheses: a token (identifier, number, operator, text, upright
    word), a group wholly inside one pair of fences ('(a + b)', '\\left. df/dx \\right|'), or --
    as a base, not a script -- a scripted unit ('xᵢ²')."""
    kids = list(node)
    if node.tag in ("mrow", "mstyle") and len(kids) == 1:
        return _unit(kids[0], script)
    if node.tag in ("mi", "mn", "mo", "mtext") or _upright_word(node):
        return True
    if node.tag in _SCRIPTS:
        return not script and (not kids or _unit(kids[0]))
    bars = [k.tag == "mo" and _text(k) in ("|", "‖") for k in kids]
    if node.tag != "mrow" or len(kids) < 2 or any(bars[1:-1]):
        return False
    if not ((_class(kids[0]) == "Open" or bars[0]) and (_class(kids[-1]) == "Close" or bars[-1])):
        return False
    depths = [0]  # the first fence must close only at the end
    for k in kids[1:-1]:
        depths.append(depths[-1] + ({"Open": 1, "Close": -1}.get(_class(k), 0) if k.tag == "mo" else 0))
    return min(depths) >= 0


def _script(base: str, script_node, marker: str) -> str:
    text = _render(script_node)
    table, chars = (_SUB if marker == "_" else _SUP), text.replace(" ", "")
    if chars and all(c in table for c in chars):
        return base + "".join(table[c] for c in chars)
    if chars and marker == "^" and set(chars) <= _RAISED:
        return base + chars
    return f"{base}{marker}{text if _unit(script_node, script=True) else f'({text})'}" if chars else base


def _render(node) -> str:
    tag, kids, text = node.tag, list(node), html.unescape(node.text or "")
    if tag == "mtext":
        return re.sub(r"\\([_$%&#{}])", r"\1", text)
    if tag in ("mi", "mn", "mo", "ms"):
        style = frozenset(re.split(r"[- ]", (node.get("mathvariant") or "").upper()))
        return "".join(_STYLED.get((style, c), c) for c in _text(node))
    if tag in ("mspace", "mphantom"):
        return " " if tag == "mspace" else ""
    if tag in ("munder", "mover") and len(kids) == 2 and _render(kids[1]).strip() in _ACCENTS:
        base, mark = _render(kids[0]), _ACCENTS[_render(kids[1]).strip()]
        return "".join(c + mark for c in base) if mark and 0 < len(base) <= 3 and base.isalnum() else base
    if tag in _SCRIPTS and len(kids) in (2, 3):
        out = _render(kids[0])
        out = out if not out or _unit(kids[0]) else f"({out})"
        markers = "_^" if len(kids) == 3 else "_" if tag in ("msub", "munder") else "^"
        for script, marker in zip(kids[1:], markers, strict=True):
            out = _script(out, script, marker)
        return out
    if tag == "mfrac" and len(kids) == 2 and node.get("linethickness") == "0":  # a stack ('\\binom')
        return f"{_render(kids[0])}; {_render(kids[1])}"
    if tag == "mfrac" and len(kids) == 2:
        top, bottom = (f"({_render(k)})" if _compound(k) else _render(k) for k in kids)
        return f"{top}/{bottom}"
    if tag in ("msqrt", "mroot"):
        radicand = kids[0] if tag == "mroot" or len(kids) == 1 else node
        index = _script("", kids[1], "^") if tag == "mroot" and len(kids) == 2 else ""
        text = _render(radicand) if radicand is not node else _render_row(kids)
        return f"{index}√{text if _unit(radicand) else f'({text})'}"
    if tag == "mtable":
        return "; ".join(_cells([_render_row(list(td)) for td in tr]) for tr in kids)
    return _render_row(kids)


def _compound(node) -> bool:
    """Has a top-level Bin, Rel or Punct: a fraction's side then needs parentheses ('(a + b)/c')."""
    kids = list(node) if node.tag in ("mrow", "mstyle") else [node]
    return any(cls in ("Bin", "Rel", "Punct") for row in _rows(kids) for cls, _ in row)


def _cells(cells: list[str]) -> str:
    """Cells joined by ', ' -- a space if one continues an alignment ('= b') or follows punctuation."""
    out = ""
    for cell in filter(None, cells):
        out += (" " if _CLASS.get(cell[0]) == "Rel" or out[-1] in ",;:" else ", ") + cell if out else cell
    return out


def _rows(kids) -> list[list[tuple[str, str]]]:
    """(class, text) atoms per row: '&' is only an alignment point, a line break starts a row, a
    run of upright letters is one word, and a Bin with no operand before it is Ord (TeX's rule)."""
    rows: list[list[tuple[str, str]]] = [[]]
    bars = 0  # '|' / '‖' with no fence marking: odd ones open, even ones close
    for upright, group in groupby(kids, key=lambda k: _upright_word(k) is not None):
        run = list(group)
        if upright:  # one word, standing in for its letters
            word = Element("mi", mathvariant="normal")
            word.text, run = "".join(map(_upright_word, run)), [word]
        for k in run:
            if k.tag == "mspace" and k.get("linebreak") == "newline":
                rows.append([])
            elif k.tag == "mspace" and rows[-1]:
                rows[-1][-1] = (rows[-1][-1][0], rows[-1][-1][1] + " ")
            elif (text := _render(k)) and not (k.tag == "mi" and k.text == "&"):
                cls = _class(k)
                if _text(k) in ("|", "‖") and k.tag == "mo" and not k.get("form"):
                    cls, bars = ("Open" if bars % 2 == 0 else "Close"), bars + 1
                if cls == "Bin" and (not rows[-1] or rows[-1][-1][0] in ("Bin", "Op", "Rel", "Open", "Punct", "Sign")):
                    cls = "Sign"  # a prefix sign: an Ord (TeX's rule) that attaches to what follows
                if rows[-1] and rows[-1][-1][0] == "Bin" and cls in ("Rel", "Close", "Punct"):
                    rows[-1][-1] = ("Ord", rows[-1][-1][1])
                rows[-1].append((cls, text))
    return rows


def _render_row(kids) -> str:
    """Atoms spaced by TeX's table; rows joined by '; ', so the output is one line."""
    lines = []
    for row in _rows(kids):
        line = row[0][1] if row else ""
        for (left, _), (right, text) in zip(row, row[1:], strict=False):
            spaced = left != "Sign" and _SPACING[left][_ORDER.index("Ord" if right == "Sign" else right)] == "1"
            line += (" " if spaced else "") + text
        if line.strip():
            lines.append(re.sub(r"\s+", " ", line).strip())
    return "; ".join(lines)


_PROSE_WORD = re.compile(r"[A-Za-z]{2,}")
_SYNTAX_PLACEHOLDER = re.compile(r"\s*(?:\.+|…)\s*")  # '$...$' in text *about* math syntax


def _looks_like_prose(content: str) -> bool:
    """Currency paired as math ('$5 and $10' -> '5 and'): no LaTeX, and 3+ words or number + word."""
    if "\\" in content or "_" in content or "^" in content:
        return False
    words = _PROSE_WORD.findall(content)
    return len(words) >= 3 or (bool(words) and content.lstrip()[:1].isdigit())


def latex_to_unicode(tex: str) -> str:
    """One LaTeX expression -> one line of Unicode; unparsable input comes back as it was (on one
    line), and prose in '$...$' with the next amount's '$' spaced as before ('5 and' -> '$5 and $')."""
    try:
        if _SYNTAX_PLACEHOLDER.fullmatch(tex):
            return f"${tex}$"
        return f"${tex.strip()} $" if _looks_like_prose(tex) else _convert(tex)
    except Exception:
        return " ".join(tex.split())


# A retry for what doesn't parse: no presentational sizing ('\left', '\big'), a doubled script
# split by '{}' (TeX's own recovery), no environment position argument ('[t]').
_TOLERANT = ((r"\\(?:left|right|[bB]igg?[lr]?)(?![A-Za-z])\s*\.?", ""), (r"\}\s*(?=[_^])", "}{}"),
             (r"(\\begin\{\w+\*?\})\[\w*\]", r"\1"))


def _convert(tex: str) -> str:
    try:
        element = convert_to_element(tex)
    except Exception:
        for pattern, replacement in _TOLERANT:
            tex = re.sub(pattern, replacement, tex)
        element = convert_to_element(tex)
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", _render(element)).strip())


# $$...$$, or $...$ on one line: a body starting with a digit is tight and not followed by a digit
# (currency '$5 or $6' never pairs); any other may be padded, as OCR writes it. '\x01' is masked code.
_MATH_SPAN = re.compile(
    r"(?<!\\)\$\$(?P<display>[^\x01]+?)(?<!\\)\$\$"
    r"|(?<!\\)\$(?:(?P<num>\d(?:[^\n$\x01]*?[^\s\\$\x01])?)\$(?!\d)"
    r"|(?P<inline>(?=[^\n$\x01]*?[^\s$\x01])[^\n$\d\x01][^\n$\x01]*?)(?<!\\)\$)")
# A fence may follow indentation and list/blockquote markers ('1. ```bash').
_FENCED_CODE = re.compile(
    r"^[ \t]*(?:(?:[-*+]|\d+[.)])[ \t]+|>[ \t]?)*(?P<fence>(?P<bt>`{3,})(?=[^`\n]*$)|~{3,}).*?"
    r"(?:^[ \t]*(?:>[ \t]?)*(?P=fence)(?(bt)`*|~*)[ \t]*\r?$|\Z)", re.MULTILINE | re.DOTALL)


# Inline code: a backtick run closed by the next equal run in the same paragraph (CommonMark).
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(?:(?!\n[ \t\r]*\n).)+?(?<!`)\1(?!`)", re.DOTALL)


def _mask_code(text: str, saved: list[str]) -> str:
    """Code's '$'s aren't math: fences, then `...` spans become '\x01N\x01' (originals to saved)."""
    if "\x01" in text:  # the sentinel is already there: masking would be ambiguous
        return text

    def keep(code: str) -> str:
        saved.append(code)
        return f"\x01{len(saved) - 1}\x01"

    return _CODE_SPAN.sub(lambda m: keep(m.group(0)), _FENCED_CODE.sub(lambda m: keep(m.group(0)), text))


def _unmask(text: str, saved: list[str]) -> str:
    return re.sub(r"\x01(\d+)\x01", lambda m: saved[int(m.group(1))], text) if saved else text


def convert_math_spans(text: str) -> str:
    """Convert each $...$/$$...$$ span in place; escaped '\\$', code, prose and unparsable spans stay."""
    saved: list[str] = []
    text, out, pos = _mask_code(text, saved), [], 0
    while m := _MATH_SPAN.search(text, pos):
        content = m.group("display") or m.group("num") or m.group("inline")
        placeholder = _SYNTAX_PLACEHOLDER.fullmatch(content)
        if placeholder or _looks_like_prose(content):
            # prose keeps only its opening '$': the closing one may open a real span
            resume = m.end() if placeholder or m.group("display") else m.start() + 1
            out, pos = out + [text[pos:resume]], resume
            continue
        try:
            converted = _convert(content)
        except Exception:
            converted = m.group(0)
        out, pos = out + [text[pos : m.start()], converted], m.end()
    return _unmask("".join(out) + text[pos:], saved)


# A bare '$$' line, content lines, a bare '$$' line (a CRLF ending in group 3).
_DISPLAY_BLOCK = re.compile(
    r"^([ \t]*)\$\$[ \t]*\r?\n((?:(?![ \t]*\$\$[ \t]*\r?$).*\n)*?)[ \t]*\$\$[ \t]*(\r?)$", re.MULTILINE)
_TEX_COMMENT = re.compile(r"(?<!(?<!\\)\\)%")  # '\%' is a percent sign; '\\%' a comment


def collapse_math_blocks(text: str) -> str:
    """Each $$ / content / $$ block onto one line (render-markdown.nvim conceals only one-line
    source), keeping indentation and CRLF; blocks in code, empty, or with a '%' comment stay."""

    def one_line(m: re.Match[str]) -> str:
        content = [c.strip() for c in m.group(2).split("\n") if c.strip()]
        if not content or any(_TEX_COMMENT.search(c) for c in content):
            return m.group(0)
        return f"{m.group(1)}$$ {' '.join(content)} $${m.group(3)}"

    saved: list[str] = []
    return _unmask(_DISPLAY_BLOCK.sub(one_line, _mask_code(text, saved)), saved)
