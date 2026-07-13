"""Three-phase pipeline orchestrator for the tree-sitter dead-code pruner.

Pipeline:
  Phase 1: Constant folding + boolean simplification (iterative convergence)
      step1 → step2 → step3 → step4, loop until no changes.

  Phase 2: Constant-returning method inlining + cascade simplification
      step5 → step1-4 cascade, loop until no new inlines.

  Phase 3: Dead method cleanup + cascade simplification
      step6 → step1-4 cascade, loop until no new dead methods.

  Quality gate: Validate all modified files and report statistics.

When both Phase 2 and Phase 3 are enabled (default), Phase 2 is merged
into Phase 3 — step6 already handles constant-method inlining — avoiding
a redundant full-project scan.

Every phase prints clear progress, per-round stats, and elapsed time
so the operator always knows what the tool is doing.
"""

import os
import shutil
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from .lang import SUPPORTED_EXTS, SKIP_DIRS
from .transform import load_config, process_file, run_pipeline
from .steps.method_inline import step5_project
from .steps.dead_methods import step6_project
from .steps.empty_cleanup import step7_empty_cleanup
from .validation import count_ast_errors
from .analysis.project_layout import ProjectLayout
from .analysis.project_scan import scan_project
from . import ui

_MIN_PARALLEL = 200


# ── Quality gate helper ────────────────────────────────────────

_file_snapshots: dict[str, bytes] = {}


def _process_files_worker(args):
    """Worker for parallel step1-4 processing.

    Receives ``(file_paths, replacements)``.
    Returns changed file paths and per-file errors.
    """
    file_paths, replacements = args
    from . import lang as _lang
    from .transform import run_pipeline

    changed = []
    errors: list[tuple[str, str]] = []
    for fp in file_paths:
        try:
            ext = os.path.splitext(fp)[1].lower()
            if ext not in _lang._PARSERS:
                continue
            with open(fp, 'rb') as fh:
                cb = fh.read()
            new_cb = run_pipeline(cb, replacements, ext=ext)
            if new_cb != cb:
                with open(fp, 'wb') as fh:
                    fh.write(new_cb)
                changed.append(fp)
        except Exception as exc:
            errors.append((fp, str(exc)))
    return changed, errors


def _run_quality_gate_rollback(target: str) -> int:
    """Roll back files whose AST error count increased after transformation."""
    rolled = 0
    items = list(_file_snapshots.items())
    total = len(items)
    ui.info(f"Validating AST quality across {total} snapshots...")
    interval = max(1, total // 100)
    for idx, (fp, orig_bytes) in enumerate(items):
        if (idx + 1) % interval == 0 or idx + 1 == total:
            ui.progress(idx + 1, total, "AST quality gate",
                        f"{rolled} rejected")
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
    ui.progress_done()
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
                    label: str = "Transforming",
                    file_subset: set[str] | None = None,
                    track_changed: bool = False):
    """Run step1-4 on files under *target*, return number of files changed.

    If *file_subset* is provided, only those files are processed (used by
    cascade passes to avoid re-scanning the entire project).

    When *track_changed* is True, returns ``(count, changed_paths)``.
    """
    cnt = 0
    changed_paths: set[str] = set()
    t0 = time.time()
    if os.path.isfile(target):
        ext = os.path.splitext(target)[1].lower()
        if not dry_run:
            _snapshot_file(target)
            if process_file(target, replacements):
                cnt = 1
                changed_paths.add(target)
        else:
            with open(target, 'rb') as f:
                orig = f.read()
            if run_pipeline(orig, replacements, ext=ext) != orig:
                cnt = 1
                changed_paths.add(target)
    else:
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
        ui.info(f"{ui.dim(label)}: processing {total} files...")
        n_workers = min(os.cpu_count() or 1, max(1, total // _MIN_PARALLEL))

        if n_workers > 1 and total >= _MIN_PARALLEL and not dry_run:
            for fp in all_targets:
                _snapshot_file(fp)
            target_chunks = min(total, n_workers * 8)
            chunk_size = max(1, (total + target_chunks - 1) // target_chunks)
            chunks = [all_targets[i:i + chunk_size]
                      for i in range(0, total, chunk_size)]
            completed = 0
            try:
                with ProcessPoolExecutor(max_workers=n_workers) as executor:
                    futures = {
                        executor.submit(
                            _process_files_worker,
                            (chunk, replacements)):
                        len(chunk)
                        for chunk in chunks
                    }
                    for future in as_completed(futures):
                        chunk_changed, chunk_errors = future.result()
                        cnt += len(chunk_changed)
                        changed_paths.update(chunk_changed)
                        for fp, message in chunk_errors:
                            ui.warn(f"Skipped {fp}: {message}")
                        completed += futures[future]
                        ui.progress(completed, total, label, f"{cnt} changed")
            except Exception as e:
                ui.progress_done()
                ui.warn(f"Parallel step1-4 failed ({e}), falling back")
                cnt = 0
                changed_paths.clear()
                for idx, fp in enumerate(all_targets):
                    if (idx + 1) % 500 == 0 or idx + 1 == total:
                        ui.progress(idx + 1, total, label, f"{cnt} changed")
                    try:
                        if process_file(fp, replacements):
                            cnt += 1
                            changed_paths.add(fp)
                    except Exception:
                        pass
        else:
            for idx, fp in enumerate(all_targets):
                try:
                    if not dry_run:
                        _snapshot_file(fp)
                        if process_file(fp, replacements):
                            cnt += 1
                            changed_paths.add(fp)
                    else:
                        with open(fp, 'rb') as fh:
                            raw = fh.read()
                        ext = os.path.splitext(fp)[1].lower()
                        if run_pipeline(raw, replacements, ext=ext) != raw:
                            cnt += 1
                            changed_paths.add(fp)
                except Exception as e:
                    ui.error(f"{fp}: {e}")
                if (idx + 1) % 500 == 0 or idx + 1 == total:
                    ui.progress(idx + 1, total, label, f"{cnt} changed")
        ui.progress_done()
    dt = time.time() - t0
    verb = "would change" if dry_run else "changed"
    ui.info(f"{cnt} files {verb}  {ui.dim(ui.fmt_elapsed(dt))}")
    if track_changed:
        return cnt, changed_paths
    return cnt


def run_phase_1(target: str, replacements: list, dry_run: bool) -> tuple[int, float]:
    ui.banner("Phase 1  Constant Folding + Boolean Simplification")
    t0 = time.time()
    ui.round_header(1, "Per-file fixed-point simplification")
    total = _run_steps_1_4(
        target, replacements, dry_run, "Transforming", track_changed=False)
    ui.success("Phase 1 converged in one project pass; each file reached its fixed point")
    elapsed = time.time() - t0
    return total, elapsed


# ── Phase 2 ───────────────────────────────────────────────────

def _snapshot_all_sources(target: str):
    source_files: list[str] = []
    for dp, dns, fns in os.walk(target):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SUPPORTED_EXTS:
                source_files.append(os.path.join(dp, fn))
    total = len(source_files)
    ui.info(f"Capturing safety snapshots for {total} source files...")
    interval = max(1, total // 100)
    for idx, fp in enumerate(source_files):
        _snapshot_file(fp)
        if (idx + 1) % interval == 0 or idx + 1 == total:
            ui.progress(idx + 1, total, "Snapshotting")
    ui.progress_done()


def run_phase_2(target: str, replacements: list, dry_run: bool) -> tuple[int, float]:
    ui.banner("Phase 2  Constant-Return Method Inlining")
    t0 = time.time()
    total = 0
    max_rounds = 10
    for r in range(1, max_rounds + 1):
        ui.round_header(r, "Constant-return method inlining")
        t_inline = time.time()
        inline_cnt, modified = step5_project(
            target, dry_run=dry_run, show_header=False)
        ui.info(f"Inlined {ui.bold(str(inline_cnt))} items  "
                f"{ui.dim(ui.fmt_elapsed(time.time() - t_inline))}")

        cascade_cnt = 0
        if inline_cnt > 0 and not dry_run and modified:
            cascade_cnt = _run_steps_1_4(
                target, replacements, dry_run, "cascade",
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
    total = 0
    max_rounds = 10

    # One unified scan for ALL rounds — subsequent rounds update
    # incrementally instead of re-scanning the full project.
    scan = scan_project(target, progress_interval=500)

    for r in range(1, max_rounds + 1):
        ui.round_header(r, "Dead declaration cleanup")
        t_dead = time.time()
        dead_cnt, modified = step6_project(
            target, dry_run=dry_run, scan=scan, show_header=False)
        ui.info(f"Cleaned {ui.bold(str(dead_cnt))} items  "
                f"{ui.dim(ui.fmt_elapsed(time.time() - t_dead))}")

        all_round_modified = set(modified) if modified else set()
        cascade_cnt = 0
        if dead_cnt > 0 and not dry_run and modified:
            result = _run_steps_1_4(
                target, replacements, dry_run, "cascade",
                file_subset=modified,
                track_changed=True,
            )
            if isinstance(result, tuple):
                cascade_cnt, cascade_changed = result
                all_round_modified |= cascade_changed
            else:
                cascade_cnt = result

        total += dead_cnt + cascade_cnt
        ui.info(f"Round {r}: dead={dead_cnt}, cascade={cascade_cnt}")

        if dead_cnt == 0 or dry_run:
            ui.success(f"Phase 3 converged after {r} round(s)")
            break

        # Incremental update: only re-scan files that were actually modified
        # in this round, instead of re-scanning all 19K+ files.
        if all_round_modified and r < max_rounds:
            scan.update_files(all_round_modified)

    elapsed = time.time() - t0
    return total, elapsed


# ── Full pipeline ─────────────────────────────────────────────

def _copy_simulation_target(target: str, temp_root: str) -> str:
    """Create an isolated project copy for an exact dry-run."""
    name = os.path.basename(os.path.abspath(target)) or 'project'
    destination = os.path.join(temp_root, name)
    if os.path.isdir(target):
        shutil.copytree(
            target, destination,
            ignore=lambda _path, names: [n for n in names if n in SKIP_DIRS],
        )
    else:
        shutil.copy2(target, destination)
    return destination


def run_full_pipeline(
    target: str,
    config_path: str,
    *,
    dry_run: bool = False,
    phases: list[int] | None = None,
    _simulation: bool = False,
    _display_target: str | None = None,
) -> dict:
    """Execute the full pipeline, including cascades in dry-run mode."""
    if dry_run and not _simulation:
        with tempfile.TemporaryDirectory(prefix='dead-code-pruner-') as temp_root:
            simulated_target = _copy_simulation_target(target, temp_root)
            return run_full_pipeline(
                simulated_target, config_path, dry_run=False, phases=phases,
                _simulation=True, _display_target=target)

    pipeline_start = time.time()
    report_dry_run = dry_run or _simulation
    mode = "DRY-RUN" if report_dry_run else "EXECUTE"

    replacements = load_config(config_path)

    layout = ProjectLayout(target) if os.path.isdir(target) else None
    layout_desc = f"{layout.kind} ({len(layout.modules)} module(s))" if layout else "single file"

    ui.banner(f"dead-code-pruner  [{mode}]")
    ui.kv("Engine", "tree-sitter AST")
    ui.kv("Target", _display_target or target)
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

    # Single snapshot pass for all phases — avoids repeated full reads.
    if not dry_run and (2 in phases or 3 in phases) and os.path.isdir(target):
        _snapshot_all_sources(target)

    results = {}
    grand_total = 0

    if 1 in phases:
        cnt, elapsed = run_phase_1(target, replacements, dry_run)
        results['phase_1'] = {'changes': cnt, 'elapsed': elapsed}
        grand_total += cnt

    # When both Phase 2 and Phase 3 are enabled, skip Phase 2 — step6
    # (Phase 3) already handles constant-method inlining, void-call
    # removal, and definition deletion.  This saves one full project scan.
    phase2_merged = 2 in phases and 3 in phases
    if 2 in phases and not phase2_merged and os.path.isdir(target):
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
        cleanup = step7_empty_cleanup(
            target, dry_run=dry_run, show_header=False)
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

        snapshot_items = list(_file_snapshots.items())
        total_snapshots = len(snapshot_items)
        ui.info(f"Final quality/statistics pass over {total_snapshots} snapshots...")
        interval = max(1, total_snapshots // 100)
        for idx, (fp, orig_bytes) in enumerate(snapshot_items):
            if (idx + 1) % interval == 0 or idx + 1 == total_snapshots:
                ui.progress(idx + 1, total_snapshots, "Quality/statistics")
            try:
                with open(fp, 'rb') as f:
                    cur_bytes = f.read()
            except FileNotFoundError:
                cur_bytes = b''
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
        ui.progress_done()

    _file_snapshots.clear()

    # ── Summary ───────────────────────────────────────────────
    ui.banner("Summary")
    rows = []
    for key in sorted(results):
        r = results[key]
        label = key.replace('_', ' ').title()
        rows.append((label, f"{r['changes']} changes  {ui.dim(ui.fmt_elapsed(r['elapsed']))}"))
    rows.append(("Events", str(grand_total)))

    if grand_total > 0:
        file_label = "Files would change" if report_dry_run else "Files changed"
        line_label = "Lines would change" if report_dry_run else "Lines changed"
        rows.append((file_label, str(len(files_changed_set))))
        net = lines_added - lines_removed
        net_str = f"{ui.green(f'+{lines_added}')} {ui.red(f'-{lines_removed}')} (net {net:+d})"
        rows.append((line_label, net_str))
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
    elif grand_total > 0 and report_dry_run:
        print()
        ui.info("Dry-run complete — the original project was not modified.")
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
