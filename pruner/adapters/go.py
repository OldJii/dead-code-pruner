"""Go language adapter.

Go visibility is determined by capitalisation: exported (uppercase first
letter) symbols form the public API and must be preserved in library
packages.  ``main``, ``init``, ``Test*``, ``Benchmark*``, and ``Example*``
are runtime/testing entry points.
"""

from __future__ import annotations

import re

from .base import BaseAdapter
from .callable_refs import CALLABLE_VALUE_PATTERNS
from .contract_utils import declared_bodies

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

_TEST_PREFIXES = ('Test', 'Benchmark', 'Example', 'Fuzz')
_LOCAL_BOOL = re.compile(
    rb'\bconst\s+(\w{3,})\s*(?:bool\s*)?=\s*(true|false)\b')
_INTERFACE_BODY = re.compile(r'\btype\s+(\w+)\s+interface\s*\{')
_INTERFACE_METHOD = re.compile(r'(?m)^\s*(\w+)\s*\(')
_RECEIVER_METHOD = re.compile(
    r'\bfunc\s*\(\s*\w*\s*\*?\s*(\w+)\s*\)\s*(\w+)\s*\(')
_GENERIC_CALL = re.compile(
    r'\b([A-Za-z_]\w*)\s*\[[^\]\n]+\]\s*\(')
_METHOD_VALUE = re.compile(
    r'\.\s*([A-Za-z_]\w*)\b(?!\s*\()')


class GoAdapter(BaseAdapter):

    @property
    def uses_structural_contracts(self) -> bool:
        return True

    @property
    def protected_names(self) -> frozenset[str]:
        return _PROTECTED_NAMES

    @property
    def local_boolean_patterns(self):
        return (_LOCAL_BOOL,)

    @property
    def implicit_reference_patterns(self):
        return CALLABLE_VALUE_PATTERNS + (_GENERIC_CALL, _METHOD_VALUE)

    @property
    def field_node_types(self) -> frozenset[str]:
        return frozenset({'const_declaration'})

    def field_names(self, declaration, content: bytes) -> list[str] | None:
        names: list[str] = []
        for spec in declaration.named_children:
            if spec.type != 'const_spec':
                continue
            for child in spec.named_children:
                if child.type == 'identifier':
                    names.append(content[child.start_byte:child.end_byte].decode())
                else:
                    break
        return names

    def field_traits(self, declaration, content: bytes) -> dict:
        return {'final': True, 'static': True}

    def parameter_count(self, declaration, content: bytes) -> int | None:
        params = declaration.child_by_field_name('parameters')
        if params is None:
            return None
        count = 0
        for param in params.named_children:
            if param.type not in ('parameter_declaration', 'variadic_parameter_declaration'):
                continue
            names = [c for c in param.named_children if c.type == 'identifier']
            count += len(names) or 1
        return count

    def declaring_type(self, declaration, content: bytes) -> str | None:
        receiver = declaration.child_by_field_name('receiver')
        if receiver is None:
            return None
        for child in receiver.named_children:
            type_node = child.child_by_field_name('type')
            if type_node is not None:
                raw = content[type_node.start_byte:type_node.end_byte].decode(
                    'utf-8', errors='ignore')
                return raw.strip().lstrip('*').rsplit('.', 1)[-1]
        return None

    def is_entry_point(self, record: dict) -> bool:
        name = record.get('name', '')
        if name in self.protected_names:
            return True
        if any(name.startswith(p) for p in _TEST_PREFIXES):
            return True
        return False

    def compute_safe_to_inline(self, record: dict) -> bool:
        if self.is_entry_point(record):
            return False
        name = record.get('name', '')
        if name and name[0].islower():
            return True
        return False

    def is_language_private(self, record: dict) -> bool:
        name = record.get('name', '')
        return bool(name and name[0].islower())

    def can_prune_unreferenced_nonconstant(self, record: dict) -> bool:
        """Allow provably unused unexported functions and receiver methods.

        Exported receiver methods may satisfy dependency or standard-library
        interfaces without an in-project declaration, so deleting them from
        syntax alone is unsound.
        """
        name = record.get('name', '')
        return bool(name and name[0].islower())

    def contract_facts(self, content: str) -> dict:
        facts = super().contract_facts(content)
        iface_methods: dict[str, set[str]] = {}
        for name, body in declared_bodies(content, _INTERFACE_BODY):
            methods = {m.group(1) for m in _INTERFACE_METHOD.finditer(body)}
            facts['contracts'].add(name)
            facts['methods'][name] = methods
            iface_methods[name] = methods

        receiver_methods: dict[str, set[str]] = {}
        for receiver, method in _RECEIVER_METHOD.findall(content):
            receiver_methods.setdefault(receiver, set()).add(method)
        for receiver, methods in receiver_methods.items():
            for iface, required in iface_methods.items():
                if required and required <= methods:
                    facts['relations'].setdefault(receiver, set()).add(iface)

        return facts
