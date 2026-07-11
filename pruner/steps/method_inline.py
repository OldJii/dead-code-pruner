"""Step 5 — inline constant-returning private/static methods.

Scans the entire project for zero-arg methods that return a boolean
constant, replaces all call sites with the literal value, and deletes
the now-unreferenced private method definitions.  Language adapters are
used for visibility and entry-point safety checks.
"""

import os
import re
import sys
import time
from collections import defaultdict

from ..lang import _PARSERS
from .. import ui
from ..adapters import get_adapter
from ..analysis.method_scanner import scan_method_definitions, scan_methods
from ..analysis.project_scan import semantic_method_key
from ..analysis.project_layout import ProjectLayout
from ..analysis.ref_index import (
    collect_files, build_ref_index, is_in_comment_or_string,
)
from ..analysis.code_edit import (
    replace_calls_in_content, clean_standalone_booleans,
    clean_standalone_constants, delete_line_ranges,
    has_dynamic_symbol_ref, verify_no_dangling_calls,
)
from ..validation import validate_transformation


def step5_project(root_dir: str, dry_run: bool = False) -> tuple[int, set[str]]:
    """Inline constant methods project-wide.

    Returns ``(total_inlined, modified_files)``."""
    t0 = time.time()
    ui.section("Step 5  Inline Constant Methods")
    layout = ProjectLayout(root_dir)
    all_files = collect_files(root_dir)
    ui.info(f"Scanning {len(all_files)} files...")

    total = len(all_files)
    all_defs_by_key: dict[tuple, list[dict]] = defaultdict(list)
    all_methods: list[dict] = []
    for idx, fp in enumerate(all_files):
        if (idx + 1) % 500 == 0 or idx + 1 == total:
            ui.progress(idx + 1, total, "Scanning",
                        f"{len(all_methods)} candidates")
        ext = os.path.splitext(fp)[1].lower()
        if ext not in _PARSERS:
            continue
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
            if b'return ' not in cb and b'= true' not in cb and b'= false' not in cb:
                continue
            mod_name = layout.get_module(fp)
            methods = scan_method_definitions(fp, cb, ext, module=mod_name)
            for m in methods:
                all_defs_by_key[semantic_method_key(m)].append(m)
                if (m.get('is_dead_candidate') and m['kind'] in ('boolean', 'constant')
                        and m['param_count'] == 0 and m['safe_to_inline']):
                    all_methods.append(m)
        except Exception as e:
            ui.error(f"scanning {fp}: {e}")
    ui.progress_done()

    if not all_methods:
        ui.info("No constant methods found.")
        return 0, set()

    variant_conflicts = set()
    for key, methods in all_defs_by_key.items():
        source_sets = {m.get('source_set') for m in methods if m.get('source_set')}
        candidate_shapes = {(m.get('kind'), m.get('value')) for m in methods if m.get('is_dead_candidate')}
        has_non_candidate = any(not m.get('is_dead_candidate') for m in methods)
        has_multiple_shapes = len(candidate_shapes) > 1
        has_source_set_variants = len(source_sets) > 1
        if len(methods) > 1 and (has_source_set_variants or has_non_candidate or has_multiple_shapes):
            variant_conflicts.add(key)
    all_methods = [m for m in all_methods if semantic_method_key(m) not in variant_conflicts]

    if not all_methods:
        ui.info("No constant methods found after source-set safety checks.")
        return 0, set()

    private_cnt = sum(1 for m in all_methods if m['is_private'])
    static_cnt  = sum(1 for m in all_methods if m['is_static'] and not m['is_private'])
    ui.info(f"Found {ui.bold(str(len(all_methods)))} constant methods "
            f"(private={private_cnt}, static={static_cnt})")

    if dry_run:
        for m in all_methods:
            rel = os.path.relpath(m['filepath'], root_dir)
            ui.info(f"{m['class_name']}.{m['name']}() → {m['value']}  "
                    f"{ui.dim(rel)}", indent=4)
        return len(all_methods), set()

    ref_index = build_ref_index(collect_files(root_dir, include_reference_files=True))
    files_modified: set[str] = set()
    total_inlined = 0

    for m in all_methods:
        name  = m['name']
        value = m['value']
        cls   = m['class_name']
        src   = m['filepath']
        cls_scope = None
        if m.get('class_start') is not None and m.get('class_end') is not None:
            cls_scope = (m['class_start'], m['class_end'])

        try:
            with open(src, 'r', encoding='utf-8') as f:
                content = f.read()
            new_content, cnt = replace_calls_in_content(
                content, name, value, cls, same_file=True, class_lines=cls_scope)
            new_content = clean_standalone_booleans(new_content)
            if value not in ('true', 'false'):
                new_content = clean_standalone_constants(new_content, value)
            if new_content != content:
                ext_v = os.path.splitext(src)[1].lower()
                validated = validate_transformation(
                    content.encode('utf-8'), new_content.encode('utf-8'), ext_v)
                new_content = validated.decode('utf-8', errors='replace')
                if new_content != content:
                    with open(src, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    files_modified.add(src)
                    total_inlined += cnt
        except Exception as e:
            ui.warn(f"same-file {src}: {e}")

        if m['is_static'] and cls:
            src_abs = os.path.abspath(src)
            for ref_file in ref_index.get(name, set()):
                if os.path.abspath(ref_file) == src_abs:
                    continue
                try:
                    with open(ref_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if cls + '.' + name not in content:
                        continue
                    new_content, cnt = replace_calls_in_content(
                        content, name, value, cls, same_file=False)
                    if value not in ('true', 'false'):
                        new_content = clean_standalone_constants(new_content, value)
                    if new_content != content:
                        ext_v = os.path.splitext(ref_file)[1].lower()
                        validated = validate_transformation(
                            content.encode('utf-8'), new_content.encode('utf-8'), ext_v)
                        new_content = validated.decode('utf-8', errors='replace')
                        if new_content != content:
                            with open(ref_file, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            files_modified.add(ref_file)
                            total_inlined += cnt
                except Exception as e:
                    ui.warn(f"cross-file {ref_file}: {e}")

    deleted = 0
    by_file: dict[str, list] = defaultdict(list)
    for m in all_methods:
        if m['is_private']:
            by_file[m['filepath']].append(m)

    for fp, methods in by_file.items():
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
            ext = os.path.splitext(fp)[1].lower()
            current_methods = scan_methods(fp, cb, ext)
            content = cb.decode('utf-8', errors='replace')
            ranges = []
            for dm in methods:
                for cm in current_methods:
                    if (cm['name'] == dm['name']
                            and cm['kind'] in ('boolean', 'constant')
                            and cm['value'] == dm['value']):
                        lines = content.split('\n')
                        has_ref = False
                        call_pat = re.compile(r'(?<!\w)' + re.escape(dm['name']) + r'\s*\(\s*\)')
                        for i, line in enumerate(lines):
                            if cm['decl_start'] <= i <= cm['decl_end']:
                                continue
                            mref = call_pat.search(line)
                            if has_dynamic_symbol_ref(line, dm['name']):
                                has_ref = True
                                break
                            if mref and not is_in_comment_or_string(line, mref.start()):
                                has_ref = True
                                break
                        if not has_ref:
                            ranges.append((cm['decl_start'], cm['decl_end']))
                        break
            if ranges:
                new_content, del_cnt = delete_line_ranges(content, ranges)
                if del_cnt > 0:
                    deleted_names = {dm['name'] for dm in methods
                                     if any(dm['decl_start'] == s for s, _ in ranges)}
                    dangling = verify_no_dangling_calls(new_content, deleted_names)
                    if dangling:
                        pass
                    else:
                        with open(fp, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        files_modified.add(fp)
                        deleted += del_cnt
        except Exception as e:
            ui.warn(f"delete {fp}: {e}")

    ui.info(f"Inlined {ui.bold(str(total_inlined))} call sites, "
            f"deleted {deleted} definitions")
    ui.info(f"Modified {len(files_modified)} files  "
            f"{ui.dim(ui.fmt_elapsed(time.time()-t0))}")
    return total_inlined, files_modified


