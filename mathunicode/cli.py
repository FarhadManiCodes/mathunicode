"""CLI entry points: stdin -> stdout, no file-path arguments.

`mathunicode`: one bare LaTeX expression -> Unicode approximation. Matches
the stdin/stdout contract render-markdown.nvim's `converter` list expects
of any named command (see its `Handler.convert()`: pipes text via stdin,
reads stdout, checks exit code 0) -- so pointing that config at
`mathunicode` needs no wrapper script. The output is always one line (see
latex_to_unicode), so render-markdown shows it exactly in place of the
concealed source.

`mathunicode-collapse-blocks`: a whole document -> the same document with
multi-line $$/content/$$ blocks collapsed to single-line form. Kept as a
separate entry point (not a flag on `mathunicode`) since the two have
different input/output contracts -- one expression in, one expression out,
vs. one document in, one document out.

Both read and write UTF-8 whatever the locale (the output is Unicode by
design), and take only --help/--version, so running one by hand doesn't
just sit waiting on the terminal.
"""

import argparse
import io
import logging
import sys

from mathunicode import __version__
from mathunicode.convert import collapse_math_blocks, latex_to_unicode


def _parse_args(argv: list[str] | None, prog: str, description: str) -> None:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)


def _setup_stdio(keep_line_endings: bool) -> None:
    """UTF-8 stdin/stdout regardless of locale; with keep_line_endings, no
    newline translation either, so a CRLF document comes back CRLF. Streams
    replaced by something other than a real text stream (tests) are left
    alone. pylatexenc's parse notes are dropped from stderr: this is a filter,
    and malformed input already falls back to the original text."""
    newline = "" if keep_line_endings else None
    if isinstance(sys.stdin, io.TextIOWrapper):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace", newline=newline)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", newline=newline)
    logging.getLogger("pylatexenc").setLevel(logging.ERROR)


def main(argv: list[str] | None = None) -> int:
    _parse_args(argv, "mathunicode", "Convert one LaTeX math expression on stdin to Unicode on stdout.")
    _setup_stdio(keep_line_endings=False)
    tex = sys.stdin.read().strip()
    sys.stdout.write(latex_to_unicode(tex))
    return 0


def main_collapse_blocks(argv: list[str] | None = None) -> int:
    _parse_args(
        argv,
        "mathunicode-collapse-blocks",
        "Collapse multi-line $$ blocks in the Markdown document on stdin onto single lines.",
    )
    _setup_stdio(keep_line_endings=True)
    text = sys.stdin.read()
    sys.stdout.write(collapse_math_blocks(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
