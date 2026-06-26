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
from .method_scanner import scan_methods


_CALL_PAT   = re.compile(r'\b(\w+)\s*\(')
_REF_PAT    = re.compile(r'::(\w+)\b')
_EXTENDS    = re.compile(r'\b(?:class|object)\s+(\w+)\s+(?:extends|:)\s+(\w+)')
_FINAL_CLS  = re.compile(r'\bfinal\s+class\s+(\w+)')
_IFACE_ABS  = re.compile(r'\b(?:interface|abstract\s+class)\s+(\w+)')
_IMPL       = re.compile(r'\bclass\s+(\w+)[^{]*\bimplements\s+')


class ProjectScanResult:
    """Container for all data collected during a unified project scan."""

    __slots__ = ('all_files', 'dead_methods', 'ref_index',
                 'children_map', 'final_classes', 'iface_abstract',
                 'implements', 'elapsed')

    def __init__(self):
        self.all_files: list[str]               = []
        self.dead_methods: list[dict]            = []
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

    # Phase A: collect file list
    for dp, dns, fns in os.walk(root_dir):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in supported:
                result.all_files.append(os.path.join(dp, fn))

    total = len(result.all_files)
    dead_count = 0
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

        # 1) Dead method scan
        try:
            methods = scan_methods(fp, cb, ext)
            if methods:
                result.dead_methods.extend(methods)
                dead_count += len(methods)
        except Exception as e:
            print(f"\n  WARN scan {fp}: {e}", file=sys.stderr)

        # 2) Reference index (method calls + method references)
        for m in _CALL_PAT.finditer(content):
            name = m.group(1)
            if len(name) > 2:
                result.ref_index[name].add(fp)
        for m in _REF_PAT.finditer(content):
            name = m.group(1)
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

    result.elapsed = time.time() - t0
    print(f"\n  Scan complete: {dead_count} dead methods, "
          f"{len(result.children_map)} class hierarchies  "
          f"({result.elapsed:.1f}s)")
    return result
