"""Language adapter registry.

Maps file extensions to their ``BaseAdapter`` instances.  Call
``get_adapter(ext)`` to obtain the appropriate adapter for a given file
extension, or ``None`` if the extension is not recognised.
"""

from __future__ import annotations

from .base import BaseAdapter
from .java_kotlin import JavaKotlinAdapter
from .go import GoAdapter
from .swift import SwiftAdapter
from .dart import DartAdapter

_ADAPTERS: dict[str, BaseAdapter] = {}


def _register(ext: str, adapter: BaseAdapter):
    _ADAPTERS[ext] = adapter


_jk = JavaKotlinAdapter()
_register('.java', _jk)
_register('.kt', _jk)
_register('.kts', _jk)

_register('.go', GoAdapter())
_register('.swift', SwiftAdapter())
_register('.dart', DartAdapter())


def get_adapter(ext: str) -> BaseAdapter | None:
    """Return the adapter for *ext* (e.g. ``'.java'``), or ``None``."""
    return _ADAPTERS.get(ext)


__all__ = ['BaseAdapter', 'get_adapter']
