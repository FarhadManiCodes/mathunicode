"""CLI entry point: stdin -> latex_to_unicode -> stdout.

Matches the stdin/stdout contract render-markdown.nvim's `converter` list
expects of any named command (see its `Handler.convert()`: pipes text via
stdin, reads stdout, checks exit code 0) -- so pointing that config at
`mathunicode` needs no wrapper script.
"""

import sys

from mathunicode.convert import latex_to_unicode


def main() -> int:
    tex = sys.stdin.read().strip()
    sys.stdout.write(latex_to_unicode(tex))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
