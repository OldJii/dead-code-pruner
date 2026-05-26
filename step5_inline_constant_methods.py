#!/usr/bin/env python3
"""
Step 5: Inline constant-returning private/static methods
Safe scope: private methods (calls only in same file), static methods (calls via ClassName.method())
"""
import os, re, sys

SKIP_DIRS = {'.git', 'build', '.gradle', '.idea', 'node_modules',
             '.cursor', '__pycache__', 'generated'}

_TYPE_KEYWORDS = {'boolean', 'Boolean', 'int', 'long', 'float', 'double', 'char',
                  'byte', 'short', 'void', 'String', 'fun'}

_SKIP_ANNOTATIONS = {'@Inject', '@InjecterModule', '@Route', '@Provides',
                     '@Bean', '@Component', '@Service'}


def is_in_comment_or_string(content, pos):
    i = 0
    in_lc = False; in_bc = False; in_str = False; sc = None
    while i < pos:
        c = content[i]
        if in_lc:
            if c == '\n': in_lc = False
        elif in_bc:
            if c == '*' and i+1 < len(content) and content[i+1] == '/':
                in_bc = False; i += 1
        elif in_str:
            if c == '\\': i += 1
            elif c == sc: in_str = False
        elif c == '/' and i+1 < len(content):
            if content[i+1] == '/': in_lc = True
            elif content[i+1] == '*': in_bc = True; i += 1
        elif c in ('"', "'"):
            in_str = True; sc = c
        i += 1
    return in_lc or in_bc or in_str


def _is_method_definition(content, match_start):
    """Check if the match is in a method definition (preceded by a type keyword)"""
    line_start = content.rfind('\n', 0, match_start) + 1
    before = content[line_start:match_start].strip()
    tokens = before.split()
    if not tokens:
        return False
    last_token = tokens[-1]
    if last_token in _TYPE_KEYWORDS:
        return True
    if last_token.endswith('>') or re.match(r'^[A-Z]\w*$', last_token):
        modifiers_before = ' '.join(tokens[:-1])
        if any(kw in modifiers_before for kw in ('public', 'private', 'protected', 'static', 'final', 'abstract')):
            return True
    return False


def collect_java_kt_files(root):
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if fn.endswith(('.java', '.kt')):
                files.append(os.path.join(dp, fn))
    return files


def find_class_name_for_line(lines, line_idx):
    for i in range(line_idx, -1, -1):
        m = re.search(r'\b(?:class|interface|enum|object)\s+(\w+)', lines[i])
        if m:
            return m.group(1)
    return None


def _has_skip_annotation(lines, method_line):
    """Check if method has an annotation that means it should be skipped"""
    for k in range(max(0, method_line - 4), method_line):
        stripped = lines[k].strip()
        for anno in _SKIP_ANNOTATIONS:
            if stripped.startswith(anno):
                return True
    return False


def find_constant_methods_in_file(filepath, content):
    """Return list of (name, value, is_static, is_private, class_name, start_line, end_line)"""
    lines = content.split('\n')
    results = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if '{' not in line:
            i += 1; continue
        has_bool = ('boolean ' in line or 'Boolean ' in line or 'fun ' in line)
        if not has_bool:
            i += 1; continue

        is_static = 'static ' in line
        is_private = 'private ' in line
        if not is_static and not is_private:
            i += 1; continue

        has_override = False
        for k in range(max(0, i-3), i):
            if '@Override' in lines[k] or 'override ' in lines[k].strip():
                has_override = True
        if has_override:
            i += 1; continue

        if _has_skip_annotation(lines, i):
            i += 1; continue

        name_match = re.search(r'\b(\w+)\s*\([^)]*\)\s*[\{:]', line)
        if not name_match:
            i += 1; continue
        name = name_match.group(1)
        if name in ('if', 'for', 'while', 'switch', 'catch', 'synchronized'):
            i += 1; continue

        # Only handle zero-arg methods
        paren_content = line[name_match.start(1):name_match.end()].split('(')[1].split(')')[0].strip()
        if paren_content:
            i += 1; continue

        brace_count = line.count('{') - line.count('}')
        if brace_count != 1:
            i += 1; continue

        j = i + 1
        body_lines = []
        while j < len(lines):
            bl = lines[j].strip()
            brace_count += bl.count('{') - bl.count('}')
            if brace_count <= 0:
                break
            if bl and not bl.startswith('//') and not bl.startswith('/*') and not bl.startswith('*'):
                body_lines.append(bl)
            j += 1

        if len(body_lines) == 1 and body_lines[0] in ('return true;', 'return false;', 'return true', 'return false'):
            val = 'true' if 'true' in body_lines[0] else 'false'
            cls = find_class_name_for_line(lines, i)
            if cls:
                anno_start = i
                while anno_start > 0 and lines[anno_start-1].strip().startswith('@'):
                    anno_start -= 1
                results.append((name, val, is_static, is_private, cls, anno_start, j))
        i += 1
    return results


def _clean_standalone_boolean_statements(content):
    """Remove standalone `true;` / `false;` statements produced by inlining void-context calls."""
    lines = content.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped in ('true;', 'false;'):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def replace_calls(content, method_name, value, class_name=None, same_file=True):
    """Replace method() or ClassName.method() with value, skipping definitions. Returns (content, count)"""
    count = 0

    if class_name:
        pat_qualified = re.compile(
            r'(?:(?:\w+\.)+)?' + re.escape(class_name) + r'\s*\.\s*' + re.escape(method_name) + r'\s*\(\s*\)')
        new_content = ''
        last_end = 0
        for m in pat_qualified.finditer(content):
            if is_in_comment_or_string(content, m.start()):
                continue
            new_content += content[last_end:m.start()] + value
            last_end = m.end()
            count += 1
        new_content += content[last_end:]
        content = new_content

    if same_file:
        pat_unqualified = re.compile(r'(?<!\w)' + re.escape(method_name) + r'\s*\(\s*\)')
        new_content = ''
        last_end = 0
        for m in pat_unqualified.finditer(content):
            if is_in_comment_or_string(content, m.start()):
                continue
            if _is_method_definition(content, m.start()):
                continue
            before_char = content[m.start()-1:m.start()] if m.start() > 0 else ''
            if before_char == '.':
                continue
            new_content += content[last_end:m.start()] + value
            last_end = m.end()
            count += 1
        new_content += content[last_end:]
        content = new_content

    content = _clean_standalone_boolean_statements(content)

    return content, count


def process_project(root):
    files = collect_java_kt_files(root)

    all_methods = {}
    static_methods = []

    for fp in files:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue
        if 'return true' not in content and 'return false' not in content:
            continue
        methods = find_constant_methods_in_file(fp, content)
        if methods:
            all_methods[fp] = (content, methods)
            for m in methods:
                if m[2] and not m[3]:
                    static_methods.append((fp, m))

    total_inlined = 0
    total_removed = 0
    files_changed = set()

    for fp, (content, methods) in all_methods.items():
        changed = False
        for name, val, is_static, is_private, cls, start, end in methods:
            if is_private:
                new_content, cnt = replace_calls(content, name, val, cls, same_file=True)
                if cnt > 0:
                    content = new_content
                    total_inlined += cnt
                    changed = True
            elif is_static:
                new_content, cnt = replace_calls(content, name, val, cls, same_file=True)
                if cnt > 0:
                    content = new_content
                    total_inlined += cnt
                    changed = True

        if changed:
            lines = content.split('\n')
            for name, val, is_static, is_private, cls, start, end in reversed(methods):
                if is_private:
                    if 0 <= start and end < len(lines):
                        del lines[start:end+1]
                        if start < len(lines) and start > 0 and lines[start-1].strip() == '' and lines[start].strip() == '':
                            del lines[start]
                        total_removed += 1
            content = '\n'.join(lines)
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(content)
            files_changed.add(fp)
            all_methods[fp] = (content, methods)

    cross_file_count = 0
    for target_fp in files:
        try:
            with open(target_fp, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        changed = False
        for src_fp, (name, val, is_static, is_private, cls, start, end) in static_methods:
            quick = cls + '.' + name
            if quick not in content:
                continue
            pat = re.compile(r'(?:(?:\w+\.)+)?' + re.escape(cls) + r'\s*\.\s*' + re.escape(name) + r'\s*\(\s*\)')
            new_content = ''
            last_end_pos = 0
            for m in pat.finditer(content):
                if is_in_comment_or_string(content, m.start()):
                    continue
                new_content += content[last_end_pos:m.start()] + val
                last_end_pos = m.end()
                cross_file_count += 1
                changed = True
            new_content += content[last_end_pos:]
            content = new_content

        if changed:
            with open(target_fp, 'w', encoding='utf-8') as f:
                f.write(content)
            files_changed.add(target_fp)

    total_inlined += cross_file_count

    print(f"  Constant methods found: private={sum(1 for fp,(c,ms) in all_methods.items() for m in ms if m[3])}, "
          f"static={len(static_methods)}")
    print(f"  Call sites inlined: {total_inlined} (same-file: {total_inlined - cross_file_count}, cross-file: {cross_file_count})")
    print(f"  Private methods deleted: {total_removed}")
    print(f"  Files modified: {len(files_changed)}")
    return total_inlined


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    process_project(root)
