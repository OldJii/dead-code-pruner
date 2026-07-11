"""Go language adapter.

Go visibility is determined by capitalisation: exported (uppercase first
letter) symbols form the public API and must be preserved in library
packages.  ``main``, ``init``, ``Test*``, ``Benchmark*``, and ``Example*``
are runtime/testing entry points.
"""

from __future__ import annotations

from .base import BaseAdapter

_PROTECTED_NAMES: frozenset[str] = frozenset({
    'main', 'init',
    # net/http handler interface
    'ServeHTTP',
    # fmt.Stringer / error interface
    'String', 'Error',
    # encoding/json
    'MarshalJSON', 'UnmarshalJSON', 'MarshalText', 'UnmarshalText',
    # database/sql
    'Scan', 'Value',
    # fmt
    'Format',
    # sort.Interface
    'Len', 'Less', 'Swap',
    # io interfaces
    'Read', 'Write', 'Close', 'ReadFrom', 'WriteTo',
    # context
    'Deadline', 'Done', 'Err',
})

_PROTECTED_ANNOTATION_PREFIXES: frozenset[str] = frozenset()

_TEST_PREFIXES = ('Test', 'Benchmark', 'Example', 'Fuzz')


class GoAdapter(BaseAdapter):

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
        if any(name.startswith(p) for p in _TEST_PREFIXES):
            return True
        if name and name[0].isupper():
            return True
        return False

    def compute_safe_to_inline(self, record: dict) -> bool:
        if self.is_entry_point(record):
            return False
        name = record.get('name', '')
        if name and name[0].islower():
            return True
        return False
