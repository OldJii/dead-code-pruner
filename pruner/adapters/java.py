"""Java and Android-specific syntax, contracts, and safety rules."""

from __future__ import annotations

import re

from .base import BaseAdapter
from .contract_utils import declared_bodies, split_type_list
from .jvm_common import JVM_PROTECTED_NAMES
from ..ast_utils import find_all, txt

_LOCAL_BOOL = re.compile(
    rb'\b(?:final\s+)?(?:boolean|Boolean)\s+(\w{3,})\s*=\s*(true|false)\s*;')
_TYPE_DECL = re.compile(
    r'\b(?:(final|abstract)\s+)?(class|interface)\s+(\w+)'
    r'([^\{]*)\{')
_CONTRACT_BODY = re.compile(
    r'\b(?:interface|abstract\s+class)\s+(\w+)\b[^\{]*\{')
_METHOD = re.compile(
    r'(?m)^\s*(?:public\s+|protected\s+|private\s+|abstract\s+|'
    r'default\s+|static\s+)*(?:[\w.<>,\[\]?]+\s+)(\w+)\s*\([^;{]*\)\s*;')

_LOMBOK_CONSTRUCTOR_ALL = frozenset({
    'AllArgsConstructor', 'Builder', 'Value',
})
_LOMBOK_CONSTRUCTOR_REQUIRED = frozenset({
    'RequiredArgsConstructor',
})
_LOMBOK_ACCESSOR_TYPES = frozenset({
    'Data', 'Value', 'Getter', 'Setter',
})
_LOMBOK_IMPLICIT_VALUE_TYPES = frozenset({
    'Data', 'Value', 'ToString', 'EqualsAndHashCode',
})
_RUNTIME_BOUND_TYPE_ANNOTATIONS = frozenset({
    # Jackson / Gson-style runtime property discovery.
    'JsonAutoDetect', 'JsonDeserialize', 'JsonIgnoreProperties',
    'JsonInclude', 'JsonSerialize', 'JsonSubTypes', 'JsonTypeInfo',
    'JsonTypeName',
    # Spring configuration binding and common ORM entity markers.
    'ConfigurationProperties', 'Document', 'Embeddable', 'Entity',
    'MappedSuperclass', 'TableName',
})


def _enclosing_type(node):
    current = node.parent
    while current:
        if current.type in {
                'class_declaration', 'interface_declaration',
                'enum_declaration', 'annotation_type_declaration'}:
            return current
        current = current.parent
    return None


def _annotation_names(node, content: bytes) -> frozenset[str]:
    if node is None:
        return frozenset()
    names: set[str] = set()
    stack = list(node.children)
    while stack:
        child = stack.pop()
        if child.type in ('annotation', 'marker_annotation'):
            name_node = child.child_by_field_name('name')
            raw = txt(name_node, content) if name_node else txt(child, content)
            names.add(raw.rsplit('.', 1)[-1].lstrip('@'))
            continue
        if child.type in ('modifiers', 'modifier'):
            stack.extend(child.children)
    return frozenset(names)


def _field_declarator(declaration, content: bytes, name: str):
    for declarator in find_all(declaration, 'variable_declarator'):
        name_node = declarator.child_by_field_name('name')
        if name_node is not None and txt(name_node, content) == name:
            return declarator
    return None


def _field_is_static(declaration, content: bytes) -> bool:
    modifiers = declaration.child_by_field_name('modifiers')
    raw = txt(modifiers, content) if modifiers is not None else txt(declaration, content)
    return bool(re.search(r'\bstatic\b', raw))


def _field_is_final(declaration, content: bytes) -> bool:
    modifiers = declaration.child_by_field_name('modifiers')
    raw = txt(modifiers, content) if modifiers is not None else txt(declaration, content)
    return bool(re.search(r'\bfinal\b', raw))


def _field_has_initializer(declaration, content: bytes, name: str) -> bool:
    declarator = _field_declarator(declaration, content, name)
    return bool(declarator and declarator.child_by_field_name('value'))


def _type_header(type_node, content: bytes) -> str:
    for child in type_node.children:
        if child.type in ('class_body', 'enum_body', 'interface_body',
                          'annotation_type_body'):
            return content[type_node.start_byte:child.start_byte].decode(
                'utf-8', errors='replace')
    return txt(type_node, content)


def _java_bean_names(name: str) -> frozenset[str]:
    if not name:
        return frozenset()
    cap = name[0].upper() + name[1:]
    # Include both boolean and ordinary getter forms.  Without type solving,
    # retaining one extra possible accessor is safer than missing Lombok's
    # generated API (which also varies with @Accessors configuration).
    return frozenset({name, 'get' + cap, 'is' + cap, 'set' + cap})


class JavaAdapter(BaseAdapter):
    @property
    def protected_names(self) -> frozenset[str]:
        return JVM_PROTECTED_NAMES

    @property
    def local_boolean_patterns(self):
        return (_LOCAL_BOOL,)

    def field_reference_names(self, declaration, content: bytes,
                              name: str) -> frozenset[str]:
        if _field_is_static(declaration, content):
            return frozenset({name})
        type_node = _enclosing_type(declaration)
        annotations = (_annotation_names(type_node, content)
                       | _annotation_names(declaration, content))
        if annotations & _LOMBOK_ACCESSOR_TYPES:
            return _java_bean_names(name)
        return frozenset({name})

    def field_is_implicitly_referenced(self, declaration, content: bytes,
                                       name: str) -> bool:
        if _field_is_static(declaration, content):
            return False
        type_node = _enclosing_type(declaration)
        if type_node is None:
            return False
        type_annotations = _annotation_names(type_node, content)
        field_annotations = _annotation_names(declaration, content)

        # These annotations generate methods whose observable value includes
        # instance fields even when no source-level field access exists.
        if type_annotations & _LOMBOK_IMPLICIT_VALUE_TYPES:
            return True
        # All-argument constructors and type-level builders consume every
        # instance field.  Removing one without rewriting constructor/builder
        # contracts changes arity and can make enum constants uncompilable.
        if type_annotations & _LOMBOK_CONSTRUCTOR_ALL:
            return True
        # Required-argument constructors consume only uninitialized final or
        # @NonNull fields.  Keep that distinction instead of blanket-skipping
        # every field in the class.
        if type_annotations & _LOMBOK_CONSTRUCTOR_REQUIRED:
            if (_field_is_final(declaration, content)
                    and not _field_has_initializer(declaration, content, name)):
                return True
            if ('NonNull' in field_annotations
                    and not _field_has_initializer(declaration, content, name)):
                return True

        header = _type_header(type_node, content)
        if re.search(r'\bimplements\b[^\{;]*\b(?:java\.io\.)?Serializable\b',
                     header):
            return True
        if type_annotations & _RUNTIME_BOUND_TYPE_ANNOTATIONS:
            return True
        return False

    def field_exposes_generated_api(self, declaration, content: bytes,
                                    name: str) -> bool:
        if _field_is_static(declaration, content):
            return False
        type_node = _enclosing_type(declaration)
        annotations = (_annotation_names(type_node, content)
                       | _annotation_names(declaration, content))
        return bool(annotations & _LOMBOK_ACCESSOR_TYPES)

    def field_initializer_has_effects(self, declaration, content: bytes,
                                      name: str) -> bool:
        declarator = _field_declarator(declaration, content, name)
        value = (declarator.child_by_field_name('value')
                 if declarator is not None else None)
        if value is None:
            return False
        stack = [value]
        while stack:
            current = stack.pop()
            if current.type in {
                    'method_invocation', 'object_creation_expression',
                    'assignment_expression', 'update_expression',
                    'lambda_expression'}:
                return True
            stack.extend(current.named_children)
        return False

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
            if kind == 'interface' or modifier == 'abstract':
                facts['contracts'].add(name)
            parents: list[str] = []
            ext = re.search(r'\bextends\s+([\w.]+)', tail)
            if ext:
                parents.append(ext.group(1).rsplit('.', 1)[-1])
            impl = re.search(r'\bimplements\s+(.+)', tail, re.S)
            if impl:
                parents.extend(split_type_list(impl.group(1)))
            if parents:
                facts['relations'][name] = set(parents)
        for name, body in declared_bodies(content, _CONTRACT_BODY):
            facts['methods'][name] = {m.group(1) for m in _METHOD.finditer(body)}
        return facts
