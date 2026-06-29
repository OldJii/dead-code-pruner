"""Step 5 — inline constant-returning private/static methods.

Scans the entire project for zero-arg methods that return a boolean
constant, replaces all call sites with the literal value, and deletes
the now-unreferenced private method definitions.
"""

import os
import re
import sys
import time
from collections import defaultdict

from ..lang import _PARSERS
from ..analysis.method_scanner import scan_method_definitions, scan_methods
from ..analysis.project_scan import semantic_method_key
from ..analysis.ref_index import (
    collect_files, build_ref_index, is_in_comment_or_string,
)
from ..analysis.code_edit import (
    replace_calls_in_content, clean_standalone_booleans, delete_line_ranges,
    has_dynamic_symbol_ref,
)


def step5_project(root_dir: str, dry_run: bool = False) -> int:
    """Inline constant methods project-wide. Returns total inlined count."""
    t0 = time.time()
    print("\n=== Step 5: Inline constant methods (tree-sitter) ===")
    all_files = collect_files(root_dir)
    print(f"  Scanning {len(all_files)} files...")

    total = len(all_files)
    all_defs_by_key: dict[tuple, list[dict]] = defaultdict(list)
    all_methods: list[dict] = []
    for idx, fp in enumerate(all_files):
        if (idx + 1) % 500 == 0 or idx + 1 == total:
            pct = (idx + 1) * 100 // total
            print(f"\r  Scanning... {idx+1}/{total} ({pct}%)  "
                  f"[{len(all_methods)} candidates]", end='', flush=True)
        ext = os.path.splitext(fp)[1].lower()
        if ext not in _PARSERS:
            continue
        try:
            with open(fp, 'rb') as f:
                cb = f.read()
            if (b'return true' not in cb and b'return false' not in cb
                    and b'= true' not in cb and b'= false' not in cb):
                continue
            methods = scan_method_definitions(fp, cb, ext)
            for m in methods:
                all_defs_by_key[semantic_method_key(m)].append(m)
                if (m.get('is_dead_candidate') and m['kind'] == 'boolean'
                        and m['param_count'] == 0 and m['safe_to_inline']):
                    all_methods.append(m)
        except Exception as e:
            print(f"\n  ERROR scanning {fp}: {e}", file=sys.stderr)
    print()  # newline after progress

    if not all_methods:
        print("  No constant methods found.")
        return 0

    variant_conflicts = set()
    for key, methods in all_defs_by_key.items():
        candidate_shapes = {(m.get('kind'), m.get('value')) for m in methods if m.get('is_dead_candidate')}
        has_non_candidate = any(not m.get('is_dead_candidate') for m in methods)
        has_multiple_shapes = len(candidate_shapes) > 1
        if len(methods) > 1 and (has_non_candidate or has_multiple_shapes):
            variant_conflicts.add(key)
    all_methods = [m for m in all_methods if semantic_method_key(m) not in variant_conflicts]

    if not all_methods:
        print("  No constant methods found after source-set safety checks.")
        return 0

    private_cnt = sum(1 for m in all_methods if m['is_private'])
    static_cnt  = sum(1 for m in all_methods if m['is_static'] and not m['is_private'])
    print(f"  Found {len(all_methods)} constant methods (private={private_cnt}, static={static_cnt})")

    if dry_run:
        for m in all_methods:
            rel = os.path.relpath(m['filepath'], root_dir)
            print(f"    {m['class_name']}.{m['name']}() -> {m['value']}  [{rel}]")
        return len(all_methods)

    ref_index = build_ref_index(collect_files(root_dir, include_reference_files=True))
    files_modified: set[str] = set()
    total_inlined = 0

    for m in all_methods:
        name  = m['name']
        value = m['value']
        cls   = m['class_name']
        src   = m['filepath']

        try:
            with open(src, 'r', encoding='utf-8') as f:
                content = f.read()
            new_content, cnt = replace_calls_in_content(content, name, value, cls, same_file=True)
            new_content = clean_standalone_booleans(new_content)
            if new_content != content:
                with open(src, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_modified.add(src)
                total_inlined += cnt
        except Exception as e:
            print(f"  WARN same-file {src}: {e}")

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
                    if new_content != content:
                        with open(ref_file, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        files_modified.add(ref_file)
                        total_inlined += cnt
                except Exception as e:
                    print(f"  WARN cross-file {ref_file}: {e}")

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
                    if cm['name'] == dm['name'] and cm['kind'] == 'boolean' and cm['value'] == dm['value']:
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
                    with open(fp, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    files_modified.add(fp)
                    deleted += del_cnt
        except Exception as e:
            print(f"  WARN delete {fp}: {e}")

    print(f"  Inlined {total_inlined} call sites, deleted {deleted} method definitions")
    print(f"  Modified {len(files_modified)} files ({time.time()-t0:.1f}s)")
    return total_inlined
