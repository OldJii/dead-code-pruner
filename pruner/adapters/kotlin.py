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

    @property
    def implicit_call_patterns(self):
        # Kotlin permits a sole function argument outside parentheses:
        # ``scheduleBeforeWork { ... }``.  The shared ``name(...)`` index cannot
        # see this form, so it belongs to the Kotlin adapter.
        return (_TRAILING_LAMBDA_CALL,)

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

    def simplify_language_expressions(self, content: bytes) -> bytes:
        from ..steps.kotlin_expr import kotlin_if_expr
        return kotlin_if_expr(content)

    def parameter_count(self, declaration, content: bytes) -> int | None:
        for child in declaration.children:
            if child.type == 'function_value_parameters':
                return sum(c.type == 'parameter' for c in child.named_children)
        return None

    def is_entry_point(self, record: dict) -> bool:
        name = record.get('name', '')
        mods = record.get('all_mods', set())
        return name in self.protected_names or name == 'main' or 'override' in mods

    def contract_facts(self, content: str) -> dict:
        facts = super().contract_facts(content)
        for match in _TYPE_DECL.finditer(content):
            modifier, kind, name, tail = match.groups()
            if modifier == 'final':
                facts['final'].add(name)
            if kind == 'interface' or modifier == 'abstract':
                facts['contracts'].add(name)
            tail = tail.strip()
            if tail.startswith(':'):
                parents = split_type_list(tail[1:])
                if parents:
                    facts['relations'][name] = set(parents)
                    if kind != 'interface':
                        facts['implementors'].add(name)
        for name, body in declared_bodies(content, _INTERFACE_BODY):
            facts['methods'][name] = {m.group(1) for m in _METHOD.finditer(body)}
        for name, body in declared_bodies(content, _ABSTRACT_BODY):
            facts['methods'][name] = {
                m.group(1) for m in _ABSTRACT_METHOD.finditer(body)
            }
        return facts
