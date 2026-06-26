"""Three-phase pipeline orchestrator for the tree-sitter dead-code pruner.

Pipeline:
  Phase 1: Constant folding + boolean simplification (iterative convergence)
      step1 → step2 → step3 → step4, loop until no changes.

  Phase 2: Constant-returning method inlining + cascade simplification
      step5 → step1-4 cascade, loop until no new inlines.

  Phase 3: Dead method cleanup + cascade simplification
      step6 → step1-4 cascade, loop until no new dead methods.

Every phase prints clear progress bars, per-round stats, and elapsed time
so the operator always knows what the tool is doing.
"""

import os
import sys
import time

from .lang import SUPPORTED_EXTS, SKIP_DIRS
from .transform import load_config, process_file, run_pipeline
from .steps.method_inline import step5_project
from .steps.dead_methods import step6_project


# ── Helpers ───────────────────────────────────────────────────

def _fmt_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m{s:.1f}s"


def _banner(text: str, width: int = 60):
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def _phase_header(phase: int, label: str, round_num: int):
    print(f"\n--- Phase {phase} · round {round_num}: {label} ---")


# ── Phase 1 ───────────────────────────────────────────────────

def _run_steps_1_4(target: str, replacements: list, dry_run: bool,
                    label: str = "Steps 1-4") -> int:
    """Run step1-4 on all files under *target*, return number of files changed."""
    cnt = 0
    t0 = time.time()
    if os.path.isfile(target):
        ext = os.path.splitext(target)[1].lower()
        if not dry_run:
            if process_file(target, replacements):
                cnt = 1
        else:
            with open(target, 'rb') as f:
                orig = f.read()
            is_kt = ext in ('.kt', '.kts')
            if run_pipeline(orig, replacements, is_kt, ext=ext) != orig:
                cnt = 1
    else:
        # Pre-filter: only process files containing replacement patterns
        pattern_bytes = [pat.encode('utf-8') for pat, _ in replacements] if replacements else []
        all_targets: list[str] = []
        for dp, dns, fns in os.walk(target):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for fn in fns:
                ext = os.path.splitext(fn)[1].lower()
                if ext in SUPPORTED_EXTS:
                    all_targets.append(os.path.join(dp, fn))

        total = len(all_targets)
        print(f"  [{label}] Processing {total} files...")
        for idx, fp in enumerate(all_targets):
            if (idx + 1) % 500 == 0 or idx + 1 == total:
                pct = (idx + 1) * 100 // total
                print(f"\r  [{label}] {idx+1}/{total} ({pct}%)  "
                      f"[{cnt} changed]", end='', flush=True)
            try:
                if pattern_bytes:
                    with open(fp, 'rb') as fh:
                        raw = fh.read()
                    if not any(pb in raw for pb in pattern_bytes):
                        continue
                if not dry_run:
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
                print(f"\n  ERROR: {fp}: {e}", file=sys.stderr)
        print()  # newline after progress
    dt = time.time() - t0
    verb = "would change" if dry_run else "changed"
    print(f"  [{label}] {cnt} files {verb} ({_fmt_elapsed(dt)})")
    return cnt


def run_phase_1(target: str, replacements: list, dry_run: bool) -> tuple[int, float]:
    """Phase 1: Constant folding + boolean simplification (iterative)."""
    _banner("Phase 1: Constant folding + boolean simplification")
    t0 = time.time()
    total = 0
    max_rounds = 20
    for r in range(1, max_rounds + 1):
        _phase_header(1, "step1-4 pipeline", r)
        cnt = _run_steps_1_4(target, replacements, dry_run, f"Round {r}")
        total += cnt
        if cnt == 0:
            print(f"  ✔ Phase 1 converged after {r} round(s)  (total: {total} files)")
            break
    else:
        print(f"  ⚠ Phase 1 did NOT converge after {max_rounds} rounds")
    elapsed = time.time() - t0
    return total, elapsed


# ── Phase 2 ───────────────────────────────────────────────────

def run_phase_2(target: str, replacements: list, dry_run: bool) -> tuple[int, float]:
    """Phase 2: Constant-returning method inlining + cascade."""
    _banner("Phase 2: Constant-returning method inlining")
    t0 = time.time()
    total = 0
    max_rounds = 10
    for r in range(1, max_rounds + 1):
        _phase_header(2, "step5 inline", r)
        t_inline = time.time()
        inline_cnt = step5_project(target, dry_run=dry_run)
        print(f"  [step5] Inlined {inline_cnt} items ({_fmt_elapsed(time.time() - t_inline)})")

        cascade_cnt = 0
        if inline_cnt > 0 and not dry_run:
            cascade_cnt = _run_steps_1_4(target, replacements, dry_run, "cascade")

        total += inline_cnt + cascade_cnt
        print(f"  Round {r}: inline={inline_cnt}, cascade={cascade_cnt}")

        if inline_cnt == 0 or dry_run:
            print(f"  ✔ Phase 2 converged after {r} round(s)")
            break
    elapsed = time.time() - t0
    return total, elapsed


# ── Phase 3 ───────────────────────────────────────────────────

def run_phase_3(target: str, replacements: list, dry_run: bool) -> tuple[int, float]:
    """Phase 3: Dead method cleanup + cascade."""
    _banner("Phase 3: Dead method cleanup")
    t0 = time.time()
    total = 0
    max_rounds = 10
    for r in range(1, max_rounds + 1):
        _phase_header(3, "step6 dead-method cleanup", r)
        t_dead = time.time()
        dead_cnt = step6_project(target, dry_run=dry_run)
        print(f"  [step6] Cleaned {dead_cnt} items ({_fmt_elapsed(time.time() - t_dead)})")

        cascade_cnt = 0
        if dead_cnt > 0 and not dry_run:
            cascade_cnt = _run_steps_1_4(target, replacements, dry_run, "cascade")

        total += dead_cnt + cascade_cnt
        print(f"  Round {r}: dead={dead_cnt}, cascade={cascade_cnt}")

        if dead_cnt == 0 or cascade_cnt == 0 or dry_run:
            print(f"  ✔ Phase 3 converged after {r} round(s)")
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
    """Execute the full 3-phase pipeline.

    Returns a summary dict with per-phase stats and total elapsed time.
    """
    pipeline_start = time.time()
    mode = "DRY-RUN" if dry_run else "EXECUTE"

    replacements = load_config(config_path)

    print("=" * 60)
    print(f"  dead-code-pruner (tree-sitter/AST) [{mode}]")
    print(f"  Engine:  tree-sitter AST")
    print(f"  Target:  {target}")
    print(f"  Config:  {config_path}")
    print(f"  Rules:   {len(replacements)} replacement(s)")
    for p, v in replacements:
        print(f"           {p} → {v}")
    print(f"  Languages: {', '.join(sorted(SUPPORTED_EXTS))}")
    if phases:
        print(f"  Phases:  {phases}")
    print("=" * 60)

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

    if 3 in phases and os.path.isdir(target):
        cnt, elapsed = run_phase_3(target, replacements, dry_run)
        results['phase_3'] = {'changes': cnt, 'elapsed': elapsed}
        grand_total += cnt

    total_elapsed = time.time() - pipeline_start

    # ── Summary ───────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Summary (tree-sitter/AST)")
    print("-" * 60)
    for key in sorted(results):
        r = results[key]
        label = key.replace('_', ' ').title()
        print(f"  {label}: {r['changes']} changes  ({_fmt_elapsed(r['elapsed'])})")
    print(f"  Total changes: {grand_total}")
    print(f"  Total elapsed: {_fmt_elapsed(total_elapsed)}")
    if grand_total > 0 and not dry_run:
        print()
        print("  Next steps:")
        print("    1. Compile your project to verify correctness")
        print("    2. Fix any compilation errors")
        print('    3. git add -A && git commit -m "refactor: prune dead code"')
    elif grand_total == 0:
        print()
        print("  No changes needed — code is already clean.")
    print("=" * 60)

    results['total'] = {'changes': grand_total, 'elapsed': total_elapsed}
    return results
