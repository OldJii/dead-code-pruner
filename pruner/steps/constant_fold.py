"""Step 1 — constant replacement + local constant propagation.

Replaces occurrences of configured identifiers (e.g. ``AppConfig.IS_DEBUG``)
with their literal values, skipping comments, strings, and declaration sites.
Then propagates locally-declared immutable boolean constants to their uses
within the same file.
"""

import re

_DECL_PREFIXES = (b'const ', b'var ', b'let ', b'val ', b'final ', b'#define ')

_LOCAL_BOOL_PATTERNS = [
    # Java: final boolean isX = true;
    re.compile(rb'\bfinal\s+(?:boolean|Boolean)\s+(\w{3,})\s*=\s*(true|false)\s*;'),
    # Kotlin: val isX = true  /  val isX: Boolean = true
    re.compile(rb'\bval\s+(\w{3,})\s*(?::\s*(?:Boolean|Bool)\s*)?=\s*(true|false)\b'),
    # Swift: let isX = true  /  let isX: Bool = true
    re.compile(rb'\blet\s+(\w{3,})\s*(?::\s*Bool\s*)?=\s*(true|false)\b'),
    # Dart: final isX = true;  /  final bool isX = true;  /  const isX = true;
    re.compile(rb'\b(?:final|const)\s+(?:bool\s+)?(\w{3,})\s*=\s*(true|false)\s*;'),
]

_TYPE_NAMES = frozenset({
    b'Boolean', b'Bool', b'boolean', b'String', b'Int', b'Long',
    b'Float', b'Double', b'Integer', b'Object', b'Void', b'Unit',
})


def _tokenize_and_replace(content_bytes: bytes, pattern_bytes: bytes,
                          replacement_bytes: bytes) -> bytes:
    """Split content into (code, non-code) tokens, apply regex only to code."""
    tokens = []
    i = 0
    n = len(content_bytes)
    code_start = 0

    while i < n:
        if content_bytes[i:i+2] == b'/*':
            if i > code_start:
                tokens.append((True, content_bytes[code_start:i]))
            end = content_bytes.find(b'*/', i + 2)
            if end == -1:
                end = n - 2
            tokens.append((False, content_bytes[i:end + 2]))
            i = end + 2
            code_start = i
            continue
        if content_bytes[i:i+2] == b'//':
            if i > code_start:
                tokens.append((True, content_bytes[code_start:i]))
            end = content_bytes.find(b'\n', i)
            if end == -1:
                end = n
            tokens.append((False, content_bytes[i:end]))
            i = end
            code_start = i
            continue
        if content_bytes[i:i+1] == b'"':
            if i > code_start:
                tokens.append((True, content_bytes[code_start:i]))
            j = i + 1
            while j < n:
                if content_bytes[j:j+1] == b'\\':
                    j += 2
                    continue
                if content_bytes[j:j+1] == b'"':
                    j += 1
                    break
                j += 1
            tokens.append((False, content_bytes[i:j]))
            i = j
            code_start = i
            continue
        if content_bytes[i:i+1] == b"'":
            if i > code_start:
                tokens.append((True, content_bytes[code_start:i]))
            j = i + 1
            while j < n:
                if content_bytes[j:j+1] == b'\\':
                    j += 2
                    continue
                if content_bytes[j:j+1] == b"'":
                    j += 1
                    break
                j += 1
            tokens.append((False, content_bytes[i:j]))
            i = j
            code_start = i
            continue
        i += 1

    if code_start < n:
        tokens.append((True, content_bytes[code_start:]))

    result = []
    for is_code, chunk in tokens:
        if is_code:
            chunk = _replace_skip_decl(chunk, pattern_bytes, replacement_bytes)
        result.append(chunk)
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


def step1_replace(cb: bytes, replacements: list) -> bytes:
    """Replace configured constants, skipping comments and strings."""
    if not replacements:
        return cb
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
                cb = _tokenize_and_replace(cb, pat, val_b)
                if cb != prev:
                    changed = True
                    break
            if changed:
                break
    return cb


# ── Step 1b: local constant propagation ──────────────────────

def _find_enclosing_scope(cb: bytes, pos: int) -> tuple[int, int]:
    """Find the ``{ ... }`` pair enclosing *pos*, skipping strings and comments.

    Returns ``(open_brace, close_brace)`` byte positions, or ``(-1, -1)``
    if no enclosing scope is found.
    """
    depth = 0
    i = pos
    while i > 0:
        i -= 1
        c = cb[i:i+1]
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
    n = len(cb)
    in_str = False
    in_lc = False
    in_bc = False
    while j < n and depth > 0:
        c = cb[j:j+1]
        if in_lc:
            if c == b'\n':
                in_lc = False
        elif in_bc:
            if c == b'*' and j + 1 < n and cb[j+1:j+2] == b'/':
                in_bc = False
                j += 1
        elif in_str:
            if c == b'\\':
                j += 1
            elif c == b'"':
                in_str = False
        elif c == b'/' and j + 1 < n:
            c2 = cb[j+1:j+2]
            if c2 == b'/':
                in_lc = True
            elif c2 == b'*':
                in_bc = True
                j += 1
        elif c == b'"':
            in_str = True
        elif c == b'{':
            depth += 1
        elif c == b'}':
            depth -= 1
        j += 1
    if depth != 0:
        return -1, -1
    return open_pos, j


def _extract_scoped_bool_constants(cb: bytes) -> list[tuple[bytes, bytes, int, int, int, int]]:
    """Find immutable local boolean declarations with their enclosing scopes.

    Returns ``[(name, value, decl_start, decl_end, scope_start, scope_end), ...]``.
    """
    results = []
    for pat in _LOCAL_BOOL_PATTERNS:
        for m in pat.finditer(cb):
            name = m.group(1)
            value = m.group(2)
            if name in _TYPE_NAMES:
                continue
            scope_start, scope_end = _find_enclosing_scope(cb, m.start())
            if scope_start < 0:
                continue
            le = cb.find(b'\n', m.end())
            decl_end = le + 1 if le != -1 else m.end()
            results.append((name, value, m.start(), decl_end, scope_start, scope_end))
    return results


def step1b_propagate_locals(cb: bytes) -> bytes:
    """Propagate locally-declared immutable boolean constants to their uses.

    Detects patterns like ``final boolean isIntl = false;`` or
    ``val isDebug = true`` and replaces non-declaration uses of the
    variable within the same enclosing scope (function body).
    """
    for _ in range(20):
        constants = _extract_scoped_bool_constants(cb)
        if not constants:
            break
        prev = cb
        for name, value, _ds, decl_end, _ss, scope_end in constants:
            after_decl = cb[decl_end:scope_end]
            pat = rb'\b' + re.escape(name) + rb'\b'
            new_after = _tokenize_and_replace(after_decl, pat, value)
            if new_after != after_decl:
                cb = cb[:decl_end] + new_after + cb[scope_end:]
                break
        if cb == prev:
            break
    return cb


# ── Step 1c: unused local variable cleanup ───────────────────

_BOOL_DECL_LINE = re.compile(
    rb'^\s*final\s+(?:boolean|Boolean|bool|Bool)\s+(\w{3,})\s*=\s*(?:true|false)\s*;\s*$',
    re.MULTILINE,
)
_IMMUTABLE_DECL_LINE = re.compile(
    rb'^\s*(?:val|let|(?:final|const)\s+(?:bool\s+)?)\s*(\w{3,})\s*(?::\s*\w+\s*)?=\s*(?:true|false)\s*;?\s*$',
    re.MULTILINE,
)


def step1c_remove_unused_bool_vars(cb: bytes) -> bytes:
    """Remove declarations of boolean variables whose names no longer appear
    within the same enclosing scope."""
    for _ in range(10):
        changed = False
        for pat in (_BOOL_DECL_LINE, _IMMUTABLE_DECL_LINE):
            for m in pat.finditer(cb):
                name = m.group(1)
                if name in _TYPE_NAMES:
                    continue
                scope_start, scope_end = _find_enclosing_scope(cb, m.start())
                if scope_start < 0:
                    continue
                le = cb.find(b'\n', m.end())
                decl_end = le + 1 if le != -1 else m.end()
                scope_rest = cb[decl_end:scope_end]
                use_pat = re.compile(rb'\b' + re.escape(name) + rb'\b')
                if not use_pat.search(scope_rest):
                    ls = cb.rfind(b'\n', 0, m.start())
                    ls = ls + 1 if ls >= 0 else 0
                    if le == -1:
                        le = len(cb)
                    else:
                        le += 1
                    cb = cb[:ls] + cb[le:]
                    changed = True
                    break
            if changed:
                break
        if not changed:
            break
    return cb
