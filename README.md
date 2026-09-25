# mathunicode

LaTeX math -> one line of readable Unicode, for terminals and editors; plus
finding math in Markdown. LaTeX is parsed by
[latex2mathml](https://github.com/roniemartinez/latex2mathml) into MathML (the
W3C structure for mathematics), and each MathML element is rendered by one
rule -- so grouping, spacing and rows follow the structure of the formula,
not guesses from its source text.

Requires Python 3.12+. Used by [papis-ask](https://github.com/FarhadManiCodes/papis-ask)
(`convert_math_spans` on answers), paper-refinery (`collapse_math_blocks` on
its review `.md`) and render-markdown.nvim (the two CLIs). The public API is
the three functions below; everything else is private.

```python
from mathunicode import latex_to_unicode, convert_math_spans, collapse_math_blocks

latex_to_unicode(r"\sum_{i=1}^{n} x_i^2")   # "∑ᵢ₌₁ⁿ xᵢ²"
latex_to_unicode(r"x^{i_j}")                # "x^(iⱼ)"
latex_to_unicode(r"f(x) = \begin{cases} 1 & x > 0 \\ 0 & \text{else} \end{cases}")
                                            # "f(x) = {1, x > 0; 0, else"
convert_math_spans("costs $50 to train, compared to $100 for the baseline.")  # unchanged
collapse_math_blocks("before\n$$\nx_{i}\n$$\nafter")  # "before\n$$ x_{i} $$\nafter"
```

## Rendering rules

1. **Scripts** use Unicode sub/superscript characters when every character
   has one (`xᵢ`, `10⁻³`, `Aᵀ`, `y′⁽ⁱ⁺¹⁾`, `90°`). Otherwise the script, and
   the base, keep their grouping: one token as is (`x^α`, `u_phy` for
   `u_{\text{phy}}`), anything more in parentheses (`x^(iⱼ)`, `e^(γt)`,
   `(a + b)ₙ`). Never a partial conversion.
2. **Fractions and roots** are linear; a side is parenthesized only if it has
   a top-level operator: `∂g/∂x`, `(a + b)/c`, `√(x² + 1)`, `³√x`.
3. **Rows** -- matrices, cases, aligned, `\substack`, `\\` -- are joined by
   `; ` and cells by `, `, so the output is always one line and composes
   with the math around it: `(1, 2; 3, 4)`, `{1, x > 0; 0, else`,
   `a = b; c = d`. A true 2-D layout would need a typesetter.
4. **Spacing** is TeX's inter-atom table, each symbol's class (relation,
   binary, punctuation, ...) taken from the character: `a ± b`, `x ∈ A`,
   `n!`, `a := b`, `σ²/N`, `1/B 1/N`. A leading sign attaches (`−x`), nothing
   is spaced before punctuation, an operator name hugs its argument
   (`det(A)`, `log₂(n)`) while limits set in a line don't run into it
   (`∑ᵢ₌₁ᵐ (…)`), and a letter never touches an upright word or a written-out
   script (`if x`, `β^FR pₖ`).
5. **LaTeX's own semantics**: source whitespace and comments don't render;
   fonts map to Unicode alphabets (`𝐱`, `𝒖`, `ℝ`, `ℋ`); accents become
   combining marks on short bases (`x̂`, `A̅B̅`). Nothing is dropped: an
   unknown macro prints its name, input that doesn't parse is retried
   without presentational sizing, and what still fails comes back as it
   was, on one line.
6. **Finding math in Markdown**: `$$...$$`, or `$...$` on one line where a
   body starting with a digit must be tight and not followed by a digit, so
   currency never pairs (`$5 or $6`); OCR's padded `$ x_i $` is math.
   Escaped `\$`, code (`` `...` ``, fences) and syntax talk (`$...$`) are
   left alone; currency that still pairs up (`$5 and $`) comes back as
   written.

## CLIs

- `mathunicode`: one LaTeX expression on stdin -> one line on stdout; the
  contract render-markdown.nvim's `converter` expects.
- `mathunicode-collapse-blocks`: a Markdown document on stdin -> the same
  document with each multi-line `$$` block on one line (render-markdown only
  conceals one-line source), keeping indentation and CRLF; blocks in code,
  empty, or with a `%` comment stay.

Both are UTF-8 whatever the locale and take only `--help` / `--version`.

## Tests

```
uv run pytest
```

`tests/test_convert.py` has one table per rule above. `examples/*.md` are
documentation and tests: each line's `<!-- expect: ... -->` comment is its
expected rendering, checked by `tests/test_examples.py`; open them in nvim
with render-markdown to see the formulas rendered in place.
