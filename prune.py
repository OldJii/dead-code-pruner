#!/usr/bin/env python3
"""
dead-code-pruner — Eliminate dead code after constant folding in Java/Kotlin projects.

Pipeline:
  Phase 1: Constant folding + boolean simplification (iterative convergence)
    step1 → step2 → step3 → step4, loop until no changes

  Phase 2: Constant-returning method inlining + cascade simplification
    step5 → step2 → step3 → step4, loop until no changes

  Phase 3: Dead method cleanup + cascade simplification
    step6 → step2 → step3 → step4, loop until no changes

Usage:
  python3 prune.py <target>                       # full pipeline
  python3 prune.py <target> --config pruner.yaml   # custom config
  python3 prune.py <target> --dry-run              # scan only, no changes
  python3 prune.py <target> --phase 1              # only phase 1
"""

import subprocess
import sys
import os
import argparse
import re
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PHASE_1_STEPS = [
    'step1_replace_constants.py',
    'step2_simple_boolean.py',
    'step3_compound_boolean.py',
    'step4_if_block.py',
]

PHASE_2_STEPS = [
    'step5_inline_constant_methods.py',
]

PHASE_3_STEPS = [
    'step6_dead_methods.py',
]

BOOLEAN_SIMPLIFY_STEPS = [
    'step2_simple_boolean.py',
    'step3_compound_boolean.py',
    'step4_if_block.py',
]


def run_script(script, target, config_path=None, dry_run=False):
    path = os.path.join(SCRIPT_DIR, script)
    if not os.path.exists(path):
        print(f"  [SKIP] {script} not found")
        return 0

    args = [sys.executable, path, target]
    if config_path:
        args.extend(['--config', config_path])
    if dry_run:
        args.append('--dry-run')

    result = subprocess.run(args, capture_output=True, text=True, cwd=os.getcwd())
    output = result.stdout.strip()
    if output:
        for line in output.split('\n'):
            print(f"  {line}")
    if result.stderr.strip():
        for line in result.stderr.strip().split('\n')[:5]:
            print(f"  [stderr] {line}")

    last_line = output.split('\n')[-1] if output else ''
    m = re.search(r'(\d+)\s+(files? changed|files? modified|simplifications?|methods?)', last_line)
    if not m:
        m2 = re.search(r'modified\s*(\d+)\s*files', output)
        if not m2:
            m2 = re.search(r'修改了\s*(\d+)\s*个文件', output)
        if m2:
            return int(m2.group(1))
    return int(m.group(1)) if m else 0


def run_phase_1(target, config_path=None, dry_run=False):
    print("\n" + "=" * 60)
    print("Phase 1: Constant folding + boolean simplification")
    print("=" * 60)

    max_rounds = 20
    total = 0
    for round_num in range(1, max_rounds + 1):
        print(f"\n--- Round {round_num} ---")
        changes = 0
        for step in PHASE_1_STEPS:
            changes += run_script(step, target, config_path, dry_run)
        total += changes
        print(f"  Round {round_num}: {changes} changes")
        if changes == 0:
            print(f"  Converged after {round_num} round(s)")
            break
    else:
        print(f"  WARNING: Did not converge after {max_rounds} rounds")

    return total


def run_phase_2(target, config_path=None, dry_run=False):
    print("\n" + "=" * 60)
    print("Phase 2: Constant-returning method inlining + cascade")
    print("=" * 60)

    total = 0
    max_rounds = 10
    for round_num in range(1, max_rounds + 1):
        print(f"\n--- Round {round_num} ---")

        print("  [step5] Inline constant methods...")
        inline_changes = run_script(PHASE_2_STEPS[0], target, config_path, dry_run)

        cascade_changes = 0
        if inline_changes > 0:
            print("  [cascade] Boolean simplification...")
            for step in BOOLEAN_SIMPLIFY_STEPS:
                cascade_changes += run_script(step, target, config_path, dry_run)

        round_total = inline_changes + cascade_changes
        total += round_total
        print(f"  Round {round_num}: inline={inline_changes}, cascade={cascade_changes}")

        if inline_changes == 0:
            print(f"  Converged after {round_num} round(s)")
            break

    return total


def run_phase_3(target, config_path=None, dry_run=False):
    print("\n" + "=" * 60)
    print("Phase 3: Dead method cleanup + cascade")
    print("=" * 60)

    total = 0
    max_rounds = 10
    for round_num in range(1, max_rounds + 1):
        print(f"\n--- Round {round_num} ---")

        print("  [step6] Dead method cleanup...")
        dead_changes = run_script(PHASE_3_STEPS[0], target, config_path, dry_run)

        cascade_changes = 0
        if dead_changes > 0:
            print("  [cascade] Boolean simplification...")
            for step in BOOLEAN_SIMPLIFY_STEPS:
                cascade_changes += run_script(step, target, config_path, dry_run)

        round_total = dead_changes + cascade_changes
        total += round_total
        print(f"  Round {round_num}: dead={dead_changes}, cascade={cascade_changes}")

        if dead_changes == 0:
            print(f"  Converged after {round_num} round(s)")
            break

    return total


def main():
    parser = argparse.ArgumentParser(
        description="dead-code-pruner: eliminate dead code after constant folding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 prune.py .                          # full pipeline on current directory
  python3 prune.py src/ --config pruner.yaml  # custom config
  python3 prune.py . --dry-run                # scan only
  python3 prune.py . --phase 1               # constant folding only
  python3 prune.py . --phase 3               # dead method cleanup only
""")
    parser.add_argument('target', nargs='?', default='.',
                        help='Target path (default: current directory)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Scan only, do not modify files')
    parser.add_argument('--phase', type=int, choices=[1, 2, 3],
                        help='Run only a specific phase (1=constant fold, 2=method inline, 3=dead methods)')
    parser.add_argument('--config', type=str, default=None,
                        help='Path to config file (default: pruner.yaml in current or script directory)')

    args = parser.parse_args()

    target = os.path.abspath(args.target)
    if not os.path.exists(target):
        print(f"Error: {target} does not exist")
        sys.exit(1)

    config_path = args.config
    if not config_path:
        for candidate in ['pruner.yaml', 'pruner.yml', 'pruner.json']:
            if os.path.exists(candidate):
                config_path = candidate
                break
            p = os.path.join(SCRIPT_DIR, candidate)
            if os.path.exists(p):
                config_path = p
                break

    start = time.time()
    mode = "DRY-RUN" if args.dry_run else "EXECUTE"
    print(f"dead-code-pruner [{mode}]")
    print(f"Target: {target}")
    if config_path:
        print(f"Config: {config_path}")

    grand_total = 0
    phases = [args.phase] if args.phase else [1, 2, 3]

    for phase in phases:
        if phase == 1:
            grand_total += run_phase_1(target, config_path, args.dry_run)
        elif phase == 2:
            grand_total += run_phase_2(target, config_path, args.dry_run)
        elif phase == 3:
            grand_total += run_phase_3(target, config_path, args.dry_run)

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"Done! Total changes: {grand_total}, elapsed: {elapsed:.1f}s")
    if grand_total > 0 and not args.dry_run:
        print("\nNext steps:")
        print("  1. Compile your project to verify correctness")
        print("  2. Fix any compilation errors")
        print("  3. git add -A && git commit -m \"refactor: prune dead code\"")
    elif grand_total == 0:
        print("\nNo changes needed. Code is already clean.")
    print("=" * 60)


if __name__ == '__main__':
    main()
