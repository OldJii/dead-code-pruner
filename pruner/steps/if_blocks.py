"""Phase 1, Step 6 — if(true)/if(false) block elimination.

Removes dead branches where the condition has been resolved to a constant
boolean, inlining the live branch and deleting dead code after early exits.
"""

import re
from ..ast_utils import parse, find_all, find_if_nodes, get_if_parts, is_bool

_BLOCK_TYPES = frozenset({'block', 'statement_block', 'compound_statement'})

_VAR_DECL_RE_B = re.compile(
    rb'^\s*(final\s+)?(String|int|long|boolean|float|double|char|byte|short|void|var|val|[A-Z]\w*(<[^>]*>)?)\s+\w+\s*[=;]',
    re.MULTILINE)


# ── byte-level helpers ──────────────────────────────────────

def _get_indent(cb, byte_pos):
    ls = cb.rfind(b'\n', 0, byte_pos)
    ls = ls + 1 if ls >= 0 else 0
    indent = b''
    for i in range(ls, len(cb)):
        if cb[i:i+1] in (b' ', b'\t'):
            indent += cb[i:i+1]
        else:
            break
    return indent, ls


def _line_end_b(cb, pos):
    le = cb.find(b'\n', pos)
    return le + 1 if le != -1 else len(cb)


def _is_block(node):
    return node.type in _BLOCK_TYPES


def _body_text_b(node, cb):
    if _is_block(node):
        raw = cb[node.start_byte:node.end_byte]
        inner = raw[1:-1]
        lines = inner.split(b'\n')
        while lines and lines[0].strip() == b'':
            lines.pop(0)
        while lines and lines[-1].strip() == b'':
            lines.pop()
        return b'\n'.join(l.rstrip() for l in lines)
    return cb[node.start_byte:node.end_byte].strip()


def _reindent_b(body, target):
    lines = body.split(b'\n')
    if not lines:
        return body
    mi = float('inf')
    for l in lines:
        s = l.lstrip()
        if s:
            mi = min(mi, len(l) - len(s))
    if mi == float('inf'):
        mi = 0
    out = []
    for l in lines:
        s = l.lstrip()
        if not s:
            out.append(b'')
        else:
            extra = len(l) - len(s) - mi
            out.append(target + b' ' * max(0, extra) + s)
    return b'\n'.join(out)


def _has_exit_b(body):
    lines = body.strip().split(b'\n')
    if not lines:
        return False
    brace = paren = 0
    waiting = True
    last_exit = False
    for line in lines:
        s = line.strip()
        if not s or s.startswith(b'//'):
            continue
        if waiting and brace == 0 and paren == 0:
            last_exit = bool(re.match(rb'^(return\b|throw\b|panic\s*\(|break\s*;?|continue\s*;?)', s))
            waiting = False
        for c in s:
            if c == ord('{'):
                brace += 1
            elif c == ord('}'):
                brace -= 1
                if brace <= 0:
                    brace = 0
                    waiting = True
            elif c == ord('('):
                paren += 1
            elif c == ord(')'):
                paren -= 1
                if paren < 0:
                    paren = 0
            elif c == ord(';') and brace == 0 and paren == 0:
                waiting = True
    return last_exit


def _find_dead_end_b(cb, start_pos):
    depth = 0
    i = start_pos
    n = len(cb)
    case_re = re.compile(rb'\bcase\s+\w')
    default_re = re.compile(rb'\bdefault\s*:')
    while i < n:
        c = cb[i:i+1]
        if c == b'/' and i + 1 < n:
            c2 = cb[i+1:i+2]
            if c2 == b'/':
                end = cb.find(b'\n', i)
                i = end if end != -1 else n
                continue
            elif c2 == b'*':
                end = cb.find(b'*/', i + 2)
                i = end + 2 if end != -1 else n
                continue
        elif c == b'"':
            i += 1
            while i < n and cb[i:i+1] != b'"':
                if cb[i:i+1] == b'\\':
                    i += 1
                i += 1
            i += 1
            continue
        elif c == b"'":
            i += 1
            while i < n and cb[i:i+1] != b"'":
                if cb[i:i+1] == b'\\':
                    i += 1
                i += 1
            i += 1
            continue
        elif c == b'{':
            depth += 1
        elif c == b'}':
            if depth == 0:
                return i
            depth -= 1
        elif depth == 0 and c in (b'c', b'd'):
            if case_re.match(cb, i) or default_re.match(cb, i):
                return i
        i += 1
    return -1


def _cross_case_declarations(cb: bytes, start: int, boundary: int,
                             indent: bytes) -> bytes:
    """Build declarations that must survive trimming to the next case.

    Java switch statement groups share one lexical scope.  A declaration
    after an early-returning branch in one case can still be assigned/read by
    a later case.  When that now-unreachable region is removed, preserve such
    declarations (without their unreachable initializers) before the return.
    """
    boundary_line_end = cb.find(b'\n', boundary)
    if boundary_line_end < 0:
        boundary_line_end = len(cb)
    boundary_text = cb[boundary:boundary_line_end].lstrip()
    if not (boundary_text.startswith(b'case ') or
            boundary_text.startswith(b'default')):
        return b''

    root, _ = parse(cb)
    declarations = [
        node for node in find_all(root, 'local_variable_declaration')
        if start <= node.start_byte and node.end_byte <= boundary
    ]
    if not declarations:
        return b''

    preserved: list[bytes] = []
    for declaration in declarations:
        type_node = declaration.child_by_field_name('type')
        if type_node is None:
            continue
        type_text = cb[type_node.start_byte:type_node.end_byte].strip()
        if not type_text or type_text == b'var':
            continue

        switch_block = declaration.parent
        while switch_block is not None and switch_block.type != 'switch_block':
            switch_block = switch_block.parent
        scope_end = switch_block.end_byte if switch_block is not None else len(cb)

        for declarator in find_all(declaration, 'variable_declarator'):
            name_node = declarator.child_by_field_name('name')
            if name_node is None:
                continue
            name = cb[name_node.start_byte:name_node.end_byte]
            later_nodes = [
                node for node in find_all(root, 'identifier')
                if boundary <= node.start_byte < scope_end
                and cb[node.start_byte:node.end_byte] == name
            ]
            if not later_nodes:
                continue
            first = min(later_nodes, key=lambda node: node.start_byte)
            parent = first.parent
            is_redeclaration = (
                parent is not None
                and parent.type == 'variable_declarator'
                and parent.child_by_field_name('name') is not None
                and parent.child_by_field_name('name').id == first.id
            )
            if not is_redeclaration:
                dimensions = b''.join(
                    cb[child.start_byte:child.end_byte]
                    for child in declarator.children
                    if child.type == 'dimensions'
                )
                preserved.append(
                    indent + type_text + dimensions + b' ' + name + b';')
    return b'\n'.join(preserved)


def _replace_and_trim_dead(cb, ls, rep, construct_end, exit_body):
    """Replace the if-construct at [ls..construct_end) with *rep*.

    When *exit_body* ends with an unconditional exit (return / throw / etc.),
    all code between *construct_end* and the enclosing scope boundary is dead
    and gets removed automatically.
    """
    if _has_exit_b(exit_body):
        dead_end = _find_dead_end_b(cb, construct_end)
        if dead_end != -1:
            between = cb[construct_end:dead_end].strip()
            if between:
                scope_start = cb.rfind(b'\n', 0, dead_end)
                scope_start = scope_start + 1 if scope_start >= 0 else dead_end
                indent = cb[ls:ls + len(cb[ls:]) - len(cb[ls:].lstrip(b' \t'))]
                declarations = _cross_case_declarations(
                    cb, construct_end, scope_start, indent)
                prefix = declarations + b'\n' if declarations else b''
                return cb[:ls] + prefix + rep + b'\n' + cb[scope_start:]
    return cb[:ls] + rep + b'\n' + cb[construct_end:]


def _is_else_if_b(if_node, cb):
    before_start = if_node.start_byte
    ls = cb.rfind(b'\n', 0, before_start)
    ls = ls + 1 if ls >= 0 else 0
    before = cb[ls:before_start].strip()
    if before.endswith(b'else'):
        idx = cb.rfind(b'else', ls, before_start)
        return True, idx
    if before.endswith(b'}'):
        brace_pos = cb.rfind(b'}', ls, before_start)
        region = cb[brace_pos:before_start]
        if b'else' in region:
            idx = cb.rfind(b'else', brace_pos, before_start)
            return True, idx
    return False, -1


def _alt_text_b(alt_node, cb):
    raw = cb[alt_node.start_byte:alt_node.end_byte].strip()
    if raw.startswith(b'else'):
        raw = raw[4:].strip()
    return raw


# ── main entry ──────────────────────────────────────────────

def phase1_step6_eliminate_dead_branches(
        cb: bytes, preserve_branch_scope: bool = True) -> bytes:
    for _ in range(500):
        root, cb = parse(cb)
        mod = False

        for if_node in find_if_nodes(root):
            cond, cons, alt = get_if_parts(if_node, cb)
            if not cond or not cons:
                continue
            value = is_bool(cond, cb)
            if not value and cond.type in ('parenthesized_expression', 'tuple_expression'):
                nc = cond.named_children
                if len(nc) == 1:
                    value = is_bool(nc[0], cb)
            if not value:
                continue

            indent, ls = _get_indent(cb, if_node.start_byte)
            is_eif, ekp = _is_else_if_b(if_node, cb)
            construct_end = _line_end_b(cb, if_node.end_byte - 1)

            if is_eif and ekp >= 0:
                if value == 'true':
                    body = _body_text_b(cons, cb)
                    rep = b'else {\n'
                    if body.strip():
                        rep += body + b'\n'
                    rep += indent + b'}'
                    cb = cb[:ekp] + rep + b'\n' + cb[construct_end:]
                else:
                    if alt:
                        remaining = b'else ' + _alt_text_b(alt, cb)
                        cb = cb[:ekp] + remaining + b'\n' + cb[construct_end:]
                    else:
                        before = cb[:ekp].rstrip(b' \t')
                        cb = before + b'\n' + cb[construct_end:]
                mod = True
                break

            if not _is_block(cons):
                stmt = cb[cons.start_byte:cons.end_byte].strip()
                before_if_nb = cb[ls:if_node.start_byte].strip()
                is_inline_nb = len(before_if_nb) > 0

                if is_inline_nb:
                    if_start = if_node.start_byte
                    if_end = if_node.end_byte
                    if value == 'false':
                        if alt:
                            at = _alt_text_b(alt, cb)
                            cb = cb[:if_start] + at + cb[if_end:]
                        else:
                            cb = cb[:if_start] + cb[if_end:]
                    elif value == 'true':
                        cb = cb[:if_start] + stmt + cb[if_end:]
                    pos = if_start
                    while pos > 0 and pos < len(cb) and cb[pos-1:pos] == b' ' and cb[pos:pos+1] == b' ':
                        cb = cb[:pos] + cb[pos+1:]
                    mod = True
                    break

                if value == 'false':
                    if alt:
                        at = _alt_text_b(alt, cb)
                        if at.startswith(b'{') and at.endswith(b'}'):
                            inner_lines = at[1:-1].split(b'\n')
                            while inner_lines and inner_lines[0].strip() == b'':
                                inner_lines.pop(0)
                            while inner_lines and inner_lines[-1].strip() == b'':
                                inner_lines.pop()
                            inner_body = b'\n'.join(l.rstrip() for l in inner_lines)
                            reindented = _reindent_b(inner_body, indent)
                            cb = _replace_and_trim_dead(cb, ls, reindented, construct_end, inner_body)
                        elif at.startswith(b'if'):
                            cb = cb[:ls] + indent + at + b'\n' + cb[construct_end:]
                        else:
                            cb = _replace_and_trim_dead(cb, ls, indent + at, construct_end, at)
                    else:
                        cb = cb[:ls] + cb[construct_end:]
                elif value == 'true':
                    cb = _replace_and_trim_dead(cb, ls, indent + stmt, construct_end, stmt)
                mod = True
                break

            body = _body_text_b(cons, cb)
            before_if = cb[ls:if_node.start_byte].strip()
            is_inline = len(before_if) > 0

            if is_inline:
                if_start = if_node.start_byte
                if_end = if_node.end_byte
                if value == 'false':
                    if alt:
                        at = _alt_text_b(alt, cb)
                        if at.startswith(b'if'):
                            cb = cb[:if_start] + at + cb[if_end:]
                        elif at.startswith(b'{') and at.endswith(b'}'):
                            inner = at[1:-1].strip()
                            cb = cb[:if_start] + inner + cb[if_end:]
                        else:
                            cb = cb[:if_start] + at + cb[if_end:]
                    else:
                        cb = cb[:if_start] + cb[if_end:]
                elif value == 'true':
                    cb = cb[:if_start] + body.strip() + cb[if_end:]
                pos = if_start
                while pos > 0 and pos < len(cb) and cb[pos-1:pos] == b' ' and cb[pos:pos+1] == b' ':
                    cb = cb[:pos] + cb[pos+1:]
                mod = True
                break

            if value == 'false':
                if alt:
                    at = _alt_text_b(alt, cb)
                    if at.startswith(b'if'):
                        cb = cb[:ls] + indent + at + b'\n' + cb[construct_end:]
                    elif at.startswith(b'{') and at.endswith(b'}'):
                        inner_lines = at[1:-1].split(b'\n')
                        while inner_lines and inner_lines[0].strip() == b'':
                            inner_lines.pop(0)
                        while inner_lines and inner_lines[-1].strip() == b'':
                            inner_lines.pop()
                        inner_body = b'\n'.join(l.rstrip() for l in inner_lines)
                        reindented = _reindent_b(inner_body, indent)
                        if _VAR_DECL_RE_B.search(inner_body) and preserve_branch_scope:
                            rep = indent + b'{\n' + reindented + b'\n' + indent + b'}'
                        else:
                            rep = reindented
                        cb = _replace_and_trim_dead(cb, ls, rep, construct_end, inner_body)
                    else:
                        cb = _replace_and_trim_dead(cb, ls, indent + at, construct_end, at)
                else:
                    cb = cb[:ls] + cb[construct_end:]
                mod = True
                break

            elif value == 'true':
                reindented = _reindent_b(body, indent)
                keep_braces = bool(_VAR_DECL_RE_B.search(body)) and preserve_branch_scope
                if keep_braces:
                    rep = indent + b'{\n' + reindented + b'\n' + indent + b'}'
                else:
                    rep = reindented
                cb = _replace_and_trim_dead(cb, ls, rep, construct_end, body)
                mod = True
                break

        if not mod:
            break
    return cb
