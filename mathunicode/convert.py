"""LaTeX math -> one line of Unicode: latex2mathml parses it into MathML (the W3C math structure), and
_render gives each element one rule. Public: latex_to_unicode, convert_math_spans, collapse_math_blocks."""

import html
import re
import unicodedata
from bisect import bisect_left
from collections import defaultdict, deque
from itertools import groupby

from latex2mathml.converter import convert_to_element

# Unicode's sub/superscript characters; a script uses them only if all have one.
_SUB = dict(zip("0123456789+-−=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ", strict=True))
_SUP = dict(zip("0123456789+-−=()abcdefghijklmnoprstuvwxyzABDEGHIJKLMNOPRTUVW∘",  # raised ∘ is a degree
                "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ°", strict=True))
_RAISED = set("′″‴°*")  # already raised: appended as they are
# Marks over/under a base -> combining characters ("" for braces: dropped).
_ACCENTS = {"^": "̂", "ˆ": "̂", "‾": "̅", "―": "̅", "¯": "̅", "~": "̃", "˜": "̃", "˙": "̇", "¨": "̈",
            "→": "⃗", "ˇ": "̌", "˘": "̆", "⏟": "", "⏞": "", "︸": "", "︷": ""}
_RELATION = tuple("=<>≤≥≈≡∼→⇒⟹≠∈")  # a table cell starting with one continues an alignment


def _tag(node) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _group(text: str) -> str:
    """Parenthesize text that isn't one character, one word or one (...)."""
    word = all(unicodedata.category(c) in ("Lu", "Ll", "Lo", "Nd", "Mn") for c in text)
    return text if word or len(text) == 1 or re.fullmatch(r"\(.*\)", text) else f"({text})"


def _script(base: str, text: str, marker: str) -> str:
    table, chars = (_SUB if marker == "_" else _SUP), text.replace(" ", "")
    if chars and all(c in table for c in chars):
        return base + "".join(table[c] for c in chars)
    if chars and marker == "^" and set(chars) <= _RAISED:
        return base + chars
    return f"{base}{marker}{_group(text)}" if chars else base


def _upright_word(node) -> str | None:
    """Letters of an upright identifier or a group of them ('\\mathrm{if}')."""
    if _tag(node) == "mi" and node.get("mathvariant") == "normal" and (node.text or "").isalpha():
        return node.text
    letters = [_upright_word(c) for c in node] if _tag(node) in ("mrow", "mstyle") else []
    return "".join(letters) if letters and all(letters) else None


def _render(node) -> str:
    tag, kids, text = _tag(node), list(node), html.unescape(node.text or "")
    if tag == "mtext":
        return re.sub(r"\\([_$%&#{}])", r"\1", text)
    if tag in ("mi", "mn", "mo", "ms"):
        return text.lstrip("\\")  # an unknown macro prints its name, never nothing
    if tag in ("mspace", "mphantom"):
        return " " if tag == "mspace" else ""
    if tag in ("msub", "msup", "munder", "mover") and len(kids) == 2:
        base, over = _render(kids[0]), _render(kids[1])
        if tag in ("munder", "mover") and over.strip() in _ACCENTS:
            mark = _ACCENTS[over.strip()]
            return "".join(c + mark for c in base) if mark and 0 < len(base) <= 3 and base.isalnum() else base
        return _script(_group(base), over, "_" if tag in ("msub", "munder") else "^")
    if tag in ("msubsup", "munderover") and len(kids) == 3:
        return _script(_script(_group(_render(kids[0])), _render(kids[1]), "_"), _render(kids[2]), "^")
    if tag == "mfrac" and len(kids) == 2:
        top, bottom = _render(kids[0]), _render(kids[1])
        return f"{top}; {bottom}" if node.get("linethickness") == "0" else f"{_group(top)}/{_group(bottom)}"
    if tag == "msqrt":
        return "√" + _group(_render_row(kids))
    if tag == "mroot" and len(kids) == 2:
        return _script("", _render(kids[1]), "^") + "√" + _group(_render(kids[0]))
    if tag == "mtable":
        return "; ".join(_cells([_render_row(list(td)) for td in tr]) for tr in kids)
    return _render_row(kids)


def _cells(cells: list[str]) -> str:
    """Cells joined by ', ' -- a space if one continues an alignment ('= b') or follows punctuation."""
    out = ""
    for cell in filter(None, cells):
        out += (" " if cell.startswith(_RELATION) or out[-1] in ",;:" else ", ") + cell if out else cell
    return out


def _render_row(kids) -> str:
    """'&' is just an alignment point; rows (line breaks) are joined by '; ': one line."""
    rows: list[list[tuple[str, str]]] = [[]]
    for upright, run in groupby(kids, key=lambda k: _upright_word(k) is not None):
        if upright:  # a run of upright letters ('\mathrm{if}') is one word
            letters = "".join(map(_upright_word, run))
            rows[-1].append(("word" if len(letters) > 1 else "", letters))
            continue
        for k in run:
            tag, text = _tag(k), _render(k)
            if tag == "mspace" and k.get("linebreak") == "newline":
                rows.append([])
            elif tag == "mi" and k.text == "&":
                continue
            elif (tag in ("mo", "mi") and len(text) > 1 and text.isalpha() and not k.get("mathvariant")) \
                    or (tag in ("msub", "msubsup", "munder", "munderover")
                        and (_tag(k[0]) == "mo" or len(_upright_word(k[0]) or "") > 1)):
                rows[-1].append(("word", text))  # sin, det, ∑ᵢ₌₁ⁿ, lim_(n → ∞), argminₓ
            else:
                rows[-1].append(("op" if tag == "mo" and text else "", text))
    return "; ".join(line for line in map(_join, rows) if line)


def _join(parts: list[tuple[str, str]]) -> str:
    """MathML's form rule: an operator after an operand is infix (spaced), else prefix (tight)."""
    out, operand, bars, last = "", False, 0, ""
    for kind, text in parts:
        category = unicodedata.category(text[0]) if text else ""  # '\\right.' is an empty operator
        opening = category == "Ps" or (text in ("|", "‖") and bars % 2 == 0)
        if kind == "op" and text in ",;":
            out, operand = out.rstrip() + text + " ", False
        elif kind == "op" and opening:
            out, operand = (out.rstrip() if last == "word" and text in "([" else out) + text, False
        elif kind == "op" and (category == "Pe" or text in ("|", "‖")):
            out, operand = out.rstrip() + text, True
        elif kind == "op":
            out, operand = (out.rstrip() + f" {text} ", False) if operand else (out + text, False)
        elif kind == "word":  # spaced from an operand or word before it, not from '(' or a prefix '−'
            gap = " " if (operand or last == "word") and not out.endswith(" ") else ""
            out, operand = out + gap + text + " ", False
        else:
            out, operand = out + text, True
        bars += kind == "op" and text in ("|", "‖")
        last = kind
    return re.sub(r"\s+", " ", out).strip()


_PROSE_WORD = re.compile(r"[A-Za-z]{2,}")
_SYNTAX_PLACEHOLDER = re.compile(r"\s*(?:\.+|…)\s*")  # '$...$' in text *about* math syntax


def _looks_like_prose(content: str) -> bool:
    """Currency paired as math ('$5 and $10' -> '5 and'): no LaTeX, and 3+ words or number + word."""
    if "\\" in content or "_" in content or "^" in content:
        return False
    words = _PROSE_WORD.findall(content)
    return len(words) >= 3 or (bool(words) and content.lstrip()[:1].isdigit())


def latex_to_unicode(tex: str) -> str:
    """One LaTeX expression -> one line of Unicode; what doesn't parse comes
    back as it was. Prose comes back in '$...$', with the space before the
    closing '$' (the next amount's sign) put back: '5 and' -> '$5 and $'."""
    try:
        if _SYNTAX_PLACEHOLDER.fullmatch(tex):
            return f"${tex}$"
        return f"${tex.strip()} $" if _looks_like_prose(tex) else _convert(tex)
    except Exception:
        return tex


def _convert(tex: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", _render(convert_to_element(tex))).strip())


# $$...$$, or $...$ on one line: a body starting with a digit must be tight
# and not followed by a digit (currency '$5 or $6' never pairs); any other
# may be padded, as OCR writes it. '\x01' marks masked code.
_MATH_SPAN = re.compile(
    r"(?<!\\)\$\$(?P<display>[^\x01]+?)(?<!\\)\$\$"
    r"|(?<!\\)\$(?:(?P<num>\d(?:[^\n$\x01]*?[^\s\\$\x01])?)\$(?!\d)"
    r"|(?P<inline>(?=[^\n$\x01]*?[^\s$\x01])[^\n$\d\x01][^\n$\x01]*?)(?<!\\)\$)")
# A fence may follow indentation and list/blockquote markers ('1. ```bash').
_FENCED_CODE = re.compile(
    r"^[ \t]*(?:(?:[-*+]|\d+[.)])[ \t]+|>[ \t]?)*(?P<fence>(?P<bt>`{3,})(?=[^`\n]*$)|~{3,}).*?"
    r"(?:^[ \t]*(?:>[ \t]?)*(?P=fence)(?(bt)`*|~*)[ \t]*\r?$|\Z)", re.MULTILINE | re.DOTALL)


def _mask_code(text: str, saved: list[str]) -> str:
    """Code's '$'s aren't math: fences, then `...` spans (a backtick run closed by
    the next equal run in its paragraph; a linear scan) become '\x01N\x01'."""
    if "\x01" in text:  # the sentinel is already there: masking would be ambiguous
        return text

    def keep(code: str) -> str:
        saved.append(code)
        return f"\x01{len(saved) - 1}\x01"

    text = _FENCED_CODE.sub(lambda m: keep(m.group(0)), text)
    runs = [m.span() for m in re.finditer(r"`+", text)]
    later: defaultdict[int, deque[int]] = defaultdict(deque)
    for i, (start, end) in enumerate(runs):
        later[end - start].append(i)
    breaks = [m.start() for m in re.finditer(r"\n[ \t\r]*\n", text)]
    parts, pos, i = [], 0, 0
    while i < len(runs):
        start, end = runs[i]
        same = later[end - start]
        while same and same[0] <= i:
            same.popleft()
        k = bisect_left(breaks, end)
        if same and (k == len(breaks) or breaks[k] >= runs[same[0]][0]):
            parts += [text[pos:start], keep(text[start : runs[same[0]][1]])]
            pos, i = runs[same[0]][1], same[0] + 1
        else:
            i += 1
    return "".join(parts) + text[pos:]


def _unmask(text: str, saved: list[str]) -> str:
    return re.sub(r"\x01(\d+)\x01", lambda m: saved[int(m.group(1))], text) if saved else text


def convert_math_spans(text: str) -> str:
    """Convert each $...$/$$...$$ span of Markdown in place, leaving escaped
    '\\$', code, prose, syntax placeholders and unparsable spans as written."""
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
