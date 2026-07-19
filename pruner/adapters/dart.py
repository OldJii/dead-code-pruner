"""Dart / Flutter language adapter.

Dart uses a leading underscore for library-private visibility.  Flutter
widgets have a well-defined lifecycle (``build``, ``initState``,
``dispose``, …) that must be preserved.
"""

from __future__ import annotations

import os
import re

from .base import BaseAdapter
from .callable_refs import CALLABLE_VALUE_PATTERNS
from .contract_utils import declared_bodies, split_type_list

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

_LOCAL_BOOL = re.compile(
    rb'\b(?:final|const)\s+(?:bool\s+)?(\w{3,})\s*=\s*(true|false)\s*;')
_TYPE_DECL = re.compile(
    r'\b(?:(abstract|final|sealed|base)\s+)?class\s+(\w+)\s*([^\{]*)\{')
_ABSTRACT_BODY = re.compile(r'\babstract\s+class\s+(\w+)\b[^\{]*\{')
_ABSTRACT_METHOD = re.compile(
    r'(?m)^\s*(?:[\w<>?,\[\]]+\s+)(\w+)\s*\([^;{]*\)\s*;')
_GENERIC_CALL = re.compile(
    r'\b([A-Za-z_]\w*)\s*<[^>\n]+>\s*\(')


_GENERATED_SUFFIXES = ('.g.dart', '.freezed.dart', '.gen.dart', '.mapper.dart')

_GENERATED_HEADER = b'GENERATED CODE'


class DartAdapter(BaseAdapter):

    def is_generated_source(self, filepath: str) -> bool:
        basename = os.path.basename(filepath)
        if any(basename.endswith(s) for s in _GENERATED_SUFFIXES):
            return True
        try:
            with open(filepath, 'rb') as f:
                header = f.read(256)
            return _GENERATED_HEADER in header
        except Exception:
            return False

    @property
    def protected_names(self) -> frozenset[str]:
        return _PROTECTED_NAMES

    @property
    def method_node_types(self) -> frozenset[str]:
        return frozenset({'method_signature', 'function_signature'})

    @property
    def field_node_types(self) -> frozenset[str]:
        # The Dart grammar represents class fields and top-level constants
        # differently; local declarations are filtered by field_scanner's
        # enclosing-function check.
        return frozenset({
            'declaration', 'field_declaration', 'local_variable_declaration',
            'static_final_declaration_list',
        })

    def field_names(self, declaration, content: bytes) -> list[str] | None:
        if (declaration.type == 'static_final_declaration_list'
                and declaration.parent is not None
                and declaration.parent.type != 'program'):
            # Class constants use their outer declaration so the deletion span
            # includes modifiers and types.  Top-level constants have no outer
            # declaration node and are represented by this list directly.
            return []
        names: list[str] = []
        stack = list(declaration.named_children)
        while stack:
            node = stack.pop()
            if node.type in ('initialized_identifier', 'static_final_declaration',
                             'variable_declarator'):
                identifier = next((c for c in node.named_children
                                   if c.type == 'identifier'), None)
                if identifier is not None:
                    names.append(content[identifier.start_byte:identifier.end_byte].decode())
                continue
            stack.extend(node.named_children)
        return names

    def field_traits(self, declaration, content: bytes) -> dict:
        if declaration.type == 'static_final_declaration_list':
            return {'final': True, 'static': True}
        raw = content[declaration.start_byte:declaration.end_byte]
        return {'final': b'const ' in raw or b'final ' in raw,
                'static': b'static ' in raw}

    def field_declaration_span(self, declaration, content: bytes) -> tuple[int, int]:
        if (declaration.type != 'static_final_declaration_list'
                or declaration.parent is None
                or declaration.parent.type != 'program'):
            return super().field_declaration_span(declaration, content)
        siblings = declaration.parent.children
        index = next((i for i, node in enumerate(siblings)
                      if node.id == declaration.id), None)
        if index is None:
            return declaration.start_byte, declaration.end_byte
        start = declaration.start_byte
        end = declaration.end_byte
        for previous in reversed(siblings[:index]):
            if previous.type in ('const_builtin', 'final_builtin',
                                 'type_identifier'):
                start = previous.start_byte
                continue
            break
        for following in siblings[index + 1:]:
            if following.type == ';':
                end = following.end_byte
            break
        return start, end

    @property
    def local_boolean_patterns(self):
        return (_LOCAL_BOOL,)

    @property
    def implicit_reference_patterns(self):
        return CALLABLE_VALUE_PATTERNS + (_GENERIC_CALL,)

    def parameter_count(self, declaration, content: bytes) -> int | None:
        signature = declaration
        if declaration.type == 'method_signature' and declaration.named_children:
            signature = declaration.named_children[0]
        params = next((c for c in signature.named_children
                       if c.type == 'formal_parameter_list'), None)
        if params is None:
            return None

        def count(node) -> int:
            if node.type in ('formal_parameter', 'default_formal_parameter'):
                return 1
            return sum(count(child) for child in node.named_children)

        return count(params)

    def accepts_method_node(self, declaration) -> bool:
        return not (declaration.type == 'function_signature'
                    and declaration.parent is not None
                    and declaration.parent.type == 'method_signature')

    def method_name(self, declaration, content: bytes) -> str | None:
        signature = declaration
        if declaration.type == 'method_signature' and declaration.named_children:
            signature = declaration.named_children[0]
        name = signature.child_by_field_name('name')
        if name is None:
            return None
        return content[name.start_byte:name.end_byte].decode('utf-8', errors='ignore')

    def method_body(self, declaration):
        owner = declaration
        if declaration.type == 'function_signature' and declaration.parent is not None:
            owner = declaration
        parent = owner.parent
        if parent is None:
            return None
        siblings = parent.named_children
        for index, sibling in enumerate(siblings):
            if sibling.id == owner.id and index + 1 < len(siblings):
                candidate = siblings[index + 1]
                if candidate.type == 'function_body':
                    return candidate
                break
        return None

    def declaration_end_byte(self, declaration, body) -> int:
        return body.end_byte if body is not None else declaration.end_byte

    def return_type_text(self, declaration, content: bytes) -> str | None:
        signature = declaration
        if declaration.type == 'method_signature' and declaration.named_children:
            signature = declaration.named_children[0]
        if not signature.named_children:
            return None
        first = signature.named_children[0]
        if first.type in ('void_type', 'type_identifier', 'nullable_type'):
            return content[first.start_byte:first.end_byte].decode(
                'utf-8', errors='ignore')
        return None

    def is_entry_point(self, record: dict) -> bool:
        name = record.get('name', '')
        if name in self.protected_names:
            return True
        mods = record.get('all_mods', set())
        if 'override' in mods:
            return True
        return False

    def can_prune_unreferenced_nonconstant(self, record: dict) -> bool:
        """Private (underscore-prefixed) Dart declarations are safely removable
        when provably unreferenced, since Dart's leading-underscore privacy is
        scoped to the library."""
        name = record.get('name', '')
        return name.startswith('_')

    def compute_safe_to_inline(self, record: dict) -> bool:
        if self.is_entry_point(record):
            return False
        name = record.get('name', '')
        if name.startswith('_'):
            return True
        mods = record.get('all_mods', set())
        return 'static' in mods

    def is_language_private(self, record: dict) -> bool:
        return record.get('name', '').startswith('_')

    def contract_facts(self, content: str) -> dict:
        facts = super().contract_facts(content)
        for match in _TYPE_DECL.finditer(content):
            modifier, name, tail = match.groups()
            if modifier == 'abstract':
                facts['contracts'].add(name)
            parents: list[str] = []
            for keyword in ('extends', 'implements', 'with'):
                rel = re.search(
                    rf'\b{keyword}\s+(.+?)(?=\bextends\b|\bimplements\b|\bwith\b|$)',
                    tail)
                if rel:
                    parents.extend(split_type_list(rel.group(1)))
            if parents:
                facts['relations'][name] = set(parents)
        for name, body in declared_bodies(content, _ABSTRACT_BODY):
            facts['methods'][name] = {
                m.group(1) for m in _ABSTRACT_METHOD.finditer(body)
            }
        return facts
