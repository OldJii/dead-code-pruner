#!/usr/bin/env python3
"""
Project-level test runner for Step 5 (inline constant methods) and Step 6 (dead method cleanup).
Copies input/ to work/, runs the corresponding step, diffs with expected/.
"""
import os
import sys
import shutil
import difflib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from pruner.steps.method_inline import step5_project  # noqa: E402
from pruner.steps.dead_methods import step6_project    # noqa: E402
from pruner.pipeline import run_full_pipeline           # noqa: E402


def run_dir_test(test_name, test_dir, step_fn):
    input_dir = os.path.join(test_dir, 'input')
    expected_dir = os.path.join(test_dir, 'expected')
    work_dir = os.path.join(test_dir, 'work')

    if not os.path.isdir(input_dir) or not os.path.isdir(expected_dir):
        print(f"  SKIP {test_name}: missing input/ or expected/")
        return None

    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    shutil.copytree(input_dir, work_dir)

    step_fn(work_dir)

    passed = 0
    failed = 0
    details = []

    expected_files = []
    for dp, _, fns in os.walk(expected_dir):
        for fn in fns:
            expected_file = os.path.join(dp, fn)
            expected_files.append(os.path.relpath(expected_file, expected_dir))

    for fn in sorted(expected_files):
        expected_file = os.path.join(expected_dir, fn)
        work_file = os.path.join(work_dir, fn)

        if not os.path.exists(work_file):
            details.append(f"    MISS: {fn}")
            failed += 1
            continue

        with open(expected_file) as f:
            exp = f.readlines()
        with open(work_file) as f:
            act = f.readlines()

        diff = list(difflib.unified_diff(exp, act, fromfile='expected', tofile='actual', lineterm=''))
        if not diff:
            passed += 1
        else:
            details.append(f"    DIFF: {fn}")
            for line in diff[:15]:
                details.append(f"      {line}")
            failed += 1

    status = "PASS" if failed == 0 else "FAIL"
    icon = "✔" if failed == 0 else "✘"
    print(f"  {icon} {test_name:20s} {status} ({passed}/{passed+failed})")
    for d in details:
        print(d)
    return failed == 0


def run_full_pipeline_test(test_name, test_dir):
    config = os.path.join(SCRIPT_DIR, 'pruner.yaml')
    return run_dir_test(
        test_name,
        test_dir,
        lambda work_dir: run_full_pipeline(work_dir, config),
    )


def main():
    print("=" * 60)
    print("Dead Code Pruner - Project-Level Test Suite (Step 5 & 6)")
    print("=" * 60)

    results = []

    step5_dir = os.path.join(SCRIPT_DIR, 'step5_dir')
    results.append(run_dir_test('step5_inline', step5_dir, step5_project))

    step6_basic = os.path.join(SCRIPT_DIR, 'step6_basic')
    results.append(run_dir_test('step6_basic', step6_basic, step6_project))

    step6_enhanced = os.path.join(SCRIPT_DIR, 'step6_enhanced')
    results.append(run_dir_test('step6_enhanced', step6_enhanced, step6_project))

    full_pipeline = os.path.join(SCRIPT_DIR, 'full_pipeline_semantic')
    results.append(run_full_pipeline_test('full_pipeline', full_pipeline))

    valid = [r for r in results if r is not None]
    passed = sum(1 for r in valid if r)
    failed = sum(1 for r in valid if not r)
    print(f"\nResults: {passed}/{len(valid)} suites passed, {failed} failed")
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
