"""Transformation steps — each module handles one pruning pass."""

from .constant_fold import (
    phase1_step1_replace_constants,
    phase1_step2_propagate_local_constants,
    phase1_step8_remove_unused_bool_vars,
)
from .bool_simplify import phase1_step3_simplify_booleans
from .compound_bool import phase1_step4_simplify_compound_expressions
from .if_blocks import phase1_step6_eliminate_dead_branches
from .unreachable import phase1_step7_remove_unreachable_code
from .kotlin_expr import phase1_step5_simplify_kotlin_expressions
from .method_inline import inline_boolean_methods_standalone
from .dead_methods import phase2_step2_cleanup_dead_declarations
from .empty_cleanup import phase2_step5_cleanup_empty_artifacts

__all__ = [
    'phase1_step1_replace_constants',
    'phase1_step2_propagate_local_constants',
    'phase1_step3_simplify_booleans',
    'phase1_step4_simplify_compound_expressions',
    'phase1_step6_eliminate_dead_branches',
    'phase1_step7_remove_unreachable_code',
    'phase1_step8_remove_unused_bool_vars',
    'phase1_step5_simplify_kotlin_expressions',
    'inline_boolean_methods_standalone',
    'phase2_step2_cleanup_dead_declarations',
    'phase2_step5_cleanup_empty_artifacts',
]
