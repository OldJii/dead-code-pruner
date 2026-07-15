"""Phase 1 single-file transformation pipeline (Steps 1–8).

Applies constant folding, boolean simplification, compound boolean /
ternary resolution, and dead-branch elimination to a single file in a
convergence loop.
"""

import os
import yaml

from . import lang as _lang
from . import ui
from .steps.constant_fold import (
    phase1_step1_replace_constants,
    phase1_step2_propagate_local_constants,
    phase1_step8_remove_unused_bool_vars,
)
from .steps.bool_simplify import phase1_step3_simplify_booleans
from .steps.compound_bool import phase1_step4_simplify_compound_expressions
from .steps.if_blocks import phase1_step6_eliminate_dead_branches
from .steps.unreachable import phase1_step7_remove_unreachable_code
from .adapters import get_adapter
from .validation import validate_transformation


def run_pipeline(cb: bytes, replacements=None, *, ext: str = '.java',
                 max_rounds: int = 10) -> bytes:
    """Run Phase 1, Steps 1–8 until no further changes occur."""
    _lang._current_ext = ext
    if replacements is None:
        replacements = []
    adapter = get_adapter(ext)
    original = cb
    for _ in range(max_rounds):
        prev = cb
        if replacements:
            cb = phase1_step1_replace_constants(cb, replacements, ext)
        cb = phase1_step2_propagate_local_constants(cb, ext)
        cb = phase1_step3_simplify_booleans(cb)
        cb = phase1_step4_simplify_compound_expressions(
            cb, preserve_left_effects=ext not in ('.java', '.kt', '.kts'))
        if adapter:
            cb = adapter.phase1_step5_simplify_language_expressions(cb)
        cb = phase1_step6_eliminate_dead_branches(
            cb, adapter.preserve_branch_scope if adapter else True)
        cb = phase1_step7_remove_unreachable_code(cb)
        cb = phase1_step8_remove_unused_bool_vars(cb, ext)
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
          - pattern: "FEATURE_FLAG"
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
            if key == 'project_boundary':
                continue
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

    new_cb = run_pipeline(cb, replacements, ext=ext)

    if new_cb != cb:
        with open(filepath, 'wb') as f:
            f.write(new_cb)
        return True
    return False
