#!/usr/bin/env python3
"""
Step 2: Simple boolean simplification (skips comments and strings)
!true→false, !false→true, true==true→true, etc.
"""
import os, re, sys

PATTERNS = [
    (r'!\s*true\b', 'false'),
    (r'!\s*false\b', 'true'),
    (r'\btrue\s*==\s*true\b', 'true'),
    (r'\bfalse\s*==\s*false\b', 'true'),
    (r'\btrue\s*!=\s*false\b', 'true'),
    (r'\bfalse\s*!=\s*true\b', 'true'),
    (r'\btrue\s*==\s*false\b', 'false'),
    (r'\bfalse\s*==\s*true\b', 'false'),
    (r'\btrue\s*!=\s*true\b', 'false'),
    (r'\bfalse\s*!=\s*false\b', 'false'),
]

PAREN_BOOL = re.compile(r'\(\s*(true|false)\s*\)')

_PAREN_REQUIRED_KW = {'if', 'while', 'for', 'switch', 'catch', 'synchronized'}
_PAREN_OPTIONAL_KW = {'return', 'throw', 'assert', 'yield'}

def _is_safe_paren_strip(content, paren_pos):
    """Check if (true)/(false) at paren_pos can safely have parens stripped.
    NOT safe after if/while/for (syntax requires parens) or identifiers (function call).
    Safe after return/throw, operators, or at start of expression."""
    i = paren_pos - 1
    while i >= 0 and content[i] in ' \t\n\r':
        i -= 1
    if i < 0:
        return True
    c = content[i]
    if not (c.isalnum() or c == '_'):
        return True
    end = i + 1
    while i >= 0 and (content[i].isalnum() or content[i] == '_'):
        i -= 1
    word = content[i+1:end]
    if word in _PAREN_REQUIRED_KW:
        return False
    if word in _PAREN_OPTIONAL_KW:
        return True
    return False


def _tokenize_and_replace(content, pattern, replacement):
    tokens = []
    i = 0
    n = len(content)
    code_start = 0
    while i < n:
        if content[i] == '/' and i+1 < n and content[i+1] == '*':
            if i > code_start: tokens.append(('code', content[code_start:i]))
            end = content.find('*/', i+2)
            if end == -1: end = n - 2
            tokens.append(('skip', content[i:end+2]))
            i = end + 2; code_start = i; continue
        if content[i] == '/' and i+1 < n and content[i+1] == '/':
            if i > code_start: tokens.append(('code', content[code_start:i]))
            end = content.find('\n', i)
            if end == -1: end = n
            tokens.append(('skip', content[i:end]))
            i = end; code_start = i; continue
        if content[i] == '"':
            if i > code_start: tokens.append(('code', content[code_start:i]))
            j = i + 1
            while j < n:
                if content[j] == '\\': j += 2; continue
                if content[j] == '"': j += 1; break
                j += 1
            tokens.append(('skip', content[i:j]))
            i = j; code_start = i; continue
        if content[i] == "'":
            if i > code_start: tokens.append(('code', content[code_start:i]))
            j = i + 1
            while j < n:
                if content[j] == '\\': j += 2; continue
                if content[j] == "'": j += 1; break
                j += 1
            tokens.append(('skip', content[i:j]))
            i = j; code_start = i; continue
        i += 1
    if code_start < n:
        tokens.append(('code', content[code_start:]))
    result = []
    for kind, text in tokens:
        if kind == 'code':
            text = re.sub(pattern, replacement, text)
        result.append(text)
    return ''.join(result)


QUICK_CHECK = ['!true', '!false', 'true ==', 'false ==', 'true !=', 'false !=',
                '== true', '== false', '!= true', '!= false']

PAREN_STRIP_INDICATORS = ['&& (true)', '&& (false)', '|| (true)', '|| (false)',
                          '&&(true)', '&&(false)', '||(true)', '||(false)',
                          '= (true)', '= (false)', ', (true)', ', (false)',
                          '((true))', '((false))',
                          '(false) &&', '(false) ||', '(true) &&', '(true) ||',
                          '(false)&&', '(false)||', '(true)&&', '(true)||',
                          '(false) ?', '(true) ?']

def _strip_paren_bools_in_code(content):
    """Strip (true) → true and (false) → false only in operator context (safe)."""
    tokens = []
    i = 0
    n = len(content)
    code_start = 0
    while i < n:
        if content[i] == '/' and i+1 < n and content[i+1] == '*':
            if i > code_start: tokens.append(('code', content[code_start:i]))
            end = content.find('*/', i+2)
            if end == -1: end = n - 2
            tokens.append(('skip', content[i:end+2]))
            i = end + 2; code_start = i; continue
        if content[i] == '/' and i+1 < n and content[i+1] == '/':
            if i > code_start: tokens.append(('code', content[code_start:i]))
            end = content.find('\n', i)
            if end == -1: end = n
            tokens.append(('skip', content[i:end]))
            i = end; code_start = i; continue
        if content[i] == '"':
            if i > code_start: tokens.append(('code', content[code_start:i]))
            j = i + 1
            while j < n:
                if content[j] == '\\': j += 2; continue
                if content[j] == '"': j += 1; break
                j += 1
            tokens.append(('skip', content[i:j]))
            i = j; code_start = i; continue
        if content[i] == "'":
            if i > code_start: tokens.append(('code', content[code_start:i]))
            j = i + 1
            while j < n:
                if content[j] == '\\': j += 2; continue
                if content[j] == "'": j += 1; break
                j += 1
            tokens.append(('skip', content[i:j]))
            i = j; code_start = i; continue
        i += 1
    if code_start < n:
        tokens.append(('code', content[code_start:]))

    changed = False
    result = []
    for kind, text in tokens:
        if kind == 'code':
            new_text = PAREN_BOOL.sub(
                lambda m: m.group(1) if _is_safe_paren_strip(text, m.start()) else m.group(0),
                text)
            if new_text != text:
                changed = True
            result.append(new_text)
        else:
            result.append(text)
    return ''.join(result), changed

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    has_patterns = any(kw in content for kw in QUICK_CHECK)
    has_paren_strip = any(kw in content for kw in PAREN_STRIP_INDICATORS)
    if not has_patterns and not has_paren_strip:
        return False
    original = content

    # Safe paren stripping: (true) → true, (false) → false only in operator context
    if has_paren_strip:
        content, _ = _strip_paren_bools_in_code(content)

    for pattern, replacement in PATTERNS:
        content = _tokenize_and_replace(content, pattern, replacement)
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    count = 0
    if os.path.isfile(root):
        if process_file(root): count = 1
    else:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in ['.git','build','.gradle','.idea','docs']]
            for f in fns:
                if f.endswith(('.java','.kt')):
                    try:
                        if process_file(os.path.join(dp, f)): count += 1
                    except: pass
    print(f'step2: {count} files changed')
    return count


if __name__ == '__main__':
    main()
