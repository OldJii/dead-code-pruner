"""Unified project scanner — single-pass collection of all analysis data.

Replaces three separate full-project traversals (method scan, reference
index, class hierarchy) with one pass that reads each file exactly once.
"""

import os
import re
import sys
import time
from collections import defaultdict

from ..lang import _PARSERS, SKIP_DIRS
from .method_scanner import scan_method_definitions
from .ref_index import REFERENCE_EXTS, iter_reference_names


_EXTENDS    = re.compile(r'\b(?:final\s+)?(?:class|object)\s+(\w+)\s*(?::|extends)\s+(\w+)')
_FINAL_CLS  = re.compile(r'\bfinal\s+class\s+(\w+)')
_IFACE_ABS  = re.compile(r'\b(?:interface|protocol|abstract\s+class)\s+(\w+)')
_IMPL       = re.compile(r'\bclass\s+(\w+)[^{]*\bimplements\s+')


class ProjectScanResult:
    """Container for all data collected during a unified project scan."""

    __slots__ = ('all_files', 'ref_files', 'dead_methods', 'variant_conflicts', 'ref_index',
                 'children_map', 'final_classes', 'iface_abstract',
                 'implements', 'elapsed')

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
        self.elapsed: float                      = 0.0


def scan_project(root_dir: str, *, progress_interval: int = 500) -> ProjectScanResult:
    """Walk *root_dir* once and collect method scan, reference index,
    and class hierarchy data in a single pass.

    Prints progress every *progress_interval* files.
    """
    t0 = time.time()
    result = ProjectScanResult()
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
    print(f"  Unified scan: {total} source files")

    # Phase B: single-pass analysis
    for idx, fp in enumerate(result.all_files):
        if (idx + 1) % progress_interval == 0 or idx + 1 == total:
            pct = (idx + 1) * 100 // total
            print(f"\r  Scanning... {idx+1}/{total} ({pct}%)  "
                  f"[{dead_count} dead methods, "
                  f"{len(result.ref_index)} unique calls]",
                  end='', flush=True)

        ext = os.path.splitext(fp)[1].lower()
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
        except Exception:
            continue

        content = cb.decode('utf-8', errors='replace')

        # 1) Method scan
        try:
            methods = scan_method_definitions(fp, cb, ext)
            for method in methods:
                key = semantic_method_key(method)
                method_defs_by_key[key].append(method)
                if method.get('is_dead_candidate'):
                    result.dead_methods.append(method)
                    dead_count += 1
        except Exception as e:
            print(f"\n  WARN scan {fp}: {e}", file=sys.stderr)

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
        candidate_shapes = {(m.get('kind'), m.get('value')) for m in methods if m.get('is_dead_candidate')}
        has_non_candidate = any(not m.get('is_dead_candidate') for m in methods)
        has_multiple_shapes = len(candidate_shapes) > 1
        if len(methods) > 1 and (has_non_candidate or has_multiple_shapes):
            result.variant_conflicts.add(key)

    result.elapsed = time.time() - t0
    print(f"\n  Scan complete: {dead_count} dead methods, "
          f"{len(result.children_map)} class hierarchies  "
          f"({result.elapsed:.1f}s)")
    return result


def semantic_method_key(method: dict) -> tuple:
    """Source-set independent method identity."""
    return (
        method.get('package_name'),
        method.get('class_name'),
        method.get('name'),
        method.get('param_count', 0),
    )
