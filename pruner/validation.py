"""AST validation — detect syntax errors introduced by transformations.

Provides lightweight checks that re-parse transformed code and compare
error counts against the original, rolling back changes that introduce
new parse errors.
"""

from . import lang as _lang
from .ast_utils import parse


def _node_text(node, code: bytes) -> str:
    return code[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _java_nonvoid_method_facts(code: bytes) -> dict[tuple, tuple[bool, bool]]:
    """Return signature -> (has_return_or_throw, has_body_statement)."""
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
        owner_names: list[str] = []
        parent = node.parent
        while parent is not None:
            if parent.type in ('class_declaration', 'interface_declaration',
                               'enum_declaration', 'annotation_type_declaration'):
                owner = parent.child_by_field_name('name')
                if owner is not None:
                    owner_names.append(_node_text(owner, code))
            parent = parent.parent
        key = (
            tuple(reversed(owner_names)),
            _node_text(name, code),
            ''.join(_node_text(parameters, code).split()),
        )
        body_stack = list(body.children)
        has_exit = False
        has_statement = False
        while body_stack:
            child = body_stack.pop()
            if child.type in ('return_statement', 'throw_statement'):
                has_exit = True
            if child.parent is body and child.is_named and child.type != 'comment':
                has_statement = True
            body_stack.extend(child.children)
        facts[key] = (has_exit, has_statement)
    return facts


def _preserves_java_method_results(original: bytes, transformed: bytes) -> bool:
    before = _java_nonvoid_method_facts(original)
    after = _java_nonvoid_method_facts(transformed)
    for key, (had_exit, had_statement) in before.items():
        if key not in after:
            continue  # Whole-method deletion is validated by project safety.
        has_exit, has_statement = after[key]
        if had_exit and not has_exit:
            return False
        if had_statement and not has_statement:
            return False
    return True


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
    if ext == '.java' and not _preserves_java_method_results(original, transformed):
        return original
    new_errors = count_ast_errors(transformed, ext)
    if new_errors == 0:
        return transformed
    old_errors = count_ast_errors(original, ext)
    if new_errors <= old_errors:
        return transformed
    return original
