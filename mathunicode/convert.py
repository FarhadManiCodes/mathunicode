"""LaTeX math -> one line of Unicode: latex2mathml parses it into MathML (the W3C math structure), and
_render gives each element one rule. Public: latex_to_unicode."""

import html
import re
import unicodedata
from itertools import groupby
from xml.etree.ElementTree import Element

from latex2mathml.converter import convert_to_element

# Character data -- sub/superscripts, TeX atom classes, styled letters -- derived from Unicode and
# unicode-math by _build_tables.py.
from mathunicode._tables import CLASS as _CLASS
from mathunicode._tables import STYLED as _STYLED
from mathunicode._tables import SUB as _SUB
from mathunicode._tables import SUP as _SUP

# Marks over/under a base -> combining characters ("" for braces: dropped).
_ACCENTS = {"^": "̂", "ˆ": "̂", "‾": "̅", "―": "̅", "¯": "̅", "~": "̃",
            "˜": "̃", "˙": "̇", "¨": "̈", "→": "⃗", "ˇ": "̌", "˘": "̆",
            "⏟": "", "⏞": "", "︸": "", "︷": ""}
# LaTeX's control symbols in text: an accent marks the next letter (\'e, \"{i}), a spacing one is a
# space (\! \/ \- \@ have no width) and any other prints its character (\_ is _).
_TEXT_ACCENTS = dict(zip("'\"^~`=.", "\u0301\u0308\u0302\u0303\u0300\u0304\u0307", strict=True))
_TEXT_SPACES = dict.fromkeys(",;:\\ \xa0", " ") | dict.fromkeys("!/-@", "")
_CONTROL_SYMBOL = re.compile(rf"\\([{re.escape(''.join(_TEXT_ACCENTS))}])\{{?(\w)\}}?|\\([^A-Za-z])")
_SCRIPTS = ("msub", "msup", "msubsup", "munder", "mover", "munderover")

# TeX's inter-atom spacing (The TeXbook, ch. 18): '1' where a space goes between a left atom (row)
# and a right atom (column), in the order of _ORDER -- but never before punctuation, as in text.
_ORDER = ("Ord", "Op", "Bin", "Rel", "Open", "Close", "Punct", "Inner")
_SPACING = dict(zip(_ORDER, ("01110001", "11010001", "11001001", "11001001", "00000000", "01110001",
                             "11011101", "11111001"), strict=True))
_SPACING["Sign"] = _SPACING["Ord"]  # a prefix sign is an Ord (and attaches to what follows)


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
    """TeX's atom class: a scripted atom has its nucleus's, a fraction or table is Inner, an
    operator name (sin, \\operatorname, an unknown macro) is Op, a fence follows MathML's form."""
    if node.get("form") in ("prefix", "postfix"):  # '\\left', '\\right'
        return "Open" if node.get("form") == "prefix" else "Close"
    if node.tag in _SCRIPTS and len(node):
        return _class(node[0])
    if node.tag in ("mfrac", "mtable"):
        return "Inner"
    if node.tag in ("mrow", "mstyle") and len(node) == 1:
        return _class(node[0])
    text = _text(node) if node.tag in ("mi", "mo") else ""
    if len(text) > 1 and text.isalpha() and not node.get("mathvariant"):
        return "Op"
    return _CLASS.get(text, "Ord") if len(text) == 1 else "Ord"


def _atoms(kids) -> list[list[tuple[str, object]]]:
    """(class, node) per row, without rendering: '&' is only an alignment point, a line break starts
    a row, a run of upright letters is one word, fences like '|' pair up (odd opens, even closes), a Bin with
    no operand before it is a Sign (TeX's Ord, attached to what follows) and before a Rel, Close or
    Punct an Ord; an explicit space is a 'Space' atom."""
    rows: list[list[tuple[str, object]]] = [[]]
    bars, last = 0, None  # last: index of the row's last non-space atom
    for upright, group in groupby(kids, key=lambda k: _upright_word(k) is not None):
        run = list(group)
        if upright:  # one word, standing in for its letters
            word = Element("mi", mathvariant="normal")
            word.text, run = "".join(map(_upright_word, run)), [word]
        for k in run:
            if k.tag == "mspace" and k.get("linebreak") == "newline":
                rows.append([])
                last = None
                continue
            if k.tag == "mi" and k.text == "&":
                continue
            cls = "Space" if k.tag == "mspace" else _class(k)
            if cls == "Fence":  # opens or closes by position ('|x|', and '|x|₁': a scripted atom has its nucleus's)
                cls, bars = ("Open" if bars % 2 == 0 else "Close"), bars + 1
            if cls == "Bin" and (last is None or rows[-1][last][0] in ("Bin", "Op", "Rel", "Open", "Punct", "Sign")):
                cls = "Sign"
            if last is not None and rows[-1][last][0] == "Bin" and cls in ("Rel", "Close", "Punct"):
                rows[-1][last] = ("Ord", rows[-1][last][1])
            rows[-1].append((cls, k))
            last = last if cls == "Space" else len(rows[-1]) - 1
    return rows


def _word(node) -> bool:
    """A multi-letter upright word, or one scripted ('Errₜ'): it never touches a letter or number."""
    nucleus = node[0] if node.tag in _SCRIPTS and len(node) else node
    return len(_upright_word(nucleus) or "") > 1


def _unit(node, script: bool = False) -> bool:
    """Reads as one unit without parentheses: a token (identifier, number, operator, text, upright
    word), a group wholly inside one pair of fences ('(a + b)', '\\left. df/dx \\right|'), or --
    as a base, not a script -- a scripted unit ('xᵢ²')."""
    if node.tag in ("mrow", "mstyle") and len(node) == 1:
        return _unit(node[0], script)
    if node.tag in ("mi", "mn", "mo", "mtext") or _upright_word(node):
        return True
    if node.tag in _SCRIPTS:
        return not script and (not len(node) or _unit(node[0]))
    rows = _atoms(list(node)) if node.tag == "mrow" else []
    classes = [c for c, _ in rows[0] if c != "Space"] if len(rows) == 1 else []
    if len(classes) < 2 or classes[0] != "Open" or classes[-1] != "Close":
        return False
    depth = [0]  # the first fence closes only at the end
    for c in classes:
        depth.append(depth[-1] + {"Open": 1, "Close": -1}.get(c, 0))
    return 0 not in depth[1:-1]


def _script(base: str, script_node, marker: str) -> str:
    text = _render(script_node)
    table, chars = (_SUB if marker == "_" else _SUP), text.replace(" ", "")
    if chars and all(c in table for c in chars):
        return base + "".join(table[c] for c in chars)
    return f"{base}{marker}{text if _unit(script_node, script=True) else f'({text})'}" if chars else base


def _render(node) -> str:
    tag, kids = node.tag, list(node)
    if tag == "mtext":
        return _CONTROL_SYMBOL.sub(lambda m: m[2] + _TEXT_ACCENTS[m[1]] if m[1] else _TEXT_SPACES.get(m[3], m[3]),
                                   html.unescape(node.text or ""))
    if tag in ("mi", "mn", "mo", "ms"):
        style = frozenset(re.split(r"[- ]", (node.get("mathvariant") or "").upper()))
        return "".join(_STYLED.get((style, c), c) for c in _text(node))
    if tag in ("mspace", "mphantom"):
        return " " if tag == "mspace" else ""
    if tag in ("munder", "mover") and len(kids) == 2 and (mark := _ACCENTS.get(_render(kids[1]).strip())) is not None:
        base = _render(kids[0])
        plain = base and all(unicodedata.category(c) in ("Lu", "Ll", "Lo", "Nd") for c in base)
        return "".join(c + mark for c in base) if mark and plain else base
    if tag in _SCRIPTS and len(kids) in (2, 3):
        out = _render(kids[0])
        out = out if not out or _unit(kids[0]) else f"({out})"
        markers = "_^" if len(kids) == 3 else "_" if tag in ("msub", "munder") else "^"
        for script, marker in zip(kids[1:], markers, strict=True):
            out = _script(out, script, marker)
        return out
    if tag == "mfrac" and len(kids) == 2 and node.get("linethickness") == "0":  # a stack ('\\binom')
        return f"{_render(kids[0])}; {_render(kids[1])}"
    if tag == "mfrac" and len(kids) == 2:  # a side is grouped only if it has a top-level Bin, Rel or Punct
        top, bottom = (f"({_render(k)})" if any(c in ("Bin", "Rel", "Punct") for row in _atoms(
            list(k) if k.tag in ("mrow", "mstyle") else [k]) for c, _ in row) else _render(k) for k in kids)
        return f"{top}/{bottom}"
    if tag in ("msqrt", "mroot"):  # an mroot is (radicand, index); an msqrt's children are its radicand
        radicand = kids[:1] if tag == "mroot" else kids
        index = _script("", kids[1], "^") if tag == "mroot" and len(kids) == 2 else ""
        text = _render_row(radicand)
        return f"{index}√{text if len(radicand) == 1 and _unit(radicand[0]) else f'({text})'}"
    if tag == "mtable":
        return "; ".join(_cells([_render_row(list(td)) for td in tr]) for tr in kids)
    return _render_row(kids)


def _cells(cells: list[str]) -> str:
    """Cells joined by ', ' -- a space instead where a cell continues an alignment ('= b') or the
    previous one already ends in a separator (',' or ';')."""
    out = ""
    for cell in filter(None, cells):
        out += (" " if _CLASS.get(cell[0]) == "Rel" or out[-1] in ",;" else ", ") + cell if out else cell
    return out


def _render_row(kids) -> str:
    """Atoms spaced by TeX's table, a word apart from a letter or number, an operator name right
    before its parenthesized argument; rows joined by '; '."""
    lines = []
    for row in _atoms(kids):
        line, left = "", None  # left: the previous atom's (class, node, text)
        for cls, node in row:
            if cls == "Space":
                line += " "
                continue
            text = _render(node)
            # An operator name hugs its argument ('det(A)', 'log₂(n)'); a big operator with limits
            # ('∑ᵢ₌₁ᵐ (…)') or a name whose limits are written out ('lim_(ϵ → 0) (…)') is spaced
            # from what follows -- set in a line, the two would run together. For the same reason a
            # letter never touches a word or a written-out script ('if x', 'β^FR p').
            op, scripted = left is not None and left[0] == "Op", left is not None and left[1].tag in _SCRIPTS
            name = op and _text(left[1][0] if scripted else left[1]).isalpha()
            limits = op and scripted and (not name or bool(re.search(r"[_^]", left[2])))  # not in Unicode scripts
            applied = name and not limits and _CLASS.get(text[:1]) == "Open"
            touching = left is not None and left[2][-1:].isalnum() and text[:1].isalnum()
            spaced = left is not None and left[0] != "Sign" and not applied and (
                limits or _SPACING[left[0]][_ORDER.index("Ord" if cls == "Sign" else cls)] == "1"
                or (touching and (_word(left[1]) or _word(node) or bool(re.search(r"[_^]\w+$", left[2])))))
            line, left = line + (" " if spaced else "") + text, (cls, node, text)
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
