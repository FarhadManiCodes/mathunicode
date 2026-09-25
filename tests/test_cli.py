"""Tests for the CLI entry points -- the stdin -> stdout contract that tools
like render-markdown.nvim rely on (pipe text in, read stdout, check exit 0)."""

import io
import os
import subprocess
import sys

from mathunicode.cli import main, main_collapse_blocks


def _run(entry, stdin_text, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    exit_code = entry([])
    out = capsys.readouterr().out
    return exit_code, out


def test_main_converts_expression(monkeypatch, capsys):
    code, out = _run(main, "x_{i}", monkeypatch, capsys)
    assert code == 0
    assert out == "xᵢ"


def test_main_strips_surrounding_whitespace(monkeypatch, capsys):
    # main() strips stdin so a trailing newline from `echo` doesn't become a
    # stray macro argument / trailing blank in the output.
    code, out = _run(main, "  \\det(A) = 0\n", monkeypatch, capsys)
    assert code == 0
    assert out == "det(A) = 0"


def test_main_never_raises_on_malformed_input(monkeypatch, capsys):
    code, out = _run(main, "\\left( unbalanced", monkeypatch, capsys)
    assert code == 0
    assert isinstance(out, str)


def test_collapse_blocks_collapses_multiline(monkeypatch, capsys):
    code, out = _run(
        main_collapse_blocks, "before\n$$\nx_i\n$$\nafter", monkeypatch, capsys
    )
    assert code == 0
    assert out == "before\n$$ x_i $$\nafter"


def test_collapse_blocks_preserves_input_verbatim_when_nothing_to_do(
    monkeypatch, capsys
):
    # Unlike main(), main_collapse_blocks() does not strip -- it must round-trip
    # a whole document untouched, trailing newline and all.
    text = "just prose\nno math here\n"
    code, out = _run(main_collapse_blocks, text, monkeypatch, capsys)
    assert code == 0
    assert out == text


# ---------------------------------------------------------------------------
# The contract as a real process sees it: exit code, stderr, encoding.
# ---------------------------------------------------------------------------


def _cli(entry, stdin: bytes, *args, env=None):
    code = f"import sys; from mathunicode.cli import {entry}; sys.exit({entry}())"
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        input=stdin, check=False,  # callers assert on the exit code
        capture_output=True,
        env={**os.environ, **(env or {})},
        timeout=30,
    )


def test_cli_process_converts_with_clean_stderr():
    # Malformed input: still exit 0, the fallback text on stdout, nothing on
    # stderr (render-markdown.nvim reads stdout and checks the exit code).
    for tex in ("x_{i}", "\\frac", "\\left( x", "\\binom{n}"):
        result = _cli("main", tex.encode())
        assert result.returncode == 0, tex
        assert result.stderr == b"", tex
    assert _cli("main", b"x_{i}").stdout.decode() == "xᵢ"


def test_cli_process_writes_utf8_under_non_utf8_locale():
    # Used to raise UnicodeEncodeError under a latin-1 terminal encoding.
    result = _cli("main", b"x_{i}", env={"PYTHONIOENCODING": "latin-1"})
    assert result.returncode == 0
    assert result.stdout.decode("utf-8") == "xᵢ"


def test_cli_process_version_does_not_wait_on_stdin():
    result = _cli("main", b"", "--version")
    assert result.returncode == 0
    assert result.stdout.decode().startswith("mathunicode ")


def test_collapse_cli_process_keeps_crlf():
    # Text-mode stdin used to turn a CRLF document into LF.
    result = _cli("main_collapse_blocks", b"a\r\n$$\r\nx\r\n$$\r\nb\r\n")
    assert result.returncode == 0
    assert result.stdout == b"a\r\n$$ x $$\r\nb\r\n"
