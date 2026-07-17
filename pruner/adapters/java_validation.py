"""Java semantic quality gates beyond parser-error validation."""

from __future__ import annotations

from .. import lang as _lang
from ..ast_utils import parse


def _node_text(node, code: bytes) -> str:
    return code[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _nonvoid_method_facts(code: bytes) -> dict[tuple, tuple[bool, bool]]:
    """Return signature -> (has return/throw, has a body statement)."""
    saved = _lang._current_ext
    _lang._current_ext = '.java'
    try:
        root, _ = parse(code)
    finally:
        _lang._current_ext = saved
    facts: dict[tuple, tuple[bool, bool]] = {}
    stack = [root]
    while stack:
        node = stack.pop()
        stack.extend(node.children)
        if node.type != 'method_declaration':
            continue
        return_type = node.child_by_field_name('type')
        name = node.child_by_field_name('name')
        parameters = node.child_by_field_name('parameters')
        body = node.child_by_field_name('body')
        if (return_type is None or name is None or parameters is None
                or body is None or _node_text(return_type, code).strip() == 'void'):
            continue
        owners: list[str] = []
        parent = node.parent
        while parent is not None:
            if parent.type in ('class_declaration', 'interface_declaration',
                               'enum_declaration', 'annotation_type_declaration'):
                owner = parent.child_by_field_name('name')
                if owner is not None:
                    owners.append(_node_text(owner, code))
            parent = parent.parent
        key = (tuple(reversed(owners)), _node_text(name, code),
               ''.join(_node_text(parameters, code).split()))
        descendants = list(body.children)
        has_exit = False
        has_statement = False
        while descendants:
            child = descendants.pop()
            if child.type in ('return_statement', 'throw_statement'):
                has_exit = True
            if child.parent is body and child.is_named and child.type != 'comment':
                has_statement = True
            descendants.extend(child.children)
        facts[key] = has_exit, has_statement
    return facts


def preserves_method_results(original: bytes, transformed: bytes) -> bool:
    """Do not empty a retained non-void method or remove its only exit."""
    before = _nonvoid_method_facts(original)
    after = _nonvoid_method_facts(transformed)
    for key, (had_exit, had_statement) in before.items():
        if key not in after:
            continue  # Whole-method deletion is governed by project analysis.
        has_exit, has_statement = after[key]
        if had_exit and not has_exit:
            return False
        if had_statement and not has_statement:
            return False
    return True
