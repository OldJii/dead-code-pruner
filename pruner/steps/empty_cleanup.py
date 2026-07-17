"""Phase 2, Step 5 — remove empty class declarations and empty files.

After dead-method removal, some classes may end up with no remaining
members.  This step detects those empty classes, verifies they are not
referenced elsewhere in the project, and removes them.  Files left with
no code (only package/import declarations) are deleted.
"""

import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed

from ..ast_utils import parse, find_all_multi, txt, build_line_offsets, byte_to_line
from ..lang import _PARSERS, SKIP_DIRS
from .. import ui
from ..analysis.ref_index import REFERENCE_EXTS
from ..analysis.project_scan import ProjectScanResult
from ..analysis.project_boundary import (
    ProjectBoundary, boundary_allows_record, detect_project_boundary,
)
from ..validation import validate_transformation

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


def _class_modifiers(node, cb: bytes) -> set[str]:
    modifiers: set[str] = set()
    for child in node.children:
        if child.type == 'modifiers':
            for modifier in child.children:
                modifiers.add(txt(modifier, cb).strip())
        elif child.type in ('modifier', 'visibility_modifier',
                            'access_control', 'inheritance_modifier'):
            modifiers.add(txt(child, cb).strip())
    return modifiers


def _class_has_annotation(node) -> bool:
    stack = list(node.children)
    while stack:
        child = stack.pop()
        if child.type in ('annotation', 'marker_annotation', 'attribute'):
            return True
        if child.type in ('modifiers', 'modifier'):
            stack.extend(child.children)
    return False


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
                                  reference_files: list[str],
                                  decl_start: int, decl_end: int,
                                  ref_index: dict[str, set[str]] | None = None,
                                  ) -> bool:
    """Check if *class_name* appears in any file, including own_file.

    When *ref_index* is provided, only files that actually mention
    *class_name* are opened — avoids reading the entire project.
    """
    own_abs = os.path.abspath(own_file)
    pat = re.compile(r'\b' + re.escape(class_name) + r'\b')

    if ref_index is not None:
        candidates = ref_index.get(class_name, set())
    else:
        candidates = reference_files

    for fp in candidates:
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


def _scan_empty_class_chunk(
        file_paths: list[str]) -> list[tuple[str, str, int, int, set[str]]]:
    """Parse one process-sized chunk and return structural empty-class facts."""
    from .. import lang as _lang

    candidates: list[tuple[str, str, int, int, set[str]]] = []
    for fp in file_paths:
        ext = os.path.splitext(fp)[1].lower()
        try:
            with open(fp, 'rb') as handle:
                content = handle.read()
        except Exception:
            continue
        _lang._current_ext = ext
        root, _ = parse(content)
        offsets = build_line_offsets(content)
        for node in find_all_multi(root, _CLASS_NODE_TYPES):
            if not _is_class_empty(node, content):
                continue
            name = _find_class_name(node, content)
            if not name or _class_has_annotation(node):
                continue
            if node.parent and node.parent.type in _CLASS_NODE_TYPES:
                continue
            candidates.append((
                fp, name,
                byte_to_line(offsets, node.start_byte),
                byte_to_line(offsets, node.end_byte),
                _class_modifiers(node, content),
            ))
    return candidates


def phase2_step5_cleanup_empty_artifacts(
    root_dir: str,
    dry_run: bool = False,
    *,
    show_header: bool = True,
    boundary: ProjectBoundary | None = None,
    world: str = 'auto',
    scan: ProjectScanResult | None = None,
) -> dict:
    """Remove empty classes and delete empty files.

    Returns ``{'classes_removed': int, 'files_deleted': int}``.
    """
    import time
    t0 = time.time()
    if show_header:
        ui.section("Empty Class & File Cleanup")
    else:
        ui.stage("Cleaning empty classes and files")
    boundary = boundary or detect_project_boundary(root_dir, mode=world)

    if scan is not None:
        source_files = [fp for fp in scan.all_files if os.path.exists(fp)]
        reference_files = [fp for fp in scan.ref_files if os.path.exists(fp)]
    else:
        source_files = []
        reference_files = []
        for dp, dns, fns in os.walk(root_dir):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for fn in fns:
                ext = os.path.splitext(fn)[1].lower()
                if ext in _PARSERS:
                    fp = os.path.join(dp, fn)
                    source_files.append(fp)
                    reference_files.append(fp)
                elif ext in REFERENCE_EXTS:
                    reference_files.append(os.path.join(dp, fn))

    structural_candidates: list[tuple[str, str, int, int, set[str]]] = []
    total_files = len(source_files)
    n_workers = min(os.cpu_count() or 1, max(1, total_files // 200))
    if n_workers > 1 and total_files >= 500:
        chunk_count = min(total_files, n_workers * 8)
        chunk_size = max(1, (total_files + chunk_count - 1) // chunk_count)
        chunks = [source_files[i:i + chunk_size]
                  for i in range(0, total_files, chunk_size)]
        completed = 0
        try:
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                futures = {
                    executor.submit(_scan_empty_class_chunk, chunk): len(chunk)
                    for chunk in chunks
                }
                for future in as_completed(futures):
                    structural_candidates.extend(future.result())
                    completed += futures[future]
                    ui.progress(completed, total_files,
                                "Scanning for empty classes")
        except Exception as exc:
            ui.progress_done()
            ui.warn(f"Parallel empty-class scan failed ({exc}), falling back")
            structural_candidates = _scan_empty_class_chunk(source_files)
            ui.progress(total_files, total_files, "Scanning for empty classes")
    else:
        structural_candidates = _scan_empty_class_chunk(source_files)
        ui.progress(total_files, total_files, "Scanning for empty classes")
    ui.progress_done()

    empty_classes: list[tuple[str, str, int, int]] = []
    for fp, name, start_line, end_line, modifiers in structural_candidates:
        record = {'name': name, 'filepath': fp, 'all_mods': modifiers}
        if boundary_allows_record(record, boundary):
            empty_classes.append((fp, name, start_line, end_line))

    if not empty_classes:
        ui.info("No empty classes found.")
        return {'classes_removed': 0, 'files_deleted': 0}

    ui.info(f"Found {len(empty_classes)} empty class candidate(s), checking references...")

    # Build a lightweight ref_index for class name lookups.
    class_names_needed = {cn for _, cn, _, _ in empty_classes}
    if scan is not None:
        class_ref_index = {
            name: set(scan.ref_index.get(name, set()))
            for name in class_names_needed
        }
        ui.info("Reusing unified project reference index")
    else:
        class_ref_index: dict[str, set[str]] = {}
        cn_pat = re.compile(
            r'\b(' + '|'.join(re.escape(n) for n in class_names_needed) + r')\b')
        total_reference_files = len(reference_files)
        for idx, fp in enumerate(reference_files):
            ui.progress(idx + 1, total_reference_files,
                        "Indexing empty-class references")
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue
            for m in cn_pat.finditer(content):
                class_ref_index.setdefault(m.group(1), set()).add(fp)
        ui.progress_done()

    classes_removed = 0
    files_to_check: set[str] = set()

    removable: list[tuple[str, str, int, int]] = []
    total_candidates = len(empty_classes)
    for idx, (fp, class_name, start_line, end_line) in enumerate(empty_classes):
        ui.progress(idx + 1, total_candidates,
                    "Validating empty-class references",
                    f"{len(removable)} removable")
        if _class_referenced_in_project(class_name, fp, reference_files,
                                         start_line, end_line,
                                         ref_index=class_ref_index):
            continue
        removable.append((fp, class_name, start_line, end_line))
    ui.progress_done()

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
            with open(fp, 'rb') as f:
                original_bytes = f.read()
            content = original_bytes.decode('utf-8', errors='replace')
            lines = content.split('\n')
            removed_here = 0
            for class_name, start_line, end_line in entries:
                if start_line <= end_line < len(lines):
                    del lines[start_line:end_line + 1]
                    removed_here += 1
            while lines and lines[-1].strip() == '':
                lines.pop()
            new_content = '\n'.join(lines)
            if new_content.strip():
                new_content += '\n'
            ext = os.path.splitext(fp)[1].lower()
            validated = validate_transformation(
                original_bytes, new_content.encode('utf-8'), ext)
            if validated == original_bytes and new_content != content:
                ui.warn(f"skipped empty-class cleanup in {rel} "
                        f"(would introduce AST errors)", indent=4)
                continue
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(validated.decode('utf-8', errors='replace'))
            classes_removed += removed_here
            for class_name, _start, _end in entries:
                ui.info(f"Removed: {class_name} {ui.dim(f'[{rel}]')}", indent=4)
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
