"""Unified contract & safety policy for dead-declaration cleanup.

Replaces scattered special-case heuristics (framework class-name prefixes,
ad-hoc public promotion, incomplete implements tracking) with a single
model:

  * **Contracts** — interface / protocol / abstract method signatures that
    concrete types must fulfil.
  * **Implements / extends** — typed edges from concrete classes to those
    contracts and parents.
  * **SafetyPolicy** — decides whether a declaration may be inlined or
    deleted, consulting language adapters + the contract graph.
"""

from __future__ import annotations

import re
from collections import defaultdict

from ..adapters import get_adapter


# ── Hierarchy / contract extraction (regex, language-agnostic enough) ──

_EXTENDS = re.compile(
    r'\b(?:final\s+|open\s+|public\s+|private\s+|protected\s+|internal\s+)*'
    r'(?:class|object)\s+(\w+)\s*(?::|extends)\s+(\w+)'
)
_FINAL_CLS = re.compile(r'\bfinal\s+class\s+(\w+)')
_IFACE_ABS = re.compile(
    r'\b(?:interface|protocol|abstract\s+class)\s+(\w+)'
)
# Java/Kotlin implements list (may be multi-line truncated at `{`)
_IMPL_JAVA = re.compile(
    r'\bclass\s+(\w+)\b[^{]*?\bimplements\s+([^{]+)'
)
# Kotlin / Swift style: `class Foo : Bar, Baz` (also covers extends)
_IMPL_COLON = re.compile(
    r'\b(?:class|object|struct|actor)\s+(\w+)\s*:\s*([^{\n]+)'
)
# Abstract / interface method signatures (no body, or abstract keyword)
_ABS_METHOD = re.compile(
    r'(?:^|\n)\s*(?:(?:public|protected|internal|open|override|abstract|fun)\s+)+'
    r'(?:[\w.<>,\[\]?\s]+\s+)?'
    r'(\w+)\s*\([^;{]*\)\s*(?::\s*[\w.<>,\[\]?\s]+)?\s*(?:;|$)',
)
_IFACE_METHOD_JAVA = re.compile(
    r'(?:^|\n)\s*(?:default\s+|static\s+)?'
    r'(?:[\w.<>,\[\]?\s]+)\s+(\w+)\s*\([^;{]*\)\s*;',
)
_KT_IFACE_METHOD = re.compile(
    r'(?:^|\n)\s*fun\s+(\w+)\s*\([^)]*\)\s*(?::\s*[^\n={]+)?\s*(?:\n|$|=)',
)
_SWIFT_PROTOCOL_METHOD = re.compile(
    r'(?:^|\n)\s*func\s+(\w+)\s*\([^)]*\)',
)


class ContractGraph:
    """Project-level type hierarchy and interface/abstract contracts."""

    __slots__ = (
        'children_map', 'final_classes', 'iface_abstract',
        'implements', 'class_implements', 'iface_methods',
        'extends',
    )

    def __init__(self):
        self.children_map: dict[str, set[str]] = defaultdict(set)
        self.final_classes: set[str] = set()
        self.iface_abstract: set[str] = set()
        # Classes that implement at least one interface (legacy set)
        self.implements: set[str] = set()
        # class → set of interface/protocol/parent type names
        self.class_implements: dict[str, set[str]] = defaultdict(set)
        # interface/abstract/protocol → method names
        self.iface_methods: dict[str, set[str]] = defaultdict(set)
        # class → direct parent class name
        self.extends: dict[str, str] = {}

    def ingest_file(self, content: str) -> None:
        """Update the graph from one source file's text.

        Files that contain no class/interface/protocol/struct keywords are
        skipped entirely, avoiding 5+ expensive regex passes on files that
        cannot contribute hierarchy data.
        """
        if not ('class ' in content or 'interface ' in content
                or 'protocol ' in content or 'struct ' in content
                or 'object ' in content or 'abstract ' in content):
            return

        for m in _EXTENDS.finditer(content):
            child, parent = m.group(1), m.group(2)
            self.children_map[parent].add(child)
            self.extends[child] = parent
            self.class_implements[child].add(parent)

        for m in _FINAL_CLS.finditer(content):
            self.final_classes.add(m.group(1))

        for m in _IFACE_ABS.finditer(content):
            self.iface_abstract.add(m.group(1))

        if 'implements ' in content:
            for m in _IMPL_JAVA.finditer(content):
                cls = m.group(1)
                self.implements.add(cls)
                for iface in _split_type_list(m.group(2)):
                    self.class_implements[cls].add(iface)
                    self.children_map[iface].add(cls)

        if ':' in content:
            for m in _IMPL_COLON.finditer(content):
                cls = m.group(1)
                types = _split_type_list(m.group(2))
                if not types:
                    continue
                self.extends.setdefault(cls, types[0])
                self.children_map[types[0]].add(cls)
                for t in types:
                    self.class_implements[cls].add(t)
                    self.children_map[t].add(cls)
                if len(types) > 1:
                    self.implements.add(cls)

        self._extract_iface_methods(content)

    def merge(self, other: 'ContractGraph') -> None:
        """Merge another ContractGraph into this one (for multiprocessing)."""
        for parent, children in other.children_map.items():
            self.children_map[parent] |= children
        self.final_classes |= other.final_classes
        self.iface_abstract |= other.iface_abstract
        self.implements |= other.implements
        for cls, ifaces in other.class_implements.items():
            self.class_implements[cls] |= ifaces
        for iface, methods in other.iface_methods.items():
            self.iface_methods[iface] |= methods
        for cls, parent in other.extends.items():
            self.extends.setdefault(cls, parent)

    def _extract_iface_methods(self, content: str) -> None:
        """Pull method names from interface / protocol / abstract class bodies."""
        for iface in list(self.iface_abstract):
            # Find body of this interface declaration in the file
            pat = re.compile(
                r'\b(?:interface|protocol|abstract\s+class)\s+'
                + re.escape(iface)
                + r'\b[^{]*\{',
            )
            m = pat.search(content)
            if not m:
                continue
            body = _extract_balanced_body(content, m.end() - 1)
            if body is None:
                continue
            names = set()
            for rx in (_IFACE_METHOD_JAVA, _KT_IFACE_METHOD,
                       _SWIFT_PROTOCOL_METHOD, _ABS_METHOD):
                for mm in rx.finditer(body):
                    name = mm.group(1)
                    if name not in ('if', 'for', 'while', 'switch', 'catch'):
                        names.add(name)
            if names:
                self.iface_methods[iface] |= names

    def is_contract_method(self, class_name: str | None, method_name: str) -> bool:
        """Return ``True`` if *method_name* fulfils an interface/abstract contract
        for *class_name* (including inherited implements via extends chain).
        """
        if not class_name or not method_name:
            return False
        seen: set[str] = set()
        stack = [class_name]
        while stack:
            cls = stack.pop()
            if cls in seen:
                continue
            seen.add(cls)
            for iface in self.class_implements.get(cls, ()):
                if method_name in self.iface_methods.get(iface, ()):
                    return True
                stack.append(iface)
            parent = self.extends.get(cls)
            if parent:
                stack.append(parent)
        # Conservative fallback: class (or any ancestor) implements/extends
        # anything, and method name appears in ANY known interface's method
        # set.  Covers parse gaps on implements lists and indirect hierarchy.
        if self._class_participates_in_hierarchy(class_name):
            for methods in self.iface_methods.values():
                if method_name in methods:
                    return True
        return False

    def _class_participates_in_hierarchy(self, class_name: str) -> bool:
        """Return ``True`` if *class_name* or any ancestor participates in
        an interface/abstract hierarchy."""
        seen: set[str] = set()
        stack = [class_name]
        while stack:
            cls = stack.pop()
            if cls in seen:
                continue
            seen.add(cls)
            if cls in self.implements or self.class_implements.get(cls):
                return True
            if cls in self.iface_abstract:
                return True
            if self.children_map.get(cls):
                return True
            parent = self.extends.get(cls)
            if parent:
                stack.append(parent)
        return False

    def has_polymorphic_targets(self, class_name: str | None) -> bool:
        """``True`` when *class_name* may be invoked through a parent/interface."""
        if not class_name:
            return True
        if class_name in self.iface_abstract:
            return True
        if class_name in self.implements or self.class_implements.get(class_name):
            return True
        if self.children_map.get(class_name):
            return True
        return False


def _split_type_list(raw: str) -> list[str]:
    """Split ``Foo, Bar<Baz>, com.x.Y`` into bare type identifiers."""
    parts: list[str] = []
    depth = 0
    cur = []
    for ch in raw:
        if ch in '<([':
            depth += 1
            cur.append(ch)
        elif ch in '>)]':
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append(''.join(cur).strip())
    names: list[str] = []
    for p in parts:
        p = p.strip().rstrip(',')
        if not p or p.startswith('where '):
            continue
        # Drop generic args and annotations
        p = re.sub(r'<[^>]*>', '', p).strip()
        p = p.split()[-1] if p.split() else p
        p = p.rsplit('.', 1)[-1]
        if re.match(r'^[A-Za-z_]\w*$', p):
            names.append(p)
    return names


def _extract_balanced_body(content: str, open_brace: int) -> str | None:
    if open_brace < 0 or open_brace >= len(content) or content[open_brace] != '{':
        return None
    depth = 0
    i = open_brace
    n = len(content)
    while i < n:
        c = content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return content[open_brace + 1:i]
        elif c in ('"', "'"):
            q = c
            i += 1
            while i < n and content[i] != q:
                if content[i] == '\\':
                    i += 1
                i += 1
        i += 1
    return None


# ── Safety policy ───────────────────────────────────────────

def is_safe_to_remove(record: dict, graph: ContractGraph,
                      *, require_zero_arg_for_inline: bool = False) -> bool:
    """Unified safety decision for deleting/inlining a method record.

    Returns ``False`` (keep) when:
      * declared on an enum
      * language adapter marks it as an entry point
      * it fulfils an interface / abstract / protocol contract
      * it is declared on an interface / abstract type itself
      * annotated / abstract / override / open / native
    """
    if record.get('class_type') == 'enum_declaration':
        return False

    name = record.get('name', '')
    cls = record.get('class_name')
    mods = record.get('all_mods', set()) or set()

    if 'abstract' in mods or 'native' in mods or 'open' in mods:
        return False
    if 'override' in mods or 'Override' in mods:
        return False

    ext = None
    fp = record.get('filepath', '')
    if fp:
        import os
        ext = os.path.splitext(fp)[1].lower()
    adapter = get_adapter(ext) if ext else None
    if adapter and adapter.is_entry_point(record):
        return False

    if cls and cls in graph.iface_abstract:
        return False

    if graph.is_contract_method(cls, name):
        return False

    # Visibility only — leaf/final does NOT auto-promote public instance.
    if adapter:
        return bool(adapter.compute_safe_to_inline(record))
    return bool(record.get('is_private') or record.get('is_static'))


def promote_unreferenced(record: dict, graph: ContractGraph,
                         has_any_ref: bool) -> bool:
    """Promote an otherwise-unsafe method when project-wide refs are absent.

    Never promotes contract methods, enum members, or polymorphic interface
    implementors whose method name matches a known contract symbol.
    """
    if has_any_ref:
        return False
    if record.get('class_type') == 'enum_declaration':
        return False

    cls = record.get('class_name')
    name = record.get('name', '')
    if graph.is_contract_method(cls, name):
        return False
    if cls and cls in graph.iface_abstract:
        return False

    mods = record.get('all_mods', set()) or set()
    if 'override' in mods or 'Override' in mods:
        return False

    # Static / private: always promotable when unreferenced
    if record.get('is_static') or record.get('is_private'):
        return True

    # Public/protected/package instance: only when the name is not a known
    # interface/abstract method anywhere (guards parse gaps), and the type
    # is a leaf (or final) so we are not removing a base API.
    if any(name in ms for ms in graph.iface_methods.values()):
        return False
    if cls and graph._class_participates_in_hierarchy(cls):
        return False
    is_final = cls in graph.final_classes if cls else False
    has_children = bool(graph.children_map.get(cls)) if cls else True
    if is_final or not has_children:
        return True
    return False
