"""CLIs, stdin -> stdout in UTF-8: `mathunicode` (one LaTeX expression -> one line,
render-markdown.nvim's `converter` contract) and `mathunicode-collapse-blocks`
(a Markdown document with its multi-line $$ blocks on one line, CRLF kept)."""

import argparse
import io
import sys

from mathunicode import __version__
from mathunicode.convert import collapse_math_blocks, latex_to_unicode


def _run(argv, prog: str, description: str, convert, keep_line_endings: bool) -> int:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)  # only --help/--version, so a bare run never waits on a terminal
    newline = "" if keep_line_endings else None
    if isinstance(sys.stdin, io.TextIOWrapper):  # not a test's StringIO
        sys.stdin.reconfigure(encoding="utf-8", errors="replace", newline=newline)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", newline=newline)
    sys.stdout.write(convert(sys.stdin.read()))
    return 0


def main(argv: list[str] | None = None) -> int:
    return _run(argv, "mathunicode", "LaTeX expression on stdin -> Unicode on stdout.",
                lambda tex: latex_to_unicode(tex.strip()), keep_line_endings=False)


def main_collapse_blocks(argv: list[str] | None = None) -> int:
    return _run(argv, "mathunicode-collapse-blocks", "Collapse multi-line $$ blocks of a Markdown document.",
                collapse_math_blocks, keep_line_endings=True)


if __name__ == "__main__":
    raise SystemExit(main())
