"""Tests for the CLI entry points -- the stdin -> stdout contract that tools
like render-markdown.nvim rely on (pipe text in, read stdout, check exit 0)."""

import io

from mathunicode.cli import main, main_collapse_blocks


def _run(entry, stdin_text, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    exit_code = entry()
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
