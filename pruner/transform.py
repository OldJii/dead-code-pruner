"""Single-file transformation pipeline (steps 1–4).

Applies constant folding, boolean simplification, compound boolean /
ternary resolution, and dead-branch elimination to a single file in a
convergence loop.
"""

import os
import sys
import yaml

from . import lang as _lang
from . import ui
from .steps.constant_fold import (
    step1_replace, step1b_propagate_locals, step1c_remove_unused_bool_vars,
)
from .steps.bool_simplify import step2_simple
from .steps.compound_bool import step3_compound
from .steps.if_blocks import step4_if_blocks
from .steps.unreachable import step1d_remove_unreachable
from .steps.kotlin_expr import kotlin_if_expr
from .validation import validate_transformation


def run_pipeline(cb: bytes, replacements=None, is_kt: bool = False,
                 ext: str = '.java', max_rounds: int = 10) -> bytes:
    """Run steps 1–4 in a convergence loop until no further changes occur."""
    _lang._current_ext = ext
    if replacements is None:
        replacements = []
    original = cb
    for _ in range(max_rounds):
        prev = cb
        if replacements:
            cb = step1_replace(cb, replacements)
        cb = step1b_propagate_locals(cb)
        cb = step2_simple(cb)
        cb = step3_compound(cb)
        if ext in ('.kt', '.kts'):
            cb = kotlin_if_expr(cb)
        cb = step4_if_blocks(cb, is_kt)
        cb = step1d_remove_unreachable(cb)
        cb = step1c_remove_unused_bool_vars(cb)
        if cb == prev:
            break
    return validate_transformation(original, cb, ext)


def load_config(path: str) -> list[tuple[str, str]]:
    """Load a ``pruner.yaml`` config and return ``[(pattern, replacement), …]``.

    Supports two formats:

    Simple (flat key→value)::

        AppConfig.IS_DEBUG: false

    Structured (list of {pattern, value})::

        replacements:
          - pattern: "INTL_FLAG"
            value: true
    """
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    replacements: list[tuple[str, str]] = []
    if 'replacements' in data and isinstance(data['replacements'], list):
        for item in data['replacements']:
            pat = item.get('pattern', '')
            val = item.get('value', '')
            if isinstance(val, bool):
                val = 'true' if val else 'false'
            replacements.append((str(pat), str(val)))
    else:
        for key, val in data.items():
            if isinstance(val, bool):
                val = 'true' if val else 'false'
            replacements.append((key, str(val)))
    return replacements


def process_file(filepath: str, replacements: list[tuple[str, str]]) -> bool:
    """Apply the full single-file pipeline to *filepath*. Returns ``True`` if modified."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in _lang._PARSERS:
        return False
    try:
        with open(filepath, 'rb') as f:
            cb = f.read()
    except Exception as e:
        ui.error(f"reading {filepath}: {e}")
        return False

    is_kt = ext in ('.kt', '.kts')
    new_cb = run_pipeline(cb, replacements, is_kt, ext)

    if new_cb != cb:
        with open(filepath, 'wb') as f:
            f.write(new_cb)
        return True
    return False
