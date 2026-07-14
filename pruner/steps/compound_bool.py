"""Phase 1, Step 4 — compound boolean + ternary simplification.

Resolves:
  - ``true && expr`` → ``expr``
  - ``false || expr`` → ``expr``
  - ``cond ? A : B`` when *cond* is a constant boolean
  - ``true + ""`` → ``"true"``
"""

from ..ast_utils import parse, txt, find_all, is_bool, replace_node


class _SpanNode:
    """Synthetic node spanning a byte range for multi-child operands
    (e.g. Dart splits ``foo()`` into identifier + selector)."""
    __slots__ = ('start_byte', 'end_byte', 'type', 'parent', 'children', 'named_children')

    def __init__(self, start, end):
        self.start_byte = start
        self.end_byte = end
        self.type = '_span'
        self.parent = None
        self.children = []
        self.named_children = []

    def child_by_field_name(self, name):  # noqa: ARG002
        return None


_BINARY_TYPES = ('binary_expression', 'conjunction_expression',
                 'disjunction_expression', 'infix_expression',
                 'logical_and_expression', 'logical_or_expression')

_OPERATOR_TYPES = frozenset({
    '&&', '||', '==', '!=', '+', '-',
    'logical_and_operator', 'logical_or_operator',
    'equality_operator',
})


def _get_binary_parts(node, cb):
    left  = node.child_by_field_name('left')
    right = node.child_by_field_name('right')
    op    = node.child_by_field_name('operator')
    if left and right and op:
        return left, txt(op, cb), right
    ch = node.children
    if len(ch) < 3:
        return None, None, None
    op_idx = None
    for i, c in enumerate(ch):
        if c.type in _OPERATOR_TYPES:
            op_idx = i
            break
    if op_idx is None:
        return ch[0], txt(ch[1], cb), ch[2]
    left_node = ch[0]
    op_text = txt(ch[op_idx], cb)
    if op_idx + 1 == len(ch) - 1:
        right_node = ch[op_idx + 1]
    else:
        right_node = _SpanNode(ch[op_idx + 1].start_byte, ch[-1].end_byte)
    return left_node, op_text, right_node


def _find_all_binary(root):
    results = []
    for t in _BINARY_TYPES:
        results.extend(find_all(root, t))
    return results


def _is_cmp_child(node, cb):
    p = node.parent
    if p and p.type in _BINARY_TYPES:
        _, op_t, _ = _get_binary_parts(p, cb)
        if op_t in ('==', '!='):
            return True
    return False


def phase1_step4_simplify_compound_expressions(cb: bytes) -> bytes:
    for _ in range(500):
        root, cb = parse(cb)
        mod = False

        for b in _find_all_binary(root):
            left, op_t, right = _get_binary_parts(b, cb)
            if not left or not right or op_t not in ('&&', '||'):
                continue
            if b.parent and b.parent.type == 'equality_expression':
                continue

            lv = is_bool(left, cb)
            rv = is_bool(right, cb)
            l_bool = lv is not None and not _is_cmp_child(left, cb)
            r_bool = rv is not None and not _is_cmp_child(right, cb)
            if not l_bool and not r_bool:
                continue

            rep = None
            if op_t == '&&':
                if l_bool and lv == 'false':    rep = 'false'
                elif r_bool and rv == 'false':  rep = 'false'
                elif l_bool and lv == 'true':   rep = txt(right, cb).strip()
                elif r_bool and rv == 'true':   rep = txt(left, cb).strip()
            elif op_t == '||':
                if l_bool and lv == 'true':     rep = 'true'
                elif r_bool and rv == 'true':   rep = 'true'
                elif l_bool and lv == 'false':  rep = txt(right, cb).strip()
                elif r_bool and rv == 'false':  rep = txt(left, cb).strip()

            if rep is not None:
                cb = replace_node(cb, b, rep)
                mod = True
                break

        if mod:
            continue

        for t in find_all(root, 'ternary_expression') + find_all(root, 'conditional_expression'):
            cond = t.child_by_field_name('condition')
            if cond is None:
                cons_node = t.child_by_field_name('consequence')
                alt_node  = t.child_by_field_name('alternative')
                for nc in t.named_children:
                    if nc is not cons_node and nc is not alt_node:
                        cond = nc
                        break
            cv = is_bool(cond, cb) if cond else None
            if not cv:
                continue
            if _is_cmp_child(cond, cb):
                continue
            cons = t.child_by_field_name('consequence')
            alt  = t.child_by_field_name('alternative')
            if not cons or not alt:
                continue
            rep = txt(cons, cb).strip() if cv == 'true' else txt(alt, cb).strip()
            cb = replace_node(cb, t, rep)
            mod = True
            break

        if mod:
            continue

        for b in _find_all_binary(root):
            left, op_t, right = _get_binary_parts(b, cb)
            if not left or not right:
                continue
            if op_t == '+':
                if left.type in ('true', 'false') and right.type == 'string_literal' and txt(right, cb) == '""':
                    cb = replace_node(cb, b, f'"{left.type}"')
                    mod = True
                    break
        if not mod:
            break
    return cb
