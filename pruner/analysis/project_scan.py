"""Unified project scanner — single-pass collection of all analysis data.

Replaces separate full-project traversals (method scan, reference index,
class hierarchy, field scan) with one pass that reads each file once.
Module-aware scanning is provided by ``ProjectLayout``.

When the project has more than ~500 source files, scanning is parallelised
across multiple CPU cores via ``ProcessPoolExecutor``, merging partial
results in the main process.
"""

import os
import re
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

from ..lang import _PARSERS, SKIP_DIRS
from .. import lang as _lang
from .. import ui
from ..ast_utils import parse, build_line_offsets
from .method_scanner import scan_method_definitions
from .field_scanner import scan_fields
from .ref_index import (
    REFERENCE_EXTS, iter_dynamic_reference_names, iter_reference_names,
    iter_type_identifiers,
)
from .project_layout import ProjectLayout
from .contracts import ContractGraph


# ── Worker for parallel scan ────────────────────────────────────

def _scan_file_chunk(file_infos):
    """Process a chunk of files in a worker process.

    *file_infos* is a list of ``(filepath, ext, module_name)`` tuples.
    Returns method/field data plus call, type, and dynamic-reference indices.
    """
    methods = []
    fields_list = []
    ref_index: dict[str, set[str]] = defaultdict(set)
    type_ref_index: dict[str, set[str]] = defaultdict(set)
    dynamic_ref_index: dict[str, set[str]] = defaultdict(set)
    contracts = ContractGraph()
    content_cache: dict[str, str] = {}

    for fp, ext, mod_name in file_infos:
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
        except Exception:
            continue

        content = cb.decode('utf-8', errors='replace')
        content_cache[fp] = content
        _lang._current_ext = ext

        root_node, _ = parse(cb)
        line_offsets = build_line_offsets(cb)

        try:
            file_methods = scan_method_definitions(
                fp, cb, ext, module=mod_name,
                root_node=root_node, line_offsets=line_offsets)
            methods.extend(file_methods)
        except Exception:
            pass

        fields_list.extend(
            scan_fields(fp, cb, ext, module=mod_name,
                        root_node=root_node, line_offsets=line_offsets))

        for name in iter_reference_names(content):
            ref_index[name].add(fp)
        for name in iter_type_identifiers(content):
            type_ref_index[name].add(fp)
        for name in iter_dynamic_reference_names(content):
            dynamic_ref_index[name].add(fp)

        contracts.ingest_file(content)

    return (methods, fields_list, dict(ref_index), dict(type_ref_index),
            dict(dynamic_ref_index), contracts, content_cache)


# ── Result container ────────────────────────────────────────────

class ProjectScanResult:
    """Container for all data collected during a unified project scan."""

    __slots__ = (
        'all_files', 'ref_files', 'dead_methods', 'all_methods', 'fields',
        'variant_conflicts', 'ref_index', 'type_ref_index',
        'dynamic_ref_index',
        'children_map', 'final_classes', 'iface_abstract',
        'implements', 'contracts', 'layout', 'elapsed',
        'content_cache',
    )

    def __init__(self):
        self.all_files: list[str] = []
        self.ref_files: list[str] = []
        self.dead_methods: list[dict] = []
        self.all_methods: list[dict] = []
        self.fields: list[dict] = []
        self.variant_conflicts: set[tuple] = set()
        self.ref_index: dict[str, set[str]] = defaultdict(set)
        self.type_ref_index: dict[str, set[str]] = defaultdict(set)
        self.dynamic_ref_index: dict[str, set[str]] = defaultdict(set)
        self.children_map: dict[str, set[str]] = defaultdict(set)
        self.final_classes: set[str] = set()
        self.iface_abstract: set[str] = set()
        self.implements: set[str] = set()
        self.contracts: ContractGraph = ContractGraph()
        self.layout: ProjectLayout | None = None
        self.elapsed: float = 0.0
        self.content_cache: dict[str, str] = {}

    # ── Incremental update ──────────────────────────────────────

    def update_files(self, modified_files: set[str]) -> None:
        """Re-scan only *modified_files*, updating all indices in place.

        Avoids a full re-read of the entire project for subsequent rounds.
        """
        t0 = time.time()
        ui.info(f"Incremental scan: preparing {len(modified_files)} modified files...")
        modified_abs = {os.path.abspath(fp) for fp in modified_files}

        self.all_methods = [m for m in self.all_methods
                           if os.path.abspath(m['filepath']) not in modified_abs]
        self.dead_methods = [m for m in self.dead_methods
                            if os.path.abspath(m['filepath']) not in modified_abs]
        self.fields = [f for f in self.fields
                      if os.path.abspath(f['filepath']) not in modified_abs]

        # Batch set subtraction: O(ref_index_size) Python iterations
        # instead of O(ref_index_size × modified_files) nested loop.
        modified_set = set(modified_files)
        for name_set in self.ref_index.values():
            name_set -= modified_set
        for name_set in self.type_ref_index.values():
            name_set -= modified_set
        for name_set in self.dynamic_ref_index.values():
            name_set -= modified_set
        for fp in modified_files:
            self.content_cache.pop(fp, None)

        deleted = [fp for fp in modified_files if not os.path.exists(fp)]
        for fp in deleted:
            if fp in self.all_files:
                self.all_files.remove(fp)
            if fp in self.ref_files:
                self.ref_files.remove(fp)

        alive = [fp for fp in modified_files if os.path.exists(fp)]
        supported = frozenset(_PARSERS.keys())
        file_infos = []
        for fp in alive:
            ext = os.path.splitext(fp)[1].lower()
            if ext in supported:
                mod_name = self.layout.get_module(fp) if self.layout else None
                file_infos.append((fp, ext, mod_name))

        # Incremental rounds contain far fewer files than the initial scan,
        # but each file still pays full tree-sitter/method/field/contract
        # analysis cost.  The old 500-file threshold forced typical
        # 38–223-file rounds onto one core (22s–2m12s in the real project).
        n_workers = min(os.cpu_count() or 1,
                        max(1, (len(file_infos) + _INCREMENTAL_FILES_PER_WORKER - 1)
                            // _INCREMENTAL_FILES_PER_WORKER))
        if (n_workers > 1
                and len(file_infos) >= _MIN_INCREMENTAL_FILES_FOR_PARALLEL):
            target_chunks = min(len(file_infos), n_workers * 4)
            chunk_sz = max(1, (len(file_infos) + target_chunks - 1) // target_chunks)
            chunks = [file_infos[i:i + chunk_sz]
                      for i in range(0, len(file_infos), chunk_sz)]
            try:
                partials = []
                completed = 0
                with ProcessPoolExecutor(max_workers=n_workers) as executor:
                    futures = {executor.submit(_scan_file_chunk, c): len(c)
                               for c in chunks}
                    for future in as_completed(futures):
                        partials.append(future.result())
                        completed += futures[future]
                        ui.progress(completed, len(file_infos),
                                    "Incremental scanning")
                ui.progress_done()
                ui.info("Merging incremental analysis indices...")
                # Merge only after every worker succeeded.  If one worker
                # fails, the sequential fallback must not duplicate records
                # already merged from completed workers.
                for partial in partials:
                    (methods, fields, ref_idx, type_idx, dynamic_idx,
                     contracts, cc) = partial
                    for m in methods:
                        self.all_methods.append(m)
                        if m.get('is_dead_candidate'):
                            self.dead_methods.append(m)
                    self.fields.extend(fields)
                    for name, fps in ref_idx.items():
                        self.ref_index[name].update(fps)
                    for name, fps in type_idx.items():
                        self.type_ref_index[name].update(fps)
                    for name, fps in dynamic_idx.items():
                        self.dynamic_ref_index[name].update(fps)
                    self.contracts.merge(contracts)
                    self.content_cache.update(cc)
            except Exception:
                ui.progress_done()
                ui.warn("Parallel incremental scan failed; retrying sequentially")
                self._update_files_sequential(file_infos, show_progress=True)
        else:
            self._update_files_sequential(file_infos, show_progress=True)

        self._recompute_variants()
        self._sync_contract_mirrors()
        dt = time.time() - t0
        ui.info(f"Incremental update: {len(file_infos)} files re-scanned  "
                f"{ui.dim(ui.fmt_elapsed(dt))}")

    def _update_files_sequential(self, file_infos: list,
                                 *, show_progress: bool = False) -> None:
        """Sequential fallback for update_files re-scanning."""
        total = len(file_infos)
        interval = max(1, total // 20)
        for idx, (fp, ext, mod_name) in enumerate(file_infos):
            try:
                with open(fp, 'rb') as f:
                    cb = f.read()
            except Exception:
                continue
            content = cb.decode('utf-8', errors='replace')
            self.content_cache[fp] = content
            _lang._current_ext = ext
            root_node, _ = parse(cb)
            line_offsets = build_line_offsets(cb)
            methods = scan_method_definitions(
                fp, cb, ext, module=mod_name,
                root_node=root_node, line_offsets=line_offsets)
            for method in methods:
                self.all_methods.append(method)
                if method.get('is_dead_candidate'):
                    self.dead_methods.append(method)
            self.fields.extend(
                scan_fields(fp, cb, ext, module=mod_name,
                            root_node=root_node, line_offsets=line_offsets))
            for name in iter_reference_names(content):
                self.ref_index[name].add(fp)
            for name in iter_type_identifiers(content):
                self.type_ref_index[name].add(fp)
            for name in iter_dynamic_reference_names(content):
                self.dynamic_ref_index[name].add(fp)
            self.contracts.ingest_file(content)
            if show_progress and ((idx + 1) % interval == 0 or idx + 1 == total):
                ui.progress(idx + 1, total, "Incremental scanning")
        if show_progress:
            ui.progress_done()

    def _recompute_variants(self) -> None:
        method_defs_by_key: dict[tuple, list[dict]] = defaultdict(list)
        for m in self.all_methods:
            key = semantic_method_key(m)
            method_defs_by_key[key].append(m)
        self.variant_conflicts = set()
        for key, methods in method_defs_by_key.items():
            source_sets = {m.get('source_set') for m in methods if m.get('source_set')}
            candidate_shapes = {
                (m.get('kind'), m.get('value')) for m in methods if m.get('is_dead_candidate')
            }
            has_non_candidate = any(not m.get('is_dead_candidate') for m in methods)
            has_multiple_shapes = len(candidate_shapes) > 1
            has_source_set_variants = len(source_sets) > 1
            if len(methods) > 1 and (has_source_set_variants or has_non_candidate
                                     or has_multiple_shapes):
                self.variant_conflicts.add(key)

    def _sync_contract_mirrors(self) -> None:
        """Keep legacy attribute mirrors in sync with ContractGraph."""
        g = self.contracts
        self.children_map = g.children_map
        self.final_classes = g.final_classes
        self.iface_abstract = g.iface_abstract
        self.implements = g.implements


# ── Parallel scan helpers ───────────────────────────────────────

def _scan_parallel(result: ProjectScanResult, file_infos: list,
                   n_workers: int) -> None:
    """Scatter file chunks across workers and merge results."""
    total = len(file_infos)
    # More chunks than workers keep all cores fed and provide frequent
    # progress updates instead of one update per 12.5% worker-sized chunk.
    target_chunks = min(total, n_workers * 8)
    chunk_size = max(1, (total + target_chunks - 1) // target_chunks)
    chunks = [file_infos[i:i + chunk_size]
              for i in range(0, total, chunk_size)]

    ui.info(f"Parallel scan: {n_workers} workers, {len(chunks)} progress chunks")

    dead_count = 0
    completed_files = 0

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(_scan_file_chunk, chunk): len(chunk)
                   for chunk in chunks}
        for future in as_completed(futures):
            chunk_len = futures[future]
            (methods, fields, ref_idx, type_idx, dynamic_idx,
             contracts, content_cache) = future.result()

            for m in methods:
                result.all_methods.append(m)
                if m.get('is_dead_candidate'):
                    result.dead_methods.append(m)
                    dead_count += 1

            result.fields.extend(fields)

            for name, fps in ref_idx.items():
                result.ref_index[name].update(fps)
            for name, fps in type_idx.items():
                result.type_ref_index[name].update(fps)
            for name, fps in dynamic_idx.items():
                result.dynamic_ref_index[name].update(fps)

            result.contracts.merge(contracts)
            result.content_cache.update(content_cache)

            completed_files += chunk_len
            ui.progress(completed_files, total, "Scanning",
                        f"{dead_count} dead methods, "
                        f"{len(result.ref_index)} refs")


def _scan_sequential(result: ProjectScanResult, file_infos: list,
                     progress_interval: int) -> None:
    """Single-process scan (small projects or fallback)."""
    total = len(file_infos)
    dead_count = 0

    for idx, (fp, ext, mod_name) in enumerate(file_infos):
        if (idx + 1) % progress_interval == 0 or idx + 1 == total:
            ui.progress(idx + 1, total, "Scanning",
                        f"{dead_count} dead methods, "
                        f"{len(result.ref_index)} refs")

        try:
            with open(fp, 'rb') as f:
                cb = f.read()
        except Exception:
            continue

        content = cb.decode('utf-8', errors='replace')
        result.content_cache[fp] = content
        _lang._current_ext = ext

        root_node, _ = parse(cb)
        line_offsets = build_line_offsets(cb)

        try:
            methods = scan_method_definitions(
                fp, cb, ext, module=mod_name,
                root_node=root_node, line_offsets=line_offsets)
            for method in methods:
                result.all_methods.append(method)
                if method.get('is_dead_candidate'):
                    result.dead_methods.append(method)
                    dead_count += 1
        except Exception as e:
            ui.warn(f"scan {fp}: {e}")

        result.fields.extend(
            scan_fields(fp, cb, ext, module=mod_name,
                        root_node=root_node, line_offsets=line_offsets))

        for name in iter_reference_names(content):
            result.ref_index[name].add(fp)
        for name in iter_type_identifiers(content):
            result.type_ref_index[name].add(fp)
        for name in iter_dynamic_reference_names(content):
            result.dynamic_ref_index[name].add(fp)

        result.contracts.ingest_file(content)


def _compute_variant_conflicts(result: ProjectScanResult) -> None:
    """Build variant_conflicts from the merged all_methods list."""
    method_defs_by_key: dict[tuple, list[dict]] = defaultdict(list)
    for m in result.all_methods:
        key = semantic_method_key(m)
        method_defs_by_key[key].append(m)

    for key, methods in method_defs_by_key.items():
        source_sets = {m.get('source_set') for m in methods if m.get('source_set')}
        candidate_shapes = {
            (m.get('kind'), m.get('value')) for m in methods
            if m.get('is_dead_candidate')
        }
        has_non_candidate = any(not m.get('is_dead_candidate') for m in methods)
        has_multiple_shapes = len(candidate_shapes) > 1
        has_source_set_variants = len(source_sets) > 1
        if len(methods) > 1 and (has_source_set_variants or has_non_candidate
                                 or has_multiple_shapes):
            result.variant_conflicts.add(key)


# ── Public API ──────────────────────────────────────────────────

_MIN_FILES_FOR_PARALLEL = 500
_MIN_INCREMENTAL_FILES_FOR_PARALLEL = 25
_INCREMENTAL_FILES_PER_WORKER = 20


def scan_project(root_dir: str, *, progress_interval: int = 500) -> ProjectScanResult:
    """Walk *root_dir* once and collect method scan, fields, reference index,
    and contract graph data in a single pass.

    For projects with ≥500 source files, scanning is automatically
    parallelised across all available CPU cores.
    """
    t0 = time.time()
    result = ProjectScanResult()
    layout = ProjectLayout(root_dir)
    result.layout = layout
    ui.kv("Project layout", f"{layout.kind} ({len(layout.modules)} module(s))")
    if len(layout.modules) > 1:
        for mod_name in layout.modules:
            ui.info(f"  · {mod_name}", indent=4)
    supported = frozenset(_PARSERS.keys())

    for dp, dns, fns in os.walk(root_dir):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in supported:
                fp = os.path.join(dp, fn)
                result.all_files.append(fp)
                result.ref_files.append(fp)
            elif ext in REFERENCE_EXTS:
                result.ref_files.append(os.path.join(dp, fn))

    total = len(result.all_files)
    ui.info(f"Unified scan: {total} source files")

    # Pre-compute module names in the main process (cheap, needs layout)
    file_infos = [(fp, os.path.splitext(fp)[1].lower(), layout.get_module(fp))
                  for fp in result.all_files]

    n_workers = min(os.cpu_count() or 1, max(1, total // 200))

    if n_workers > 1 and total >= _MIN_FILES_FOR_PARALLEL:
        try:
            _scan_parallel(result, file_infos, n_workers)
        except Exception as e:
            ui.warn(f"Parallel scan failed ({e}), falling back to sequential")
            result.all_methods.clear()
            result.dead_methods.clear()
            result.fields.clear()
            result.ref_index.clear()
            result.type_ref_index.clear()
            result.dynamic_ref_index.clear()
            result.contracts = ContractGraph()
            result.content_cache.clear()
            _scan_sequential(result, file_infos, progress_interval)
    else:
        _scan_sequential(result, file_infos, progress_interval)

    ui.progress_done()
    ui.info("Finalizing reference, variant, and hierarchy indices...")

    # Reference-only files (storyboards, XML, JSON, etc.)
    source_set = set(result.all_files)
    for fp in result.ref_files:
        if fp in source_set:
            continue
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
        result.content_cache[fp] = content
        for name in iter_reference_names(content):
            result.ref_index[name].add(fp)
        for name in iter_type_identifiers(content):
            result.type_ref_index[name].add(fp)
        for name in iter_dynamic_reference_names(content):
            result.dynamic_ref_index[name].add(fp)

    _compute_variant_conflicts(result)
    result._sync_contract_mirrors()

    result.elapsed = time.time() - t0
    dead_count = len(result.dead_methods)
    ui.info(f"Scan complete: {dead_count} dead methods, "
            f"{len(result.children_map)} class hierarchies  "
            f"{ui.dim(ui.fmt_elapsed(result.elapsed))}")
    return result


def semantic_method_key(method: dict) -> tuple:
    """Module-aware, source-set independent method identity."""
    return (
        method.get('module'),
        method.get('package_name'),
        method.get('class_name'),
        method.get('name'),
        method.get('param_count', 0),
    )


def build_identifier_index(all_files: list[str],
                           content_cache: dict[str, str] | None = None,
                           ) -> dict[str, set[str]]:
    """Build ``{identifier: {filepath}}`` for bare name occurrences.

    When *content_cache* is provided, file contents are read from cache
    instead of disk — avoids a full re-read of the project.
    """
    pat = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]{2,})\b')
    index: dict[str, set[str]] = defaultdict(set)
    for fp in all_files:
        content = content_cache.get(fp) if content_cache else None
        if content is None:
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue
        for m in pat.finditer(content):
            index[m.group(1)].add(fp)
    return index
