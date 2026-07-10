# mathunicode

LaTeX -> readable Unicode approximation, built on
[pylatexenc](https://github.com/phfaist/pylatexenc), with three things
pylatexenc doesn't do on its own:

- **Fixes macros pylatexenc silently drops or mishandles** -- not
  cosmetically, but as real content loss (`\|x\|^2` -> `x^2`, losing the
  norm; `\det(A)` -> `(A)`, losing the operator name). Found by
  systematically testing every macro used across a real paper library (149
  unique names), not guessed.
- **Real Unicode subscript/superscript characters** where every character
  in a `_{...}`/`^{...}` group has one (`x_{i}` -> `xᵢ`, `_{int}` ->
  `ᵢₙₜ`), falling back to the plain `_word` text pylatexenc would otherwise
  produce when it isn't fully representable -- Unicode has no subscript
  glyph for several letters (`b,c,d,f,g,q,w,y,z`), any uppercase letter, or
  any Greek letter, so `u_{phy}` (missing `y`) stays as `u_phy`, never a
  partial conversion like `ᵤ_phy`.
- **A guard against `$...$` false positives**: naive math-span detection
  (this package's own `convert_math_spans`, and confirmed directly via a
  live tree-sitter-markdown parse, `render-markdown.nvim`'s own inline-math
  grammar) pairs the first `$` with whichever `$` comes next, regardless of
  content -- "costs `$50` ... `$100`" reads as one math span. Multi-word
  prose with no macro or sub/superscript marker is detected and returned
  with its `$` signs restored, rather than silently losing the currency
  marks once concealed.

Exposes both a Python API and CLIs (stdin -> stdout, no file-path
arguments) so it's usable in-process by other tools (e.g.
[papis-ask](https://github.com/FarhadManiCodes/papis-ask)) and as a
drop-in shell-command `converter` for tools like
[render-markdown.nvim](https://github.com/MeanderingProgrammer/render-markdown.nvim).

```python
from mathunicode import latex_to_unicode, convert_math_spans, collapse_math_blocks

latex_to_unicode(r"\det(A) = 0")     # "det(A) = 0"
latex_to_unicode(r"x_{i}")           # "xᵢ"
latex_to_unicode(r"u_{phy}")         # "u_phy" -- 'y' has no subscript form, not partial

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

## Tests

```
uv run --extra test pytest tests/
```
