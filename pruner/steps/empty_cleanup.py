"""Step 7 — remove empty class declarations and empty files.

After dead-method removal, some classes may end up with no remaining
members.  This step detects those empty classes, verifies they are not
referenced elsewhere in the project, and removes them.  Files left with
no code (only package/import declarations) are deleted.
"""

import os
import re

from ..ast_utils import parse, find_all, txt
from ..lang import _PARSERS, SKIP_DIRS
from .. import ui
from ..analysis.ref_index import build_ref_index

_CLASS_NODE_TYPES = frozenset({
    'class_declaration', 'class_definition',
    'interface_declaration', 'object_declaration',
})

_MEMBER_TYPES = frozenset({
    'method_declaration', 'function_declaration', 'function_definition',
    'method_definition', 'constructor_declaration', 'constructor_definition',
    'field_declaration', 'property_declaration', 'variable_declaration',
    'init_declaration', 'static_initializer', 'instance_initializer',
    'class_declaration', 'interface_declaration', 'enum_declaration',
    'object_declaration', 'companion_object',
    'annotation_type_element_declaration',
})

_SKIP_TYPES = frozenset({
    'comment', 'block_comment', 'line_comment', 'multiline_comment',
    '{', '}',
})


def _find_class_name(node, cb: bytes) -> str | None:
    """Extract the class name from a class/interface declaration."""
    name_node = node.child_by_field_name('name')
    if name_node:
        return txt(name_node, cb)
    for c in node.children:
        if c.type in ('identifier', 'simple_identifier', 'type_identifier'):
            return txt(c, cb)
    return None


def _find_class_body(node):
    """Find the class_body / body node within a class declaration."""
    body = node.child_by_field_name('body')
    if body:
        return body
    for c in node.children:
        if c.type in ('class_body', 'enum_body', 'interface_body',
                       'block', 'declaration_list'):
            return c
    return None


def _is_class_empty(node, cb: bytes) -> bool:
    """Return True if the class has no meaningful members."""
    if node.type == 'enum_declaration':
        return False

    body = _find_class_body(node)
    if body is None:
        return False

    for child in body.children:
        if child.type in _SKIP_TYPES:
            continue
        if child.type in _MEMBER_TYPES:
            return False
        if child.type == 'modifiers':
            continue
        ctext = txt(child, cb).strip()
        if ctext and ctext not in ('{', '}', ''):
            if child.type not in ('comment', 'block_comment', 'line_comment',
                                   'multiline_comment', 'annotation'):
                return False
    return True


def _class_referenced_in_project(class_name: str, own_file: str,
                                  all_files: list[str],
                                  decl_start: int, decl_end: int) -> bool:
    """Check if *class_name* appears in any file, including own_file.

    For own_file, the declaration's own line range (decl_start..decl_end)
    is excluded so the class name in its own header doesn't count.
    """
    own_abs = os.path.abspath(own_file)
    pat = re.compile(r'\b' + re.escape(class_name) + r'\b')
    for fp in all_files:
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue

        if os.path.abspath(fp) == own_abs:
            lines = content.split('\n')
            outside = '\n'.join(
                line for i, line in enumerate(lines)
                if i < decl_start or i > decl_end
            )
            if pat.search(outside):
                return True
        else:
            if pat.search(content):
                return True
    return False


def _file_has_only_imports(content: str) -> bool:
    """True when file has no code besides package/import declarations and comments."""
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        if stripped.startswith('package ') or stripped.startswith('import '):
            continue
        if stripped == '*/':
            continue
        return False
    return True


def step7_empty_cleanup(root_dir: str, dry_run: bool = False) -> dict:
    """Remove empty classes and delete empty files.

    Returns ``{'classes_removed': int, 'files_deleted': int}``.
    """
    import time
    t0 = time.time()
    ui.section("Step 7  Empty Class & File Cleanup")

    all_files: list[str] = []
    for dp, dns, fns in os.walk(root_dir):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in _PARSERS:
                all_files.append(os.path.join(dp, fn))

    empty_classes: list[tuple[str, str, int, int]] = []
    for fp in all_files:
        ext = os.path.splitext(fp)[1].lower()
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
        except Exception:
            continue

        from .. import lang as _lang
        _lang._current_ext = ext
        root, _ = parse(cb)

        for ct in _CLASS_NODE_TYPES:
            for node in find_all(root, ct):
                if not _is_class_empty(node, cb):
                    continue
                name = _find_class_name(node, cb)
                if not name:
                    continue
                if node.parent and node.parent.type in _CLASS_NODE_TYPES:
                    continue

                start_line = cb[:node.start_byte].count(b'\n')
                end_line = cb[:node.end_byte].count(b'\n')
                empty_classes.append((fp, name, start_line, end_line))

    if not empty_classes:
        ui.info("No empty classes found.")
        return {'classes_removed': 0, 'files_deleted': 0}

    ui.info(f"Found {len(empty_classes)} empty class candidate(s), checking references...")

    classes_removed = 0
    files_to_check: set[str] = set()

    removable: list[tuple[str, str, int, int]] = []
    for fp, class_name, start_line, end_line in empty_classes:
        if _class_referenced_in_project(class_name, fp, all_files,
                                         start_line, end_line):
            continue
        removable.append((fp, class_name, start_line, end_line))

    by_file: dict[str, list[tuple[str, int, int]]] = {}
    for fp, class_name, start_line, end_line in removable:
        by_file.setdefault(fp, []).append((class_name, start_line, end_line))

    for fp, entries in by_file.items():
        entries.sort(key=lambda e: e[1], reverse=True)
        rel = os.path.relpath(fp, root_dir)

        if dry_run:
            for class_name, start_line, end_line in entries:
                ui.info(f"Would remove: {class_name} {ui.dim(f'[{rel}:{start_line}-{end_line}]')}", indent=4)
                classes_removed += 1
            continue

        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.split('\n')
            for class_name, start_line, end_line in entries:
                if start_line <= end_line < len(lines):
                    del lines[start_line:end_line + 1]
                    classes_removed += 1
                    ui.info(f"Removed: {class_name} {ui.dim(f'[{rel}]')}", indent=4)
            while lines and lines[-1].strip() == '':
                lines.pop()
            new_content = '\n'.join(lines)
            if new_content.strip():
                new_content += '\n'
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(new_content)
            files_to_check.add(fp)
        except Exception as e:
            ui.warn(f"removing classes in {rel}: {e}", indent=4)

    files_deleted = 0
    for fp in files_to_check:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
            if _file_has_only_imports(content):
                rel = os.path.relpath(fp, root_dir)
                if dry_run:
                    ui.info(f"Would delete: {ui.dim(rel)}", indent=4)
                else:
                    os.remove(fp)
                    ui.info(f"Deleted: {ui.dim(rel)}", indent=4)
                files_deleted += 1
        except Exception as e:
            ui.warn(f"checking empty file: {e}", indent=4)

    elapsed = time.time() - t0
    ui.info(f"Removed {classes_removed} empty classes, "
            f"deleted {files_deleted} empty files  "
            f"{ui.dim(ui.fmt_elapsed(elapsed))}")
    return {'classes_removed': classes_removed, 'files_deleted': files_deleted}
