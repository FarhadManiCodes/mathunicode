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
   has one (`xᵢ`, `10⁻³`, `Aᵀ`, `f′`, `90°`). Otherwise the script, and a
   base, keep their grouping: one word as is (`u_phy`), more than one in
   parentheses (`x^(iⱼ)`, `e^(−x²)`, `(a + b)ₙ`). Never a partial conversion.
2. **Fractions and roots** are linear: `(a + b)/c`, `√(x² + 1)`.
3. **Rows** -- matrices, cases, aligned, `\substack`, `\\` -- are joined by
   `; ` and cells by `, `, so the output is always one line and composes
   with the math around it: `(1, 2; 3, 4)`, `{1, x > 0; 0, else`,
   `a = b; c = d`. A true 2-D layout would need a typesetter.
4. **Spacing** follows MathML's form rule: an operator right after an
   operand is infix and spaced (`a → b`, `x ∈ A`), otherwise prefix and
   tight (`−x`); fences are tight; words (`sin`, `det`, `\mathrm{if}`,
   `∑ᵢ₌₁ⁿ`) are spaced from operands.
5. **LaTeX's own semantics**: source whitespace and comments don't render;
   fonts map to Unicode alphabets (`𝐱`, `ℝ`); accents become combining marks
   on short bases (`x̂`, `A̅B̅`). Nothing is dropped: an unknown macro prints
   its name, and input that doesn't parse comes back as it was.
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
