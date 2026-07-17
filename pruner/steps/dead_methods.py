"""Phase 2, Step 2 — dead declaration detection and cleanup.

Pipeline:
  1. Unified scan: methods + fields + reference index + contract graph.
  2. Safety analysis via ``ContractGraph`` / language adapters (no
     class-name heuristics or ad-hoc public promotion patches).
  3. Iterative call replacement for zero-arg boolean/void methods.
  4. Definition deletion for unreferenced methods approved by the language
     adapter (including unused fields).
  5. Bound leading comments are removed with their host declaration.
"""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

from ..adapters import get_adapter
from .. import ui
from ..analysis.project_scan import scan_project, semantic_method_key, ProjectScanResult
from ..analysis.project_boundary import (
    ProjectBoundary, boundary_allows_record, detect_project_boundary,
)
from ..analysis.ref_index import (
    clear_text_index_cache, is_in_comment_or_string,
    iter_dynamic_reference_names, iter_implicit_reference_names,
)
from ..analysis.contracts import promote_unreferenced
from ..analysis.code_edit import (
    replace_calls_in_content, remove_void_calls_in_content,
    clean_standalone_booleans, delete_line_ranges, has_cross_file_refs,
    has_dynamic_symbol_ref, verify_no_dangling_calls,
)
from ..analysis.method_scanner import scan_method_definitions
from ..analysis.field_scanner import scan_fields
from ..validation import validate_transformation

_MIN_PARALLEL = 50
_SIMPLIFY_FILES_PER_WORKER = 40


def _simplify_files_worker(file_paths):
    """Worker: run the Phase 1 simplification loop on a batch of files."""
    from ..transform import run_pipeline

    errors: list[tuple[str, str]] = []
    for fp in file_paths:
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
            original_cb = cb
            ext = os.path.splitext(fp)[1].lower()
            cb = run_pipeline(cb, ext=ext, max_rounds=5)
            if cb != original_cb:
                with open(fp, 'wb') as f:
                    f.write(cb)
        except Exception as exc:
            errors.append((fp, str(exc)))
    return errors


def _scan_field_refs_worker(args):
    """Worker: extract word occurrences matching candidate field names."""
    file_paths, candidate_names_list = args
    candidate_set = frozenset(candidate_names_list)
    word_pat = re.compile(r'\b(\w+)\b')
    refs: dict[str, list[str]] = {}
    for fp in file_paths:
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except Exception:
            continue
        for word in word_pat.findall(content):
            if word in candidate_set:
                refs.setdefault(word, []).append(fp)
    return refs


def _simplify_single(fp: str) -> str | None:
    """Sequential fallback: simplify one file in-place."""
    try:
        with open(fp, 'rb') as f:
            cb = f.read()
        original_cb = cb
        ext = os.path.splitext(fp)[1].lower()
        from ..transform import run_pipeline
        cb = run_pipeline(cb, ext=ext, max_rounds=5)
        if cb != original_cb:
            with open(fp, 'wb') as f:
                f.write(cb)
        return None
    except Exception as exc:
        return str(exc)


def _method_key(method: dict) -> tuple:
    return (
        os.path.abspath(method.get('filepath', '')),
        method.get('class_name'),
        method.get('name'),
        method.get('param_count', 0),
        method.get('decl_start'),
        method.get('decl_end'),
    )


def phase2_step2_cleanup_dead_declarations(
    root_dir: str,
    dry_run: bool = False,
    *,
    scan: ProjectScanResult | None = None,
    show_header: bool = True,
    boundary: ProjectBoundary | None = None,
    world: str = 'auto',
) -> tuple[int, set[str]]:
    """Run full dead-declaration cleanup on *root_dir*.

    When *scan* is provided, skip the expensive full-project scan and use
    the pre-computed data.  This enables incremental rounds without
    re-reading the entire project.

    Returns ``(processed_count, modified_files)``.
    """
    t0 = time.time()
    if show_header:
        ui.section("Dead Declaration Cleanup")
    clear_text_index_cache()

    if boundary is None and world != 'auto':
        boundary = detect_project_boundary(root_dir, mode=world)
    if boundary is None and scan is not None:
        boundary = scan.boundary
    if boundary is None:
        boundary = detect_project_boundary(root_dir)
    if scan is None:
        scan = scan_project(
            root_dir, progress_interval=500, boundary=boundary)

    contracts = scan.contracts
    content_cache = scan.content_cache
    all_dead = [
        dict(dm) for dm in scan.dead_methods
        if semantic_method_key(dm) not in scan.variant_conflicts
    ]
    for method in all_dead:
        if not boundary_allows_record(method, boundary):
            method['safe_to_inline'] = False
    ref_index = dict(scan.ref_index)

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

    t_unused = time.time()
    ui.info("Analyzing non-constant removable methods for unused definitions...")
    unused_extra = _collect_unused_methods(
        scan, contracts, ref_index, content_cache=content_cache,
        member_ref_index=scan.member_ref_index,
        type_ref_index=scan.type_ref_index,
        dynamic_ref_index=scan.dynamic_ref_index,
        implicit_ref_index=scan.implicit_ref_index,
        boundary=boundary)
    if unused_extra:
        ui.info(f"Unused non-constant methods: {len(unused_extra)}")
        all_dead.extend(unused_extra)
    ui.info(f"Unused-method analysis complete  "
            f"{ui.dim(ui.fmt_elapsed(time.time()-t_unused))}")

    if dry_run:
        for dm in all_dead:
            rel = os.path.relpath(dm['filepath'], root_dir)
            safe_tag = f" {ui.green('[SAFE]')}" if dm.get('safe_to_inline') else ""
            val = dm.get('value')
            ui.info(f"{dm.get('kind', '?')} {dm.get('class_name', '?')}.{dm['name']}"
                    f"{'=' + val if val else ''}  "
                    f"{ui.dim(rel)}{safe_tag}", indent=4)
        return len(all_dead), set()

    t_pre = time.time()
    _promote_unreferenced(
        all_dead, ref_index, contracts, content_cache=content_cache,
        member_ref_index=scan.member_ref_index,
        type_ref_index=scan.type_ref_index,
        dynamic_ref_index=scan.dynamic_ref_index,
        implicit_ref_index=scan.implicit_ref_index,
        boundary=boundary)
    safe_count = sum(1 for d in all_dead if d['safe_to_inline'])
    ui.info(f"Pre-check complete: safe={safe_count}  "
            f"{ui.dim(ui.fmt_elapsed(time.time()-t_pre))}")

    files_modified: set[str] = set()
    total_processed = 0
    processed_methods: set[tuple] = set()
    for iteration in range(5):
        new_dead = [
            dm for dm in all_dead
            if dm.get('safe_to_inline')
            and dm.get('kind') in ('void', 'boolean')
            and dm.get('param_count', 0) == 0
            and _method_key(dm) not in processed_methods
        ]
        if not new_dead:
            break
        ui.stage(f"Call-site rewriting · pass {iteration + 1}")
        ui.info(f"Processing {len(new_dead)} methods...", indent=4)

        round_modified: set[str] = set()
        round_processed = 0
        same_file_edits: dict[str, list[dict]] = {}
        cross_file_edits: list[tuple[str, dict]] = []

        for dm in new_dead:
            processed_methods.add(_method_key(dm))
            same_file_edits.setdefault(dm['filepath'], []).append(dm)
            if dm.get('class_name'):
                src_abs = os.path.abspath(dm['filepath'])
                for ref_file in ref_index.get(dm['name'], set()):
                    if os.path.abspath(ref_file) != src_abs:
                        cross_file_edits.append((ref_file, dm))

        total_edit_files = len(same_file_edits)
        edited_files_done = 0
        for src, methods in same_file_edits.items():
            try:
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                original = content
                cnt = 0
                for dm in methods:
                    cls_scope = None
                    if dm.get('class_start') is not None and dm.get('class_end') is not None:
                        cls_scope = (dm['class_start'], dm['class_end'])
                    kind, name, value, cls = (
                        dm['kind'], dm['name'], dm.get('value'), dm.get('class_name'))
                    if kind == 'void':
                        content, c = remove_void_calls_in_content(
                            content, name, cls, same_file=True, class_lines=cls_scope)
                    else:
                        content, c = replace_calls_in_content(
                            content, name, value, cls, same_file=True, class_lines=cls_scope)
                        content = clean_standalone_booleans(content)
                    cnt += c
                if content != original:
                    ext_v = os.path.splitext(src)[1].lower()
                    validated = validate_transformation(
                        original.encode('utf-8'), content.encode('utf-8'), ext_v)
                    content = validated.decode('utf-8', errors='replace')
                    if content != original:
                        with open(src, 'w', encoding='utf-8') as f:
                            f.write(content)
                        round_modified.add(src)
                        round_processed += cnt
            except Exception as e:
                ui.warn(f"{src}: {e}", indent=4)
            edited_files_done += 1
            ui.progress(edited_files_done, max(1, total_edit_files),
                        "Rewriting local call sites", indent=4)
        if total_edit_files:
            ui.progress_done()

        by_ref: dict[str, list[dict]] = {}
        for ref_file, dm in cross_file_edits:
            by_ref.setdefault(ref_file, []).append(dm)
        total_ref_files = len(by_ref)
        ref_files_done = 0
        for ref_file, methods in by_ref.items():
            try:
                with open(ref_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                original = content
                cnt = 0
                for dm in methods:
                    cls, name, kind, value = (
                        dm.get('class_name'), dm['name'], dm['kind'], dm.get('value'))
                    quick = (cls + '.' + name) if cls else name
                    if quick not in content and name + '(' not in content:
                        continue
                    if kind == 'void':
                        content, c = remove_void_calls_in_content(
                            content, name, cls, same_file=False)
                    else:
                        content, c = replace_calls_in_content(
                            content, name, value, cls, same_file=False)
                        content = clean_standalone_booleans(content)
                    cnt += c
                if content != original:
                    ext_v = os.path.splitext(ref_file)[1].lower()
                    validated = validate_transformation(
                        original.encode('utf-8'), content.encode('utf-8'), ext_v)
                    content = validated.decode('utf-8', errors='replace')
                    if content != original:
                        with open(ref_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                        round_modified.add(ref_file)
                        round_processed += cnt
            except Exception as e:
                ui.warn(f"{ref_file}: {e}", indent=4)
            ref_files_done += 1
            ui.progress(ref_files_done, max(1, total_ref_files),
                        "Rewriting external call sites", indent=4)
        if total_ref_files:
            ui.progress_done()

        files_modified |= round_modified
        total_processed += round_processed

        if round_modified:
            ui.info(f"Simplifying {len(round_modified)} modified files...", indent=4)
            mod_list = sorted(round_modified)
            n_workers = min(os.cpu_count() or 1,
                            max(1, (len(mod_list) + _SIMPLIFY_FILES_PER_WORKER - 1)
                                // _SIMPLIFY_FILES_PER_WORKER))
            if n_workers > 1 and len(mod_list) >= _MIN_PARALLEL:
                target_chunks = min(len(mod_list), n_workers * 4)
                chunk_sz = max(1, (len(mod_list) + target_chunks - 1)
                               // target_chunks)
                chunks = [mod_list[i:i + chunk_sz]
                          for i in range(0, len(mod_list), chunk_sz)]
                try:
                    with ProcessPoolExecutor(max_workers=n_workers) as ex:
                        futures = {ex.submit(_simplify_files_worker, chunk): len(chunk)
                                   for chunk in chunks}
                        completed = 0
                        for future in as_completed(futures):
                            for fp, message in future.result():
                                ui.warn(f"Skipped {fp}: {message}", indent=4)
                            completed += futures[future]
                            ui.progress(completed, len(mod_list),
                                        "Simplifying", indent=4)
                    ui.progress_done()
                except Exception:
                    ui.progress_done()
                    ui.warn("Parallel simplification failed; retrying sequentially",
                            indent=4)
                    for idx, fp in enumerate(mod_list):
                        error = _simplify_single(fp)
                        if error:
                            ui.warn(f"Skipped {fp}: {error}", indent=4)
                        ui.progress(idx + 1, len(mod_list),
                                    "Simplifying", indent=4)
                    ui.progress_done()
            else:
                for idx, fp in enumerate(mod_list):
                    error = _simplify_single(fp)
                    if error:
                        ui.warn(f"Skipped {fp}: {error}", indent=4)
                    ui.progress(idx + 1, len(mod_list),
                                "Simplifying", indent=4)
                ui.progress_done()

        ui.info(f"Rewrite pass {iteration+1}: {round_processed} call sites, "
                f"{len(round_modified)} files modified", indent=4)
        if not round_modified:
            break

    ui.info(f"Call-site rewriting complete: {total_processed} call sites  "
            f"({iteration+1} pass{'es' if iteration > 0 else ''})")

    # Update ref_index incrementally for modified files before deletion.
    ui.stage("Deleting unreferenced definitions")
    t_del = time.time()
    if files_modified:
        ui.info(f"Updating ref index for {len(files_modified)} modified files...", indent=4)
        modified_set = set(files_modified)
        for name_set in ref_index.values():
            name_set -= modified_set
        for name_set in scan.member_ref_index.values():
            name_set -= modified_set
        for name_set in scan.implicit_ref_index.values():
            name_set -= modified_set
        from ..analysis.ref_index import iter_reference_names
        for fp in files_modified:
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                content_cache[fp] = content
                member_names: set[str] = set()
                for name in iter_reference_names(
                        content, member_names=member_names):
                    ref_index.setdefault(name, set()).add(fp)
                for name in member_names:
                    scan.member_ref_index.setdefault(name, set()).add(fp)
                ext = os.path.splitext(fp)[1].lower()
                for name in iter_implicit_reference_names(content, ext):
                    scan.implicit_ref_index.setdefault((ext, name), set()).add(fp)
            except Exception:
                pass
    clear_text_index_cache()

    by_file: dict[str, list] = {}
    for dm in all_dead:
        if dm.get('safe_to_inline'):
            by_file.setdefault(dm['filepath'], []).append(dm)

    del_count = 0
    files_to_process = list(by_file.items())
    for i, (fp, methods) in enumerate(files_to_process):
        if (i + 1) % 100 == 0 or i + 1 == len(files_to_process):
            ui.progress(i + 1, len(files_to_process), "Checking",
                        f"{del_count} deleted", indent=4)
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
            ext = os.path.splitext(fp)[1].lower()
            # Include non-constant method definitions because this pass also
            # deletes records classified as ``unused``.
            current_methods = scan_method_definitions(fp, cb, ext)
            content = cb.decode('utf-8', errors='replace')
            ranges = []
            matched_methods: list[dict] = []
            available = list(current_methods)
            for dm in methods:
                compatible = []
                for cm in available:
                    if cm['name'] != dm['name']:
                        continue
                    if cm.get('class_name') != dm.get('class_name'):
                        continue
                    if cm.get('param_count', 0) != dm.get('param_count', 0):
                        continue
                    if dm.get('kind') == 'unused':
                        compatible.append(cm)
                        continue
                    if cm.get('kind') != dm.get('kind'):
                        continue
                    if (cm['kind'] in ('boolean', 'constant', 'null_return')
                            and cm.get('value') != dm.get('value')):
                        continue
                    compatible.append(cm)
                matched = min(
                    compatible,
                    key=lambda cm: abs(cm['decl_start'] - dm['decl_start']),
                    default=None)
                if matched is None:
                    continue
                available.remove(matched)

                if _has_same_file_refs(dm, matched, content):
                    continue
                src_abs = os.path.abspath(fp)
                poly = contracts.has_polymorphic_targets(dm.get('class_name'))
                if has_cross_file_refs(
                        dm, ref_index, src_abs,
                        contracts.children_map, contracts.iface_abstract,
                        polymorphic=poly,
                        content_cache=content_cache,
                        member_ref_index=scan.member_ref_index,
                        type_ref_index=scan.type_ref_index,
                        dynamic_ref_index=scan.dynamic_ref_index,
                        implicit_ref_index=scan.implicit_ref_index):
                    continue
                if contracts.is_contract_method(dm.get('class_name'), dm['name']):
                    continue
                ranges.append((matched['decl_start'], matched['decl_end']))
                matched_methods.append(matched)

            if ranges:
                new_content, cnt = delete_line_ranges(content, ranges)
                if cnt > 0:
                    deleted_names = {m['name'] for m in matched_methods}
                    dangling = verify_no_dangling_calls(new_content, deleted_names)
                    if dangling:
                        ui.warn(f"skipped deletion in "
                               f"{os.path.relpath(fp, root_dir)} "
                               f"(dangling refs: {dangling})", indent=4)
                    else:
                        validated = validate_transformation(
                            cb, new_content.encode('utf-8'), ext)
                        new_content = validated.decode(
                            'utf-8', errors='replace')
                    if not dangling and new_content != content:
                        with open(fp, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        files_modified.add(fp)
                        del_count += cnt
        except Exception as e:
            ui.warn(f"delete {fp}: {e}", indent=4)

    ui.progress_done()
    ui.info(f"Definition deletion complete: {del_count} deleted  "
            f"{ui.dim(ui.fmt_elapsed(time.time()-t_del))}")

    field_del = _cleanup_unused_fields(scan, files_modified, boundary=boundary)
    del_count += field_del

    total_elapsed = time.time() - t0
    ui.info(f"Total: {len(files_modified)} files modified  "
            f"{ui.dim(ui.fmt_elapsed(total_elapsed))}")
    clear_text_index_cache()
    return total_processed + del_count, files_modified


def _collect_unused_methods(scan, contracts, ref_index,
                            content_cache: dict[str, str] | None = None,
                            member_ref_index: dict[str, set[str]] | None = None,
                            type_ref_index: dict[str, set[str]] | None = None,
                            dynamic_ref_index: dict[str, set[str]] | None = None,
                            implicit_ref_index: dict[tuple[str, str], set[str]] | None = None,
                            boundary: ProjectBoundary | None = None,
                            ) -> list[dict]:
    """Find unused non-constant methods allowed by the language policy.

    Arbitrary method bodies are removed only when the owning adapter declares
    that all relevant reference forms are covered.  This is intentionally
    stricter than constant/empty cleanup: a visibility check alone cannot
    prove absence of implicit calls or callable-value references.
    """
    from ..analysis.contracts import is_safe_to_remove

    already = {
        (os.path.abspath(m['filepath']), m.get('class_name'), m['name'], m.get('param_count', 0))
        for m in scan.dead_methods
    }

    candidates: list[dict] = []
    for m in scan.all_methods:
        key = (os.path.abspath(m['filepath']), m.get('class_name'),
               m['name'], m.get('param_count', 0))
        if key in already:
            continue
        if m.get('class_type') in ('interface_declaration', 'enum_declaration'):
            continue
        if m.get('has_annotation'):
            continue
        adapter = get_adapter(os.path.splitext(m['filepath'])[1].lower())
        if (adapter is None
                or not adapter.can_prune_unreferenced_nonconstant(m)):
            continue
        mods = m.get('all_mods', set()) or set()
        if mods & {'abstract', 'open', 'override', 'native', 'Override'}:
            continue
        if contracts.is_contract_method(m.get('class_name'), m['name']):
            continue
        if not is_safe_to_remove(m, contracts, boundary=boundary):
            continue
        candidates.append(m)

    extra: list[dict] = []
    same_file_live = _batch_same_file_refs(
        candidates, content_cache, label="Checking local unused-method refs")
    for idx, m in enumerate(candidates):
        if (idx + 1) % 100 == 0 or idx + 1 == len(candidates):
            ui.progress(idx + 1, len(candidates),
                        "Checking cross-file method refs",
                        f"{len(extra)} unused", indent=4)
        fp = m['filepath']
        if _method_key(m) in same_file_live:
            continue
        src_abs = os.path.abspath(fp)
        poly = contracts.has_polymorphic_targets(m.get('class_name'))
        if has_cross_file_refs(m, ref_index, src_abs,
                               contracts.children_map, contracts.iface_abstract,
                               polymorphic=poly,
                               content_cache=content_cache,
                               member_ref_index=member_ref_index,
                               type_ref_index=type_ref_index,
                               dynamic_ref_index=dynamic_ref_index,
                               implicit_ref_index=implicit_ref_index):
            continue

        rec = dict(m)
        rec['kind'] = 'unused'
        rec['value'] = None
        rec['safe_to_inline'] = True
        rec['is_dead_candidate'] = True
        extra.append(rec)
    if candidates:
        ui.progress_done()
    return extra


_WORD_PAT = re.compile(r'\b(\w+)\b')


def _read_current(fp: str, files_modified: set[str],
                  scan: ProjectScanResult) -> str | None:
    """Return current content for *fp*: disk for modified files, cache otherwise."""
    if fp in files_modified:
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                return fh.read()
        except Exception:
            return None
    cc = scan.content_cache.get(fp)
    if cc is not None:
        return cc
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
            return fh.read()
    except Exception:
        return None


def _cleanup_unused_fields(scan: ProjectScanResult,
                           files_modified: set[str], *,
                           boundary: ProjectBoundary | None = None) -> int:
    """Remove unused final fields allowed by the project boundary.

    Uses word extraction + frozenset lookup instead of a huge alternation
    regex, making the scan O(text) instead of O(text × num_candidates).
    """
    ui.stage("Cleaning unused fields")
    t0 = time.time()

    fresh_fields: list[dict] = [
        f for f in scan.fields
        if f['filepath'] not in files_modified
    ]
    for fp in files_modified:
        ext = os.path.splitext(fp)[1].lower()
        try:
            with open(fp, 'rb') as fh:
                cb = fh.read()
            fresh_fields.extend(scan_fields(fp, cb, ext))
        except Exception:
            continue

    candidate_fields: list[dict] = []
    candidate_names: set[str] = set()
    for f in fresh_fields:
        if (f.get('has_annotation') or f.get('has_implicit_reference')
                or f.get('initializer_has_effects')):
            continue
        if not f.get('is_final'):
            continue
        # Open-world modules expose public/exported fields to unseen callers.
        # Closed-world modules may additionally remove unreferenced static
        # constants because every source consumer is inside the scan boundary.
        if (not f.get('is_private')
                and not (boundary is not None
                         and boundary.allows_external_api_pruning(f['filepath'])
                         and (f.get('is_static')
                              or f.get('class_name') is None))):
            continue
        if (f.get('has_generated_api')
                and (boundary is None
                     or not boundary.allows_external_api_pruning(f['filepath']))):
            continue
        candidate_fields.append(f)
        candidate_names.update(f.get('reference_names') or (f['name'],))

    if not candidate_names:
        ui.info(f"Unused-field cleanup: no candidates  "
                f"{ui.dim(ui.fmt_elapsed(time.time()-t0))}")
        return 0

    candidate_names_frozen = frozenset(candidate_names)

    # Build field_refs: word extraction + frozenset lookup.
    # Workers read from disk (OS page cache makes it fast).
    field_refs: dict[str, set[str]] = defaultdict(set)
    all_file_list = list(scan.all_files)
    n_workers = min(os.cpu_count() or 1,
                    max(1, len(all_file_list) // _MIN_PARALLEL))
    if n_workers > 1 and len(all_file_list) >= _MIN_PARALLEL:
        target_chunks = min(len(all_file_list), n_workers * 8)
        chunk_sz = max(1, (len(all_file_list) + target_chunks - 1)
                       // target_chunks)
        chunks = [all_file_list[i:i + chunk_sz]
                  for i in range(0, len(all_file_list), chunk_sz)]
        cand_list = list(candidate_names)
        try:
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                futs = {ex.submit(_scan_field_refs_worker, (c, cand_list)): c
                        for c in chunks}
                completed = 0
                for fut in as_completed(futs):
                    for name, fps in fut.result().items():
                        field_refs[name].update(fps)
                    completed += len(futs[fut])
                    ui.progress(completed, len(all_file_list),
                                "Scanning field references")
            ui.progress_done()
        except Exception:
            ui.progress_done()
            ui.warn("Parallel field-reference scan failed; retrying sequentially")
            for idx, fp in enumerate(all_file_list):
                ui.progress(idx + 1, len(all_file_list),
                            "Scanning field references")
                content = _read_current(fp, files_modified, scan)
                if content is None:
                    continue
                for word in _WORD_PAT.findall(content):
                    if word in candidate_names_frozen:
                        field_refs[word].add(fp)
            ui.progress_done()
    else:
        for idx, fp in enumerate(all_file_list):
            ui.progress(idx + 1, len(all_file_list),
                        "Scanning field references")
            content = _read_current(fp, files_modified, scan)
            if content is None:
                continue
            for word in _WORD_PAT.findall(content):
                if word in candidate_names_frozen:
                    field_refs[word].add(fp)
        ui.progress_done()

    # Group candidates by file for batched same-file ref checking.
    candidates_by_file: dict[str, list[dict]] = {}
    for f in candidate_fields:
        reference_names = f.get('reference_names') or (f['name'],)
        refs: set[str] = set()
        for reference_name in reference_names:
            refs.update(field_refs.get(reference_name, ()))
        src_abs = os.path.abspath(f['filepath'])
        if any(os.path.abspath(r) != src_abs for r in refs):
            continue
        candidates_by_file.setdefault(f['filepath'], []).append(f)

    unused_fields: list[dict] = []
    total_candidate_files = len(candidates_by_file)
    for idx, (fp, fields) in enumerate(candidates_by_file.items()):
        content = _read_current(fp, files_modified, scan)
        if content is None:
            continue
        lines = content.split('\n')
        for f in fields:
            if not _field_has_same_file_refs_lines(
                    f.get('reference_names') or (f['name'],), lines,
                                                    f['decl_start'], f['decl_end']):
                unused_fields.append(f)
        ui.progress(idx + 1, total_candidate_files,
                    "Validating field candidates",
                    f"{len(unused_fields)} unused")
    if total_candidate_files:
        ui.progress_done()

    # A single declaration can define multiple fields (``A = 1, B = 2``).
    # Its line range may be deleted only when every field in that declaration
    # is eligible and unused.  Deleting the range for just B would also remove
    # a live A and leave dangling references.
    def field_key(field: dict) -> tuple:
        return (field['filepath'], field['decl_start'], field['decl_end'],
                field['name'])

    all_by_declaration: dict[tuple, list[dict]] = defaultdict(list)
    for field in fresh_fields:
        decl_key = (field['filepath'], field['decl_start'], field['decl_end'])
        all_by_declaration[decl_key].append(field)
    eligible_keys = {field_key(field) for field in candidate_fields}
    unused_keys = {field_key(field) for field in unused_fields}

    by_file: dict[str, list[dict]] = defaultdict(list)
    for decl_key, declared_fields in all_by_declaration.items():
        keys = {field_key(field) for field in declared_fields}
        if keys and keys <= eligible_keys and keys <= unused_keys:
            by_file[decl_key[0]].append(declared_fields[0])

    deleted = 0
    for fp, fields in by_file.items():
        try:
            with open(fp, 'rb') as fh:
                original_bytes = fh.read()
            content = original_bytes.decode('utf-8', errors='replace')
            ranges = [(f['decl_start'], f['decl_end']) for f in fields]
            new_content, cnt = delete_line_ranges(content, ranges)
            if cnt > 0 and new_content != content:
                ext = os.path.splitext(fp)[1].lower()
                validated = validate_transformation(
                    original_bytes, new_content.encode('utf-8'), ext)
                if validated == original_bytes:
                    ui.warn(
                        f"skipped field deletion in {fp} "
                        f"(would introduce AST errors)", indent=4)
                    continue
                with open(fp, 'w', encoding='utf-8') as fh:
                    fh.write(validated.decode('utf-8', errors='replace'))
                files_modified.add(fp)
                deleted += cnt
        except Exception as e:
            ui.warn(f"field delete {fp}: {e}", indent=4)

    ui.info(f"Unused-field cleanup complete: {deleted} deleted  "
            f"{ui.dim(ui.fmt_elapsed(time.time()-t0))}")
    return deleted


def _field_has_same_file_refs_lines(names, lines: list[str],
                                     decl_start: int, decl_end: int) -> bool:
    """Check if any source/generated field name appears outside its span.

    Accepts pre-split *lines* so multiple fields in the same file share
    one ``split('\\n')`` call.
    """
    alternatives = '|'.join(re.escape(name) for name in names)
    pat = re.compile(r'\b(?:' + alternatives + r')\b')
    for i, line in enumerate(lines):
        if decl_start <= i <= decl_end:
            continue
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('/*'):
            continue
        if pat.search(line):
            return True
    return False


def _promote_unreferenced(
        all_dead, ref_index, contracts,
        content_cache: dict[str, str] | None = None,
        member_ref_index: dict[str, set[str]] | None = None,
        type_ref_index: dict[str, set[str]] | None = None,
        dynamic_ref_index: dict[str, set[str]] | None = None,
        implicit_ref_index: dict[tuple[str, str], set[str]] | None = None,
        boundary: ProjectBoundary | None = None):
    candidates = [dm for dm in all_dead if not dm.get('safe_to_inline')]
    same_file_live = _batch_same_file_refs(
        candidates, content_cache, label="Checking local promotion refs")
    promoted = 0
    for i, dm in enumerate(candidates):
        if (i + 1) % 200 == 0:
            ui.progress(i + 1, len(candidates), "Pre-checking",
                        f"{promoted} promoted", indent=4)
        fp = dm['filepath']
        has_ref = _method_key(dm) in same_file_live

        if not has_ref:
            src_abs = os.path.abspath(fp)
            poly = contracts.has_polymorphic_targets(dm.get('class_name'))
            if has_cross_file_refs(
                    dm, ref_index, src_abs,
                    contracts.children_map, contracts.iface_abstract,
                    polymorphic=poly,
                    content_cache=content_cache,
                    member_ref_index=member_ref_index,
                    type_ref_index=type_ref_index,
                    dynamic_ref_index=dynamic_ref_index,
                    implicit_ref_index=implicit_ref_index):
                has_ref = True

        if promote_unreferenced(
                dm, contracts, has_ref, boundary=boundary):
            dm['safe_to_inline'] = True
            promoted += 1

    if len(candidates) >= 200:
        ui.progress_done()
    if promoted:
        ui.info(f"Promoted {promoted} unreferenced methods", indent=4)


def _has_same_file_refs(dm: dict, cm: dict, content: str) -> bool:
    method_name = dm['name']
    param_count = dm.get('param_count', 0)
    decl_start, decl_end = cm['decl_start'], cm['decl_end']
    lines = content.split('\n')
    if param_count == 0:
        call_pat = re.compile(r'(?<!\w)' + re.escape(method_name) + r'\s*\(\s*\)')
    else:
        call_pat = re.compile(r'(?<!\w)' + re.escape(method_name) + r'\s*\(')
    ref_pat = re.compile(r'::' + re.escape(method_name) + r'\b')
    adapter = get_adapter(os.path.splitext(dm.get('filepath', ''))[1].lower())
    implicit_patterns = adapter.implicit_reference_patterns if adapter else ()
    offset = 0
    for i, line in enumerate(lines):
        if decl_start <= i <= decl_end:
            offset += len(line) + 1
            continue
        if line.strip().startswith('//') or line.strip().startswith('/*'):
            offset += len(line) + 1
            continue
        if (call_pat.search(line) or ref_pat.search(line)
                or has_dynamic_symbol_ref(line, method_name)):
            return True
        for pattern in implicit_patterns:
            for match in pattern.finditer(line):
                if (match.group(1) == method_name
                        and not is_in_comment_or_string(
                            content, offset + match.start(1))):
                    return True
        offset += len(line) + 1
    return False


_ANY_CALL_PAT = re.compile(r'(?<!\w)([A-Za-z_]\w*)\s*\(')
_ANY_METHOD_REF_PAT = re.compile(r'::([A-Za-z_]\w*)\b')


def _batch_same_file_refs(
        candidates: list[dict],
        content_cache: dict[str, str] | None = None,
        *, label: str = "Checking local references") -> set[tuple]:
    """Return candidate keys referenced outside their declaration spans.

    Each source file is scanned once regardless of how many candidate
    methods it declares.  The previous implementation split and searched
    a large file once per candidate, which became quadratic for controller
    and utility classes with hundreds of methods.
    """
    by_file: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        by_file[candidate['filepath']].append(candidate)

    live: set[tuple] = set()
    total_files = len(by_file)
    for idx, (fp, methods) in enumerate(by_file.items()):
        content = (content_cache or {}).get(fp)
        if content is None:
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
            except Exception:
                ui.progress(idx + 1, total_files, label,
                            f"{len(live)} referenced", indent=4)
                continue

        wanted = {m['name'] for m in methods}
        adapter = get_adapter(os.path.splitext(fp)[1].lower())
        reference_patterns = [_ANY_CALL_PAT, _ANY_METHOD_REF_PAT]
        if adapter:
            reference_patterns.extend(adapter.implicit_call_patterns)
            reference_patterns.extend(adapter.implicit_reference_patterns)
        call_lines: dict[str, set[int]] = defaultdict(set)
        offset = 0
        for line_no, line in enumerate(content.splitlines(keepends=True)):
            for pattern in reference_patterns:
                for match in pattern.finditer(line):
                    name = match.group(1)
                    if name not in wanted:
                        continue
                    if is_in_comment_or_string(content, offset + match.start()):
                        continue
                    call_lines[name].add(line_no)
            offset += len(line)

        for method in methods:
            start, end = method['decl_start'], method['decl_end']
            if any(line_no < start or line_no > end
                   for line_no in call_lines.get(method['name'], ())):
                live.add(_method_key(method))
        dynamic_names = set(iter_dynamic_reference_names(content))
        if dynamic_names:
            for method in methods:
                if method['name'] in dynamic_names:
                    live.add(_method_key(method))
        ui.progress(idx + 1, total_files, label,
                    f"{len(live)} referenced", indent=4)
    if total_files:
        ui.progress_done()
    return live
