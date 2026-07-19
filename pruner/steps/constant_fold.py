"""Phase 1, Steps 1–2 and 8 — constant and local-variable handling.

Replaces occurrences of configured identifiers (e.g. ``AppConfig.IS_DEBUG``)
with their literal values, skipping comments, strings, and declaration sites.
Then propagates locally-declared immutable boolean constants to their uses
within the same file.
"""

import re

from ..adapters import get_adapter
from ..ast_utils import parse
from ..lang import _PARSERS

_DECL_PREFIXES = (b'const ', b'var ', b'let ', b'val ', b'final ', b'#define ')

_TYPE_NAMES = frozenset({
    b'Boolean', b'Bool', b'boolean', b'String', b'Int', b'Long',
    b'Float', b'Double', b'Integer', b'Object', b'Void', b'Unit',
})


def _non_code_spans(content: bytes, ext: str) -> list[tuple[int, int]]:
    """Return tree-sitter string/comment spans for one complete or partial file."""
    parser = _PARSERS.get(ext)
    if parser is None:
        return []
    root = parser.parse(content).root_node
    spans: list[tuple[int, int]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        node_type = node.type.lower()
        lexical = ('comment' in node_type or 'string' in node_type
                   or node_type in {'character_literal', 'rune_literal'})
        if lexical:
            spans.append((node.start_byte, node.end_byte))
            continue
        stack.extend(node.named_children)
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _masked_code(content: bytes, ext: str) -> bytes:
    masked = bytearray(content)
    for start, end in _non_code_spans(content, ext):
        masked[start:end] = b' ' * (end - start)
    return bytes(masked)


def _tokenize_and_replace(content_bytes: bytes, pattern_bytes: bytes,
                          replacement_bytes: bytes, ext: str) -> bytes:
    """Apply a replacement only to tree-sitter-confirmed code spans."""
    result: list[bytes] = []
    position = 0
    for start, end in _non_code_spans(content_bytes, ext):
        if position < start:
            result.append(_replace_skip_decl(
                content_bytes[position:start], pattern_bytes, replacement_bytes))
        result.append(content_bytes[start:end])
        position = end
    if position < len(content_bytes):
        result.append(_replace_skip_decl(
            content_bytes[position:], pattern_bytes, replacement_bytes))
    return b''.join(result)


def _replace_skip_decl(chunk: bytes, pattern: bytes, replacement: bytes) -> bytes:
    """Replace *pattern* in *chunk*, skipping declaration/definition contexts
    and member access (dot-prefixed names like ``.cancelable()``)."""
    out = b''
    pos = 0
    for m in re.finditer(pattern, chunk):
        ms, me = m.start(), m.end()

        if ms > 0 and chunk[ms-1:ms] == b'.':
            out += chunk[pos:me]
            pos = me
            continue

        after_char = chunk[me:me+1]
        if after_char == b'(':
            out += chunk[pos:me]
            pos = me
            continue

        ls = chunk.rfind(b'\n', 0, ms)
        ls = ls + 1 if ls >= 0 else 0
        before_on_line = chunk[ls:ms]
        stripped = before_on_line.lstrip()
        is_decl = False
        for pfx in _DECL_PREFIXES:
            if stripped.startswith(pfx) or stripped.startswith(b'static ' + pfx):
                after = chunk[me:chunk.find(b'\n', me) if chunk.find(b'\n', me) != -1 else len(chunk)]
                if b'=' in after or after.strip().startswith(b'='):
                    is_decl = True
                    break
                if pfx == b'#define ':
                    is_decl = True
                    break
        if not is_decl:
            after_match = chunk[me:me+3].lstrip()
            if after_match.startswith(b'=') and not after_match.startswith(b'=='):
                is_decl = True
        if is_decl:
            out += chunk[pos:me]
            pos = me
        else:
            out += chunk[pos:ms] + replacement
            pos = me
    out += chunk[pos:]
    return out


def phase1_step1_replace_constants(
        cb: bytes, replacements: list, ext: str = '.java') -> bytes:
    """Replace configured constants, skipping comments and strings."""
    if not replacements:
        return cb
    method_rules = [rule for rule in replacements
                    if getattr(rule, 'kind', 'symbol') == 'method_call']
    adapter = get_adapter(ext)
    if method_rules and adapter:
        cb = adapter.replace_configured_calls(cb, method_rules)
    replacements = [rule for rule in replacements
                    if getattr(rule, 'kind', 'symbol') == 'symbol']
    if not replacements:
        return cb
    spans = _non_code_spans(cb, ext)
    chunks: list[tuple[bool, bytes]] = []
    position = 0
    for start, end in spans:
        if position < start:
            chunks.append((True, cb[position:start]))
        chunks.append((False, cb[start:end]))
        position = end
    if position < len(cb):
        chunks.append((True, cb[position:]))
    return b''.join(
        _replace_configured_chunk(chunk, replacements) if is_code else chunk
        for is_code, chunk in chunks
    )


def _replace_configured_chunk(cb: bytes, replacements: list) -> bytes:
    """Reach a replacement fixed point inside one AST-confirmed code span."""
    changed = True
    while changed:
        changed = False
        for pat_str, value in replacements:
            pat_b = pat_str.encode('utf-8')
            if pat_b not in cb:
                continue
            escaped = re.escape(pat_b)
            val_b = value.encode('utf-8')
            for pat in [rb'[a-zA-Z_][a-zA-Z0-9_.]*\.' + escaped + rb'\b',
                        rb'\b' + escaped + rb'\b']:
                prev = cb
                cb = _replace_skip_decl(cb, pat, val_b)
                if cb != prev:
                    changed = True
                    break
            if changed:
                break
    return cb


# ── Phase 1, Step 2: local constant propagation ──────────────

def _find_enclosing_scope(cb: bytes, pos: int, ext: str,
                          code: bytes | None = None) -> tuple[int, int]:
    """Find the ``{ ... }`` pair enclosing *pos*, skipping strings and comments.

    Returns ``(open_brace, close_brace)`` byte positions, or ``(-1, -1)``
    if no enclosing scope is found.
    """
    if code is None:
        code = _masked_code(cb, ext)
    depth = 0
    i = pos
    while i > 0:
        i -= 1
        c = code[i:i+1]
        if c == b'}':
            depth += 1
        elif c == b'{':
            if depth == 0:
                break
            depth -= 1
    else:
        return -1, -1
    open_pos = i

    depth = 1
    j = pos
    n = len(code)
    while j < n and depth > 0:
        c = code[j:j+1]
        if c == b'{':
            depth += 1
        elif c == b'}':
            depth -= 1
        j += 1
    if depth != 0:
        return -1, -1
    return open_pos, j


def _extract_scoped_bool_constants(
        cb: bytes, patterns, ext: str
        ) -> list[tuple[bytes, bytes, int, int, int, int, int]]:
    """Find immutable local boolean declarations with their enclosing scopes.

    Returns ``[(name, value, decl_start, match_end, decl_end,
    scope_start, scope_end), ...]``.  ``match_end`` distinguishes a standalone
    declaration from one embedded in a multi-statement line; ``decl_end`` is
    the start of the following line used for propagation.
    """
    results = []
    code = _masked_code(cb, ext)
    parser = _PARSERS.get(ext)
    root = parser.parse(cb).root_node if parser is not None else None
    adapter = get_adapter(ext)
    for pat in patterns:
        for m in pat.finditer(code):
            name = m.group(1)
            value = m.group(2)
            if name in _TYPE_NAMES:
                continue
            scope_start, scope_end = _find_enclosing_scope(
                cb, m.start(), ext, code)
            if scope_start < 0:
                continue
            le = cb.find(b'\n', m.end())
            decl_end = le + 1 if le != -1 else m.end()
            if (adapter is not None and root is not None
                    and not adapter.local_boolean_is_propagatable(
                        root, code, name, m.start(), decl_end, scope_end)):
                continue
            results.append((name, value, m.start(), m.end(), decl_end,
                            scope_start, scope_end))
    return results


def phase1_step2_propagate_local_constants(
        cb: bytes, ext: str = '.java') -> bytes:
    """Propagate locally-declared immutable boolean constants to their uses.

    Detects patterns like ``final boolean isPrimary = false;`` or
    ``val isDebug = true`` and replaces non-declaration uses of the
    variable within the same enclosing scope (function body).
    """
    adapter = get_adapter(ext)
    patterns = adapter.local_boolean_patterns if adapter else ()
    for _ in range(20):
        constants = _extract_scoped_bool_constants(cb, patterns, ext)
        if not constants:
            break
        prev = cb
        for name, value, _ds, _match_end, decl_end, _ss, scope_end in constants:
            after_decl = cb[decl_end:scope_end]
            pat = rb'\b' + re.escape(name) + rb'\b'
            new_after = _tokenize_and_replace(after_decl, pat, value, ext)
            if new_after != after_decl:
                cb = cb[:decl_end] + new_after + cb[scope_end:]
                break
        if cb == prev:
            break
    return cb


# ── Phase 1, Step 8: unused local variable cleanup ───────────

def phase1_step8_remove_unused_bool_vars(
        cb: bytes, ext: str = '.java') -> bytes:
    """Remove declarations of boolean variables whose names no longer appear
    within the same enclosing callable scope.

    Candidate discovery is deliberately shared with constant propagation so
    this cleanup cannot broaden the policy and mistake a class field for a
    local variable merely because both use the same declaration syntax.
    """
    adapter = get_adapter(ext)
    patterns = adapter.local_boolean_patterns if adapter else ()
    for _ in range(10):
        changed = False
        code = _masked_code(cb, ext)
        candidates = _extract_scoped_bool_constants(cb, patterns, ext)
        for (name, _value, decl_start, match_end, decl_end,
             _scope_start, scope_end) in candidates:
            line_start = cb.rfind(b'\n', 0, decl_start) + 1
            line_end = cb.find(b'\n', decl_start)
            if line_end < 0:
                line_end = len(cb)
            prefix = cb[line_start:decl_start]
            declaration_tail = cb[match_end:line_end]
            if prefix.strip() or declaration_tail.strip(b' \t;'):
                continue
            scope_rest = cb[decl_end:scope_end]
            use_pat = re.compile(rb'\b' + re.escape(name) + rb'\b')
            if not use_pat.search(scope_rest):
                cb = cb[:line_start] + cb[decl_end:]
                changed = True
                break
        if not changed:
            break
    return cb
