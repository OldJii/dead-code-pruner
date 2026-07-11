"""Step 6 — dead method detection and cleanup.

Pipeline:
  1. Unified scan: collect dead methods + reference index + class hierarchy
     in a single pass over all source files.
  2. Safety analysis: enhance leaf/final class methods, pre-check public
     instance methods for cross-file references.
  3. Iterative call replacement: replace boolean call sites with constant
     values, remove void calls, then re-simplify modified files.
  4. Definition deletion: remove method definitions that have no remaining
     references.
"""

import os
import re
import time

from .. import lang as _lang
from .. import ui
from ..analysis.project_scan import scan_project, semantic_method_key
from ..analysis.ref_index import build_ref_index, is_in_comment_or_string
from ..analysis.class_hierarchy import enhance_safety, is_framework_class
from ..analysis.code_edit import (
    replace_calls_in_content, remove_void_calls_in_content,
    clean_standalone_booleans, clean_standalone_constants,
    delete_line_ranges, has_cross_file_refs,
    has_dynamic_symbol_ref, verify_no_dangling_calls,
)
from ..analysis.method_scanner import scan_methods
from ..validation import validate_transformation
from ..steps.constant_fold import step1b_propagate_locals, step1c_remove_unused_bool_vars
from ..steps.bool_simplify import step2_simple
from ..steps.compound_bool import step3_compound
from ..steps.if_blocks import step4_if_blocks
from ..steps.unreachable import step1d_remove_unreachable


def _method_key(method: dict) -> tuple:
    """Stable project-level identity for a method candidate."""
    return (
        os.path.abspath(method.get('filepath', '')),
        method.get('class_name'),
        method.get('name'),
        method.get('param_count', 0),
        method.get('decl_start'),
        method.get('decl_end'),
    )


def step6_project(root_dir: str, dry_run: bool = False) -> tuple[int, set[str]]:
    """Run full dead-method cleanup on *root_dir*.

    Returns ``(processed_count, modified_files)``."""
    t0 = time.time()
    ui.section("Step 6  Dead Method Cleanup")

    scan = scan_project(root_dir, progress_interval=500)
    all_files   = scan.all_files
    ref_files   = scan.ref_files
    all_dead    = [
        dm for dm in scan.dead_methods
        if semantic_method_key(dm) not in scan.variant_conflicts
    ]
    ref_index   = dict(scan.ref_index)

    void_count = sum(1 for d in all_dead if d['kind'] == 'void')
    bool_count = sum(1 for d in all_dead if d['kind'] == 'boolean')
    const_count = sum(1 for d in all_dead if d['kind'] == 'constant')
    null_count = sum(1 for d in all_dead if d['kind'] == 'null_return')
    safe_count = sum(1 for d in all_dead if d['safe_to_inline'])
    kind_str = f"void={void_count}, boolean={bool_count}"
    if const_count:
        kind_str += f", constant={const_count}"
    if null_count:
        kind_str += f", null_return={null_count}"
    ui.info(f"Dead methods: {ui.bold(str(len(all_dead)))} ({kind_str}, safe={safe_count})")

    # ── Phase 2: Safety analysis ────────────────────────────
    t_safety = time.time()
    ui.info("Analyzing class hierarchy for safety promotion...")
    enhanced = enhance_safety(
        all_dead, scan.children_map, scan.final_classes,
        scan.iface_abstract, scan.implements)
    safe_count = sum(1 for d in all_dead if d['safe_to_inline'])
    ui.info(f"Promoted {enhanced} leaf/final → safe={safe_count}  "
            f"{ui.dim(ui.fmt_elapsed(time.time()-t_safety))}")

    if dry_run:
        for dm in all_dead:
            rel = os.path.relpath(dm['filepath'], root_dir)
            safe_tag = f" {ui.green('[SAFE]')}" if dm.get('safe_to_inline') else ""
            ui.info(f"{dm['kind']} {dm.get('class_name', '?')}.{dm['name']}"
                    f"{'=' + dm['value'] if dm['value'] else ''}  "
                    f"{ui.dim(rel)}{safe_tag}", indent=4)
        return len(all_dead), set()

    t_pre = time.time()
    _pre_check_public_methods(
        all_dead, ref_index,
        scan.children_map, scan.final_classes,
        scan.iface_abstract, scan.implements)
    safe_count = sum(1 for d in all_dead if d['safe_to_inline'])
    ui.info(f"Pre-check complete: safe={safe_count}  "
            f"{ui.dim(ui.fmt_elapsed(time.time()-t_pre))}")

    files_modified: set[str] = set()
    total_processed = 0

    # ── Phase 3: Iterative call replacement ─────────────────
    iteration = 0
    processed_methods: set[tuple] = set()
    for iteration in range(5):
        new_dead = [dm for dm in all_dead
                    if dm.get('safe_to_inline') and _method_key(dm) not in processed_methods]
        if not new_dead:
            break
        ui.info(f"\nPhase 3 · round {iteration+1}: processing {len(new_dead)} methods...")

        round_modified: set[str] = set()
        round_processed = 0
        for i, dm in enumerate(new_dead):
            if (i + 1) % 100 == 0:
                ui.progress(i + 1, len(new_dead), "Replacing calls", indent=4)

            processed_methods.add(_method_key(dm))
            name  = dm['name']
            kind  = dm['kind']
            value = dm.get('value')
            cls   = dm.get('class_name')
            src   = dm['filepath']
            cls_scope = None
            if dm.get('class_start') is not None and dm.get('class_end') is not None:
                cls_scope = (dm['class_start'], dm['class_end'])
            if dm.get('param_count', 0) > 0:
                continue
            try:
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                if kind == 'void':
                    new_content, cnt = remove_void_calls_in_content(
                        content, name, cls, same_file=True, class_lines=cls_scope)
                elif kind in ('boolean', 'constant'):
                    new_content, cnt = replace_calls_in_content(
                        content, name, value, cls, same_file=True, class_lines=cls_scope)
                    new_content = clean_standalone_booleans(new_content)
                    if kind == 'constant':
                        new_content = clean_standalone_constants(new_content, value)
                else:
                    continue
                if new_content != content:
                    ext_v = os.path.splitext(src)[1].lower()
                    validated = validate_transformation(
                        content.encode('utf-8'), new_content.encode('utf-8'), ext_v)
                    new_content = validated.decode('utf-8', errors='replace')
                    if new_content != content:
                        with open(src, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        round_modified.add(src)
                        round_processed += cnt
            except Exception as e:
                ui.warn(f"{src}: {e}", indent=4)

            if cls:
                src_abs = os.path.abspath(src)
                for ref_file in ref_index.get(name, set()):
                    if os.path.abspath(ref_file) == src_abs:
                        continue
                    try:
                        with open(ref_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        quick = cls + '.' + name
                        if quick not in content and name + '(' not in content:
                            continue
                        if kind == 'void':
                            new_content, cnt = remove_void_calls_in_content(content, name, cls, same_file=False)
                        elif kind in ('boolean', 'constant'):
                            new_content, cnt = replace_calls_in_content(content, name, value, cls, same_file=False)
                            new_content = clean_standalone_booleans(new_content)
                            if kind == 'constant':
                                new_content = clean_standalone_constants(new_content, value)
                        else:
                            continue
                        if new_content != content:
                            ext_v = os.path.splitext(ref_file)[1].lower()
                            validated = validate_transformation(
                                content.encode('utf-8'), new_content.encode('utf-8'), ext_v)
                            new_content = validated.decode('utf-8', errors='replace')
                            if new_content != content:
                                with open(ref_file, 'w', encoding='utf-8') as f:
                                    f.write(new_content)
                                round_modified.add(ref_file)
                                round_processed += cnt
                    except Exception as e:
                        ui.warn(f"{ref_file}: {e}", indent=4)

        if len(new_dead) >= 100:
            ui.progress_done()
        files_modified |= round_modified
        total_processed += round_processed

        if round_modified:
            ui.info(f"Simplifying {len(round_modified)} modified files...", indent=4)
            for j, fp in enumerate(round_modified):
                if (j + 1) % 50 == 0:
                    ui.progress(j + 1, len(round_modified), "Simplifying", indent=4)
                try:
                    with open(fp, 'rb') as f:
                        cb = f.read()
                    original_cb = cb
                    ext = os.path.splitext(fp)[1].lower()
                    _lang._current_ext = ext
                    for _ in range(5):
                        prev = cb
                        cb = step1b_propagate_locals(cb)
                        cb = step2_simple(cb)
                        cb = step3_compound(cb)
                        cb = step4_if_blocks(cb, ext in ('.kt', '.kts'))
                        cb = step1d_remove_unreachable(cb)
                        cb = step1c_remove_unused_bool_vars(cb)
                        if cb == prev:
                            break
                    cb = validate_transformation(original_cb, cb, ext)
                    if cb != original_cb:
                        with open(fp, 'wb') as f:
                            f.write(cb)
                except Exception as e:
                    ui.warn(f"re-simplify {fp}: {e}", indent=4)
            if len(round_modified) >= 50:
                ui.progress_done()

        ui.info(f"Round {iteration+1}: {round_processed} call sites, "
                f"{len(round_modified)} files modified", indent=4)

        if not round_modified:
            break

    ui.info(f"Phase 3 complete: {total_processed} call sites  "
            f"({iteration+1} round{'s' if iteration > 0 else ''})")

    ui.info("\nPhase 4: Deleting unreferenced definitions...")
    t_del = time.time()
    ui.info("Rebuilding reference index...", indent=4)
    ref_index = build_ref_index(ref_files)

    by_file: dict[str, list] = {}
    for dm in all_dead:
        if dm.get('safe_to_inline'):
            by_file.setdefault(dm['filepath'], []).append(dm)

    del_count = 0
    files_to_process = list(by_file.items())
    for i, (fp, methods) in enumerate(files_to_process):
        if (i + 1) % 50 == 0 or i + 1 == len(files_to_process):
            ui.progress(i + 1, len(files_to_process), "Checking",
                        f"{del_count} deleted", indent=4)
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
            ext = os.path.splitext(fp)[1].lower()
            current_methods = scan_methods(fp, cb, ext)
            content = cb.decode('utf-8', errors='replace')
            ranges = []
            for dm in methods:
                for cm in current_methods:
                    if cm['name'] != dm['name'] or cm['kind'] != dm['kind']:
                        continue
                    if cm['kind'] in ('boolean', 'constant', 'null_return') and cm['value'] != dm.get('value'):
                        continue
                    if _has_same_file_refs(dm, cm, content):
                        break
                    src_abs = os.path.abspath(fp)
                    if not has_cross_file_refs(dm, ref_index, src_abs,
                                              scan.children_map, scan.iface_abstract):
                        ranges.append((cm['decl_start'], cm['decl_end']))
                    break
            if ranges:
                new_content, cnt = delete_line_ranges(content, ranges)
                if cnt > 0:
                    deleted_names = set()
                    for start, end in ranges:
                        for dm in methods:
                            if dm['decl_start'] == start:
                                deleted_names.add(dm['name'])
                    dangling = verify_no_dangling_calls(new_content, deleted_names)
                    if dangling:
                        ui.warn(f"skipped deletion in "
                               f"{os.path.relpath(fp, root_dir)} "
                               f"(dangling refs: {dangling})", indent=4)
                    else:
                        with open(fp, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        files_modified.add(fp)
                        del_count += cnt
        except Exception as e:
            ui.warn(f"delete {fp}: {e}", indent=4)

    ui.progress_done()
    ui.info(f"Phase 4: deleted {del_count} definitions  "
            f"{ui.dim(ui.fmt_elapsed(time.time()-t_del))}")
    total_elapsed = time.time() - t0
    ui.info(f"Total: {len(files_modified)} files modified  "
            f"{ui.dim(ui.fmt_elapsed(total_elapsed))}")
    return total_processed + del_count, files_modified


# ── internal helpers ────────────────────────────────────────

def _pre_check_public_methods(all_dead, ref_index, children_map,
                              final_classes, iface_abstract, implements):
    """Promote unreferenced non-private non-static instance methods to
    safe-to-inline by verifying they have no same-file or cross-file
    references.

    Covers public, protected, and package-private methods regardless of
    class hierarchy depth — the cross-file reference check already
    catches ``super.method()`` calls and polymorphic invocations.
    Methods declared in interfaces/abstract classes are skipped because
    they serve as contracts for external implementors.
    """
    candidates = [dm for dm in all_dead
                  if not dm.get('safe_to_inline')
                  and dm.get('class_type') != 'enum_declaration'
                  and not dm.get('is_private')
                  and 'static' not in dm.get('all_mods', set())]

    promoted = 0
    for i, dm in enumerate(candidates):
        if (i + 1) % 50 == 0:
            ui.progress(i + 1, len(candidates), "Pre-checking",
                        f"{promoted} promoted", indent=4)

        cls = dm.get('class_name')
        if not cls or is_framework_class(cls):
            continue
        if cls in iface_abstract:
            continue

        try:
            with open(dm['filepath'], 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            has_ref = _has_same_file_refs_direct(
                dm['name'], dm.get('param_count', 0),
                content, dm['decl_start'], dm['decl_end'])
        except Exception:
            continue

        src_abs = os.path.abspath(dm['filepath'])
        if not has_ref and has_cross_file_refs(dm, ref_index, src_abs,
                                              children_map, iface_abstract):
            has_ref = True
        if not has_ref:
            dm['safe_to_inline'] = True
            promoted += 1

    if len(candidates) >= 50:
        ui.progress_done()
    if promoted:
        ui.info(f"Promoted {promoted} non-private instance methods (unreferenced)", indent=4)


def _has_same_file_refs_direct(method_name: str, param_count: int,
                               content: str, decl_start: int,
                               decl_end: int) -> bool:
    """Check same-file references using known declaration line range."""
    lines = content.split('\n')
    if param_count == 0:
        call_pat = re.compile(r'(?<!\w)' + re.escape(method_name) + r'\s*\(\s*\)')
    else:
        call_pat = re.compile(r'(?<!\w)' + re.escape(method_name) + r'\s*\(')
    ref_pat = re.compile(r'::' + re.escape(method_name) + r'\b')
    for i, line in enumerate(lines):
        if decl_start <= i <= decl_end:
            continue
        if line.strip().startswith('//') or line.strip().startswith('/*'):
            continue
        if call_pat.search(line) or ref_pat.search(line) or has_dynamic_symbol_ref(line, method_name):
            return True
    return False


def _has_same_file_refs(dm: dict, cm: dict, content: str) -> bool:
    """Return ``True`` if *dm* has call-site references in the same file."""
    return _has_same_file_refs_direct(
        dm['name'], dm.get('param_count', 0),
        content, cm['decl_start'], cm['decl_end'])
