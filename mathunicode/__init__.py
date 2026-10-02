"""LaTeX math -> one line of Unicode, plus finding math in Markdown.

The public names load on first use (PEP 562): `import mathunicode` -- and so every CLI start, which
nvim pays per formula -- imports no parser and no package metadata."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mathunicode.convert import latex_to_unicode
    from mathunicode.markdown import collapse_math_blocks, convert_math_spans

__all__ = ["__version__", "collapse_math_blocks", "convert_math_spans", "latex_to_unicode"]

_SUBMODULE = {"latex_to_unicode": "convert", "collapse_math_blocks": "markdown",
              "convert_math_spans": "markdown"}


def __getattr__(name: str):
    if name in _SUBMODULE:
        value = getattr(import_module(f"mathunicode.{_SUBMODULE[name]}"), name)
    elif name == "__version__":
        from importlib.metadata import PackageNotFoundError, version  # ~15 ms: only when asked

        try:
            value = version("mathunicode")
        except PackageNotFoundError:  # running from an uninstalled checkout
            value = "0+unknown"
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
