"""Transformation steps — each module handles one pruning pass."""

from .constant_fold import step1_replace, step1b_propagate_locals, step1c_remove_unused_bool_vars
from .bool_simplify import step2_simple
from .compound_bool import step3_compound
from .if_blocks import step4_if_blocks
from .unreachable import step1d_remove_unreachable
from .kotlin_expr import kotlin_if_expr
from .method_inline import step5_project
from .dead_methods import step6_project
from .empty_cleanup import step7_empty_cleanup

__all__ = [
    'step1_replace', 'step1b_propagate_locals', 'step1c_remove_unused_bool_vars',
    'step1d_remove_unreachable',
    'step2_simple', 'step3_compound',
    'step4_if_blocks', 'kotlin_if_expr',
    'step5_project', 'step6_project', 'step7_empty_cleanup',
]
