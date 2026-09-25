# mathunicode

LaTeX -> readable Unicode approximation, built on
[pylatexenc](https://github.com/phfaist/pylatexenc), with three things
pylatexenc doesn't do on its own:

- **Fixes macros pylatexenc silently drops or mishandles** -- not
  cosmetically, but as real content loss (`\|x\|^2` -> `x^2`, losing the
  norm; `\det(A)` -> `(A)`, losing the operator name). Found by
  systematically testing every macro used across a real paper library (149
  unique names), not guessed.
  The same goes for operators it drops outright (`\ker`, `\dim`,
  `\gcd`, `\neg`, `\iff`, `\implies`, `\pmod{n}`, ...), and for the
  space after operator names and relations that it glues away (`\sin x`
  -> `sin x`, not `sinx`; `a \to b` -> `a → b`, not `a →b`).
- **One line, whatever the input**: multi-row math has a linear notation
  that composes with the math around it -- `(1 2; 3 4)` for a pmatrix,
  `|a b; c d|` for a vmatrix, `{1, x>0; 0, else}` for cases, `a = b; c = d`
  for aligned; a source line break is only a space, as in LaTeX. A true 2-D
  layout would need a box-layout typesetter; rows as separate output lines
  misalign as soon as anything surrounds the environment.
- **Real Unicode subscript/superscript characters** where every character
  in a `_{...}`/`^{...}` group has one (`x_{i}` -> `xᵢ`, `x^{n + 1}` ->
  `xⁿ⁺¹`, `A^{T}` -> `Aᵀ`, `f^{\prime}` -> `f′`). Unicode has none for
  several letters (subscript `b,c,d,f,g,q,w,y,z` and every capital;
  superscript `C,F,Q,S,X,Y,Z`) or any Greek letter, and there's never a
  partial conversion. A group that can't be converted keeps its grouping
  visible: one token stays as is (`u_{phy}` -> `u_phy`), more than one is
  parenthesized, as plain-text math writes it (`x^{i_j}` -> `x^(iⱼ)`,
  `e^{-x^2}` -> `e^(-x²)`, `\min_{\Theta,\Lambda}` -> `min_(Θ,Λ)`).
- **LaTeX's own whitespace rules**: a source line break is only a space,
  and spaces inside math fonts are ignored -- OCR's `\mathrm{a r g m i n}`
  is `argmin`.
- **A guard against `$...$` false positives**: naive math-span detection
  (and, confirmed directly via a live tree-sitter-markdown parse,
  `render-markdown.nvim`'s own inline-math grammar) pairs the first `$` with
  whichever `$` comes next, regardless of content -- "costs `$50` ...
  `$100`" reads as one math span. `convert_math_spans` pairs `$...$` by
  Pandoc's rule (no space just inside either `$`, and a span starting with
  a digit can't close right before another digit), plus the padded forms
  OCR tools write (`$ x _ {i} $`); it skips `$` inside Markdown code
  (`` `echo $HOME` ``, fenced blocks); and multi-word prose with no macro or
  sub/superscript marker is returned with its `$` signs restored rather
  than silently losing the currency marks once concealed.

Exposes both a Python API and CLIs (stdin -> stdout, no file-path
arguments) so it's usable in-process by other tools (e.g.
[papis-ask](https://github.com/FarhadManiCodes/papis-ask)) and as a
drop-in shell-command `converter` for tools like
[render-markdown.nvim](https://github.com/MeanderingProgrammer/render-markdown.nvim).

Requires Python 3.12+ and pylatexenc 2.x. Used by
[papis-ask](https://github.com/FarhadManiCodes/papis-ask) (`convert_math_spans`
on answers), paper-refinery (`collapse_math_blocks` on its review `.md`) and
render-markdown.nvim (the two CLIs). The public API is the three functions
below; everything else is private.

```python
from mathunicode import latex_to_unicode, convert_math_spans, collapse_math_blocks

latex_to_unicode(r"\det(A) = 0")     # "det(A) = 0"
latex_to_unicode(r"x_{i}")           # "xᵢ"
latex_to_unicode(r"u_{phy}")         # "u_phy" -- 'y' has no subscript form, not partial
latex_to_unicode("5 and")            # "$5 and $" -- currency paired by mistake: '$'s restored

convert_math_spans("costs $50 to train, compared to $100 for the baseline.")
# unchanged -- not mistaken for math despite the two $ signs

collapse_math_blocks("before\n$$\nx_{i}\n$$\nafter")
# "before\n$$ x_{i} $$\nafter"
```

## CLIs

- `mathunicode`: one bare LaTeX expression (no `$` delimiters) on stdin ->
  Unicode approximation on stdout. Matches the stdin/stdout contract
  `render-markdown.nvim`'s `converter` list expects of any named command,
  so pointing it there needs no wrapper script.
- `mathunicode-collapse-blocks`: a whole document on stdin -> the same
  document with multi-line `$$` / content / `$$` blocks collapsed to
  single-line `$$ content $$` form on stdout. Some Markdown renderers
  (confirmed for `render-markdown.nvim`'s LaTeX handler) only conceal the
  raw source and show the render in its place when the equation is written
  on one source line -- a block spanning three lines shows both side by
  side with no config fix available; this is the batch-fixable workaround.
  Blocks inside fenced code, blocks with a `%` comment (joining the lines
  would comment out the rest of the equation), and unclosed or empty blocks
  are left unchanged; the collapsed line keeps the block's indentation.

Both read and write UTF-8 whatever the locale, and take only `--help` /
`--version`. `mathunicode-collapse-blocks` keeps CRLF line endings.

## Tests

```
uv run pytest
```

`examples/test-sample.md` and `examples/multiline.md` are both documentation
and tests: each example line's `<!-- expect: ... -->` comment is its expected
rendering, checked by `tests/test_examples.py`. Open them in nvim with
render-markdown to see the same formulas rendered in place.
