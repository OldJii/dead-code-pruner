"""AST-based method scanner — detects dead void/boolean methods.

Uses tree-sitter to parse source files and identify methods whose bodies
are empty (void) or return a boolean constant, making them candidates for
inlining or removal.  Language adapters are consulted for entry-point
detection and visibility-based safety analysis.
"""

import os

from ..ast_utils import (
    parse, txt, find_all, find_all_multi, is_bool,
    build_line_offsets, byte_to_line,
)
from .. import lang as _lang
from ..adapters import get_adapter

_METHOD_NODE_TYPES = ('method_declaration', 'function_declaration',
                      'function_definition', 'method_definition')
_METHOD_NODE_SET = frozenset(_METHOD_NODE_TYPES)
_CLASS_NODE_TYPES = ('class_declaration', 'class_definition',
                     'object_declaration', 'interface_declaration',
                     'enum_declaration')
_SKIP_NAME_PATTERNS = ('__find_views_',)


# ── AST helpers ─────────────────────────────────────────────

def _find_enclosing_class(node, cb, line_offsets=None):
    """Walk up the AST to find the enclosing class name, type, and line range."""
    p = node.parent
    while p:
        if p.type in _CLASS_NODE_TYPES:
            name_node = p.child_by_field_name('name')
            name = None
            if name_node:
                name = txt(name_node, cb)
            else:
                for c in p.children:
                    if c.type in ('identifier', 'simple_identifier', 'type_identifier'):
                        name = txt(c, cb)
                        break
            if line_offsets is not None:
                cls_start = byte_to_line(line_offsets, p.start_byte)
                cls_end = byte_to_line(line_offsets, p.end_byte)
            else:
                cls_start = cb[:p.start_byte].count(b'\n')
                cls_end = cb[:p.end_byte].count(b'\n')
            return name, p.type, cls_start, cls_end
        p = p.parent
    return None, None, None, None


def _get_package_name(root, cb) -> str | None:
    for node_type in ('package_declaration', 'package_header'):
        nodes = find_all(root, node_type)
        if nodes:
            raw = txt(nodes[0], cb).strip()
            raw = raw.replace('package', '', 1).strip()
            return raw.rstrip(';').strip() or None
    return None


def _get_source_set(filepath: str) -> str | None:
    parts = os.path.normpath(filepath).split(os.sep)
    for idx, part in enumerate(parts[:-1]):
        if part == 'src' and idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _get_modifiers(node, cb) -> set[str]:
    """Extract modifier keywords from a method/function declaration."""
    mods = set()
    mod_node = node.child_by_field_name('modifiers')
    if mod_node:
        for c in mod_node.children:
            mods.add(txt(c, cb).strip())
    for c in node.children:
        t = c.type
        if t in ('modifier', 'visibility_modifier', 'member_modifier',
                 'function_modifier', 'inheritance_modifier', 'access_control'):
            mods.add(txt(c, cb).strip())
        if t == 'modifiers':
            for mc in c.children:
                mods.add(txt(mc, cb).strip())
    return mods


def _has_any_annotation(node, cb) -> bool:
    """Return ``True`` if *node* carries any annotation.

    Annotated methods are treated as potentially framework-managed and
    are excluded from dead-code cleanup.
    """
    def _has_anno(nodes):
        for c in nodes:
            if c.type in ('annotation', 'marker_annotation', 'attribute'):
                return True
            if c.type == 'modifiers':
                if _has_anno(c.children):
                    return True
        return False

    if _has_anno(node.children):
        return True

    if node.parent:
        idx = None
        for i, sib in enumerate(node.parent.children):
            if sib.id == node.id:
                idx = i
                break
        if idx is not None:
            for j in range(idx - 1, -1, -1):
                prev = node.parent.children[j]
                if prev.type in ('annotation', 'marker_annotation', 'attribute'):
                    return True
                elif prev.type == 'modifiers':
                    if _has_anno(prev.children):
                        return True
                else:
                    break
    return False


def _get_method_name(node, cb):
    name_node = node.child_by_field_name('name')
    if name_node:
        return txt(name_node, cb)
    name_node = node.child_by_field_name('declarator')
    if name_node:
        inner = name_node.child_by_field_name('declarator')
        if inner:
            return txt(inner, cb)
        return txt(name_node, cb).split('(')[0].strip()
    for c in node.children:
        if c.type in ('identifier', 'simple_identifier'):
            t = txt(c, cb)
            if t not in ('fun', 'func', 'function', 'def', 'void', 'boolean',
                          'Boolean', 'static', 'private', 'public', 'protected'):
                return t
    return None


def _get_param_count(node, cb) -> int:
    params = node.child_by_field_name('parameters')
    if params:
        return len(params.named_children)
    for c in node.children:
        if c.type in ('formal_parameters', 'function_value_parameters',
                       'parameter_clause', 'parameter_list', 'formal_parameter_list'):
            return len(c.named_children)
    return 0


def _get_body(node, cb):
    body = node.child_by_field_name('body')
    if body:
        return body
    for c in node.children:
        if c.type in ('block', 'function_body', 'compound_statement'):
            return c
    return None


_NULL_TYPES = frozenset({'null_literal', 'nil'})
_INT_TYPES = frozenset({
    'decimal_integer_literal', 'integer_literal', 'int_literal',
    'hex_integer_literal', 'octal_integer_literal', 'binary_integer_literal',
    'number_literal', 'long_literal',
})
_FLOAT_TYPES = frozenset({
    'decimal_floating_point_literal', 'hex_floating_point_literal',
    'real_literal', 'float_literal',
})
_STRING_TYPES = frozenset({
    'string_literal', 'interpreted_string_literal', 'raw_string_literal',
    'character_literal', 'rune_literal',
})
_NUMERIC_TYPES = _INT_TYPES | _FLOAT_TYPES


def _classify_constant_expr(expr, cb) -> tuple[str, str] | None:
    """Classify a single AST expression node as a constant.

    Returns ``(kind, value_text)`` or ``None``.
    """
    bool_val = is_bool(expr, cb)
    if bool_val:
        return ('boolean', bool_val)

    if expr.type in _NULL_TYPES:
        return ('null_return', txt(expr, cb))
    if expr.type in ('identifier', 'simple_identifier'):
        t = cb[expr.start_byte:expr.end_byte]
        if t in (b'null', b'nil'):
            return ('null_return', t.decode())

    if expr.type in _INT_TYPES | _FLOAT_TYPES:
        return ('constant', txt(expr, cb))

    if expr.type in _STRING_TYPES:
        value_text = txt(expr, cb)
        if len(value_text) <= 200:
            return ('constant', value_text)

    if expr.type in ('unary_expression', 'prefix_expression'):
        children = expr.children
        if len(children) == 2:
            op_text = cb[children[0].start_byte:children[0].end_byte]
            if op_text == b'-' and children[1].type in _NUMERIC_TYPES:
                return ('constant', txt(expr, cb))

    return None


def _is_return_constant(body_node, cb) -> tuple[str, str] | None:
    """Detect constant-returning method bodies.

    Returns ``(kind, value)`` where *kind* is ``'boolean'`` or
    ``'constant'``, or ``None`` if the body is not a single-return
    constant.
    """
    stmts = [c for c in body_node.named_children
             if c.type not in ('comment', 'block_comment', 'multiline_comment', 'line_comment')]
    if len(stmts) == 0:
        return None
    if len(stmts) == 1 and stmts[0].type in ('block', 'statements'):
        stmts = [c for c in stmts[0].named_children
                 if c.type not in ('comment', 'block_comment', 'multiline_comment', 'line_comment')]
    if len(stmts) != 1:
        return None
    stmt = stmts[0]
    if stmt.type not in ('return_statement', 'jump_expression',
                          'control_transfer_statement', 'return_expression'):
        return None
    ret_children = [c for c in stmt.named_children if c.type not in ('comment', 'return')]
    if len(ret_children) != 1:
        return None
    return _classify_constant_expr(ret_children[0], cb)


def _is_empty_void(body_node, cb) -> bool:
    """``True`` if the body is empty or contains only ``return;``."""
    stmts = [c for c in body_node.named_children
             if c.type not in ('comment', 'block_comment', 'multiline_comment', 'line_comment')]
    if len(stmts) == 0:
        return True
    if len(stmts) == 1 and stmts[0].type in ('block', 'statements'):
        stmts = [c for c in stmts[0].named_children
                 if c.type not in ('comment', 'block_comment', 'multiline_comment', 'line_comment')]
    if len(stmts) == 0:
        return True
    if len(stmts) == 1:
        stmt = stmts[0]
        if stmt.type in ('return_statement', 'control_transfer_statement') and len(stmt.named_children) == 0:
            return True
        if txt(stmt, cb).strip() in ('return;', 'return'):
            return True
    return False


def _get_return_type(node, cb) -> str:
    """``'void'``, ``'boolean'``, or ``'other'``."""
    type_node = node.child_by_field_name('type')
    if type_node:
        t = txt(type_node, cb).strip()
        if t in ('void', 'Unit'):
            return 'void'
        if t in ('boolean', 'Boolean', 'Bool', 'bool'):
            return 'boolean'
        return 'other'
    for c in node.children:
        if c.type in ('user_type', 'simple_identifier'):
            t = txt(c, cb).strip()
            if t in ('Boolean', 'Bool'):
                return 'boolean'
    rt = node.child_by_field_name('return_type')
    if rt:
        t = txt(rt, cb).strip()
        if t in ('void', 'Unit'):     return 'void'
        if t in ('boolean', 'Boolean', 'Bool', 'bool'): return 'boolean'
    return 'other'


def _scan_method_records(filepath: str, cb: bytes, ext: str, *,
                         include_all: bool, module: str | None = None,
                         root_node=None, line_offsets=None) -> list[dict]:
    """Scan *filepath* and return method records.

    When include_all is false, only dead-method candidates are returned.
    The language adapter for *ext* is consulted for entry-point detection
    and visibility-based safety analysis.

    When *root_node* / *line_offsets* are supplied, the redundant re-parse
    and line-offset rebuild are skipped (used by the unified scan to share
    a single parse per file).
    """
    _lang._current_ext = ext
    if root_node is None:
        root_node, _ = parse(cb)
    if line_offsets is None:
        line_offsets = build_line_offsets(cb)
    package_name = _get_package_name(root_node, cb)
    adapter = get_adapter(ext)
    methods: list[dict] = []
    source_set = _get_source_set(filepath)

    for node in find_all_multi(root_node, _METHOD_NODE_SET):
            mods = _get_modifiers(node, cb)
            excluded_by_modifier = bool(mods & {'abstract', 'open', 'override', 'native'})
            if excluded_by_modifier and not include_all:
                continue
            has_annotation = _has_any_annotation(node, cb)
            if has_annotation and not include_all:
                continue

            name = _get_method_name(node, cb)
            if not name or name in ('if', 'for', 'while', 'switch', 'catch', 'synchronized'):
                continue
            if any(name.startswith(pat) for pat in _SKIP_NAME_PATTERNS):
                continue

            param_count = _get_param_count(node, cb)
            body = _get_body(node, cb)
            if not body:
                continue

            is_private = 'private' in mods
            is_static  = 'static' in mods
            class_name, class_type, cls_start, cls_end = _find_enclosing_class(
                node, cb, line_offsets)

            record_preview = {
                'name': name,
                'is_private': is_private,
                'is_static': is_static,
                'all_mods': mods,
                'class_name': class_name,
                'class_type': class_type,
                'param_count': param_count,
            }
            if adapter:
                safe_to_inline = adapter.compute_safe_to_inline(record_preview)
                is_entry = adapter.is_entry_point(record_preview)
            else:
                safe_to_inline = is_private or is_static
                is_entry = False

            if is_entry and not include_all:
                continue

            ret_type  = _get_return_type(node, cb)
            const_result = _is_return_constant(body, cb)
            is_void   = _is_empty_void(body, cb)

            kind = value = None
            if const_result is not None:
                c_kind, c_value = const_result
                if c_kind == 'boolean' and ret_type in ('boolean', 'other'):
                    kind = 'boolean'
                    value = c_value
                elif c_kind == 'null_return' and ret_type != 'void':
                    kind = 'null_return'
                    value = c_value
                elif c_kind == 'constant' and ret_type != 'void':
                    kind = 'constant'
                    value = c_value
            if kind is None and is_void and ret_type in ('void', 'other'):
                kind = 'void'

            if kind is None and not include_all:
                continue

            start_line = byte_to_line(line_offsets, node.start_byte)
            end_line   = byte_to_line(line_offsets, node.end_byte)
            anno_start = node.start_byte
            if node.parent:
                idx = None
                for i, sib in enumerate(node.parent.children):
                    if sib.id == node.id:
                        idx = i
                        break
                if idx is not None:
                    for j in range(idx - 1, -1, -1):
                        prev = node.parent.children[j]
                        if prev.type in ('annotation', 'marker_annotation', 'attribute',
                                          'comment', 'block_comment', 'line_comment',
                                          'multiline_comment'):
                            line_start = cb.rfind(b'\n', 0, prev.start_byte) + 1
                            if cb[line_start:prev.start_byte].strip():
                                # Trailing comments belong to the preceding
                                # declaration and must never extend this
                                # method's deletion range backwards.
                                break
                            anno_start = prev.start_byte
                        else:
                            break
            anno_start_line = byte_to_line(line_offsets, anno_start)

            methods.append({
                'name': name,
                'kind': kind,
                'value': value,
                'is_dead_candidate': kind is not None and not excluded_by_modifier
                                     and not has_annotation and not is_entry,
                'package_name': package_name,
                'module': module,
                'source_set': source_set,
                'class_name': class_name,
                'class_type': class_type,
                'class_start': cls_start,
                'class_end': cls_end,
                'param_count': param_count,
                'safe_to_inline': safe_to_inline,
                'is_private': is_private,
                'is_static': is_static,
                'all_mods': mods,
                'has_annotation': has_annotation,
                'decl_start': anno_start_line,
                'decl_end': end_line,
                'start_byte': anno_start,
                'end_byte': node.end_byte,
                'filepath': filepath,
            })

    return methods


# ── public API ──────────────────────────────────────────────

def scan_method_definitions(filepath: str, cb: bytes, ext: str,
                            *, module: str | None = None,
                            root_node=None, line_offsets=None) -> list[dict]:
    """Scan *filepath* and return all concrete method definitions."""
    return _scan_method_records(filepath, cb, ext, include_all=True, module=module,
                                root_node=root_node, line_offsets=line_offsets)


def scan_methods(filepath: str, cb: bytes, ext: str,
                 *, module: str | None = None,
                 root_node=None, line_offsets=None) -> list[dict]:
    """Scan *filepath* and return a list of dead-method info dicts.

    Each dict contains: name, kind, value, class_name, class_type,
    param_count, safe_to_inline, is_private, is_static, all_mods,
    decl_start, decl_end, start_byte, end_byte, filepath, module.
    """
    return _scan_method_records(filepath, cb, ext, include_all=False, module=module,
                                root_node=root_node, line_offsets=line_offsets)
