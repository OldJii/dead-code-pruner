"""Unified contract & safety policy for dead-declaration cleanup.

Replaces scattered special-case heuristics (framework class-name prefixes,
ad-hoc public promotion, incomplete implements tracking) with a single
model:

  * **Contracts** — interface / protocol / abstract method signatures that
    concrete types must fulfil.
  * **Type relations** — typed edges from concrete classes to those
    contracts and parents.
  * **SafetyPolicy** — decides whether a declaration may be inlined or
    deleted, consulting language adapters + the contract graph.
"""

from __future__ import annotations

import os
from collections import defaultdict

from ..adapters import get_adapter


class ContractGraph:
    """Project-level type hierarchy and interface/abstract contracts."""

    __slots__ = (
        'children_map', 'iface_abstract', 'class_implements', 'iface_methods',
        '_facts_by_file',
    )

    def __init__(self):
        self.children_map: dict[str, set[str]] = defaultdict(set)
        self.iface_abstract: set[str] = set()
        # class → set of interface/protocol/parent type names
        self.class_implements: dict[str, set[str]] = defaultdict(set)
        # interface/abstract/protocol → method names
        self.iface_methods: dict[str, set[str]] = defaultdict(set)
        self._facts_by_file: dict[str, dict] = {}

    def ingest_file(self, content: str, ext: str, filepath: str) -> None:
        """Extract and merge one file through its language adapter."""
        adapter = get_adapter(ext)
        if adapter is None:
            return
        facts = adapter.contract_facts(content)
        if filepath in self._facts_by_file:
            self._facts_by_file[filepath] = facts
            self._rebuild()
            return
        self._facts_by_file[filepath] = facts
        self._merge_facts(facts)

    def remove_files(self, filepaths: set[str]) -> None:
        """Remove stale per-file facts before an incremental re-scan."""
        changed = False
        for filepath in filepaths:
            if self._facts_by_file.pop(filepath, None) is not None:
                changed = True
        if changed:
            self._rebuild()

    def merge(self, other: 'ContractGraph') -> None:
        """Merge another ContractGraph into this one (for multiprocessing)."""
        overlap = self._facts_by_file.keys() & other._facts_by_file.keys()
        self._facts_by_file.update(other._facts_by_file)
        if overlap:
            self._rebuild()
        else:
            for facts in other._facts_by_file.values():
                self._merge_facts(facts)

    def _merge_facts(self, facts: dict) -> None:
        self.iface_abstract.update(facts.get('contracts', ()))
        for child, parents in facts.get('relations', {}).items():
            parents = set(parents)
            self.class_implements[child].update(parents)
            for parent in parents:
                self.children_map[parent].add(child)
        for contract, methods in facts.get('methods', {}).items():
            self.iface_methods[contract].update(methods)

    def _rebuild(self) -> None:
        self.children_map = defaultdict(set)
        self.iface_abstract = set()
        self.class_implements = defaultdict(set)
        self.iface_methods = defaultdict(set)
        for facts in self._facts_by_file.values():
            self._merge_facts(facts)

    def is_contract_method(self, class_name: str | None, method_name: str) -> bool:
        """Return ``True`` if *method_name* fulfils an interface/abstract contract
        for *class_name* (including inherited type relations).
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
        return bool(
            self.class_implements.get(class_name)
            or class_name in self.iface_abstract
            or self.children_map.get(class_name)
        )

    def has_polymorphic_targets(self, class_name: str | None) -> bool:
        """``True`` when *class_name* may be invoked through a parent/interface."""
        if not class_name:
            return True
        if class_name in self.iface_abstract:
            return True
        if self.class_implements.get(class_name):
            return True
        if self.children_map.get(class_name):
            return True
        return False


# ── Safety policy ───────────────────────────────────────────

def is_safe_to_remove(record: dict, graph: ContractGraph, *, boundary=None) -> bool:
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

    # Annotated methods are framework/reflection entry points even when no
    # source-level call exists (Lua bridges, DI providers, event handlers,
    # serialization hooks, and similar APIs).
    if record.get('has_annotation'):
        return False

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
    if adapter and adapter.uses_structural_contracts:
        if any(name in methods for methods in graph.iface_methods.values()):
            return False
        # Exported Go receiver methods may satisfy interfaces declared in
        # dependencies or the standard library, which syntax-only analysis
        # cannot enumerate safely.
        if cls and name and name[0].isupper():
            return False

    from .project_boundary import boundary_allows_record
    if not boundary_allows_record(record, boundary):
        return False

    # Visibility only — leaf/final does NOT auto-promote public instance.
    if adapter:
        return bool(adapter.compute_safe_to_inline(record))
    return bool(record.get('is_private') or record.get('is_static'))


def promote_unreferenced(record: dict, graph: ContractGraph,
                         has_any_ref: bool, *, boundary=None) -> bool:
    """Promote an otherwise-unsafe method when project-wide refs are absent.

    Never promotes contract methods, enum members, or polymorphic types whose
    method name matches a known contract symbol.
    """
    if has_any_ref:
        return False
    if record.get('has_annotation'):
        return False
    if record.get('class_type') == 'enum_declaration':
        return False

    cls = record.get('class_name')
    name = record.get('name', '')
    ext = os.path.splitext(record.get('filepath', ''))[1].lower()
    adapter = get_adapter(ext) if ext else None
    if adapter and adapter.is_entry_point(record):
        return False
    if graph.is_contract_method(cls, name):
        return False
    if cls and cls in graph.iface_abstract:
        return False

    if (adapter and adapter.uses_structural_contracts
            and cls and name and name[0].isupper()):
        return False

    mods = record.get('all_mods', set()) or set()
    if 'override' in mods or 'Override' in mods:
        return False

    from .project_boundary import boundary_allows_record
    if not boundary_allows_record(record, boundary):
        return False

    # Static / private: always promotable when unreferenced
    if record.get('is_static') or record.get('is_private'):
        return True

    # Top-level functions have no class hierarchy to consult.  They are
    # removable only when the owning module is explicitly/detectably closed.
    if (boundary is not None and not cls
            and boundary.allows_external_api_pruning(record.get('filepath', ''))):
        return True

    # Public/protected/package instance: only when the name is not a known
    # interface/abstract method anywhere (guards parse gaps), and the type
    # does not participate in a hierarchy.
    if any(name in ms for ms in graph.iface_methods.values()):
        return False
    if cls and graph._class_participates_in_hierarchy(cls):
        return False

    return bool(cls)
