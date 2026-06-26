"""Class hierarchy analysis — detects leaf/final classes for safe inlining.

Methods in leaf classes (classes with no subclasses) or ``final`` classes
can be treated as effectively private for dead-code purposes.
"""

import re
from collections import defaultdict

_FRAMEWORK_PREFIXES = ('Abstract', 'Abs', 'Base', 'I')


def is_framework_class(class_name: str | None) -> bool:
    """Return ``True`` if *class_name* looks like a framework base class."""
    if not class_name:
        return True
    if class_name.startswith('Abstract') or class_name.endswith('Base'):
        return True
    if class_name.startswith('Abs') and len(class_name) > 3 and class_name[3].isupper():
        return True
    if class_name.startswith('Base') and len(class_name) > 4 and class_name[4].isupper():
        return True
    if class_name.startswith('I') and len(class_name) > 1 and class_name[1].isupper():
        return True
    return False


def build_class_hierarchy(all_files: list[str]):
    """Return ``(children_map, final_classes, iface_abstract, implements)``."""
    children_map: dict[str, set[str]] = defaultdict(set)
    final_classes: set[str]     = set()
    iface_abstract: set[str]    = set()
    implements: set[str]        = set()
    extends_pat = re.compile(r'\b(?:class|object)\s+(\w+)\s+(?:extends|:)\s+(\w+)')
    final_pat   = re.compile(r'\bfinal\s+class\s+(\w+)')
    iface_pat   = re.compile(r'\b(?:interface|abstract\s+class)\s+(\w+)')
    impl_pat    = re.compile(r'\bclass\s+(\w+)[^{]*\bimplements\s+')

    for fp in all_files:
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
        for m in extends_pat.finditer(content):
            children_map[m.group(2)].add(m.group(1))
        for m in final_pat.finditer(content):
            final_classes.add(m.group(1))
        for m in iface_pat.finditer(content):
            iface_abstract.add(m.group(1))
        for m in impl_pat.finditer(content):
            implements.add(m.group(1))

    return children_map, final_classes, iface_abstract, implements


def enhance_safety(all_dead: list[dict], children_map, final_classes,
                   iface_abstract, implements) -> int:
    """Promote leaf/final-class methods to ``safe_to_inline``.

    Returns the number of methods upgraded.
    """
    enhanced = 0
    for dm in all_dead:
        if dm.get('safe_to_inline'):
            continue
        if dm.get('class_type') == 'enum_declaration':
            continue
        mods = dm.get('all_mods', set())
        if not dm.get('is_private'):
            if 'public' in mods and 'static' not in mods:
                continue
            if 'protected' in mods:
                continue
            if not mods:
                continue
        cls = dm.get('class_name')
        if not cls or is_framework_class(cls):
            continue
        if cls in iface_abstract or cls in implements:
            continue
        is_final     = cls in final_classes
        has_children = cls in children_map and len(children_map[cls]) > 0
        if is_final or not has_children:
            dm['safe_to_inline'] = True
            enhanced += 1
    return enhanced
