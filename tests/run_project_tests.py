#!/usr/bin/env python3
"""
Project-level tests for Phase 2 and the standalone boolean-inline utility.
Copies input/ to work/, runs the corresponding operation, and diffs with
expected/.
"""
import os
import sys
import shutil
import difflib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from pruner.steps.method_inline import inline_boolean_methods_standalone  # noqa: E402
from pruner.steps.dead_methods import phase2_step2_cleanup_dead_declarations  # noqa: E402
from pruner.steps.empty_cleanup import phase2_step5_cleanup_empty_artifacts  # noqa: E402
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

    actual_files = []
    for dp, _, fns in os.walk(work_dir):
        for fn in fns:
            actual_file = os.path.join(dp, fn)
            actual_files.append(os.path.relpath(actual_file, work_dir))

    unexpected = sorted(set(actual_files) - set(expected_files))
    for fn in unexpected:
        details.append(f"    EXTRA: {fn}")
        failed += 1

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


def run_full_pipeline_test(test_name, test_dir, *, world=None):
    config = os.path.join(SCRIPT_DIR, 'pruner.yaml')
    return run_dir_test(
        test_name,
        test_dir,
        lambda work_dir: run_full_pipeline(work_dir, config, world=world),
    )


def main():
    print("=" * 60)
    print("Dead Code Pruner - Project-Level Test Suite")
    print("=" * 60)

    results = []

    standalone_inline_fixture = os.path.join(
        SCRIPT_DIR, 'standalone_boolean_inline')
    results.append(run_dir_test(
        'standalone_inline', standalone_inline_fixture,
        inline_boolean_methods_standalone))

    project_cleanup_basic_fixture = os.path.join(
        SCRIPT_DIR, 'project_cleanup_basic')
    results.append(run_dir_test(
        'project_cleanup_basic', project_cleanup_basic_fixture,
        lambda root: phase2_step2_cleanup_dead_declarations(
            root, world='closed')))

    project_cleanup_enhanced_fixture = os.path.join(
        SCRIPT_DIR, 'project_cleanup_enhanced')
    results.append(run_dir_test(
        'project_cleanup_enhanced', project_cleanup_enhanced_fixture,
        lambda root: phase2_step2_cleanup_dead_declarations(
            root, world='closed')))

    short_names = os.path.join(SCRIPT_DIR, 'project_cleanup_short_names')
    results.append(run_dir_test(
        'project_cleanup_short_names', short_names,
        lambda root: phase2_step2_cleanup_dead_declarations(
            root, world='closed')))

    metadata_refs = os.path.join(
        SCRIPT_DIR, 'project_cleanup_metadata_refs')
    results.append(run_dir_test(
        'project_cleanup_metadata_refs', metadata_refs,
        lambda root: phase2_step2_cleanup_dead_declarations(
            root, world='closed')))

    receiver_refs = os.path.join(
        SCRIPT_DIR, 'project_cleanup_receiver_refs')
    results.append(run_dir_test(
        'project_cleanup_receiver_refs', receiver_refs,
        lambda root: phase2_step2_cleanup_dead_declarations(
            root, world='closed')))

    lombok_fields = os.path.join(
        SCRIPT_DIR, 'project_cleanup_lombok_fields')
    results.append(run_dir_test(
        'project_cleanup_lombok', lombok_fields,
        lambda root: phase2_step2_cleanup_dead_declarations(
            root, world='closed')))

    kotlin_trailing = os.path.join(
        SCRIPT_DIR, 'project_cleanup_kotlin_trailing_lambda')
    results.append(run_dir_test(
        'project_cleanup_kotlin_lambda', kotlin_trailing,
        phase2_step2_cleanup_dead_declarations))

    empty_cleanup_manifest_fixture = os.path.join(
        SCRIPT_DIR, 'project_cleanup_empty_manifest')
    results.append(run_dir_test(
        'empty_cleanup_manifest_entry', empty_cleanup_manifest_fixture,
        lambda root: phase2_step5_cleanup_empty_artifacts(
            root, world='closed')))

    full_pipeline = os.path.join(SCRIPT_DIR, 'full_pipeline_semantic')
    results.append(run_full_pipeline_test('full_pipeline', full_pipeline))

    multilang = os.path.join(SCRIPT_DIR, 'project_multilang')
    for lang in ('java', 'kotlin', 'go', 'swift', 'dart'):
        lang_dir = os.path.join(multilang, lang)
        results.append(run_full_pipeline_test(
            f'multilang_{lang}', lang_dir, world='closed'))

    valid = [r for r in results if r is not None]
    passed = sum(1 for r in valid if r)
    failed = sum(1 for r in valid if not r)
    print(f"\nResults: {passed}/{len(valid)} suites passed, {failed} failed")
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
