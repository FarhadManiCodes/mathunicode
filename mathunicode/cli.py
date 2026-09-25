"""CLIs, stdin -> stdout in UTF-8: `mathunicode` (one LaTeX expression -> one line,
render-markdown.nvim's `converter` contract) and `mathunicode-collapse-blocks`
(a Markdown document with its multi-line $$ blocks on one line, CRLF kept)."""

import argparse
import io
import sys

from mathunicode import __version__
from mathunicode.convert import collapse_math_blocks, latex_to_unicode


def _run(argv, prog: str, description: str, convert, keep_crlf: bool) -> int:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)  # only --help/--version, so a bare run never waits on a terminal
    newline = "" if keep_crlf else None  # no newline translation
    if isinstance(sys.stdin, io.TextIOWrapper):  # not a test's StringIO
        sys.stdin.reconfigure(encoding="utf-8", errors="replace", newline=newline)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", newline=newline)
    sys.stdout.write(convert(sys.stdin.read()))
    return 0


def main(argv: list[str] | None = None) -> int:
    return _run(argv, "mathunicode", "LaTeX in, Unicode out.", lambda t: latex_to_unicode(t.strip()), keep_crlf=False)


def main_collapse_blocks(argv: list[str] | None = None) -> int:
    return _run(argv, "mathunicode-collapse-blocks", "Put $$ blocks on one line.", collapse_math_blocks, keep_crlf=True)
