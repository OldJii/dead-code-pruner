"""AST validation — detect syntax errors introduced by transformations.

Provides lightweight checks that re-parse transformed code and compare
error counts against the original, rolling back changes that introduce
new parse errors.
"""

from . import lang as _lang
from .ast_utils import parse


def _count_errors(node) -> int:
    """Walk the AST and count ERROR / MISSING nodes."""
    count = 0
    if node.type == 'ERROR' or node.is_missing:
        count += 1
    for child in node.children:
        count += _count_errors(child)
    return count


def count_ast_errors(code_bytes: bytes, ext: str) -> int:
    """Return the number of AST error nodes in *code_bytes*."""
    if ext not in _lang._PARSERS:
        return 0
    saved = _lang._current_ext
    _lang._current_ext = ext
    try:
        root, _ = parse(code_bytes)
        return _count_errors(root)
    finally:
        _lang._current_ext = saved


def validate_transformation(original: bytes, transformed: bytes, ext: str) -> bytes:
    """Return *transformed* when it does not increase AST errors; otherwise *original*.

    Files that already contained parse errors before transformation are
    allowed through — only *newly introduced* errors trigger a rollback.
    """
    if original == transformed:
        return transformed
    new_errors = count_ast_errors(transformed, ext)
    if new_errors == 0:
        return transformed
    old_errors = count_ast_errors(original, ext)
    if new_errors <= old_errors:
        return transformed
    return original
