"""Phase 1, Step 7 — remove unreachable code after unconditional exits.

Scans every block (method body, if-body, loop body, …) for statements
that follow an unconditional exit and removes them.  An "unconditional
exit" is either a direct ``return``/``throw``/``break``/``continue``
or an ``if-else`` (including ``else-if`` chains) where **every branch**
unconditionally exits.  Uses tree-sitter AST to ensure correctness.

Language-specific considerations:
  * Go:     statements live inside a ``statement_list`` child of ``block``.
  * Swift:  statements live inside a ``statements`` child of ``function_body``.
  * Kotlin: ``break``/``continue`` are parsed as ``identifier`` nodes;
            ``if_expression`` is used instead of ``if_statement``;
            bodies may be wrapped in ``control_structure_body``.
"""

from ..ast_utils import parse, find_all

_EXIT_TYPES = frozenset({
    'return_statement',
    'throw_statement', 'throw_expression',
    'break_statement', 'continue_statement',
    'jump_expression',
    'control_transfer_statement',
})

_IF_TYPES = frozenset({
    'if_statement', 'if_expression',
})

_BLOCK_TYPES = frozenset({
    'block', 'statement_block', 'compound_statement',
    'function_body',
    'statement_list', 'statements',
})

_BODY_TYPES = _BLOCK_TYPES | frozenset({
    'control_structure_body',
})

_SKIP_CHILD_TYPES = frozenset({
    'comment', 'block_comment', 'line_comment', 'multiline_comment',
    '{', '}',
})


def _is_exit(node, cb: bytes) -> bool:
    """Return True if *node* is an unconditional exit statement."""
    if node.type in _EXIT_TYPES:
        text = cb[node.start_byte:node.end_byte]
        if node.type == 'jump_expression':
            stripped = text.lstrip()
            return stripped.startswith(b'return') or stripped.startswith(b'throw')
        if node.type == 'control_transfer_statement':
            stripped = text.strip()
            return (stripped.startswith(b'return')
                    or stripped.startswith(b'throw')
                    or stripped.startswith(b'break')
                    or stripped.startswith(b'continue'))
        return True
    if node.type in ('identifier', 'simple_identifier'):
        text = cb[node.start_byte:node.end_byte]
        if text in (b'break', b'continue'):
            if node.parent and node.parent.type in _BODY_TYPES:
                return True
    return False


def _get_if_branches(node):
    """Extract (then_branch, else_branch) from an if node.

    Returns ``(then_node, else_node)`` where *else_node* may be ``None``
    (no else clause), a block (plain else), or another if node (else-if).
    Works across Java, Kotlin, Go, Swift, and Dart tree-sitter grammars.
    """
    then_br = node.child_by_field_name('consequence')
    else_br = node.child_by_field_name('alternative')

    if then_br is None:
        then_br = node.child_by_field_name('body')

    if else_br is not None:
        return then_br, else_br

    for child in node.children:
        if child.type in ('else_clause', 'else'):
            for sub in child.children:
                if sub.type in _BODY_TYPES or sub.type in _IF_TYPES:
                    return then_br, sub
            return then_br, child
    return then_br, None


def _definitely_exits(node, cb: bytes) -> bool:
    """Return True if *node* unconditionally exits.

    Handles three patterns:
    1. Direct exit statement (return / throw / break / continue)
    2. Block whose last meaningful statement definitely exits
    3. if-else (including else-if chains) where ALL branches
       definitely exit
    """
    if _is_exit(node, cb):
        return True

    if node.type in _BODY_TYPES:
        children = [c for c in node.children if c.type not in _SKIP_CHILD_TYPES]
        return bool(children) and _definitely_exits(children[-1], cb)

    if node.type in _IF_TYPES:
        then_br, else_br = _get_if_branches(node)
        if then_br is not None and else_br is not None:
            return (_definitely_exits(then_br, cb)
                    and _definitely_exits(else_br, cb))

    return False


def _collect_dead_ranges(root, cb: bytes) -> list[tuple[int, int]]:
    """Find byte ranges of unreachable statements in all blocks."""
    ranges: list[tuple[int, int]] = []
    blocks: list = []
    for bt in _BLOCK_TYPES:
        blocks.extend(find_all(root, bt))

    for block in blocks:
        children = [c for c in block.children if c.type not in _SKIP_CHILD_TYPES]
        found_exit = False
        dead_start = -1
        dead_end = -1
        for child in children:
            if found_exit:
                if dead_start < 0:
                    dead_start = child.start_byte
                dead_end = child.end_byte
            elif _definitely_exits(child, cb):
                found_exit = True

        if dead_start >= 0 and dead_end > dead_start:
            ranges.append((dead_start, dead_end))

    return ranges


def _remove_ranges(cb: bytes, ranges: list[tuple[int, int]]) -> bytes:
    """Remove byte ranges, eliminating resulting blank lines."""
    if not ranges:
        return cb

    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    result = []
    pos = 0
    for start, end in merged:
        ls = cb.rfind(b'\n', 0, start)
        trim_start = ls + 1 if ls >= 0 else start
        before = cb[trim_start:start]
        if before.strip() == b'':
            start = trim_start

        le = cb.find(b'\n', end)
        if le != -1:
            after = cb[end:le]
            if after.strip() == b'':
                end = le + 1

        result.append(cb[pos:start])
        pos = end
    result.append(cb[pos:])

    out = b''.join(result)

    lines = out.split(b'\n')
    cleaned = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == b''
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank
    return b'\n'.join(cleaned)


def phase1_step7_remove_unreachable_code(cb: bytes) -> bytes:
    """Remove unreachable code after return/throw/break/continue.

    Iterates until no more unreachable code is found (handles cascading
    cases where removing dead code exposes new unreachable regions).
    """
    for _ in range(20):
        root, _ = parse(cb)
        ranges = _collect_dead_ranges(root, cb)
        if not ranges:
            break
        prev = cb
        cb = _remove_ranges(cb, ranges)
        if cb == prev:
            break
    return cb
