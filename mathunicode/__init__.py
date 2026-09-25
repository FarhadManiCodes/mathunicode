from importlib.metadata import PackageNotFoundError, version

from mathunicode.convert import (
    collapse_math_blocks,
    convert_math_spans,
    latex_to_unicode,
)

try:
    __version__ = version("mathunicode")
except PackageNotFoundError:  # running from an uninstalled checkout
    __version__ = "0+unknown"

__all__ = ["__version__", "collapse_math_blocks", "convert_math_spans", "latex_to_unicode"]
