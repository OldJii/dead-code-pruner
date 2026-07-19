"""Code-editing helpers for method inlining and deletion.

Provides regex-based call-site replacement, void-call removal, standalone
boolean cleanup, line-range deletion, and cross-file reference detection.
"""

import os
import re
from .ref_index import REFERENCE_EXTS, is_in_comment_or_string
from .text_index import clean_standalone_literal_lines


def _is_reference_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in REFERENCE_EXTS


def has_dynamic_symbol_ref(content: str, method_name: str) -> bool:
    selector = re.escape(method_name)
    patterns = (
        r'#selector\s*\([^)]*\b' + selector + r'\b',
        r'\bselector="' + selector + r'\b',
        r'\baction="' + selector + r'\b',
        r'\b(?:android:)?onClick="' + selector + r'\b',
    )
    return any(re.search(p, content) for p in patterns)


def _line_of_offset(content: str, offset: int) -> int:
    """Return the 0-based line number for byte offset *offset*."""
    return content.count('\n', 0, offset)


def replace_calls_in_content(content: str, method_name: str, value: str,
                             class_name: str | None = None,
                             same_file: bool = True,
                             class_lines: tuple[int, int] | None = None,
                             ) -> tuple[str, int]:
    """Replace ``method()`` / ``Class.method()`` with *value*.

    When *class_lines* ``(start, end)`` is provided and *same_file* is
    ``True``, bare (unqualified) call replacements are restricted to lines
    within the enclosing class scope, preventing cross-class mis-replacement
    in files that contain multiple classes with same-name methods.
    Qualified calls (``ClassName.method()``) are always replaced file-wide.
    """
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
            if class_lines is not None:
                line_no = _line_of_offset(content, m.start())
                if not (class_lines[0] <= line_no <= class_lines[1]):
                    continue
            line_start = content.rfind('\n', 0, m.start()) + 1
            before = content[line_start:m.start()].strip().split()
            if before and before[-1] in type_kws:
                continue
            if before and re.match(r'^[A-Z]\w*$', before[-1]):
                continue
            new_content += content[last:m.start()] + value
            last = m.end()
            count += 1
        new_content += content[last:]
        content = new_content

    return content, count


def remove_void_calls_in_content(content: str, method_name: str,
                                 class_name: str | None = None,
                                 same_file: bool = True,
                                 class_lines: tuple[int, int] | None = None,
                                 ) -> tuple[str, int]:
    """Remove standalone void method calls.

    When *class_lines* ``(start, end)`` is provided and *same_file* is
    ``True``, bare (unqualified) calls are only removed within the
    enclosing class scope.  Qualified calls (``this.method()``,
    ``ClassName.method()``) are always removed file-wide.
    """
    lines = content.split('\n')
    new_lines = []
    count = 0

    bare_pat = re.compile(
        r'^\s*' + re.escape(method_name) + r'\s*\(\s*\)\s*;?\s*$')
    this_pat = re.compile(
        r'^\s*this\s*\.\s*' + re.escape(method_name) + r'\s*\(\s*\)\s*;?\s*$')
    cls_pat = (re.compile(
        r'^\s*' + re.escape(class_name) + r'\s*\.\s*'
        + re.escape(method_name) + r'\s*\(\s*\)\s*;?\s*$')
        if class_name else None)

    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if is_in_comment_or_string(line, line.find(method_name)) if method_name in line else False:
            new_lines.append(line)
            continue
        if same_file and this_pat.match(stripped):
            count += 1
            continue
        if cls_pat and cls_pat.match(stripped):
            count += 1
            continue
        if same_file and bare_pat.match(stripped):
            if class_lines is not None and not (class_lines[0] <= i <= class_lines[1]):
                new_lines.append(line)
                continue
            count += 1
            continue
        if not same_file and not class_name:
            if bare_pat.match(stripped):
                count += 1
                continue
        new_lines.append(line)
    return '\n'.join(new_lines), count


def clean_standalone_booleans(content: str) -> str:
    """Remove standalone ``true;`` / ``false;`` statements.

    Multi-line assignment RHS lines (previous non-blank line ends with ``=``)
    are preserved so forms like ``boolean x =\\n    false;`` stay valid.
    """
    return clean_standalone_literal_lines(content, {'true;', 'false;'})


def delete_line_ranges(content: str, ranges: list[tuple[int, int]]) -> tuple[str, int]:
    """Delete *ranges* ``[(start_line, end_line), …]`` from *content*.

    Lines that look like import/package declarations are never removed,
    even if they fall within a deletion range (guards against AST line
    drift that would accidentally strip imports).

    Returns ``(new_content, deleted_count)``.
    """
    if not ranges:
        return content, 0
    lines = content.split('\n')
    deleted = 0
    # Duplicate ranges are possible when several stale candidate records
    # resolve to the same current declaration.  Applying the same deletion
    # twice would remove the declaration *and then unrelated following code*.
    for start, end in sorted(set(ranges), reverse=True):
        if 0 <= start <= end < len(lines):
            safe_start = start
            while safe_start <= end:
                stripped = lines[safe_start].strip()
                if stripped.startswith(('import ', 'package ')):
                    safe_start += 1
                else:
                    break
            if safe_start > end:
                continue
            del lines[safe_start:end + 1]
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
    if needle not in content and not has_dynamic_symbol_ref(content, method_name):
        return False
    if has_dynamic_symbol_ref(content, method_name):
        return True

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


_KOTLIN_PROPERTY_PREFIXES = ('is', 'get', 'has')


def _kotlin_property_name(method_name: str) -> str | None:
    """Derive the Kotlin property name from a Java getter.

    ``isEnabled`` → ``isEnabled`` (``is`` prefix kept for boolean).
    ``getCount``  → ``count``.
    ``hasItems``  → ``hasItems`` (``has`` kept — not a standard property).
    Returns *None* when the name does not match a getter pattern.
    """
    if method_name.startswith('is') and len(method_name) > 2 and method_name[2].isupper():
        return method_name
    if method_name.startswith('get') and len(method_name) > 3 and method_name[3].isupper():
        return method_name[3].lower() + method_name[4:]
    if method_name.startswith('has') and len(method_name) > 3 and method_name[3].isupper():
        return method_name
    return None


def _has_kotlin_property_ref(content: str, method_name: str) -> bool:
    """Check for Kotlin-style property access of a Java getter.

    Searches for ``.propertyName`` where *propertyName* is either the
    original method name (``is*``, ``has*``) or the decapitalised
    ``get*`` form.
    """
    prop = _kotlin_property_name(method_name)
    if not prop:
        return False
    dot_prop = '.' + prop
    start = 0
    while True:
        idx = content.find(dot_prop, start)
        if idx == -1:
            return False
        after = idx + len(dot_prop)
        if after < len(content) and (content[after].isalnum() or content[after] == '_'):
            start = after
            continue
        if is_in_comment_or_string(content, idx):
            start = after
            continue
        return True


def verify_no_dangling_calls(content: str, method_names: set[str]) -> list[str]:
    """Return names from *method_names* that still appear as call sites in *content*."""
    dangling = []
    for name in method_names:
        pat = re.compile(r'(?<!\w)' + re.escape(name) + r'\s*\(\s*\)')
        for m in pat.finditer(content):
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:content.find('\n', m.start())]
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*'):
                continue
            if not is_in_comment_or_string(content, m.start()):
                dangling.append(name)
                break
    return dangling


def has_cross_file_refs(dm: dict, ref_index: dict, src_abs: str,
                        children_map: dict | None = None,
                        iface_abstract: set | None = None,
                        *,
                        polymorphic: bool | None = None,
                        content_cache: dict[str, str] | None = None,
                        member_ref_index: dict[str, set[str]] | None = None,
                        type_ref_index: dict[str, set[str]] | None = None,
                        dynamic_ref_index: dict[str, set[str]] | None = None,
                        implicit_ref_index: dict[tuple[str, str], set[str]] | None = None,
                        ) -> bool:
    """Return ``True`` if method *dm* has cross-file references.

    When *content_cache* ``{filepath: content_str}`` is provided, file
    contents are looked up from cache to avoid repeated disk I/O.

    Detection strategies (applied in order):
      1. Qualified:  ``ClassName.methodName`` in the file.
      2. Contextual: both ``ClassName`` and ``methodName(`` in the file.
      3. Instance:   bare ``methodName(`` **call** for non-private, non-static
         methods.  When the declaring type participates in polymorphism
         (subclasses, interface implements, abstract type), bare calls are
         accepted without requiring the concrete class name — covering
         casts like ``((Iface) x).method()``.
      4. Receiver: ``factory().methodName(`` / ``value.methodName(`` for
         public instance methods whose receiver type is inferred rather than
         written in the caller.
      5. Kotlin property: ``.isXxx`` / ``.xxx`` (for ``getXxx``) property
         access without parentheses — Java/Kotlin interop.
    """
    name = dm['name']
    cls  = dm.get('class_name', '')
    is_private = dm.get('is_private', False)
    is_static  = dm.get('is_static', False)
    is_instance = not is_private and not is_static

    if polymorphic is None:
        has_hierarchy = False
        if is_instance and cls and children_map:
            has_hierarchy = bool(children_map.get(cls))
        if is_instance and cls and iface_abstract and cls in iface_abstract:
            has_hierarchy = True
    else:
        has_hierarchy = bool(polymorphic)

    prop_name = _kotlin_property_name(name)
    check_property = prop_name is not None

    ref_files = set(ref_index.get(name, set()))
    if implicit_ref_index is not None:
        ext = os.path.splitext(dm.get('filepath', ''))[1].lower()
        ref_files |= implicit_ref_index.get((ext, name), set())
    if check_property and prop_name != name:
        ref_files |= ref_index.get(prop_name, set())

    # The unified scanner builds two compact secondary indices.  They turn
    # the overwhelmingly common checks into C-level set operations instead
    # of re-running regex/string scans for every candidate method.
    can_use_secondary_indices = (
        type_ref_index is not None
        and dynamic_ref_index is not None
    )
    if can_use_secondary_indices:
        external_refs = {rf for rf in ref_files
                         if os.path.abspath(rf) != src_abs}
        if not external_refs:
            return False

        dynamic_files = set(dynamic_ref_index.get(name, set()))
        if check_property and prop_name != name:
            dynamic_files |= dynamic_ref_index.get(prop_name, set())
        if external_refs & dynamic_files:
            return True

        if cls:
            contextual_files = set(type_ref_index.get(cls, set()))
            # Static methods are inherited and may be called bare from any
            # descendant.  Expand the declaring type through the known
            # hierarchy so ``Child : Middle`` can safely call a method
            # declared on ``Base`` without spelling ``Base.method``.
            if is_static and children_map:
                pending = list(children_map.get(cls, ()))
                seen = set(pending)
                while pending:
                    child = pending.pop()
                    contextual_files |= type_ref_index.get(child, set())
                    for descendant in children_map.get(child, ()):
                        if descendant not in seen:
                            seen.add(descendant)
                            pending.append(descendant)
            if external_refs & contextual_files:
                return True
        elif not cls:
            # Top-level functions are called by bare/package-qualified name.
            # Any external language-index hit is direct evidence.
            return True

        # A public instance method may be invoked through a factory return,
        # fluent chain, inferred local type, or dependency-injection result,
        # none of which has to spell the declaring type in the caller.  A
        # distinct ``.method(...)`` index preserves those receiver calls
        # without treating unrelated bare same-name functions as references.
        if is_instance and member_ref_index is not None:
            member_files = set(member_ref_index.get(name, set()))
            if check_property and prop_name != name:
                member_files |= member_ref_index.get(prop_name, set())
            if external_refs & member_files:
                return True

        # Polymorphic calls can be made through an interface/base-typed
        # receiver without mentioning the concrete class.  Treat any
        # external call-index hit as live; false positives only retain code.
        if is_instance and has_hierarchy:
            return True

        if check_property:
            # Property syntax omits the method parentheses, so inspect only
            # the already narrowed external files.  This path is uncommon;
            # keeping it exact avoids retaining unrelated same-name getters.
            for rf in external_refs:
                rc = content_cache.get(rf) if content_cache else None
                if rc is None:
                    try:
                        with open(rf, 'r', encoding='utf-8', errors='ignore') as fh:
                            rc = fh.read()
                    except Exception:
                        continue
                if _has_kotlin_property_ref(rc, name):
                    return True
        return False

    for rf in ref_files:
        if os.path.abspath(rf) == src_abs:
            continue
        rc = content_cache.get(rf) if content_cache else None
        if rc is None:
            try:
                with open(rf, 'r', encoding='utf-8', errors='ignore') as fh:
                    rc = fh.read()
            except Exception:
                continue
        if _is_reference_file(rf) and has_dynamic_symbol_ref(rc, name):
            return True
        if has_dynamic_symbol_ref(rc, name):
            return True
        qualified = cls + '.' + name if cls else ''
        if qualified and qualified in rc:
            return True
        if cls and cls in rc and name + '(' in rc:
            return True
        if is_instance:
            if has_hierarchy:
                if _has_call_site(rc, name):
                    return True
            else:
                if cls and cls in rc and _has_call_site(rc, name):
                    return True
        if check_property and _has_kotlin_property_ref(rc, name):
            return True
    return False
