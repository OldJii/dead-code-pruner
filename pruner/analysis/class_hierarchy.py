"""Class hierarchy analysis — detects leaf/final classes for safe inlining.

Methods in leaf classes (classes with no subclasses) or ``final`` classes
can be treated as effectively private for dead-code purposes.
"""


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
