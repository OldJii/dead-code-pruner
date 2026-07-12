"""Class hierarchy helpers — thin facade over ``ContractGraph``.

Kept for backward compatibility with existing imports.  New code should
use ``pruner.analysis.contracts`` directly.
"""

from .contracts import ContractGraph, is_safe_to_remove, promote_unreferenced


def is_framework_class(class_name: str | None) -> bool:
    """Deprecated name-heuristic; always returns ``False``.

    Framework entry points are decided by language adapters and the
    contract graph — class-name prefixes are not used.
    """
    return False


def enhance_safety(all_dead: list[dict], children_map, final_classes,
                   iface_abstract, implements,
                   contracts: ContractGraph | None = None) -> int:
    """Promote leaf/final-class methods that are already visibility-safe.

    Public / protected / package-private instance methods are NOT promoted
    here — that is handled exclusively by ``promote_unreferenced`` after a
    project-wide reference check, so same-file callers are respected.
    """
    if contracts is None:
        contracts = ContractGraph()
        contracts.children_map = children_map
        contracts.final_classes = final_classes
        contracts.iface_abstract = iface_abstract
        contracts.implements = implements

    enhanced = 0
    for dm in all_dead:
        if dm.get('safe_to_inline'):
            continue
        if dm.get('class_type') == 'enum_declaration':
            continue
        if contracts.is_contract_method(dm.get('class_name'), dm.get('name', '')):
            continue
        mods = dm.get('all_mods', set()) or set()
        # Mirror historical visibility gate: only touch private-like methods
        # for leaf/final promotion.  Public instance stays for ref-based
        # promotion later.
        if not dm.get('is_private'):
            if 'public' in mods and 'static' not in mods:
                continue
            if 'protected' in mods:
                continue
            if not mods:
                continue
        cls = dm.get('class_name')
        if not cls:
            continue
        if cls in contracts.iface_abstract:
            continue
        is_final = cls in contracts.final_classes
        has_children = bool(contracts.children_map.get(cls))
        if is_final or not has_children:
            if is_safe_to_remove(dm, contracts) or dm.get('is_private'):
                dm['safe_to_inline'] = True
                enhanced += 1
    return enhanced


__all__ = [
    'is_framework_class', 'enhance_safety',
    'ContractGraph', 'is_safe_to_remove', 'promote_unreferenced',
]
