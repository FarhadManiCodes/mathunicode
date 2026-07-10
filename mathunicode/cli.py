"""CLI entry points: stdin -> stdout, no file-path arguments.

`mathunicode`: one bare LaTeX expression -> Unicode approximation. Matches
the stdin/stdout contract render-markdown.nvim's `converter` list expects
of any named command (see its `Handler.convert()`: pipes text via stdin,
reads stdout, checks exit code 0) -- so pointing that config at
`mathunicode` needs no wrapper script.

`mathunicode-collapse-blocks`: a whole document -> the same document with
multi-line $$/content/$$ blocks collapsed to single-line form. Kept as a
separate entry point (not a flag on `mathunicode`) since the two have
different input/output contracts -- one expression in, one expression out,
vs. one document in, one document out.
"""

import sys

from mathunicode.convert import collapse_math_blocks, latex_to_unicode


def main() -> int:
    tex = sys.stdin.read().strip()
    sys.stdout.write(latex_to_unicode(tex))
    return 0


def main_collapse_blocks() -> int:
    text = sys.stdin.read()
    sys.stdout.write(collapse_math_blocks(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
