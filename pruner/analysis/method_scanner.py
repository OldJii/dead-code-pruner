"""AST-based method scanner — detects dead void/boolean methods.

Uses tree-sitter to parse source files and identify methods whose bodies
are empty (void) or return a boolean constant, making them candidates for
inlining or removal.
"""

from ..ast_utils import parse, txt, find_all, is_bool
from .. import lang as _lang

_METHOD_NODE_TYPES = ('method_declaration', 'function_declaration',
                      'function_definition', 'method_definition')
_CLASS_NODE_TYPES = ('class_declaration', 'class_definition',
                     'object_declaration', 'interface_declaration',
                     'enum_declaration')
_SKIP_NAME_PATTERNS = ('__find_views_',)


# ── AST helpers ─────────────────────────────────────────────

def _find_enclosing_class(node, cb):
    """Walk up the AST to find the enclosing class name and type."""
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
            return name, p.type
        p = p.parent
    return None, None


def _get_package_name(root, cb) -> str | None:
    for node_type in ('package_declaration', 'package_header'):
        nodes = find_all(root, node_type)
        if nodes:
            raw = txt(nodes[0], cb).strip()
            raw = raw.replace('package', '', 1).strip()
            return raw.rstrip(';').strip() or None
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


def _is_return_constant(body_node, cb):
    """``'true'`` / ``'false'`` if body is ``return <bool>``, else ``None``."""
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
    if stmt.type not in ('return_statement', 'jump_expression', 'control_transfer_statement'):
        return None
    ret_children = [c for c in stmt.named_children if c.type not in ('comment', 'return')]
    if len(ret_children) != 1:
        return None
    return is_bool(ret_children[0], cb)


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


def _scan_method_records(filepath: str, cb: bytes, ext: str, *, include_all: bool) -> list[dict]:
    """Scan *filepath* and return method records.

    When include_all is false, only dead-method candidates are returned.
    """
    _lang._current_ext = ext
    root, _ = parse(cb)
    package_name = _get_package_name(root, cb)
    methods: list[dict] = []

    for node_type in _METHOD_NODE_TYPES:
        for node in find_all(root, node_type):
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
            safe_to_inline = is_private or is_static
            class_name, class_type = _find_enclosing_class(node, cb)

            ret_type  = _get_return_type(node, cb)
            const_val = _is_return_constant(body, cb)
            is_void   = _is_empty_void(body, cb)

            kind = value = None
            if const_val is not None and ret_type in ('boolean', 'other'):
                kind  = 'boolean'
                value = const_val
            elif is_void and ret_type in ('void', 'other'):
                kind = 'void'

            if kind is None and not include_all:
                continue

            start_line = cb[:node.start_byte].count(b'\n')
            end_line   = cb[:node.end_byte].count(b'\n')
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
                            anno_start = prev.start_byte
                        else:
                            break
            anno_start_line = cb[:anno_start].count(b'\n')

            methods.append({
                'name': name,
                'kind': kind,
                'value': value,
                'is_dead_candidate': kind is not None and not excluded_by_modifier and not has_annotation,
                'package_name': package_name,
                'class_name': class_name,
                'class_type': class_type,
                'param_count': param_count,
                'safe_to_inline': safe_to_inline,
                'is_private': is_private,
                'is_static': is_static,
                'all_mods': mods,
                'decl_start': anno_start_line,
                'decl_end': end_line,
                'start_byte': anno_start,
                'end_byte': node.end_byte,
                'filepath': filepath,
            })

    return methods


# ── public API ──────────────────────────────────────────────

def scan_method_definitions(filepath: str, cb: bytes, ext: str) -> list[dict]:
    """Scan *filepath* and return all concrete method definitions."""
    return _scan_method_records(filepath, cb, ext, include_all=True)


def scan_methods(filepath: str, cb: bytes, ext: str) -> list[dict]:
    """Scan *filepath* and return a list of dead-method info dicts.

    Each dict contains: name, kind, value, class_name, class_type,
    param_count, safe_to_inline, is_private, is_static, all_mods,
    decl_start, decl_end, start_byte, end_byte, filepath.
    """
    return _scan_method_records(filepath, cb, ext, include_all=False)
