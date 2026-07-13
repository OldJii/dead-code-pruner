"""Language adapter registry.

Maps file extensions to their ``BaseAdapter`` instances.  Call
``get_adapter(ext)`` to obtain the appropriate adapter for a given file
extension, or ``None`` if the extension is not recognised.
"""

from __future__ import annotations

from .base import BaseAdapter
from .java import JavaAdapter
from .kotlin import KotlinAdapter
from .go import GoAdapter
from .swift import SwiftAdapter
from .dart import DartAdapter

_ADAPTERS: dict[str, BaseAdapter] = {}


def _register(ext: str, adapter: BaseAdapter):
    _ADAPTERS[ext] = adapter


_register('.java', JavaAdapter())
_register('.kt', KotlinAdapter())
_register('.kts', KotlinAdapter())

_register('.go', GoAdapter())
_register('.swift', SwiftAdapter())
_register('.dart', DartAdapter())


def get_adapter(ext: str) -> BaseAdapter | None:
    """Return the adapter for *ext* (e.g. ``'.java'``), or ``None``."""
    return _ADAPTERS.get(ext)


def all_adapters() -> tuple[BaseAdapter, ...]:
    """Return unique registered adapter instances."""
    return tuple({id(adapter): adapter for adapter in _ADAPTERS.values()}.values())


__all__ = ['BaseAdapter', 'get_adapter', 'all_adapters']
