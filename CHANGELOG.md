# Changelog

All notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- The Markdown layer (finding math spans, skipping code, collapsing `$$`
  blocks) is its own module, `mathunicode.markdown`. The public API is
  unchanged.

## [0.4.0] - 2026-09-25

The remaining special cases became general rules. About 700 formulas in a
153-paper library render differently, all of them better or equivalent.

### Added
- `\text{}` follows LaTeX's control symbols: accents mark the next letter
  (`café`, `naïve`), spacing commands are a space, and `\!`, `\/`, `\-`,
  `\@` print nothing.

### Changed
- Sub/superscripts, TeX atom classes and styled letters come from tables
  generated from Unicode and unicode-math data (`python -m
  mathunicode._build_tables`); a test fails when they are stale. The CLI
  starts about 9% faster.
- Sub/superscripts cover Greek and more capitals (`eᵞᵗ`, `𝒮ᵟ`). Characters
  from Latin Extended-D (e.g. `ꟲ`), which fonts often lack, are written out
  (`B^C`).
- A letter never touches a written-out script: `n_cows q`, `β^FR pₖ`.
- Limits written out with `_`/`^` are spaced from what follows:
  `min_𝐱 ‖𝐀𝐱 − 𝐛‖₂²`.
- Bar pairing covers every two-sided fence; operator names hug any opening
  bracket; accents apply to runs of plain letters of any length.

### Fixed
- `\boldsymbol{\Theta}` renders `𝜣`, not the THETA SYMBOL variant `𝜭`.

## [0.3.0] - 2026-09-25

### Added
- `--help` and `--version` for both CLIs.
- CI on Python 3.12, 3.13 and 3.14.

### Changed
- LaTeX is parsed by latex2mathml into MathML, and each element is rendered
  by one rule, replacing pylatexenc and text-based patching. The README's
  "Rendering rules" section is the specification.
- Spacing follows TeX's inter-atom table with symbol classes from
  unicode-math: no space before punctuation, operator names hug their
  argument, limits are spaced.
- Output is always one line: matrices, cases and aligned rows are joined by
  `; `, cells by `, `.
- Script groups read unambiguously: `x^{i_j}` is `x^(iⱼ)`.
- Math fonts (`\mathbf`, `\boldsymbol`, `\mathcal`, ...) map to Unicode
  math alphabets.

### Fixed
- The CLIs read and write UTF-8 whatever the locale; `collapse` keeps CRLF,
  and code fences are recognised with CRLF line endings.
- Input that doesn't parse is retried without sizing macros, then returned
  as written, on one line.
- `$...$` in text about math syntax, and currency paired by tree-sitter,
  stay as written.

## [0.2.0] - 2026-09-25

### Added
- `mathunicode.__version__`.

### Changed
- Stricter `$...$` pairing: currency never pairs, padded OCR spans do.
- Markdown code spans and fences, including those in lists and
  blockquotes, are skipped.
- Operator names and relations are spaced.

### Fixed
- Operator and symbol macros that pylatexenc dropped (`\colon`, ...), wide
  accents, labelled arrows and binomials no longer lose content.
- Conversion failures return the original input.
- `collapse_math_blocks` edge cases; escaped `\_` and `\^` aren't read as
  scripts.

## [0.1.1] - 2026-07-22

### Fixed
- Escaped `\$` and display-math prose guards; no partial nested scripts.

## [0.1.0] - 2026-07-11

### Added
- `latex_to_unicode`, with Unicode sub/superscripts where representable.
- `convert_math_spans` for `$...$`/`$$...$$` in Markdown, with a prose guard.
- `collapse_math_blocks` and the `mathunicode-collapse-blocks` CLI.
