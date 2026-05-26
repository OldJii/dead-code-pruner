#!/usr/bin/env python3
"""
Step 3: Compound boolean simplification (with operator precedence awareness)
- false && EXPR → false
- EXPR && false → false
- true && EXPR → EXPR
- EXPR && true → EXPR
- true || EXPR → true
- EXPR || true → true
- false || EXPR → EXPR
- EXPR || false → EXPR (remove || false)
- false ? X : Y → Y
- true ? X : Y → X
"""
import os, re, sys


def _build_code_mask(text):
    """Pre-compute a boolean mask: True at positions that are in code (not comment/string)."""
    n = len(text)
    mask = [True] * n
    in_str = False
    in_block = False
    i = 0
    while i < n:
        if in_block:
            mask[i] = False
            if text[i] == '*' and i + 1 < n and text[i+1] == '/':
                mask[i+1] = False
                in_block = False
                i += 2; continue
            i += 1; continue
        if in_str:
            mask[i] = False
            if text[i] == '\\':
                if i + 1 < n: mask[i+1] = False
                i += 2; continue
            if text[i] == '"':
                in_str = False
            i += 1; continue
        if text[i] == '"':
            mask[i] = False
            in_str = True
            i += 1; continue
        if text[i] == "'":
            mask[i] = False
            i += 1
            while i < n and text[i] != "'":
                mask[i] = False
                if text[i] == '\\':
                    i += 1
                    if i < n: mask[i] = False
                i += 1
            if i < n: mask[i] = False
            i += 1; continue
        if text[i] == '/' and i + 1 < n:
            if text[i+1] == '*':
                mask[i] = False; mask[i+1] = False
                in_block = True
                i += 2; continue
            if text[i+1] == '/':
                eol = text.find('\n', i)
                if eol == -1: eol = n
                for j in range(i, eol):
                    mask[j] = False
                i = eol; continue
        i += 1
    return mask


_cached_mask = {}

def find_non_comment_match(pattern, text, start=0):
    text_id = id(text)
    if text_id not in _cached_mask or _cached_mask[text_id][0] is not text:
        _cached_mask.clear()
        _cached_mask[text_id] = (text, _build_code_mask(text))
    mask = _cached_mask[text_id][1]

    pos = start
    while pos < len(text):
        m = pattern.search(text, pos)
        if not m:
            return None
        if mask[m.start()]:
            return m
        pos = m.end()
    return None


def find_expr_end_forward(text, start, stop_at_and=True):
    """Find end of expression after an operator. Handles parens, brackets, braces, method calls.
    stop_at_and=False: used after || operators, since && has higher precedence and should not split the operand."""
    depth_paren = 0
    depth_brace = 0
    depth_bracket = 0
    i = start
    n = len(text)
    while i < n and text[i] in ' \t\n\r':
        i += 1
    while i < n:
        c = text[i]
        if c == '(' : depth_paren += 1
        elif c == ')':
            if depth_paren == 0: return i
            depth_paren -= 1
        elif c == '[': depth_bracket += 1
        elif c == ']':
            if depth_bracket == 0: return i
            depth_bracket -= 1
        elif c == '{': depth_brace += 1
        elif c == '}':
            if depth_brace == 0: return i
            depth_brace -= 1
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\': i += 1
                i += 1
        elif depth_paren == 0 and depth_brace == 0 and depth_bracket == 0:
            if c in ';': return i
            if c == '&' and i+1 < n and text[i+1] == '&':
                if stop_at_and:
                    return i
            elif c == '|' and i+1 < n and text[i+1] == '|': return i
            if c == '?' and not (i+1 < n and text[i+1] == '.'): return i
            if c == ':' and i > 0 and text[i-1] != ':' and (i+1 >= n or text[i+1] != ':'): return i
            if c == ',': return i
        i += 1
    return n


def find_expr_start_backward(text, end, stop_at_and=True):
    """Find start of expression before an operator. Handles parens, brackets.
    stop_at_and=False: used before || operators, since && has higher precedence and should not split the operand."""
    depth_paren = 0
    depth_bracket = 0
    n = len(text)
    i = end - 1
    while i >= 0 and text[i] in ' \t\n\r':
        i -= 1
    while i >= 0:
        c = text[i]
        if c == ')': depth_paren += 1
        elif c == '(':
            if depth_paren == 0: return i + 1
            depth_paren -= 1
        elif c == ']': depth_bracket += 1
        elif c == '[':
            if depth_bracket == 0: return i + 1
            depth_bracket -= 1
        elif c == '"':
            i -= 1
            while i >= 0 and text[i] != '"':
                i -= 1
        elif depth_paren == 0 and depth_bracket == 0:
            if c == '}': return i + 1
            if c == ';': return i + 1
            if c == '=':
                prev = text[i-1] if i > 0 else ''
                nxt = text[i+1] if i + 1 < n else ''
                if prev not in '=!<>' and nxt != '=':
                    return i + 1
            if c == '&' and i > 0 and text[i-1] == '&':
                if stop_at_and:
                    return i + 1
            elif c == '|' and i > 0 and text[i-1] == '|': return i + 1
            if c == '?': return i + 1
            if c == ':' and (i == 0 or text[i-1] != ':') and (i + 1 >= n or text[i+1] != ':'):
                return i + 1
            if c == ',': return i + 1
            if c == '{': return i + 1
        i -= 1
    return 0


def find_ternary_parts(text, q_pos):
    """Given '?' position, find X and Y in '? X : Y'. Returns (x_start, x_end, colon, y_start, y_end)."""
    x_start = q_pos + 1
    while x_start < len(text) and text[x_start] in ' \t\n\r':
        x_start += 1
    depth = 0
    ternary_depth = 0
    i = x_start
    n = len(text)
    colon_pos = -1
    while i < n:
        c = text[i]
        if c == '(': depth += 1
        elif c == ')':
            if depth == 0: break
            depth -= 1
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\': i += 1
                i += 1
        elif depth == 0:
            if c == '?' and not (i+1 < n and text[i+1] == '.'):
                ternary_depth += 1
            elif c == ':' and (i == 0 or text[i-1] != ':') and (i+1 >= n or text[i+1] != ':'):
                if ternary_depth > 0:
                    ternary_depth -= 1
                else:
                    colon_pos = i
                    break
            elif c in ';,{}':
                break
        i += 1

    if colon_pos == -1:
        return None

    x_end = colon_pos
    while x_end > x_start and text[x_end-1] in ' \t\n\r':
        x_end -= 1

    y_start = colon_pos + 1
    while y_start < n and text[y_start] in ' \t\n\r':
        y_start += 1

    y_end = find_expr_end_forward(text, y_start)
    return (x_start, x_end, colon_pos, y_start, y_end)


_EXPR_PREFIX_KW = ('return', 'throw')


def _skip_expr_prefix(content, start, limit):
    """Skip whitespace, comment lines, and expression-prefix keywords (return, throw)."""
    while start < limit:
        while start < limit and content[start] in ' \t\n\r':
            start += 1
        if start + 1 < limit and content[start:start+2] == '//':
            eol = content.find('\n', start)
            if eol == -1 or eol >= limit:
                break
            start = eol + 1
            continue
        if start + 1 < limit and content[start:start+2] == '/*':
            end_bc = content.find('*/', start)
            if end_bc == -1 or end_bc + 2 > limit:
                break
            start = end_bc + 2
            continue
        break
    n = len(content)
    for kw in _EXPR_PREFIX_KW:
        kend = start + len(kw)
        if (kend <= n and content[start:kend] == kw
                and (kend >= n or (not content[kend].isalnum() and content[kend] != '_'))):
            start = kend
            while start < limit and content[start] in ' \t\n\r':
                start += 1
            break
    return start


def _preceded_by_cmp(content, pos):
    """Check if pos is preceded (ignoring whitespace) by == or !=."""
    i = pos - 1
    while i >= 0 and content[i] in ' \t\n\r':
        i -= 1
    if i >= 1 and content[i] == '=' and content[i-1] in '=!':
        return True
    return False


def _followed_by_cmp(content, pos):
    """Check if pos is followed (ignoring whitespace) by == or !=."""
    i = pos
    while i < len(content) and content[i] in ' \t\n\r':
        i += 1
    if i + 1 < len(content) and content[i:i+2] in ('==', '!='):
        return True
    return False


def _find_safe_match(pattern, content, check_pre=False, check_post=False, start_pos=0):
    """Find first match not in a comparison context (== or !=)."""
    pos = start_pos
    while True:
        m = find_non_comment_match(pattern, content, pos)
        if not m:
            return None
        if check_pre and _preceded_by_cmp(content, m.start()):
            pos = m.end(); continue
        if check_post and _followed_by_cmp(content, m.end()):
            pos = m.end(); continue
        return m


def _extend_removal_past_preceding_comments(content, pos):
    """When removing '&& true' or '|| false', also remove preceding comment-only lines
    that belong to the removed operand."""
    result = pos
    while True:
        line_start = content.rfind('\n', 0, result)
        if line_start == -1:
            break
        line_text = content[line_start + 1:result].strip()
        if line_text == '' or line_text.startswith('//') or line_text.startswith('/*') or line_text.startswith('*'):
            result = line_start
        else:
            break
    return result


QUICK_KEYWORDS = ['false &&', '&& false', 'true &&', '&& true',
                  'true ||', '|| true', 'false ||', '|| false',
                  'false ?', 'true ?',
                  'false + ""', 'true + ""']

_MULTILINE_QUICK = re.compile(
    r'\b(true|false)\s*\n\s*(&&|\|\||\?)'
    r'|(&&|\|\|)\s*\n\s*(true|false)\b')

_PAT_FALSE_AND = re.compile(r'\bfalse\s*&&\s*')
_PAT_AND_FALSE = re.compile(r'&&\s*false\b')
_PAT_TRUE_AND  = re.compile(r'\btrue\s*&&\s*')
_PAT_AND_TRUE  = re.compile(r'\s*&&\s*true\b')
_PAT_TRUE_OR   = re.compile(r'\btrue\s*\|\|\s*')
_PAT_OR_TRUE   = re.compile(r'\|\|\s*true\b')
_PAT_FALSE_OR  = re.compile(r'\bfalse\s*\|\|\s*')
_PAT_OR_FALSE  = re.compile(r'\s*\|\|\s*false\b')
_PAT_FALSE_Q   = re.compile(r'\bfalse\s*\?\s*')
_PAT_TRUE_Q    = re.compile(r'\btrue\s*\?\s*')
_PAT_FALSE_STR = re.compile(r'\bfalse\s*\+\s*""')
_PAT_TRUE_STR  = re.compile(r'\btrue\s*\+\s*""')

def process_content(content):
    if not any(kw in content for kw in QUICK_KEYWORDS):
        if not _MULTILINE_QUICK.search(content):
            return content, 0
    changes = 0
    max_iter = 500
    iteration = 0
    _cached_mask.clear()

    while iteration < max_iter:
        iteration += 1
        modified = False

        # false && EXPR → false
        m = _find_safe_match(_PAT_FALSE_AND, content, check_pre=True)
        if m:
            end = find_expr_end_forward(content, m.end())
            content = content[:m.start()] + 'false' + content[end:]
            changes += 1; modified = True; continue

        # EXPR && false → false
        m = _find_safe_match(_PAT_AND_FALSE, content, check_post=True)
        if m:
            start = find_expr_start_backward(content, m.start())
            start = _skip_expr_prefix(content, start, m.start())
            content = content[:start] + 'false' + content[m.end():]
            changes += 1; modified = True; continue

        # true && EXPR → EXPR
        m = _find_safe_match(_PAT_TRUE_AND, content, check_pre=True)
        if m:
            content = content[:m.start()] + content[m.end():]
            changes += 1; modified = True; continue

        # EXPR && true → EXPR (remove && true, including preceding comment-only lines)
        m = _find_safe_match(_PAT_AND_TRUE, content, check_post=True)
        if m:
            remove_start = _extend_removal_past_preceding_comments(content, m.start())
            content = content[:remove_start] + content[m.end():]
            changes += 1; modified = True; continue

        # true || EXPR → true (stop_at_and=False: && has higher precedence, A && B is one operand of ||)
        m = _find_safe_match(_PAT_TRUE_OR, content, check_pre=True)
        if m:
            end = find_expr_end_forward(content, m.end(), stop_at_and=False)
            content = content[:m.start()] + 'true' + content[end:]
            changes += 1; modified = True; continue

        # EXPR || true → true (stop_at_and=False: same reason)
        m = _find_safe_match(_PAT_OR_TRUE, content, check_post=True)
        if m:
            start = find_expr_start_backward(content, m.start(), stop_at_and=False)
            start = _skip_expr_prefix(content, start, m.start())
            content = content[:start] + 'true' + content[m.end():]
            changes += 1; modified = True; continue

        # false || EXPR → EXPR
        m = _find_safe_match(_PAT_FALSE_OR, content, check_pre=True)
        if m:
            content = content[:m.start()] + content[m.end():]
            changes += 1; modified = True; continue

        # EXPR || false → EXPR (remove || false, including preceding comment-only lines)
        m = _find_safe_match(_PAT_OR_FALSE, content, check_post=True)
        if m:
            remove_start = _extend_removal_past_preceding_comments(content, m.start())
            content = content[:remove_start] + content[m.end():]
            changes += 1; modified = True; continue

        # false ? X : Y → Y
        m = _find_safe_match(_PAT_FALSE_Q, content, check_pre=True)
        if m:
            parts = find_ternary_parts(content, m.end() - 1)
            if parts:
                x_start, x_end, colon, y_start, y_end = parts
                y_text = content[y_start:y_end]
                content = content[:m.start()] + y_text + content[y_end:]
                changes += 1; modified = True; continue

        # true ? X : Y → X
        m = _find_safe_match(_PAT_TRUE_Q, content, check_pre=True)
        if m:
            parts = find_ternary_parts(content, m.end() - 1)
            if parts:
                x_start, x_end, colon, y_start, y_end = parts
                x_text = content[x_start:x_end]
                content = content[:m.start()] + x_text + content[y_end:]
                changes += 1; modified = True; continue

        # false + "" → "false"
        m = find_non_comment_match(_PAT_FALSE_STR, content)
        if m:
            content = content[:m.start()] + '"false"' + content[m.end():]
            changes += 1; modified = True; continue

        # true + "" → "true"
        m = find_non_comment_match(_PAT_TRUE_STR, content)
        if m:
            content = content[:m.start()] + '"true"' + content[m.end():]
            changes += 1; modified = True; continue

        break

    return content, changes


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content, changes = process_content(content)
    if changes:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
    return changes


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
    print(f'step3: {total} simplifications in {files} files')
    return total


if __name__ == '__main__':
    main()
