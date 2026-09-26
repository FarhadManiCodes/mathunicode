"""Math in Markdown: find $...$/$$...$$ spans outside code and convert them in place, or put
multi-line $$ blocks on one line. Public: convert_math_spans, collapse_math_blocks."""

import re

from mathunicode.convert import _SYNTAX_PLACEHOLDER, _convert, _looks_like_prose

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
