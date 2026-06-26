"""Kotlin if-expression handling.

Kotlin if-expressions such as::

    return if (true) { body } else EXPR
    val x = if (false) "A" else "B"

are resolved in a dedicated text pre-pass before AST-based step 4 runs.
"""

import re


def _kt_find_non_comment(pat, code: str):
    """Return the first non-comment match of *pat* together with its line start."""
    offset = 0
    while True:
        m = pat.search(code, offset)
        if not m:
            return None
        ls = code.rfind('\n', 0, m.start())
        ls = ls + 1 if ls >= 0 else 0
        before = code[ls:m.start()].strip()
        if not before.startswith('//'):
            return m, ls
        offset = m.end()


def _kt_find_assignment_if(pat, code: str):
    """Return the first non-comment match in an assignment context."""
    offset = 0
    while True:
        m = pat.search(code, offset)
        if not m:
            return None
        ls = code.rfind('\n', 0, m.start())
        ls = ls + 1 if ls >= 0 else 0
        before = code[ls:m.start()].strip()
        if before.startswith('//'):
            offset = m.end()
            continue
        prefix_stripped = before.rstrip()
        prev_le = ls - 1
        prev_line = ''
        if prev_le > 0:
            prev_ls = code.rfind('\n', 0, prev_le)
            prev_ls = prev_ls + 1 if prev_ls >= 0 else 0
            prev_line = code[prev_ls:ls].rstrip()
        is_assignment = (prefix_stripped.endswith('=')
                         or prev_line.endswith('=')
                         or '=' in before)
        if is_assignment:
            return m, ls, prev_line, prefix_stripped
        offset = m.end()


def kotlin_if_expr(cb: bytes) -> bytes:
    """Resolve Kotlin if-expressions with constant conditions."""
    code = cb.decode('utf-8', errors='replace')
    pat1 = re.compile(r'(return\s+)if\s*\(\s*(true|false)\s*\)\s*\{')
    pat2 = re.compile(r'if\s*\(\s*(true|false)\s*\)\s+(.+?)\s+else\s+(.+?)([\n;]|$)')
    changed = True
    safety = 0
    while changed and safety < 200:
        changed = False
        safety += 1

        found = _kt_find_non_comment(pat1, code)
        if found:
            m, ls = found
            value = m.group(2)
            n = len(code)
            brace_start = m.end() - 1
            depth = 1
            i = brace_start + 1
            while i < n and depth > 0:
                if code[i] == '{': depth += 1
                elif code[i] == '}': depth -= 1
                elif code[i] == '"':
                    i += 1
                    while i < n and code[i] != '"':
                        if code[i] == '\\': i += 1
                        i += 1
                i += 1
            brace_end = i - 1
            body_text = code[brace_start + 1:brace_end].strip()

            j = brace_end + 1
            while j < n and code[j] in ' \t\n\r':
                j += 1
            if j + 4 <= n and code[j:j+4] == 'else' and (j+4 >= n or not code[j+4].isalnum()):
                ek = j + 4
                while ek < n and code[ek] in ' \t\n\r':
                    ek += 1
                if ek < n and code[ek] == '{':
                    depth2 = 1
                    k = ek + 1
                    while k < n and depth2 > 0:
                        if code[k] == '{': depth2 += 1
                        elif code[k] == '}': depth2 -= 1
                        k += 1
                    else_text = code[ek + 1:k - 1].strip()
                    else_end = k
                else:
                    paren_d = 0
                    k = ek
                    while k < n:
                        if code[k] == '(': paren_d += 1
                        elif code[k] == ')':
                            paren_d -= 1
                            if paren_d < 0: paren_d = 0
                        elif code[k] == '\n' and paren_d == 0: break
                        elif code[k] == ';' and paren_d == 0: break
                        k += 1
                    else_text = code[ek:k].strip()
                    else_end = k

                result = body_text if value == 'true' else else_text
                indent_ws = ''
                for c in code[ls:]:
                    if c in ' \t': indent_ws += c
                    else: break

                le = code.find('\n', else_end)
                if le == -1: le = n
                else: le += 1

                code = code[:ls] + indent_ws + 'return ' + result + '\n' + code[le:]
                changed = True
                continue

        found2 = _kt_find_assignment_if(pat2, code)
        if found2:
            m2, ls, prev_line, prefix_stripped = found2
            value = m2.group(1)
            a_expr = m2.group(2).strip()
            b_expr = m2.group(3).strip()
            terminator = m2.group(4)
            trail = ''
            if terminator == ';':
                trail = ';'
            if b_expr.endswith(';'):
                b_expr = b_expr[:-1]
                trail = ';'
            if a_expr.endswith(';'):
                a_expr = a_expr[:-1]
                trail = ';'
            result = a_expr if value == 'true' else b_expr

            if prev_line.endswith('=') and not prefix_stripped:
                prev_le = ls - 1
                prev_ls2 = code.rfind('\n', 0, prev_le)
                prev_ls2 = prev_ls2 + 1 if prev_ls2 >= 0 else 0
                le = m2.end()
                after = code[le:]
                nl = '\n' if not after.startswith('\n') else ''
                code = code[:prev_ls2] + prev_line + ' ' + result + trail + nl + code[le:]
                changed = True
                continue

            le = m2.end()
            after = code[le:]
            nl = '\n' if not after.startswith('\n') else ''
            code = code[:m2.start()] + result + trail + nl + code[le:]
            changed = True
            continue

    return code.encode('utf-8')
