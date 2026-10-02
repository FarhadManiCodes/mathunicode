"""CLIs, stdin -> stdout in UTF-8: `mathunicode` (one LaTeX expression -> one line,
render-markdown.nvim's `converter` contract; it asks a warm server if there is one, see server.py)
and `mathunicode-collapse-blocks` (a Markdown document with its multi-line $$ blocks on one line,
CRLF kept).

nvim starts these once per formula or document, so a bare run imports only what it uses: no
argparse, no parser, no package metadata (those cost ~45 of the 58 ms it used to take)."""

import io
import sys


def _parse(argv: list[str], prog: str, description: str) -> None:
    """Only --help and --version exist; anything else is a usage error. Either way it exits."""
    import argparse

    from mathunicode import __version__

    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)


def _run(argv, prog: str, description: str, convert, keep_crlf: bool) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:  # a bare run never waits on a terminal
        _parse(argv, prog, description)
    newline = "" if keep_crlf else None  # no newline translation
    if isinstance(sys.stdin, io.TextIOWrapper):  # not a test's StringIO
        sys.stdin.reconfigure(encoding="utf-8", errors="replace", newline=newline)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", newline=newline)
    sys.stdout.write(convert(sys.stdin.read()))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["serve"]:
        from mathunicode.server import main as serve

        return serve(argv[1:])
    if argv:  # --help, --version, or a mistake
        _parse(argv, "mathunicode", "LaTeX in, Unicode out. `mathunicode serve --help` for the "
               "warm server that makes it fast.")
    from mathunicode.server import convert_bytes, request

    raw = sys.stdin.buffer.read() if isinstance(sys.stdin, io.TextIOWrapper) else sys.stdin.read().encode()
    out = request(raw)  # a warm server's answer, else convert here
    if out is None:
        out = convert_bytes(raw)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(out.decode("utf-8"))
    return 0


def main_collapse_blocks(argv: list[str] | None = None) -> int:
    from mathunicode.markdown import collapse_math_blocks

    return _run(argv, "mathunicode-collapse-blocks", "Put $$ blocks on one line.", collapse_math_blocks, keep_crlf=True)
