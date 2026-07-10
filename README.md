# mathunicode

LaTeX -> readable Unicode approximation, with fixes for macros
[pylatexenc](https://github.com/phfaist/pylatexenc) silently drops or
mishandles (e.g. `\|x\|^2` -> `x^2`, losing the norm; `\det(A)` -> `(A)`,
losing the operator name).

Exposes both a Python API and a CLI (`mathunicode`, reads stdin, writes
stdout) so it's a drop-in `converter` for tools like
[render-markdown.nvim](https://github.com/MeanderingProgrammer/render-markdown.nvim),
as well as an in-process dependency for other tools (e.g.
[papis-ask](https://github.com/FarhadManiCodes/papis-ask)).

```python
from mathunicode import latex_to_unicode, convert_math_spans

latex_to_unicode(r"\det(A) = 0")        # "det(A) = 0"
convert_math_spans("cost is $50")       # unchanged -- not mistaken for math
```
