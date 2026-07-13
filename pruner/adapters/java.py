"""Java and Android-specific syntax, contracts, and safety rules."""

from __future__ import annotations

import re

from .base import BaseAdapter
from .contract_utils import declared_bodies, split_type_list
from .jvm_common import JVM_PROTECTED_NAMES

_LOCAL_BOOL = re.compile(
    rb'\bfinal\s+(?:boolean|Boolean)\s+(\w{3,})\s*=\s*(true|false)\s*;')
_TYPE_DECL = re.compile(
    r'\b(?:(final|abstract)\s+)?(class|interface)\s+(\w+)'
    r'([^\{]*)\{')
_CONTRACT_BODY = re.compile(
    r'\b(?:interface|abstract\s+class)\s+(\w+)\b[^\{]*\{')
_METHOD = re.compile(
    r'(?m)^\s*(?:public\s+|protected\s+|private\s+|abstract\s+|'
    r'default\s+|static\s+)*(?:[\w.<>,\[\]?]+\s+)(\w+)\s*\([^;{]*\)\s*;')


class JavaAdapter(BaseAdapter):
    @property
    def protected_names(self) -> frozenset[str]:
        return JVM_PROTECTED_NAMES

    @property
    def local_boolean_patterns(self):
        return (_LOCAL_BOOL,)

    def is_entry_point(self, record: dict) -> bool:
        name = record.get('name', '')
        mods = record.get('all_mods', set())
        return (name in self.protected_names
                or (name == 'main' and 'static' in mods)
                or 'override' in mods or 'Override' in mods)

    def can_prune_unreferenced_nonconstant(self, record: dict) -> bool:
        """Java static calls and method references are explicitly indexable."""
        return bool(record.get('is_static'))

    def contract_facts(self, content: str) -> dict:
        facts = super().contract_facts(content)
        for match in _TYPE_DECL.finditer(content):
            modifier, kind, name, tail = match.groups()
            if modifier == 'final':
                facts['final'].add(name)
            if kind == 'interface' or modifier == 'abstract':
                facts['contracts'].add(name)
            parents: list[str] = []
            ext = re.search(r'\bextends\s+([\w.]+)', tail)
            if ext:
                parents.append(ext.group(1).rsplit('.', 1)[-1])
            impl = re.search(r'\bimplements\s+(.+)', tail, re.S)
            if impl:
                parents.extend(split_type_list(impl.group(1)))
                facts['implementors'].add(name)
            if parents:
                facts['relations'][name] = set(parents)
        for name, body in declared_bodies(content, _CONTRACT_BODY):
            facts['methods'][name] = {m.group(1) for m in _METHOD.finditer(body)}
        return facts
