"""Field / constant scanner — detects unused field declarations.

Complements method scanning so project cleanup can remove orphaned
``static final String`` AB keys and similar fields once no remaining
references exist.
"""

from __future__ import annotations

import os
import re

from ..ast_utils import (
    parse, txt, find_all, find_all_multi, build_line_offsets, byte_to_line,
)
from .. import lang as _lang
from ..adapters import get_adapter

_FIELD_NODE_TYPES = (
    'field_declaration', 'property_declaration', 'const_declaration',
    'variable_declaration', 'lexical_declaration',
)
_FIELD_NODE_SET = frozenset(_FIELD_NODE_TYPES)
_CLASS_NODE_TYPES = (
    'class_declaration', 'class_definition',
    'object_declaration', 'interface_declaration',
    'enum_declaration',
)

_NAME_CHARS = re.compile(r'^[A-Za-z_]\w*$')

_LOMBOK_CONSTRUCTOR_ANNOTATIONS = frozenset({
    'AllArgsConstructor', 'RequiredArgsConstructor',
    'Value', 'Data', 'Builder',
})


def _enclosing_class(node, cb: bytes) -> tuple[str | None, str | None]:
    p = node.parent
    while p:
        if p.type in _CLASS_NODE_TYPES:
            name_node = p.child_by_field_name('name')
            name = txt(name_node, cb) if name_node else None
            if not name:
                for c in p.children:
                    if c.type in ('identifier', 'simple_identifier', 'type_identifier'):
                        name = txt(c, cb)
                        break
            return name, p.type
        p = p.parent
    return None, None


def _modifiers(node, cb: bytes) -> set[str]:
    mods: set[str] = set()
    mod_node = node.child_by_field_name('modifiers')
    if mod_node:
        for c in mod_node.children:
            mods.add(txt(c, cb).strip())
    for c in node.children:
        if c.type in ('modifier', 'visibility_modifier', 'property_modifier',
                       'member_modifier', 'modifiers'):
            if c.type == 'modifiers':
                for mc in c.children:
                    mods.add(txt(mc, cb).strip())
            else:
                mods.add(txt(c, cb).strip())
    return mods


def _has_annotation(node, declaration_start: int | None = None) -> bool:
    """Return whether a field declaration is annotation-managed."""
    stack = list(node.children)
    while stack:
        child = stack.pop()
        if child.type in ('annotation', 'marker_annotation', 'attribute'):
            return True
        if child.type in ('modifiers', 'modifier'):
            stack.extend(child.children)
    if node.parent:
        index = next((i for i, sibling in enumerate(node.parent.children)
                      if sibling.id == node.id), None)
        if index is not None:
            start = node.start_byte if declaration_start is None else declaration_start
            for previous in reversed(node.parent.children[:index]):
                if previous.start_byte >= start:
                    continue
                if previous.type in ('annotation', 'marker_annotation',
                                     'attribute', 'metadata'):
                    return True
                if previous.type in ('comment', 'block_comment', 'line_comment',
                                     'multiline_comment'):
                    continue
                break
    return False


def _class_has_constructor_annotation(node, cb: bytes) -> bool:
    """Return whether the enclosing class/enum has a Lombok annotation
    that generates a constructor from fields (e.g. @AllArgsConstructor,
    @Value, @Data, @Builder).  Fields in such classes are implicitly
    used by the generated constructor and must not be pruned."""
    p = node.parent
    while p:
        if p.type in _CLASS_NODE_TYPES:
            stack = list(p.children)
            while stack:
                child = stack.pop()
                if child.type in ('annotation', 'marker_annotation'):
                    name_node = child.child_by_field_name('name')
                    ann_name = txt(name_node, cb) if name_node else txt(child, cb)
                    bare = ann_name.rsplit('.', 1)[-1].lstrip('@')
                    if bare in _LOMBOK_CONSTRUCTOR_ANNOTATIONS:
                        return True
                if child.type in ('modifiers', 'modifier'):
                    stack.extend(child.children)
            return False
        p = p.parent
    return False


def _leading_doc_start(node, cb: bytes,
                       declaration_start: int | None = None) -> int:
    """Include immediately preceding comments/annotations in the span."""
    start = node.start_byte if declaration_start is None else declaration_start
    if not node.parent:
        return start
    idx = None
    for i, sib in enumerate(node.parent.children):
        if sib.id == node.id:
            idx = i
            break
    if idx is None:
        return start
    for j in range(idx - 1, -1, -1):
        prev = node.parent.children[j]
        if prev.start_byte >= start:
            continue
        if prev.type in ('annotation', 'marker_annotation', 'attribute',
                          'comment', 'block_comment', 'line_comment',
                          'multiline_comment'):
            # A trailing comment belongs to the previous declaration, not
            # the following field.  Binding it here shifts decl_start onto
            # the live previous field and deleting the next unused field
            # removes both (e.g. ``LIVE; // ...`` followed by ``DEAD;``).
            line_start = cb.rfind(b'\n', 0, prev.start_byte) + 1
            if cb[line_start:prev.start_byte].strip():
                break
            start = prev.start_byte
        else:
            break
    return start


def _field_names(node, cb: bytes) -> list[str]:
    """Extract declared field/constant identifier(s) from a declaration node."""
    names: list[str] = []

    # Java field_declaration → variable_declarator(s)
    for decl in find_all(node, 'variable_declarator'):
        name_node = decl.child_by_field_name('name')
        if name_node:
            n = txt(name_node, cb)
            if _NAME_CHARS.match(n):
                names.append(n)
        else:
            for c in decl.children:
                if c.type in ('identifier', 'simple_identifier'):
                    n = txt(c, cb)
                    if _NAME_CHARS.match(n):
                        names.append(n)
                    break

    if names:
        return names

    # Kotlin property / Go const / Swift let
    name_node = node.child_by_field_name('name')
    if name_node:
        n = txt(name_node, cb)
        if _NAME_CHARS.match(n):
            return [n]

    for c in node.children:
        if c.type in ('identifier', 'simple_identifier', 'type_identifier',
                       'property_declaration', 'variable_declarator'):
            if c.type in ('property_declaration', 'variable_declarator'):
                continue
            n = txt(c, cb)
            if n in ('var', 'val', 'let', 'const', 'static', 'final',
                      'private', 'public', 'protected', 'internal',
                      'String', 'Int', 'Boolean', 'Bool', 'boolean',
                      'int', 'long', 'float', 'double'):
                continue
            if _NAME_CHARS.match(n):
                names.append(n)
                break
    return names


def scan_fields(filepath: str, cb: bytes, ext: str,
                *, module: str | None = None,
                root_node=None, line_offsets=None) -> list[dict]:
    """Return field/constant records for *filepath*.

    Each record: name, reference_names, class_name, is_private, is_static,
    is_final, decl_start, decl_end, start_byte, end_byte, filepath, module.

    When *root_node* and *line_offsets* are provided, skip re-parsing
    (used by unified scan to share a single parse per file).
    """
    _lang._current_ext = ext
    if root_node is None:
        root_node, _ = parse(cb)
    if line_offsets is None:
        line_offsets = build_line_offsets(cb)
    fields: list[dict] = []
    source_set = _source_set(filepath)

    adapter = get_adapter(ext)
    field_node_types = adapter.field_node_types if adapter else _FIELD_NODE_SET
    class_node_types = adapter.class_node_types if adapter else frozenset(_CLASS_NODE_TYPES)

    for node in find_all_multi(root_node, field_node_types):
            p = node.parent
            in_method = False
            while p:
                if p.type in ('method_declaration', 'function_declaration',
                               'function_definition', 'method_definition',
                               'constructor_declaration', 'init_declaration',
                               'block', 'function_body', 'compound_statement'):
                    if p.type in ('method_declaration', 'function_declaration',
                                   'function_definition', 'method_definition',
                                   'constructor_declaration', 'init_declaration'):
                        in_method = True
                        break
                if p.type in class_node_types:
                    break
                p = p.parent
            if in_method:
                continue

            mods = _modifiers(node, cb)
            span_start, span_end = (
                adapter.field_declaration_span(node, cb)
                if adapter else (node.start_byte, node.end_byte))
            has_annotation = (_has_annotation(node, span_start)
                              or _class_has_constructor_annotation(node, cb))
            class_name, class_type = _enclosing_class(node, cb)

            adapter_names = adapter.field_names(node, cb) if adapter else None
            traits = adapter.field_traits(node, cb) if adapter else {}
            for name in adapter_names if adapter_names is not None else _field_names(node, cb):
                start = _leading_doc_start(node, cb, span_start)
                fields.append({
                    'name': name,
                    'reference_names': (
                        adapter.field_reference_names(node, cb, name)
                        if adapter else frozenset({name})),
                    'kind': 'field',
                    'class_name': class_name,
                    'class_type': class_type,
                    'is_private': traits.get(
                        'private', 'private' in mods or 'fileprivate' in mods
                        or name.startswith('_') or (ext == '.go' and name[:1].islower())),
                    'is_static': traits.get(
                        'static', 'static' in mods or 'companion' in mods),
                    'is_final': traits.get(
                        'final', bool(mods & {'final', 'const', 'val', 'let'})),
                    'all_mods': mods,
                    'has_annotation': has_annotation,
                    'decl_start': byte_to_line(line_offsets, start),
                    'decl_end': byte_to_line(line_offsets, span_end),
                    'start_byte': start,
                    'end_byte': span_end,
                    'filepath': filepath,
                    'module': module,
                    'source_set': source_set,
                })
    return fields


def _source_set(filepath: str) -> str | None:
    parts = os.path.normpath(filepath).split(os.sep)
    for idx, part in enumerate(parts[:-1]):
        if part == 'src' and idx + 1 < len(parts):
            return parts[idx + 1]
    return None
