"""Core AST utility functions shared across all transformation steps.

All operations are byte-offset based to match tree-sitter's byte positions.
"""

from . import lang as _lang


def parse(code_bytes: bytes):
    """Parse *code_bytes* with the parser for the active language extension."""
    p = _lang._PARSERS.get(_lang._current_ext, _lang._PARSERS.get('.java'))
    return p.parse(code_bytes).root_node, code_bytes


def txt(node, cb: bytes) -> str:
    """Extract the UTF-8 text of *node* from *cb*."""
    return cb[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def find_all(node, type_name: str) -> list:
    """Non-recursive DFS collecting all descendants with *type_name*."""
    results = []
    stack = [node]
    while stack:
        cur = stack.pop()
        if cur.type == type_name:
            results.append(cur)
        stack.extend(reversed(cur.children))
    return results


def bstr(s) -> bytes:
    """Ensure *s* is ``bytes``."""
    return s.encode('utf-8') if isinstance(s, str) else s


def replace_node(cb: bytes, node, rep_str) -> bytes:
    """Replace *node*'s byte range in *cb* with *rep_str*."""
    return cb[:node.start_byte] + bstr(rep_str) + cb[node.end_byte:]


def replace_range(cb: bytes, start: int, end: int, rep_str) -> bytes:
    return cb[:start] + bstr(rep_str) + cb[end:]


def is_bool(node, cb: bytes) -> str | None:
    """Return ``'true'``/``'false'`` if *node* is a boolean literal, else ``None``.

    Handles Java (true/false node types), Kotlin (identifier),
    Swift (boolean_literal), and C# (true/false keywords).
    """
    if node.type in ('true', 'false'):
        return node.type
    if node.type in ('identifier', 'boolean_literal'):
        t = cb[node.start_byte:node.end_byte]
        if t in (b'true', b'false'):
            return t.decode()
    return None


def find_if_nodes(root) -> list:
    return find_all(root, 'if_statement') + find_all(root, 'if_expression')


class PseudoBlock:
    """Synthetic block wrapping braces + content for languages
    without a dedicated ``block`` AST node (e.g. Swift *statements*)."""

    def __init__(self, start: int, end: int):
        self.type = 'block'
        self.start_byte = start
        self.end_byte = end
        self.children: list = []
        self.named_children: list = []
        self.parent = None
        self.id = id(self)

    def child_by_field_name(self, name):  # noqa: ARG002
        return None


def get_if_parts(if_node, cb: bytes):
    """Extract ``(condition, consequence, alternative)`` from an if node.

    Supports Java, Kotlin, Swift, Go, Rust, C, C++, JS, TS, C#.
    """
    cond = if_node.child_by_field_name('condition')
    cons = if_node.child_by_field_name('consequence')
    alt  = if_node.child_by_field_name('alternative')
    if cons and cond:
        return cond, cons, alt

    children = if_node.children
    found_cond = cond
    found_cons = None
    found_alt  = None
    saw_else   = False
    skip_types = {'if', '(', ')', '{', '}', 'else'}

    if not found_cond:
        for child in children:
            if child.type in skip_types or child.type == 'statements':
                continue
            found_cond = child
            break
    if not found_cond:
        return None, None, None

    for child in children:
        if child.type in ('if', '(', ')') or child.id == found_cond.id:
            continue
        if child.type == 'else':
            saw_else = True
            continue
        if child.type in ('{', '}'):
            continue
        if not saw_else and found_cons is None:
            found_cons = child
        elif saw_else and found_alt is None:
            found_alt = child

    if found_cons and found_cons.type == 'statements':
        bo = bc = None
        for child in children:
            if child.start_byte > found_cond.end_byte and child.type == '{' and not bo:
                bo = child
            if bo and child.type == '}' and child.start_byte >= found_cons.end_byte:
                bc = child
                break
        if bo and bc:
            found_cons = PseudoBlock(bo.start_byte, bc.end_byte)

    if found_alt and found_alt.type == 'statements':
        bo = bc = None
        for child in children:
            if child.type == '{' and child.start_byte < found_alt.start_byte:
                bo = child
            if bo and child.type == '}' and child.start_byte >= found_alt.end_byte:
                bc = child
                break
        if bo and bc:
            found_alt = PseudoBlock(bo.start_byte, bc.end_byte)

    return found_cond, found_cons, found_alt
