"""Dart / Flutter language adapter.

Dart uses a leading underscore for library-private visibility.  Flutter
widgets have a well-defined lifecycle (``build``, ``initState``,
``dispose``, …) that must be preserved.
"""

from __future__ import annotations

from .base import BaseAdapter

_PROTECTED_NAMES: frozenset[str] = frozenset({
    # ── Dart entry ──
    'main',

    # ── Flutter Widget lifecycle ──
    'build', 'createState', 'initState', 'dispose',
    'didChangeDependencies', 'didUpdateWidget',
    'reassemble', 'deactivate', 'activate',

    # ── Flutter RenderObject ──
    'createElement', 'paint', 'performLayout',
    'hitTest', 'hitTestSelf', 'hitTestChildren',
    'debugFillProperties', 'debugDescribeChildren',

    # ── Serialization ──
    'toJson', 'fromJson', 'toMap', 'fromMap',

    # ── Object ──
    'toString', 'hashCode',

    # ── State management ──
    'mapEventToState', 'listen',
})

_PROTECTED_ANNOTATION_PREFIXES: frozenset[str] = frozenset({
    '@override', '@visibleForTesting', '@required',
    '@protected', '@mustCallSuper', '@immutable',
    '@pragma',
})


class DartAdapter(BaseAdapter):

    @property
    def protected_names(self) -> frozenset[str]:
        return _PROTECTED_NAMES

    @property
    def protected_annotation_prefixes(self) -> frozenset[str]:
        return _PROTECTED_ANNOTATION_PREFIXES

    def is_entry_point(self, record: dict) -> bool:
        name = record.get('name', '')
        if name in self.protected_names:
            return True
        mods = record.get('all_mods', set())
        if 'override' in mods:
            return True
        return False

    def compute_safe_to_inline(self, record: dict) -> bool:
        if self.is_entry_point(record):
            return False
        name = record.get('name', '')
        if name.startswith('_'):
            return True
        mods = record.get('all_mods', set())
        return 'static' in mods
