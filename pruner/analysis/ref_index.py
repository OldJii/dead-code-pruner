"""Reference index — maps method names to files that contain call sites.

Also provides helper utilities: file collection and comment/string detection.
"""

import os
import re
from collections import defaultdict
from ..lang import _PARSERS, SKIP_DIRS
from .. import ui
from .text_index import TextIndex


REFERENCE_EXTS = frozenset({
    '.storyboard', '.xib', '.plist', '.xml', '.json',
})

_CALL_PAT = re.compile(r'\b(\w+)\s*\(')
_REF_PAT = re.compile(r'::(\w+)\b')
_SWIFT_SELECTOR_PAT = re.compile(
    r'#selector\s*\(\s*(?:getter:\s*|setter:\s*)?(?:(?:\w+)\.)?(\w+)\b')
_IB_SELECTOR_PAT = re.compile(r'\bselector="([A-Za-z_]\w*)')
_XML_CALLBACK_PAT = re.compile(
    r'\b(?:action|android:onClick|onClick)="([A-Za-z_]\w*)')
_DOT_PROPERTY_PAT = re.compile(r'\.([a-z]\w*)\b(?!\s*\()')
_TYPE_IDENTIFIER_PAT = re.compile(r'\b([A-Z][A-Za-z0-9_]*)\b')
_IMPORT_SYMBOL_PAT = re.compile(
    r'(?m)^\s*import\s+(?:static\s+)?[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*'
    r'\.([A-Za-z_]\w*)\s*;?\s*$')

# Content-keyed cache.  Do NOT key by id(content) alone — CPython reuses
# object ids after GC, which would return a stale TextIndex for a new string.
_INDEX_CACHE: dict[tuple[int, int], TextIndex] = {}
_INDEX_CACHE_ORDER: list[tuple[int, int]] = []


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

    Rare patterns (``::ref``, ``#selector``, ``selector=``) are guarded
    by cheap substring pre-checks so files without those constructs skip
    the expensive regex entirely.
    """
    for m in _CALL_PAT.finditer(content):
        yield m.group(1)
    if '::' in content:
        for m in _REF_PAT.finditer(content):
            yield m.group(1)
    if '#selector' in content:
        for m in _SWIFT_SELECTOR_PAT.finditer(content):
            yield m.group(1)
    if 'selector="' in content:
        for m in _IB_SELECTOR_PAT.finditer(content):
            yield m.group(1)
    if 'action="' in content or 'onClick="' in content:
        for m in _XML_CALLBACK_PAT.finditer(content):
            yield m.group(1)
    if '.' in content:
        for m in _DOT_PROPERTY_PAT.finditer(content):
            yield m.group(1)
    if 'import ' in content:
        # An unused static/Kotlin import still has to resolve at compile
        # time.  Index the imported terminal symbol even when no call
        # remains after constant folding.
        for m in _IMPORT_SYMBOL_PAT.finditer(content):
            yield m.group(1)


def iter_type_identifiers(content: str):
    """Yield conventional type identifiers used for contextual call lookup.

    Java, Kotlin, Swift, Dart, and exported Go types conventionally start
    with an uppercase letter.  Keeping this small secondary index lets the
    dead-method safety pass answer ``TypeName.method()`` questions with set
    intersections instead of repeatedly scanning whole files.
    """
    for m in _TYPE_IDENTIFIER_PAT.finditer(content):
        yield m.group(1)


def iter_dynamic_reference_names(content: str):
    """Yield selector/action names referenced by framework metadata."""
    if '#selector' in content:
        for m in _SWIFT_SELECTOR_PAT.finditer(content):
            yield m.group(1)
    if 'selector="' in content:
        for m in _IB_SELECTOR_PAT.finditer(content):
            yield m.group(1)
    if 'action="' in content or 'onClick="' in content:
        for m in _XML_CALLBACK_PAT.finditer(content):
            yield m.group(1)


def build_ref_index(all_files: list[str], *, quiet: bool = False,
                    content_cache: dict[str, str] | None = None,
                    ) -> dict[str, set[str]]:
    """Build a ``{method_name: {filepath, …}}`` reverse index.

    When *content_cache* is provided, file contents are read from cache
    instead of disk.
    """
    index: dict[str, set[str]] = defaultdict(set)
    total = len(all_files)
    for idx, fp in enumerate(all_files):
        if not quiet and ((idx + 1) % 1000 == 0 or idx + 1 == total):
            ui.progress(idx + 1, total, "Building ref index", indent=4)
        content = content_cache.get(fp) if content_cache else None
        if content is None:
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue
        for name in iter_reference_names(content):
            # Short method names are common in logging and compatibility
            # APIs (for example d/e/bs).  Dropping them makes live methods
            # look unreferenced and is therefore never safe.
            index[name].add(fp)
    if not quiet and total > 100:
        ui.progress_done()
    return index


def clear_text_index_cache() -> None:
    """Drop cached ``TextIndex`` instances (call between major pipeline phases)."""
    _INDEX_CACHE.clear()
    _INDEX_CACHE_ORDER.clear()


def is_in_comment_or_string(content: str, pos: int) -> bool:
    """Return ``True`` if *pos* falls inside a comment or string literal.

    Uses a per-content ``TextIndex`` so repeated queries are O(log n) after
    a single linear scan of the file.
    """
    key = (len(content), hash(content))
    idx = _INDEX_CACHE.get(key)
    if idx is None:
        idx = TextIndex(content)
        _INDEX_CACHE[key] = idx
        _INDEX_CACHE_ORDER.append(key)
        if len(_INDEX_CACHE_ORDER) > 64:
            old = _INDEX_CACHE_ORDER.pop(0)
            _INDEX_CACHE.pop(old, None)
    return idx.covers(pos)
