#!/usr/bin/env python3
"""
Step 4: if(true)/if(false) block elimination
- if(false) { A } → remove
- if(false) { A } else { B } → keep B
- if(false) { A } else if (X) { B } else { C } → if (X) { B } else { C }
- if(true) { A } → unwrap A (with dead code removal)
- if(true) { A } else { B } → keep A
- if(true) { A } else if (X) { B } → keep A (remove entire else-if chain)
- if(true) { A } else if (X) { B } else { C } → keep A
- single-line: if (false) return X; → remove
- Kotlin assignment: x = if (false) 0 else y → remove assignment line
"""
import os, re, sys

IF_PATTERN = re.compile(r'\bif\s*\(\s*(true|false)\s*\)')


def find_matching_brace(content, start):
    depth = 0
    i = start
    n = len(content)
    while i < n:
        c = content[i]
        if c == '/' and i + 1 < n:
            if content[i+1] == '/':
                end = content.find('\n', i)
                i = end if end != -1 else n
                continue
            elif content[i+1] == '*':
                end = content.find('*/', i+2)
                i = end + 2 if end != -1 else n
                continue
        elif c == '"':
            i += 1
            while i < n and content[i] != '"':
                if content[i] == '\\': i += 1
                i += 1
            i += 1; continue
        elif c == "'":
            i += 1
            while i < n and content[i] != "'":
                if content[i] == '\\': i += 1
                i += 1
            i += 1; continue
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return i
        i += 1
    return -1


def find_else_chain_end(content, close_brace_pos):
    """After a closing '}', find the full extent of any else/else-if chain.
    Returns (has_else, chain_start, chain_end) where chain covers from 'else' keyword
    to the closing '}' of the last block in the chain."""
    i = close_brace_pos + 1
    n = len(content)
    while i < n and content[i] in ' \t\n\r':
        i += 1
    if i + 4 > n or content[i:i+4] != 'else':
        return (False, -1, -1)
    if i + 4 < n and content[i+4].isalnum():
        return (False, -1, -1)

    chain_start = i
    j = i + 4
    while j < n and content[j] in ' \t\n\r':
        j += 1

    if j < n and content[j] == '{':
        # simple else { ... }
        close = find_matching_brace(content, j)
        if close != -1:
            return (True, chain_start, close)
        return (False, -1, -1)

    if j + 2 <= n and content[j:j+2] == 'if':
        # else if (...) { ... } [else ...]
        end = _find_if_chain_end(content, j)
        if end != -1:
            return (True, chain_start, end)

    # else EXPR (Kotlin expression or simple Java statement without braces)
    paren_d = 0
    k = j
    while k < n:
        c = content[k]
        if c == '(': paren_d += 1
        elif c == ')':
            paren_d -= 1
            if paren_d < 0: paren_d = 0
        elif c == '"':
            k += 1
            while k < n and content[k] != '"':
                if content[k] == '\\': k += 1
                k += 1
        elif c == ';' and paren_d == 0:
            return (True, chain_start, k)
        elif c == '\n' and paren_d == 0:
            return (True, chain_start, k - 1)
        k += 1
    if k > j:
        return (True, chain_start, n - 1)
    return (False, -1, -1)


def _find_if_chain_end(content, if_pos):
    """Find end of if(...){...} [else if(...){...}]* [else{...}] chain."""
    n = len(content)
    pos = if_pos
    while pos < n:
        # Match 'if' and its condition
        m = re.match(r'\s*if\s*\(', content[pos:])
        if not m:
            return -1
        # Find matching ')' for condition
        paren_start = pos + m.end() - 1
        depth = 1
        k = paren_start + 1
        while k < n and depth > 0:
            if content[k] == '(': depth += 1
            elif content[k] == ')': depth -= 1
            elif content[k] == '"':
                k += 1
                while k < n and content[k] != '"':
                    if content[k] == '\\': k += 1
                    k += 1
            k += 1
        # Find opening '{'
        while k < n and content[k] in ' \t\n\r':
            k += 1
        if k >= n or content[k] != '{':
            return -1
        close = find_matching_brace(content, k)
        if close == -1:
            return -1
        # Check for else after this block
        j = close + 1
        while j < n and content[j] in ' \t\n\r':
            j += 1
        if j + 4 <= n and content[j:j+4] == 'else' and (j+4 >= n or not content[j+4].isalnum()):
            k2 = j + 4
            while k2 < n and content[k2] in ' \t\n\r':
                k2 += 1
            if k2 < n and content[k2] == '{':
                final_close = find_matching_brace(content, k2)
                return final_close if final_close != -1 else close
            elif k2 + 2 <= n and content[k2:k2+2] == 'if':
                pos = k2
                continue
            else:
                return close
        else:
            return close
    return -1


def get_body_content(content, open_brace, close_brace):
    body = content[open_brace+1:close_brace]
    lines = body.split('\n')
    while lines and lines[0].strip() == '':
        lines.pop(0)
    while lines and lines[-1].strip() == '':
        lines.pop()
    return '\n'.join(line.rstrip() for line in lines)


def get_line_start(content, pos):
    ls = content.rfind('\n', 0, pos)
    return ls + 1 if ls != -1 else 0


def get_line_end(content, pos):
    le = content.find('\n', pos)
    return le + 1 if le != -1 else len(content)


def is_in_comment_or_string(content, pos):
    """Check if position is inside a comment or string literal.
    Scans from file start to be accurate (handles '/*' inside strings like \"*/*\")."""
    in_str = False
    in_block_comment = False
    i = 0
    n = len(content)
    while i < pos:
        if in_block_comment:
            if content[i] == '*' and i + 1 < n and content[i+1] == '/':
                in_block_comment = False
                i += 2; continue
            i += 1; continue
        if in_str:
            if content[i] == '\\':
                i += 2; continue
            if content[i] == '"':
                in_str = False
            i += 1; continue
        c = content[i]
        if c == '"':
            in_str = True
            i += 1; continue
        if c == "'":
            i += 1
            while i < n and content[i] != "'":
                if content[i] == '\\': i += 1
                i += 1
            i += 1; continue
        if c == '/' and i + 1 < n:
            if content[i+1] == '*':
                in_block_comment = True
                i += 2; continue
            if content[i+1] == '/':
                eol = content.find('\n', i)
                if eol == -1: eol = n
                if pos <= eol:
                    return True
                i = eol + 1; continue
        i += 1
    return in_str or in_block_comment


def reindent_body(body, target_indent):
    """Re-indent body to target_indent level, preserving relative indentation."""
    lines = body.split('\n')
    if not lines:
        return body
    min_indent = float('inf')
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            min_indent = min(min_indent, len(line) - len(stripped))
    if min_indent == float('inf'):
        min_indent = 0
    result = []
    for line in lines:
        stripped = line.lstrip()
        if not stripped:
            result.append('')
        else:
            extra = len(line) - len(stripped) - min_indent
            result.append(target_indent + ' ' * extra + stripped)
    return '\n'.join(result)


def body_has_unconditional_exit(body):
    """Check if the last top-level statement is return/throw/break/continue.
    Tracks both brace and paren depth to handle multi-line return/throw."""
    lines = body.strip().split('\n')
    if not lines:
        return False
    brace = 0
    paren = 0
    waiting_for_stmt_start = True
    last_stmt_is_exit = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            continue
        if waiting_for_stmt_start and brace == 0 and paren == 0:
            last_stmt_is_exit = bool(re.match(
                r'^(return\b|throw\b|break\s*;|continue\s*;)', stripped))
            waiting_for_stmt_start = False
        for c in stripped:
            if c == '{': brace += 1
            elif c == '}':
                brace -= 1
                if brace <= 0:
                    brace = 0
                    waiting_for_stmt_start = True
            elif c == '(': paren += 1
            elif c == ')':
                paren -= 1
                if paren < 0: paren = 0
            elif c == ';' and brace == 0 and paren == 0:
                waiting_for_stmt_start = True
    return last_stmt_is_exit


_VAR_DECL_RE = re.compile(
    r'^\s*(final\s+)?(String|int|long|boolean|float|double|char|byte|short|void|var|val|[A-Z]\w*(<[^>]*>)?)\s+\w+\s*[=;]',
    re.MULTILINE)

_CASE_RE = re.compile(r'\bcase\s+\w')
_DEFAULT_RE = re.compile(r'\bdefault\s*:')

def find_dead_code_end(content, start_pos):
    depth = 0
    i = start_pos
    n = len(content)
    while i < n:
        c = content[i]
        if c == '/' and i+1 < n:
            if content[i+1] == '/':
                end = content.find('\n', i)
                i = end if end != -1 else n; continue
            elif content[i+1] == '*':
                end = content.find('*/', i+2)
                i = end + 2 if end != -1 else n; continue
        elif c == '"':
            i += 1
            while i < n and content[i] != '"':
                if content[i] == '\\': i += 1
                i += 1
            i += 1; continue
        elif c == "'":
            i += 1
            while i < n and content[i] != "'":
                if content[i] == '\\': i += 1
                i += 1
            i += 1; continue
        elif c == '{': depth += 1
        elif c == '}':
            if depth == 0: return i
            depth -= 1
        elif depth == 0 and c in 'cd':
            if _CASE_RE.match(content, i) or _DEFAULT_RE.match(content, i):
                return i
        i += 1
    return -1


def _find_inline_else(content, start):
    """Find 'else' keyword on the same line (before \\n at paren depth 0).
    Returns position of 'e' in 'else', or -1."""
    pd = 0
    i = start
    n = len(content)
    while i < n:
        c = content[i]
        if c == '(': pd += 1
        elif c == ')':
            pd -= 1
            if pd < 0: pd = 0
        elif c == '"':
            i += 1
            while i < n and content[i] != '"':
                if content[i] == '\\': i += 1
                i += 1
        elif c == ';' and pd == 0:
            return -1
        elif c == '\n' and pd == 0:
            return -1
        elif pd == 0 and i + 4 <= n and content[i:i+4] == 'else' and (i+4 >= n or not content[i+4].isalnum()):
            return i
        i += 1
    return -1


def _find_expr_end_inline(content, start):
    """Find end of inline expression: stops at ; or \\n at paren depth 0."""
    pd = 0
    i = start
    n = len(content)
    while i < n:
        c = content[i]
        if c == '(': pd += 1
        elif c == ')':
            pd -= 1
            if pd < 0: pd = 0
        elif c == '"':
            i += 1
            while i < n and content[i] != '"':
                if content[i] == '\\': i += 1
                i += 1
        elif c == ';' and pd == 0:
            return i + 1
        elif c == '\n' and pd == 0:
            return i
        i += 1
    return n


def _find_single_else_end(content, after_stmt_pos):
    """After a single-line if's stmt ends, look for an else clause.
    If found, returns the line_end after the else clause.
    If not found, returns get_line_end(content, after_stmt_pos - 1)."""
    i = after_stmt_pos
    n = len(content)
    while i < n and content[i] in ' \t\n\r':
        i += 1
    if i + 4 > n or content[i:i+4] != 'else':
        return get_line_end(content, after_stmt_pos - 1)
    if i + 4 < n and content[i+4].isalnum():
        return get_line_end(content, after_stmt_pos - 1)
    j = i + 4
    while j < n and content[j] in ' \t\n\r':
        j += 1
    if j < n and content[j] == '{':
        close = find_matching_brace(content, j)
        if close != -1:
            return get_line_end(content, close)
    elif j + 2 <= n and content[j:j+2] == 'if':
        end = _find_if_chain_end(content, j)
        if end != -1:
            return get_line_end(content, end)
    else:
        semi = content.find(';', j)
        if semi != -1:
            return get_line_end(content, semi)
    return get_line_end(content, after_stmt_pos - 1)


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'true' not in content and 'false' not in content:
        return 0
    if not IF_PATTERN.search(content):
        return 0
    original = content
    changes = 0
    max_iter = 500
    search_from = 0

    for _ in range(max_iter):
        match = IF_PATTERN.search(content, search_from)
        if not match:
            break

        if is_in_comment_or_string(content, match.start()):
            search_from = match.end()
            continue

        value = match.group(1)
        if_start = match.start()
        if_end = match.end()
        brace_pos = if_end
        while brace_pos < len(content) and content[brace_pos] in ' \t\n\r':
            brace_pos += 1

        if brace_pos >= len(content) or content[brace_pos] != '{':
            # --- 单行 if ---
            # Check for Kotlin-style: x = if (false) 0 else y
            line_start = get_line_start(content, if_start)
            before_if = content[line_start:if_start].strip()

            if value == 'false':
                # 1. Check for inline else on same line (Kotlin ternary)
                inline_else = _find_inline_else(content, if_end)
                if inline_else != -1:
                    ek = inline_else + 4
                    while ek < len(content) and content[ek] in ' \t':
                        ek += 1
                    expr_end = _find_expr_end_inline(content, ek)
                    else_expr = content[ek:expr_end].strip()
                    line_end_full = get_line_end(content, min(expr_end, len(content) - 1))
                    assign_start = line_start
                    prev_le = line_start - 1
                    if prev_le > 0:
                        prev_start = get_line_start(content, prev_le)
                        prev = content[prev_start:line_start].strip()
                        if prev.endswith('='):
                            assign_start = prev_start
                    if assign_start < line_start:
                        assign_line = content[assign_start:line_start].rstrip()
                        content = content[:assign_start] + assign_line + ' ' + else_expr + '\n' + content[line_end_full:]
                    else:
                        before = content[line_start:if_start]
                        content = content[:line_start] + before + else_expr + '\n' + content[line_end_full:]
                    changes += 1; search_from = 0; continue

                # 2. Find end of this statement (limited to current line for safety)
                stmt_end = _find_expr_end_inline(content, if_end)

                # 3. Check for else on next line(s) after the stmt
                after_stmt = stmt_end
                while after_stmt < len(content) and content[after_stmt] in ' \t\n\r':
                    after_stmt += 1
                if (after_stmt + 4 <= len(content) and content[after_stmt:after_stmt+4] == 'else'
                        and (after_stmt+4 >= len(content) or not content[after_stmt+4].isalnum())):
                    ek = after_stmt + 4
                    while ek < len(content) and content[ek] in ' \t\n\r':
                        ek += 1
                    indent = content[line_start:if_start]
                    if ek < len(content) and content[ek] == '{':
                        close = find_matching_brace(content, ek)
                        if close != -1:
                            body = get_body_content(content, ek, close)
                            lend = get_line_end(content, close)
                            reindented = reindent_body(body, indent)
                            content = content[:line_start] + reindented + '\n' + content[lend:]
                            changes += 1; search_from = 0; continue
                    elif ek + 2 <= len(content) and content[ek:ek+2] == 'if':
                        end = _find_if_chain_end(content, ek)
                        if end != -1:
                            eif = content[ek:end+1]
                            lend = get_line_end(content, end)
                            content = content[:line_start] + indent + eif + '\n' + content[lend:]
                            changes += 1; search_from = 0; continue
                    else:
                        else_end = _find_expr_end_inline(content, ek)
                        estmt = content[ek:else_end].strip()
                        lend = get_line_end(content, min(else_end, len(content) - 1))
                        content = content[:line_start] + indent + estmt + '\n' + content[lend:]
                        changes += 1; search_from = 0; continue

                # 4. Simple delete: remove the if(false) statement
                line_end = get_line_end(content, min(stmt_end, len(content) - 1))
                content = content[:line_start] + content[line_end:]
                changes += 1; search_from = 0; continue

            elif value == 'true':
                # Check for Kotlin ternary: if (true) A else B (no braces)
                else_check = _find_inline_else(content, if_end)
                if else_check != -1:
                    a_expr = content[if_end:else_check].strip()
                    ek = else_check + 4
                    while ek < len(content) and content[ek] in ' \t':
                        ek += 1
                    expr_end = _find_expr_end_inline(content, ek)
                    line_end_full = get_line_end(content, min(expr_end, len(content) - 1))
                    assign_start = line_start
                    prev_le = line_start - 1
                    if prev_le > 0:
                        prev_start = get_line_start(content, prev_le)
                        prev = content[prev_start:line_start].strip()
                        if prev.endswith('='):
                            assign_start = prev_start
                    if assign_start < line_start:
                        assign_line = content[assign_start:line_start].rstrip()
                        content = content[:assign_start] + assign_line + ' ' + a_expr + '\n' + content[line_end_full:]
                    else:
                        before = content[line_start:if_start]
                        content = content[:line_start] + before + a_expr + '\n' + content[line_end_full:]
                    changes += 1; search_from = 0; continue

                # if (true) stmt → stmt (and remove else clause if present)
                stmt_end = _find_expr_end_inline(content, if_end)
                stmt = content[if_end:stmt_end].strip()
                if not stmt:
                    search_from = if_end; continue
                indent = content[line_start:if_start]
                line_end = _find_single_else_end(content, stmt_end)
                is_exit = bool(re.match(r'^(return\b|throw\b|break\b|continue\b)', stmt))
                if is_exit:
                    dead_end = find_dead_code_end(content, line_end)
                    if dead_end != -1:
                        between = content[line_end:dead_end].strip()
                        if between:
                            scope_line_start = get_line_start(content, dead_end)
                            content = content[:line_start] + indent + stmt + '\n' + content[scope_line_start:]
                        else:
                            content = content[:line_start] + indent + stmt + '\n' + content[line_end:]
                    else:
                        content = content[:line_start] + indent + stmt + '\n' + content[line_end:]
                else:
                    content = content[:line_start] + indent + stmt + '\n' + content[line_end:]
                changes += 1; search_from = 0; continue

            search_from = if_end
            continue

        # --- Block if { ... } ---
        open_brace = brace_pos
        close_brace = find_matching_brace(content, open_brace)
        if close_brace == -1:
            search_from = if_end; continue

        body = get_body_content(content, open_brace, close_brace)
        line_start = get_line_start(content, if_start)
        has_else, else_start, else_end = find_else_chain_end(content, close_brace)

        if has_else:
            construct_end = get_line_end(content, else_end)
        else:
            construct_end = get_line_end(content, close_brace)

        # --- Check if this is "else if" ---
        is_else_if = False
        else_kw_pos = -1
        before_if = content[line_start:if_start]
        # Look for "} else" or just "else" before the if keyword
        bi_stripped = before_if.strip()
        if bi_stripped.endswith('else'):
            is_else_if = True
            # Find the position of "else" keyword before if_start
            idx = before_if.rfind('else')
            else_kw_pos = line_start + idx

        if is_else_if:
            # --- else if (true/false) { ... } [else ...] ---
            # Get the indent of the line (whitespace only, before the "}")
            line_indent = ''
            for c in content[line_start:]:
                if c in ' \t': line_indent += c
                else: break

            if value == 'true':
                # else if (true) { A } [else { B }] → else { A }
                replacement = 'else {\n'
                if body.strip():
                    replacement += body + '\n'
                replacement += line_indent + '}'
                content = content[:else_kw_pos] + replacement + '\n' + content[construct_end:]
                changes += 1; search_from = 0
            else:
                # else if (false) { A } [else ...] → keep else chain or remove
                if has_else:
                    remaining = content[close_brace+1:else_end+1].strip()
                    content = content[:else_kw_pos] + remaining + '\n' + content[construct_end:]
                else:
                    # else if (false) { A } → remove entirely
                    before = content[:else_kw_pos].rstrip(' \t')
                    content = before + '\n' + content[construct_end:]
                changes += 1; search_from = 0
            continue

        # --- Standalone if (not preceded by else) ---
        # Detect inline vs line-level: is there other code before `if` on the same line?
        before_if_on_line = content[line_start:if_start].strip()
        is_inline = len(before_if_on_line) > 0

        if is_inline:
            # --- INLINE if block: replace only the if construct, not the whole line ---
            if has_else:
                replace_end = else_end + 1
            else:
                replace_end = close_brace + 1

            if value == 'false':
                if has_else:
                    else_content = content[close_brace+1:else_end+1].strip()
                    else_content = re.sub(r'^else\s*', '', else_content, count=1)
                    if else_content.startswith('if'):
                        content = content[:if_start] + else_content + content[replace_end:]
                    elif else_content.startswith('{'):
                        inner_close = find_matching_brace_str(else_content, 0)
                        if inner_close != -1:
                            inner_body = get_body_content(else_content, 0, inner_close).strip()
                            content = content[:if_start] + inner_body + content[replace_end:]
                        else:
                            content = content[:if_start] + else_content + content[replace_end:]
                    else:
                        content = content[:if_start] + else_content + content[replace_end:]
                else:
                    content = content[:if_start] + content[replace_end:]
            elif value == 'true':
                body_text = body.strip()
                if has_else:
                    content = content[:if_start] + body_text + content[replace_end:]
                else:
                    content = content[:if_start] + body_text + content[replace_end:]
            # Collapse double spaces at the join point
            pos = if_start
            while pos > 0 and pos < len(content) and content[pos-1] == ' ' and content[pos] == ' ':
                content = content[:pos] + content[pos+1:]
            changes += 1; search_from = 0
            continue

        # --- LINE-LEVEL if block: if is the main statement on this line ---
        if_indent = content[line_start:if_start]

        if value == 'false':
            if has_else:
                else_content = content[close_brace+1:else_end+1].strip()
                else_content = re.sub(r'^else\s*', '', else_content, count=1)
                if else_content.startswith('if'):
                    content = content[:line_start] + if_indent + else_content + '\n' + content[construct_end:]
                else:
                    if else_content.startswith('{'):
                        inner_close = find_matching_brace_str(else_content, 0)
                        if inner_close != -1:
                            inner_body = get_body_content(else_content, 0, inner_close)
                            reindented = reindent_body(inner_body, if_indent)
                            is_kt = filepath.endswith('.kt')
                            if _VAR_DECL_RE.search(inner_body) and not is_kt:
                                content = content[:line_start] + if_indent + '{\n' + reindented + '\n' + if_indent + '}\n' + content[construct_end:]
                            else:
                                content = content[:line_start] + reindented + '\n' + content[construct_end:]
                        else:
                            content = content[:line_start] + content[construct_end:]
                    else:
                        content = content[:line_start] + if_indent + else_content + '\n' + content[construct_end:]
            else:
                content = content[:line_start] + content[construct_end:]
            changes += 1; search_from = 0

        elif value == 'true':
            reindented = reindent_body(body, if_indent)
            is_kt = filepath.endswith('.kt')
            keep_braces = bool(_VAR_DECL_RE.search(body)) and not is_kt
            if keep_braces:
                replacement = if_indent + '{\n' + reindented + '\n' + if_indent + '}'
            else:
                replacement = reindented
            if has_else:
                has_exit = body_has_unconditional_exit(body)
                if has_exit:
                    dead_end = find_dead_code_end(content, construct_end)
                    if dead_end != -1:
                        between = content[construct_end:dead_end].strip()
                        if between:
                            scope_line_start = get_line_start(content, dead_end)
                            content = content[:line_start] + replacement + '\n' + content[scope_line_start:]
                        else:
                            content = content[:line_start] + replacement + '\n' + content[construct_end:]
                    else:
                        content = content[:line_start] + replacement + '\n' + content[construct_end:]
                else:
                    content = content[:line_start] + replacement + '\n' + content[construct_end:]
                changes += 1; search_from = 0
            else:
                has_exit = body_has_unconditional_exit(body)
                if has_exit:
                    dead_end = find_dead_code_end(content, construct_end)
                    if dead_end != -1:
                        between = content[construct_end:dead_end].strip()
                        if between:
                            scope_line_start = get_line_start(content, dead_end)
                            content = content[:line_start] + replacement + '\n' + content[scope_line_start:]
                        else:
                            content = content[:line_start] + replacement + '\n' + content[construct_end:]
                    else:
                        content = content[:line_start] + replacement + '\n' + content[construct_end:]
                else:
                    content = content[:line_start] + replacement + '\n' + content[construct_end:]
                changes += 1; search_from = 0

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return changes


def find_matching_brace_str(s, start):
    depth = 0
    for i in range(start, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0: return i
    return -1


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    total = 0
    files = 0
    if os.path.isfile(root):
        c = process_file(root)
        if c: total += c; files += 1
    else:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in ['.git','build','.gradle','.idea','docs']]
            for f in fns:
                if f.endswith(('.java','.kt')):
                    try:
                        c = process_file(os.path.join(dp, f))
                        if c: total += c; files += 1
                    except Exception as e:
                        print(f'  ERROR: {os.path.join(dp,f)}: {e}', file=sys.stderr)
    print(f'step4: {total} simplifications in {files} files')
    return total


if __name__ == '__main__':
    main()
