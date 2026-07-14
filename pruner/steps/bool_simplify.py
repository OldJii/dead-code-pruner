"""Phase 1, Step 3 — simple boolean simplification.

Resolves trivial boolean expressions:
  - ``!true`` → ``false``
  - ``true == false`` → ``false``
  - ``(true)`` → ``true``  (unwrap redundant parens, context-aware)
"""

from ..ast_utils import parse, txt, find_all, is_bool, replace_node


def phase1_step3_simplify_booleans(cb: bytes) -> bytes:
    for _ in range(200):
        root, cb = parse(cb)
        mod = False

        for u in find_all(root, 'unary_expression') + find_all(root, 'prefix_expression'):
            ch = u.children
            if len(ch) >= 2:
                op_text = txt(ch[0], cb)
                if op_text in ('!', '!'):
                    bv = is_bool(ch[1], cb)
                    if bv:
                        rep = 'false' if bv == 'true' else 'true'
                        cb = replace_node(cb, u, rep)
                        mod = True
                        break

        if mod:
            continue

        for b in (find_all(root, 'binary_expression')
                  + find_all(root, 'equality_expression')
                  + find_all(root, 'infix_expression')):
            left  = b.child_by_field_name('left')
            right = b.child_by_field_name('right')
            op    = b.child_by_field_name('operator')
            if not (left and right and op):
                ch = b.children
                if len(ch) >= 3:
                    left, op, right = ch[0], ch[1], ch[2]
                else:
                    continue
            lv = is_bool(left, cb)
            rv = is_bool(right, cb)
            if not lv or not rv:
                continue
            op_t = txt(op, cb)
            if op_t == '==':
                res = 'true' if lv == rv else 'false'
            elif op_t == '!=':
                res = 'false' if lv == rv else 'true'
            else:
                continue
            cb = replace_node(cb, b, res)
            mod = True
            break

        if mod:
            continue

        for p in find_all(root, 'parenthesized_expression') + find_all(root, 'tuple_expression'):
            inner = p.named_children
            if len(inner) == 1 and is_bool(inner[0], cb):
                parent = p.parent
                if parent and parent.type in ('if_statement', 'while_statement',
                                               'for_statement', 'do_statement',
                                               'if_expression'):
                    cond = parent.child_by_field_name('condition')
                    if cond and cond.start_byte == p.start_byte:
                        continue
                if parent and parent.type in ('method_invocation', 'argument_list',
                                               'call_expression', 'value_arguments'):
                    continue
                sb = p.start_byte
                if sb > 0:
                    prev_ch = cb[sb - 1:sb]
                    if prev_ch in (b'_', b'.', b'>', b']', b')'):
                        continue
                    try:
                        if chr(cb[sb - 1]).isalnum():
                            continue
                    except (ValueError, IndexError):
                        pass
                bv = is_bool(inner[0], cb)
                cb = replace_node(cb, p, bv)
                mod = True
                break

        if not mod:
            break
    return cb
