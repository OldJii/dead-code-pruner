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
from ..analysis.project_scan import scan_project, semantic_method_key
from ..analysis.ref_index import build_ref_index
from ..analysis.class_hierarchy import enhance_safety, is_framework_class
from ..analysis.code_edit import (
    replace_calls_in_content, remove_void_calls_in_content,
    clean_standalone_booleans, delete_line_ranges, has_cross_file_refs,
    has_dynamic_symbol_ref,
)
from ..analysis.method_scanner import scan_methods
from ..steps.bool_simplify import step2_simple
from ..steps.compound_bool import step3_compound
from ..steps.if_blocks import step4_if_blocks


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


def step6_project(root_dir: str, dry_run: bool = False) -> int:
    """Run full dead-method cleanup on *root_dir*. Returns processed count."""
    t0 = time.time()
    print("\n=== Step 6: Dead method cleanup (tree-sitter) ===")

    # ── Phase 1: Unified scan ───────────────────────────────
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
    safe_count = sum(1 for d in all_dead if d['safe_to_inline'])
    print(f"  Dead methods: {len(all_dead)} (void={void_count}, boolean={bool_count}, safe={safe_count})")

    # ── Phase 2: Safety analysis ────────────────────────────
    t_safety = time.time()
    print("  Analyzing class hierarchy for safety promotion...")
    enhanced = enhance_safety(
        all_dead, scan.children_map, scan.final_classes,
        scan.iface_abstract, scan.implements)
    safe_count = sum(1 for d in all_dead if d['safe_to_inline'])
    print(f"  Promoted {enhanced} leaf/final methods → total safe={safe_count}  "
          f"({time.time()-t_safety:.1f}s)")

    if dry_run:
        for dm in all_dead:
            rel = os.path.relpath(dm['filepath'], root_dir)
            safe_tag = " [SAFE]" if dm.get('safe_to_inline') else ""
            print(f"    {dm['kind']} {dm.get('class_name', '?')}.{dm['name']}"
                  f"{'=' + dm['value'] if dm['value'] else ''}  [{rel}]{safe_tag}")
        return len(all_dead)

    # Pre-check: promote unreferenced public instance methods
    t_pre = time.time()
    _pre_check_public_methods(
        all_dead, ref_index,
        scan.children_map, scan.final_classes,
        scan.iface_abstract, scan.implements)
    safe_count = sum(1 for d in all_dead if d['safe_to_inline'])
    print(f"  Pre-check complete: total safe={safe_count}  ({time.time()-t_pre:.1f}s)")

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
        print(f"\n  Phase 3 · round {iteration+1}: processing {len(new_dead)} methods...")

        round_modified: set[str] = set()
        round_processed = 0
        for i, dm in enumerate(new_dead):
            if (i + 1) % 100 == 0:
                print(f"\r    Replacing calls... {i+1}/{len(new_dead)}", end='', flush=True)

            processed_methods.add(_method_key(dm))
            name  = dm['name']
            kind  = dm['kind']
            value = dm.get('value')
            cls   = dm.get('class_name')
            src   = dm['filepath']
            if dm.get('param_count', 0) > 0:
                continue
            try:
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                if kind == 'void':
                    new_content, cnt = remove_void_calls_in_content(content, name, cls, same_file=True)
                elif kind == 'boolean':
                    new_content, cnt = replace_calls_in_content(content, name, value, cls, same_file=True)
                    new_content = clean_standalone_booleans(new_content)
                else:
                    continue
                if new_content != content:
                    with open(src, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    round_modified.add(src)
                    round_processed += cnt
            except Exception as e:
                print(f"\n    WARN {src}: {e}")

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
                        elif kind == 'boolean':
                            new_content, cnt = replace_calls_in_content(content, name, value, cls, same_file=False)
                            new_content = clean_standalone_booleans(new_content)
                        else:
                            continue
                        if new_content != content:
                            with open(ref_file, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            round_modified.add(ref_file)
                            round_processed += cnt
                    except Exception as e:
                        print(f"\n    WARN {ref_file}: {e}")

        if len(new_dead) >= 100:
            print()  # newline after progress
        files_modified |= round_modified
        total_processed += round_processed

        if round_modified:
            print(f"    Simplifying {len(round_modified)} modified files...")
            for j, fp in enumerate(round_modified):
                if (j + 1) % 50 == 0:
                    print(f"\r    Simplifying... {j+1}/{len(round_modified)}", end='', flush=True)
                try:
                    with open(fp, 'rb') as f:
                        cb = f.read()
                    original_cb = cb
                    ext = os.path.splitext(fp)[1].lower()
                    _lang._current_ext = ext
                    for _ in range(5):
                        prev = cb
                        cb = step2_simple(cb)
                        cb = step3_compound(cb)
                        cb = step4_if_blocks(cb, ext in ('.kt', '.kts'))
                        if cb == prev:
                            break
                    if cb != original_cb:
                        with open(fp, 'wb') as f:
                            f.write(cb)
                except Exception as e:
                    print(f"\n    WARN re-simplify {fp}: {e}")
            if len(round_modified) >= 50:
                print()

        print(f"    Round {iteration+1} result: {round_processed} call sites, "
              f"{len(round_modified)} files modified")

        if not round_modified:
            break

    print(f"  Phase 3 complete: {total_processed} call sites processed "
          f"({iteration+1} round{'s' if iteration > 0 else ''})")

    # ── Phase 4: Delete definitions ─────────────────────────
    print("\n  Phase 4: Deleting unreferenced method definitions...")
    t_del = time.time()
    print("    Rebuilding reference index after call replacement...")
    ref_index = build_ref_index(ref_files)

    by_file: dict[str, list] = {}
    for dm in all_dead:
        if dm.get('safe_to_inline'):
            by_file.setdefault(dm['filepath'], []).append(dm)

    del_count = 0
    files_to_process = list(by_file.items())
    for i, (fp, methods) in enumerate(files_to_process):
        if (i + 1) % 50 == 0 or i + 1 == len(files_to_process):
            print(f"\r    Checking definitions... {i+1}/{len(files_to_process)}  "
                  f"({del_count} deleted)", end='', flush=True)
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
                    if cm['kind'] == 'boolean' and cm['value'] != dm.get('value'):
                        continue
                    if _has_same_file_refs(dm, cm, content):
                        break
                    src_abs = os.path.abspath(fp)
                    if not has_cross_file_refs(dm, ref_index, src_abs):
                        ranges.append((cm['decl_start'], cm['decl_end']))
                    break
            if ranges:
                new_content, cnt = delete_line_ranges(content, ranges)
                if cnt > 0:
                    with open(fp, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    files_modified.add(fp)
                    del_count += cnt
        except Exception as e:
            print(f"\n    WARN delete {fp}: {e}")

    print(f"\n  Phase 4 complete: deleted {del_count} method definitions  "
          f"({time.time()-t_del:.1f}s)")
    total_elapsed = time.time() - t0
    print(f"  Total: modified {len(files_modified)} files  ({total_elapsed:.1f}s)")
    return total_processed + del_count


# ── internal helpers ────────────────────────────────────────

def _pre_check_public_methods(all_dead, ref_index, children_map,
                              final_classes, iface_abstract, implements):
    """Promote unreferenced public non-static methods in leaf/final classes."""
    candidates = [dm for dm in all_dead
                  if not dm.get('safe_to_inline')
                  and dm.get('class_type') != 'enum_declaration'
                  and 'public' in dm.get('all_mods', set())
                  and 'static' not in dm.get('all_mods', set())
                  and not dm.get('is_private')
                  and 'protected' not in dm.get('all_mods', set())]

    promoted = 0
    for i, dm in enumerate(candidates):
        if (i + 1) % 50 == 0:
            print(f"\r    Pre-checking public methods... {i+1}/{len(candidates)}  "
                  f"({promoted} promoted)", end='', flush=True)

        cls = dm.get('class_name')
        if not cls or is_framework_class(cls):
            continue
        if cls in iface_abstract or cls in implements:
            continue
        is_final     = cls in final_classes
        has_children = cls in children_map and len(children_map[cls]) > 0
        if not (is_final or not has_children):
            continue

        # Use existing scan data — no need to re-read the file for method positions
        # Check same-file refs using the already-known declaration range
        try:
            with open(dm['filepath'], 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            has_ref = _has_same_file_refs_direct(
                dm['name'], dm.get('param_count', 0),
                content, dm['decl_start'], dm['decl_end'])
        except Exception:
            continue

        src_abs = os.path.abspath(dm['filepath'])
        if not has_ref and has_cross_file_refs(dm, ref_index, src_abs):
            has_ref = True
        if not has_ref:
            dm['safe_to_inline'] = True
            promoted += 1

    if len(candidates) >= 50:
        print()
    if promoted:
        print(f"    Promoted {promoted} public methods (verified unreferenced)")


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
