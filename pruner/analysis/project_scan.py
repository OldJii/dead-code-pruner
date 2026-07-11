"""Unified project scanner — single-pass collection of all analysis data.

Replaces three separate full-project traversals (method scan, reference
index, class hierarchy) with one pass that reads each file exactly once.
Module-aware scanning is provided by ``ProjectLayout`` to avoid conflating
same-named methods across different modules in multi-module projects.
"""

import os
import re
import sys
import time
from collections import defaultdict

from ..lang import _PARSERS, SKIP_DIRS
from .. import ui
from .method_scanner import scan_method_definitions
from .ref_index import REFERENCE_EXTS, iter_reference_names
from .project_layout import ProjectLayout


_EXTENDS    = re.compile(r'\b(?:final\s+)?(?:class|object)\s+(\w+)\s*(?::|extends)\s+(\w+)')
_FINAL_CLS  = re.compile(r'\bfinal\s+class\s+(\w+)')
_IFACE_ABS  = re.compile(r'\b(?:interface|protocol|abstract\s+class)\s+(\w+)')
_IMPL       = re.compile(r'\bclass\s+(\w+)[^{]*\bimplements\s+')


class ProjectScanResult:
    """Container for all data collected during a unified project scan."""

    __slots__ = ('all_files', 'ref_files', 'dead_methods', 'variant_conflicts', 'ref_index',
                 'children_map', 'final_classes', 'iface_abstract',
                 'implements', 'layout', 'elapsed')

    def __init__(self):
        self.all_files: list[str]               = []
        self.ref_files: list[str]               = []
        self.dead_methods: list[dict]            = []
        self.variant_conflicts: set[tuple]       = set()
        self.ref_index: dict[str, set[str]]      = defaultdict(set)
        self.children_map: dict[str, set[str]]   = defaultdict(set)
        self.final_classes: set[str]             = set()
        self.iface_abstract: set[str]            = set()
        self.implements: set[str]                = set()
        self.layout: ProjectLayout | None        = None
        self.elapsed: float                      = 0.0


def scan_project(root_dir: str, *, progress_interval: int = 500) -> ProjectScanResult:
    """Walk *root_dir* once and collect method scan, reference index,
    and class hierarchy data in a single pass.

    Detects multi-module project layout and includes module identity in
    method records so that same-named methods across modules are not
    conflated.  Prints progress every *progress_interval* files.
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

    # Phase A: collect source files and semantic reference files.
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
    dead_count = 0
    method_defs_by_key: dict[tuple, list[dict]] = defaultdict(list)
    ui.info(f"Unified scan: {total} source files")

    # Phase B: single-pass analysis
    for idx, fp in enumerate(result.all_files):
        if (idx + 1) % progress_interval == 0 or idx + 1 == total:
            ui.progress(idx + 1, total, "Scanning",
                        f"{dead_count} dead methods, {len(result.ref_index)} refs")

        ext = os.path.splitext(fp)[1].lower()
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
        except Exception:
            continue

        content = cb.decode('utf-8', errors='replace')

        # 1) Method scan (module-aware)
        try:
            mod_name = layout.get_module(fp)
            methods = scan_method_definitions(fp, cb, ext, module=mod_name)
            for method in methods:
                key = semantic_method_key(method)
                method_defs_by_key[key].append(method)
                if method.get('is_dead_candidate'):
                    result.dead_methods.append(method)
                    dead_count += 1
        except Exception as e:
            ui.warn(f"scan {fp}: {e}")

        # 2) Reference index (method calls + method references)
        for name in iter_reference_names(content):
            if len(name) > 2:
                result.ref_index[name].add(fp)

        # 3) Class hierarchy
        for m in _EXTENDS.finditer(content):
            result.children_map[m.group(2)].add(m.group(1))
        for m in _FINAL_CLS.finditer(content):
            result.final_classes.add(m.group(1))
        for m in _IFACE_ABS.finditer(content):
            result.iface_abstract.add(m.group(1))
        for m in _IMPL.finditer(content):
            result.implements.add(m.group(1))

    # Phase C: include non-source semantic references, e.g. Storyboard/XIB selectors.
    source_set = set(result.all_files)
    for fp in result.ref_files:
        if fp in source_set:
            continue
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
        for name in iter_reference_names(content):
            if len(name) > 2:
                result.ref_index[name].add(fp)

    for key, methods in method_defs_by_key.items():
        source_sets = {m.get('source_set') for m in methods if m.get('source_set')}
        candidate_shapes = {(m.get('kind'), m.get('value')) for m in methods if m.get('is_dead_candidate')}
        has_non_candidate = any(not m.get('is_dead_candidate') for m in methods)
        has_multiple_shapes = len(candidate_shapes) > 1
        has_source_set_variants = len(source_sets) > 1
        if len(methods) > 1 and (has_source_set_variants or has_non_candidate or has_multiple_shapes):
            result.variant_conflicts.add(key)

    result.elapsed = time.time() - t0
    ui.progress_done()
    ui.info(f"Scan complete: {dead_count} dead methods, "
            f"{len(result.children_map)} class hierarchies  "
            f"{ui.dim(ui.fmt_elapsed(result.elapsed))}")
    return result


def semantic_method_key(method: dict) -> tuple:
    """Module-aware, source-set independent method identity.

    Including the module prevents conflation of same-named methods across
    different Gradle sub-projects, Go modules, or Dart packages.
    """
    return (
        method.get('module'),
        method.get('package_name'),
        method.get('class_name'),
        method.get('name'),
        method.get('param_count', 0),
    )
