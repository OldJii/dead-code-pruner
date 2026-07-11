"""Reference index — maps method names to files that contain call sites.

Also provides helper utilities: file collection and comment/string detection.
"""

import os
import re
from collections import defaultdict
from ..lang import _PARSERS, SKIP_DIRS
from .. import ui


REFERENCE_EXTS = frozenset({
    '.storyboard', '.xib', '.plist', '.xml', '.json',
})

_CALL_PAT = re.compile(r'\b(\w+)\s*\(')
_REF_PAT = re.compile(r'::(\w+)\b')
_SWIFT_SELECTOR_PAT = re.compile(
    r'#selector\s*\(\s*(?:getter:\s*|setter:\s*)?(?:(?:\w+)\.)?(\w+)\b')
_IB_SELECTOR_PAT = re.compile(r'\bselector="([A-Za-z_]\w*)')
_DOT_PROPERTY_PAT = re.compile(r'\.([a-z]\w*)\b(?!\s*\()')


def collect_files(root_dir: str, *, include_reference_files: bool = False) -> list[str]:
    """Walk *root_dir* and collect source files, plus semantic reference files when requested."""
    files = []
    supported = frozenset(_PARSERS.keys())
    for dp, dns, fns in os.walk(root_dir):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in supported or (include_reference_files and ext in REFERENCE_EXTS):
                files.append(os.path.join(dp, fn))
    return files


def iter_reference_names(content: str):
    """Yield symbol names that may represent call sites or dynamic references.

    Includes dot-property access patterns (e.g. ``.isEnabled``) to
    capture Kotlin-style property access of Java getters.
    """
    for m in _CALL_PAT.finditer(content):
        yield m.group(1)
    for m in _REF_PAT.finditer(content):
        yield m.group(1)
    for m in _SWIFT_SELECTOR_PAT.finditer(content):
        yield m.group(1)
    for m in _IB_SELECTOR_PAT.finditer(content):
        yield m.group(1)
    for m in _DOT_PROPERTY_PAT.finditer(content):
        yield m.group(1)


def build_ref_index(all_files: list[str], *, quiet: bool = False) -> dict[str, set[str]]:
    """Build a ``{method_name: {filepath, …}}`` reverse index."""
    index: dict[str, set[str]] = defaultdict(set)
    total = len(all_files)
    for idx, fp in enumerate(all_files):
        if not quiet and ((idx + 1) % 1000 == 0 or idx + 1 == total):
            ui.progress(idx + 1, total, "Building ref index", indent=4)
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
        for name in iter_reference_names(content):
            if len(name) > 2:
                index[name].add(fp)
    if not quiet and total > 100:
        ui.progress_done()
    return index


def is_in_comment_or_string(content: str, pos: int) -> bool:
    """Return ``True`` if *pos* falls inside a comment or string literal.

    Handles string interpolation for Kotlin/Dart (``${expr}``) and
    Swift (``\\(expr)``).  Code inside interpolation braces/parens is
    treated as normal code, not as part of the enclosing string.
    """
    i = 0
    in_lc = in_bc = False
    str_stack: list[str] = []
    interp_depth: list[int] = []

    while i < pos:
        c = content[i]

        if in_lc:
            if c == '\n':
                in_lc = False
            i += 1
            continue

        if in_bc:
            if c == '*' and i + 1 < len(content) and content[i + 1] == '/':
                in_bc = False
                i += 2
                continue
            i += 1
            continue

        if interp_depth and interp_depth[-1] > 0:
            if c == '{':
                interp_depth[-1] += 1
            elif c == '}':
                interp_depth[-1] -= 1
                if interp_depth[-1] == 0:
                    interp_depth.pop()
            elif c == '(' and str_stack and str_stack[-1] == 'swift_interp':
                interp_depth[-1] += 1
            elif c == ')' and str_stack and str_stack[-1] == 'swift_interp':
                interp_depth[-1] -= 1
                if interp_depth[-1] == 0:
                    interp_depth.pop()
                    str_stack.pop()
            elif c == '/' and i + 1 < len(content):
                if content[i + 1] == '/':
                    in_lc = True
                    i += 1
                elif content[i + 1] == '*':
                    in_bc = True
                    i += 2
                    continue
            elif c in ('"', "'"):
                str_stack.append(c)
            i += 1
            continue

        if str_stack:
            sc = str_stack[-1]
            if sc == 'swift_interp':
                i += 1
                continue
            if c == '\\':
                if sc == '"' and i + 1 < len(content) and content[i + 1] == '(':
                    str_stack.append('swift_interp')
                    interp_depth.append(1)
                    i += 2
                    continue
                i += 2
                continue
            if c == '$' and sc == '"' and i + 1 < len(content) and content[i + 1] == '{':
                interp_depth.append(1)
                i += 2
                continue
            if c == sc:
                str_stack.pop()
            i += 1
            continue

        if c == '/' and i + 1 < len(content):
            if content[i + 1] == '/':
                in_lc = True
                i += 2
                continue
            if content[i + 1] == '*':
                in_bc = True
                i += 2
                continue

        if c in ('"', "'"):
            str_stack.append(c)

        i += 1

    if in_lc or in_bc:
        return True
    if str_stack and not interp_depth:
        return True
    if interp_depth:
        return False
    return bool(str_stack)
