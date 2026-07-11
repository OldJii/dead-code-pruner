"""Three-phase pipeline orchestrator for the tree-sitter dead-code pruner.

Pipeline:
  Phase 1: Constant folding + boolean simplification (iterative convergence)
      step1 → step2 → step3 → step4, loop until no changes.

  Phase 2: Constant-returning method inlining + cascade simplification
      step5 → step1-4 cascade, loop until no new inlines.

  Phase 3: Dead method cleanup + cascade simplification
      step6 → step1-4 cascade, loop until no new dead methods.

  Quality gate: Validate all modified files and report statistics.

Every phase prints clear progress, per-round stats, and elapsed time
so the operator always knows what the tool is doing.
"""

import os
import sys
import time
from collections import defaultdict

from .lang import SUPPORTED_EXTS, SKIP_DIRS
from .transform import load_config, process_file, run_pipeline
from .steps.method_inline import step5_project
from .steps.dead_methods import step6_project
from .steps.empty_cleanup import step7_empty_cleanup
from .validation import count_ast_errors
from .analysis.project_layout import ProjectLayout
from . import ui


# ── Quality gate helper ────────────────────────────────────────

_file_snapshots: dict[str, bytes] = {}


def _run_quality_gate_rollback(target: str) -> int:
    """Roll back files whose AST error count increased after transformation."""
    rolled = 0
    for fp, orig_bytes in list(_file_snapshots.items()):
        try:
            with open(fp, 'rb') as f:
                cur_bytes = f.read()
        except Exception:
            continue
        if cur_bytes == orig_bytes:
            continue
        ext = os.path.splitext(fp)[1].lower()
        errs = count_ast_errors(cur_bytes, ext)
        if errs > 0:
            orig_errs = count_ast_errors(orig_bytes, ext)
            if errs > orig_errs:
                try:
                    with open(fp, 'wb') as f:
                        f.write(orig_bytes)
                    rolled += 1
                    rel = os.path.relpath(fp, target)
                    ui.warn(f"ROLLBACK (new AST errors): {rel}")
                except Exception:
                    pass
    return rolled


# ── Phase 1 ───────────────────────────────────────────────────


def _snapshot_file(filepath: str):
    if filepath not in _file_snapshots:
        try:
            with open(filepath, 'rb') as f:
                _file_snapshots[filepath] = f.read()
        except Exception:
            pass


def _run_steps_1_4(target: str, replacements: list, dry_run: bool,
                    label: str = "Steps 1-4",
                    prefilter_replacements: bool = True,
                    file_subset: set[str] | None = None) -> int:
    """Run step1-4 on files under *target*, return number of files changed.

    If *file_subset* is provided, only those files are processed (used by
    cascade passes to avoid re-scanning the entire project).
    """
    cnt = 0
    t0 = time.time()
    if os.path.isfile(target):
        ext = os.path.splitext(target)[1].lower()
        if not dry_run:
            _snapshot_file(target)
            if process_file(target, replacements):
                cnt = 1
        else:
            with open(target, 'rb') as f:
                orig = f.read()
            is_kt = ext in ('.kt', '.kts')
            if run_pipeline(orig, replacements, is_kt, ext=ext) != orig:
                cnt = 1
    else:
        pattern_bytes = (
            [pat.encode('utf-8') for pat, _ in replacements]
            if replacements and prefilter_replacements else []
        )
        if file_subset is not None:
            all_targets = sorted(file_subset)
        else:
            all_targets: list[str] = []
            for dp, dns, fns in os.walk(target):
                dns[:] = [d for d in dns if d not in SKIP_DIRS]
                for fn in fns:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in SUPPORTED_EXTS:
                        all_targets.append(os.path.join(dp, fn))

        total = len(all_targets)
        ui.info(f"{ui.dim(label)}  Processing {total} files...")
        for idx, fp in enumerate(all_targets):
            if (idx + 1) % 500 == 0 or idx + 1 == total:
                ui.progress(idx + 1, total, label, f"{cnt} changed")
            try:
                if pattern_bytes:
                    with open(fp, 'rb') as fh:
                        raw = fh.read()
                    if not any(pb in raw for pb in pattern_bytes):
                        continue
                if not dry_run:
                    _snapshot_file(fp)
                    if process_file(fp, replacements):
                        cnt += 1
                else:
                    if not pattern_bytes:
                        with open(fp, 'rb') as fh:
                            raw = fh.read()
                    ext = os.path.splitext(fp)[1].lower()
                    is_kt = ext in ('.kt', '.kts')
                    if run_pipeline(raw, replacements, is_kt, ext=ext) != raw:
                        cnt += 1
            except Exception as e:
                ui.error(f"{fp}: {e}")
        ui.progress_done()
    dt = time.time() - t0
    verb = "would change" if dry_run else "changed"
    ui.info(f"{cnt} files {verb}  {ui.dim(ui.fmt_elapsed(dt))}")
    return cnt


def run_phase_1(target: str, replacements: list, dry_run: bool) -> tuple[int, float]:
    ui.banner("Phase 1  Constant Folding + Boolean Simplification")
    t0 = time.time()
    total = 0
    max_rounds = 20
    for r in range(1, max_rounds + 1):
        ui.phase_header(1, "step1-4 pipeline", r)
        cnt = _run_steps_1_4(target, replacements, dry_run, f"Round {r}")
        total += cnt
        if cnt == 0:
            ui.success(f"Phase 1 converged after {r} round(s)  "
                       f"{ui.dim(f'(total: {total} files)')}")
            break
    else:
        ui.warn(f"Phase 1 did NOT converge after {max_rounds} rounds")
    elapsed = time.time() - t0
    return total, elapsed


# ── Phase 2 ───────────────────────────────────────────────────

def _snapshot_all_sources(target: str):
    for dp, dns, fns in os.walk(target):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SUPPORTED_EXTS:
                _snapshot_file(os.path.join(dp, fn))


def run_phase_2(target: str, replacements: list, dry_run: bool) -> tuple[int, float]:
    ui.banner("Phase 2  Constant-Return Method Inlining")
    t0 = time.time()
    if not dry_run:
        _snapshot_all_sources(target)
    total = 0
    max_rounds = 10
    for r in range(1, max_rounds + 1):
        ui.phase_header(2, "step5 inline", r)
        t_inline = time.time()
        inline_cnt, modified = step5_project(target, dry_run=dry_run)
        ui.info(f"Inlined {ui.bold(str(inline_cnt))} items  "
                f"{ui.dim(ui.fmt_elapsed(time.time() - t_inline))}")

        cascade_cnt = 0
        if inline_cnt > 0 and not dry_run and modified:
            cascade_cnt = _run_steps_1_4(
                target, replacements, dry_run, "cascade",
                prefilter_replacements=False,
                file_subset=modified,
            )

        total += inline_cnt + cascade_cnt
        ui.info(f"Round {r}: inline={inline_cnt}, cascade={cascade_cnt}")

        if inline_cnt == 0 or dry_run:
            ui.success(f"Phase 2 converged after {r} round(s)")
            break
    elapsed = time.time() - t0
    return total, elapsed


# ── Phase 3 ───────────────────────────────────────────────────

def run_phase_3(target: str, replacements: list, dry_run: bool) -> tuple[int, float]:
    ui.banner("Phase 3  Dead Method Cleanup")
    t0 = time.time()
    if not dry_run:
        _snapshot_all_sources(target)
    total = 0
    max_rounds = 10
    for r in range(1, max_rounds + 1):
        ui.phase_header(3, "step6 dead-method cleanup", r)
        t_dead = time.time()
        dead_cnt, modified = step6_project(target, dry_run=dry_run)
        ui.info(f"Cleaned {ui.bold(str(dead_cnt))} items  "
                f"{ui.dim(ui.fmt_elapsed(time.time() - t_dead))}")

        cascade_cnt = 0
        if dead_cnt > 0 and not dry_run and modified:
            cascade_cnt = _run_steps_1_4(
                target, replacements, dry_run, "cascade",
                prefilter_replacements=False,
                file_subset=modified,
            )

        total += dead_cnt + cascade_cnt
        ui.info(f"Round {r}: dead={dead_cnt}, cascade={cascade_cnt}")

        if dead_cnt == 0 or dry_run:
            ui.success(f"Phase 3 converged after {r} round(s)")
            break
    elapsed = time.time() - t0
    return total, elapsed


# ── Full pipeline ─────────────────────────────────────────────

def run_full_pipeline(
    target: str,
    config_path: str,
    *,
    dry_run: bool = False,
    phases: list[int] | None = None,
) -> dict:
    """Execute the full 3-phase pipeline."""
    pipeline_start = time.time()
    mode = "DRY-RUN" if dry_run else "EXECUTE"

    replacements = load_config(config_path)

    layout = ProjectLayout(target) if os.path.isdir(target) else None
    layout_desc = f"{layout.kind} ({len(layout.modules)} module(s))" if layout else "single file"

    ui.banner(f"dead-code-pruner  [{mode}]")
    ui.kv("Engine", "tree-sitter AST")
    ui.kv("Target", target)
    ui.kv("Layout", layout_desc)
    ui.kv("Config", config_path)
    ui.kv("Rules", f"{len(replacements)} replacement(s)")
    for p, v in replacements:
        ui.info(f"         {p} → {v}")
    ui.kv("Languages", ', '.join(sorted(SUPPORTED_EXTS)))
    if phases:
        ui.kv("Phases", str(phases))

    if phases is None:
        phases = [1, 2, 3]

    results = {}
    grand_total = 0

    if 1 in phases:
        cnt, elapsed = run_phase_1(target, replacements, dry_run)
        results['phase_1'] = {'changes': cnt, 'elapsed': elapsed}
        grand_total += cnt

    if 2 in phases and os.path.isdir(target):
        cnt, elapsed = run_phase_2(target, replacements, dry_run)
        results['phase_2'] = {'changes': cnt, 'elapsed': elapsed}
        grand_total += cnt

    pre_rollback_count = 0
    if not dry_run and grand_total > 0:
        pre_rollback_count = _run_quality_gate_rollback(target)

    if 3 in phases and os.path.isdir(target):
        cnt, elapsed = run_phase_3(target, replacements, dry_run)
        results['phase_3'] = {'changes': cnt, 'elapsed': elapsed}
        grand_total += cnt

        t_cleanup = time.time()
        cleanup = step7_empty_cleanup(target, dry_run=dry_run)
        cleanup_cnt = cleanup['classes_removed'] + cleanup['files_deleted']
        if cleanup_cnt > 0:
            results['cleanup'] = {
                'changes': cleanup_cnt,
                'elapsed': time.time() - t_cleanup,
            }
            grand_total += cleanup_cnt

    total_elapsed = time.time() - pipeline_start

    # ── Final quality gate ────────────────────────────────────
    lines_added = lines_removed = 0
    files_changed_set: set[str] = set()
    rejected_count = pre_rollback_count

    if grand_total > 0 and not dry_run:
        post_rollback = _run_quality_gate_rollback(target)
        rejected_count += post_rollback

        for fp, orig_bytes in _file_snapshots.items():
            try:
                with open(fp, 'rb') as f:
                    cur_bytes = f.read()
            except Exception:
                continue
            if cur_bytes == orig_bytes:
                continue
            files_changed_set.add(fp)
            orig_lines = orig_bytes.decode('utf-8', errors='replace').split('\n')
            cur_lines  = cur_bytes.decode('utf-8', errors='replace').split('\n')
            orig_set, cur_set = set(orig_lines), set(cur_lines)
            lines_added   += len(cur_set - orig_set)
            lines_removed += len(orig_set - cur_set)

    _file_snapshots.clear()

    # ── Summary ───────────────────────────────────────────────
    ui.banner("Summary")
    rows = []
    for key in sorted(results):
        r = results[key]
        label = key.replace('_', ' ').title()
        rows.append((label, f"{r['changes']} changes  {ui.dim(ui.fmt_elapsed(r['elapsed']))}"))
    rows.append(("Events", str(grand_total)))

    if not dry_run and grand_total > 0:
        rows.append(("Files changed", str(len(files_changed_set))))
        net = lines_added - lines_removed
        net_str = f"{ui.green(f'+{lines_added}')} {ui.red(f'-{lines_removed}')} (net {net:+d})"
        rows.append(("Lines changed", net_str))
        gate_passed = rejected_count == 0
        rows.append(("Quality gate", f"{ui.quality_badge(gate_passed)}  "
                      f"({rejected_count} rejected)"))

    rows.append(("Elapsed", ui.fmt_elapsed(total_elapsed)))
    ui.summary_table(rows)

    if grand_total > 0 and not dry_run:
        print()
        ui.info("Next steps:")
        ui.info("  1. Compile your project to verify correctness", indent=2)
        ui.info("  2. Fix any compilation errors", indent=2)
        ui.info('  3. git add -A && git commit -m "refactor: prune dead code"', indent=2)
    elif grand_total == 0:
        print()
        ui.success("No changes needed — code is already clean.")

    results['total'] = {'changes': grand_total, 'elapsed': total_elapsed}
    results['quality'] = {
        'files_changed': len(files_changed_set),
        'lines_added': lines_added,
        'lines_removed': lines_removed,
        'rejected': rejected_count,
    }
    return results
