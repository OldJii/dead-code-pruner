"""Kotlin-specific syntax, contracts, and Android/JVM safety rules."""

from __future__ import annotations

import re

from .base import BaseAdapter
from .contract_utils import declared_bodies, split_type_list
from .jvm_common import JVM_PROTECTED_NAMES

_LOCAL_BOOL = re.compile(
    rb'\bval\s+(\w{3,})\s*(?::\s*(?:Boolean|Bool)\s*)?=\s*(true|false)\b')
_TYPE_DECL = re.compile(
    r'\b(?:(final|abstract)\s+)?(class|interface|object)\s+(\w+)'
    r'\s*([^\{]*)\{')
_INTERFACE_BODY = re.compile(r'\binterface\s+(\w+)\b[^\{]*\{')
_ABSTRACT_BODY = re.compile(r'\babstract\s+class\s+(\w+)\b[^\{]*\{')
_METHOD = re.compile(r'(?m)^\s*(?:[\w@]+\s+)*fun\s+(\w+)\s*\([^)]*\)')
_ABSTRACT_METHOD = re.compile(
    r'(?m)^\s*(?:public\s+|protected\s+|internal\s+)*abstract\s+fun\s+'
    r'(\w+)\s*\(')
_TRAILING_LAMBDA_CALL = re.compile(r'(?<!\w)([A-Za-z_]\w*)\s*\{')
_INFIX_CALL = re.compile(
    r'''(?x)
    [A-Za-z0-9_\)\]\}"']
    \s+([A-Za-z_]\w*)\s+
    (?=[A-Za-z0-9_\(\[\{"'!+\-])
    ''')


class KotlinAdapter(BaseAdapter):
    @property
    def protected_names(self) -> frozenset[str]:
        return JVM_PROTECTED_NAMES

    @property
    def preserve_branch_scope(self) -> bool:
        return False

    @property
    def local_boolean_patterns(self):
        return (_LOCAL_BOOL,)

    def local_boolean_is_propagatable(
            self, root, content: bytes, name: bytes, declaration_start: int,
            declaration_end: int, scope_end: int) -> bool:
        """Only propagate Kotlin val booleans declared inside a function body."""
        current = root.descendant_for_byte_range(
            declaration_start, declaration_end)
        while current is not None:
            if current.type == 'property_declaration':
                break
            if current.type in (
                    'function_declaration', 'function_definition',
                    'secondary_constructor', 'init'):
                return True
            current = current.parent
        return False

    @property
    def implicit_call_patterns(self):
        # Kotlin calls may omit parentheses for a trailing lambda or for an
        # infix function: ``schedule { ... }`` / ``value withWeight 10``.
        # Neither shape is visible to the shared ``name(...)`` index.
        return (_TRAILING_LAMBDA_CALL, _INFIX_CALL)

    @property
    def field_node_types(self) -> frozenset[str]:
        return frozenset({'property_declaration'})

    def field_names(self, declaration, content: bytes) -> list[str] | None:
        for child in declaration.named_children:
            if child.type == 'variable_declaration':
                for item in child.named_children:
                    if item.type == 'identifier':
                        return [content[item.start_byte:item.end_byte].decode()]
        return []

    def field_traits(self, declaration, content: bytes) -> dict:
        raw = content[declaration.start_byte:declaration.end_byte].lstrip()
        return {'final': bool(re.search(rb'\b(?:const\s+)?val\b', raw))}

    def field_reference_names(self, declaration, content: bytes,
                              name: str) -> frozenset[str]:
        """Include JVM accessors generated for Kotlin properties.

        Java calls a regular Kotlin ``val property`` through ``getProperty()``
        (or ``isReady()`` for boolean-style names).  Delegated and extension
        properties use the same accessor naming.  ``const`` and ``@JvmField``
        declarations expose a field directly and therefore have no generated
        accessor to index.
        """
        raw = content[declaration.start_byte:declaration.end_byte]
        names = {name}
        if re.search(rb'\bconst\s+val\b', raw) or b'@JvmField' in raw:
            return frozenset(names)

        capitalized = name[:1].upper() + name[1:]
        names.add('get' + capitalized)
        if re.match(r'is[A-Z]', name):
            names.add(name)
        if re.search(rb'\bvar\b', raw):
            setter_suffix = name[2:] if re.match(r'is[A-Z]', name) else capitalized
            names.add('set' + setter_suffix)
        return frozenset(names)

    def phase1_step5_simplify_language_expressions(
            self, content: bytes) -> bytes:
        from ..steps.kotlin_expr import phase1_step5_simplify_kotlin_expressions
        return phase1_step5_simplify_kotlin_expressions(content)

    def parameter_count(self, declaration, content: bytes) -> int | None:
        for child in declaration.children:
            if child.type == 'function_value_parameters':
                return sum(c.type == 'parameter' for c in child.named_children)
        return None

    def is_entry_point(self, record: dict) -> bool:
        name = record.get('name', '')
        mods = record.get('all_mods', set())
        return name in self.protected_names or name == 'main' or 'override' in mods

    def can_prune_unreferenced_nonconstant(self, record: dict) -> bool:
        """Private Kotlin declarations are safely removable when unreferenced."""
        return 'private' in (record.get('all_mods', set()) or set())

    def contract_facts(self, content: str) -> dict:
        facts = super().contract_facts(content)
        for match in _TYPE_DECL.finditer(content):
            modifier, kind, name, tail = match.groups()
            if kind == 'interface' or modifier == 'abstract':
                facts['contracts'].add(name)
            tail = tail.strip()
            if tail.startswith(':'):
                parents = split_type_list(tail[1:])
                if parents:
                    facts['relations'][name] = set(parents)
        for name, body in declared_bodies(content, _INTERFACE_BODY):
            facts['methods'][name] = {m.group(1) for m in _METHOD.finditer(body)}
        for name, body in declared_bodies(content, _ABSTRACT_BODY):
            facts['methods'][name] = {
                m.group(1) for m in _ABSTRACT_METHOD.finditer(body)
            }
        return facts
