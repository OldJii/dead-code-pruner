"""AST-safe configured Java method-call replacement."""

from __future__ import annotations

from ..ast_utils import find_all, parse, replace_node, txt

_EFFECTFUL_NODES = frozenset({
    'assignment_expression', 'method_invocation', 'object_creation_expression',
    'update_expression', 'lambda_expression', 'array_access',
})


def _expression_is_stable(node) -> bool:
    """Whether discarding an expression cannot drop an observable evaluation."""
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in _EFFECTFUL_NODES:
            return False
        stack.extend(current.named_children)
    return True


def _rule_matches(node, content: bytes, rule) -> bool:
    name_node = node.child_by_field_name('name')
    args_node = node.child_by_field_name('arguments')
    if name_node is None or args_node is None:
        return False
    expected_receiver = None
    expected_name = rule.pattern
    if '.' in rule.pattern:
        expected_receiver, expected_name = rule.pattern.rsplit('.', 1)
    if txt(name_node, content) != expected_name:
        return False
    if rule.arity is not None and len(args_node.named_children) != rule.arity:
        return False

    receiver = node.child_by_field_name('object')
    if expected_receiver is not None:
        if receiver is None:
            return False
        actual = txt(receiver, content).replace(' ', '')
        expected = expected_receiver.replace(' ', '')
        if actual != expected and not actual.endswith('.' + expected):
            return False
    elif not rule.allow_unqualified:
        return False

    if rule.discard_side_effects:
        return True
    if receiver is not None and not _expression_is_stable(receiver):
        return False
    return all(_expression_is_stable(argument)
               for argument in args_node.named_children)


def replace_configured_calls(content: bytes, rules: list) -> bytes:
    """Replace matched invocation nodes while preserving declarations and effects."""
    # Reparse after every edit so tree-sitter byte spans never become stale.
    for _ in range(500):
        root, _ = parse(content)
        changed = False
        for invocation in find_all(root, 'method_invocation'):
            for rule in rules:
                if _rule_matches(invocation, content, rule):
                    content = replace_node(content, invocation, rule.value)
                    changed = True
                    break
            if changed:
                break
        if not changed:
            break
    return content
