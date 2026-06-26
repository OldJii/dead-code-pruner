"""Code-editing helpers for method inlining and deletion.

Provides regex-based call-site replacement, void-call removal, standalone
boolean cleanup, line-range deletion, and cross-file reference detection.
"""

import os
import re
from .ref_index import is_in_comment_or_string


def replace_calls_in_content(content: str, method_name: str, value: str,
                             class_name: str | None = None,
                             same_file: bool = True) -> tuple[str, int]:
    """Replace ``method()`` / ``Class.method()`` with *value*. Returns ``(new_content, count)``."""
    count = 0
    if class_name:
        pat = re.compile(
            r'(?:(?:\w+\.)+)?' + re.escape(class_name) + r'\s*\.\s*'
            + re.escape(method_name) + r'\s*\(\s*\)')
        new_content = ''
        last = 0
        for m in pat.finditer(content):
            if is_in_comment_or_string(content, m.start()):
                continue
            new_content += content[last:m.start()] + value
            last = m.end()
            count += 1
        new_content += content[last:]
        content = new_content

    if same_file:
        pat = re.compile(r'(?<!\w)' + re.escape(method_name) + r'\s*\(\s*\)')
        new_content = ''
        last = 0
        type_kws = {'boolean', 'Boolean', 'void', 'int', 'long', 'float', 'double',
                     'char', 'byte', 'short', 'String', 'fun', 'def', 'func', 'Bool'}
        for m in pat.finditer(content):
            if is_in_comment_or_string(content, m.start()):
                continue
            if m.start() > 0 and content[m.start() - 1] == '.':
                continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            before = content[line_start:m.start()].strip().split()
            if before and before[-1] in type_kws:
                continue
            new_content += content[last:m.start()] + value
            last = m.end()
            count += 1
        new_content += content[last:]
        content = new_content

    return content, count


def remove_void_calls_in_content(content: str, method_name: str,
                                 class_name: str | None = None,
                                 same_file: bool = True) -> tuple[str, int]:
    """Remove standalone void method calls. Returns ``(new_content, count)``."""
    lines = content.split('\n')
    new_lines = []
    count = 0
    if same_file:
        qualifiers = [r'', r'this\s*\.\s*']
        if class_name:
            qualifiers.append(re.escape(class_name) + r'\s*\.\s*')
    else:
        qualifiers = [re.escape(class_name) + r'\s*\.\s*'] if class_name else [r'']
    qual_pat = '|'.join(f'(?:{q})' for q in qualifiers)
    pat = re.compile(
        r'^\s*(?:' + qual_pat + r')' + re.escape(method_name) + r'\s*\(\s*\)\s*;?\s*$')
    for line in lines:
        if pat.match(line.rstrip()):
            count += 1
            continue
        new_lines.append(line)
    return '\n'.join(new_lines), count


def clean_standalone_booleans(content: str) -> str:
    """Remove standalone ``true;`` / ``false;`` statements."""
    lines = content.split('\n')
    return '\n'.join(l for l in lines if l.strip() not in ('true;', 'false;'))


def delete_line_ranges(content: str, ranges: list[tuple[int, int]]) -> tuple[str, int]:
    """Delete *ranges* ``[(start_line, end_line), …]`` from *content*.

    Returns ``(new_content, deleted_count)``.
    """
    if not ranges:
        return content, 0
    lines = content.split('\n')
    deleted = 0
    for start, end in sorted(ranges, reverse=True):
        if 0 <= start <= end < len(lines):
            del lines[start:end + 1]
            deleted += 1
    final = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ''
        if is_blank and prev_blank:
            continue
        final.append(line)
        prev_blank = is_blank
    return '\n'.join(final), deleted


_TYPE_KEYWORDS = frozenset({
    'void', 'boolean', 'Boolean', 'int', 'long', 'float', 'double', 'char',
    'byte', 'short', 'String', 'Bool', 'fun', 'func', 'def', 'override',
    'public', 'private', 'protected', 'static', 'final', 'abstract',
    'open', 'internal',
})


def _has_call_site(content: str, method_name: str) -> bool:
    """Return ``True`` if *content* contains a **call** to *method_name*
    that is NOT an invocation of a locally defined same-name method.

    Strategy: first check if the file defines its own ``method_name`` — if
    so, any bare ``method()`` calls are assumed to target the local
    definition (no type analysis available).  Only ``qualifier.method()``
    patterns (dot-prefixed) would indicate an external reference, which
    are already covered by the qualified/contextual strategies.
    """
    needle = method_name + '('
    if needle not in content:
        return False

    has_local_def = False
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('/*'):
            continue
        idx = stripped.find(needle)
        if idx == -1:
            continue
        before = stripped[:idx].split()
        if before and before[-1] in _TYPE_KEYWORDS:
            has_local_def = True
            break

    start = 0
    while True:
        idx = content.find(needle, start)
        if idx == -1:
            return False
        if is_in_comment_or_string(content, idx):
            start = idx + 1
            continue
        line_start = content.rfind('\n', 0, idx) + 1
        before = content[line_start:idx].strip().split()
        if before and before[-1] in _TYPE_KEYWORDS:
            start = idx + 1
            continue
        if has_local_def:
            # Bare call with local definition → likely self-reference; skip.
            # But `something.method(` with a dot prefix is an external call.
            if idx > 0 and content[idx - 1] == '.':
                return True
            start = idx + 1
            continue
        return True


def has_cross_file_refs(dm: dict, ref_index: dict, src_abs: str) -> bool:
    """Return ``True`` if method *dm* has cross-file references.

    Detection strategies (applied in order):
      1. Qualified:  ``ClassName.methodName`` in the file.
      2. Contextual: both ``ClassName`` and ``methodName(`` in the file.
      3. Instance:   bare ``methodName(`` **call** for non-private, non-static
         methods.  Instance methods can be called via any variable reference
         (e.g. ``obj.field.method()``), so the class name may never appear
         in the calling file.  Definitions in other files are excluded.
    """
    name = dm['name']
    cls  = dm.get('class_name', '')
    is_private = dm.get('is_private', False)
    is_static  = dm.get('is_static', False)
    is_instance = not is_private and not is_static

    for rf in ref_index.get(name, set()):
        if os.path.abspath(rf) == src_abs:
            continue
        try:
            with open(rf, 'r', encoding='utf-8', errors='ignore') as fh:
                rc = fh.read()
        except Exception:
            continue
        qualified = cls + '.' + name if cls else ''
        if qualified and qualified in rc:
            return True
        if cls and cls in rc and name + '(' in rc:
            return True
        if is_instance and _has_call_site(rc, name):
            return True
    return False
