"""Step 1 — constant replacement (fold known identifiers to literal values).

Replaces occurrences of configured identifiers (e.g. ``AppConfig.IS_DEBUG``)
with their literal values, skipping comments, strings, and declaration sites.
"""

import re

_DECL_PREFIXES = (b'const ', b'var ', b'let ', b'val ', b'final ', b'#define ')


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
    """Replace *pattern* in *chunk*, skipping declaration/definition contexts."""
    out = b''
    pos = 0
    for m in re.finditer(pattern, chunk):
        ms, me = m.start(), m.end()
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
