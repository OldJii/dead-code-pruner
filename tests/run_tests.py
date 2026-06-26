#!/usr/bin/env python3
"""Run all language test cases and compare with expected output."""
import os
import sys
import shutil
import difflib

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, PROJECT_DIR)

from pruner.transform import load_config, run_pipeline  # noqa: E402

CONFIG = os.path.join(TESTS_DIR, 'pruner.yaml')

TEST_FILES = [
    ('test_java.java', 'test_java_expected.java'),
    ('test_kotlin.kt', 'test_kotlin_expected.kt'),
    ('test_go.go', 'test_go_expected.go'),
    ('test_swift.swift', 'test_swift_expected.swift'),
    ('test_js.js', 'test_js_expected.js'),
    ('test_ts.ts', 'test_ts_expected.ts'),
    ('test_c.c', 'test_c_expected.c'),
    ('test_cpp.cpp', 'test_cpp_expected.cpp'),
    ('test_rust.rs', 'test_rust_expected.rs'),
    ('test_csharp.cs', 'test_csharp_expected.cs'),
]


def run_test(input_file, expected_file):
    lang = os.path.splitext(input_file)[1][1:]
    input_path = os.path.join(TESTS_DIR, input_file)
    expected_path = os.path.join(TESTS_DIR, expected_file)

    if not os.path.exists(input_path):
        return lang, 'SKIP', 'input file not found'
    if not os.path.exists(expected_path):
        return lang, 'SKIP', 'expected file not found'

    ext = os.path.splitext(input_file)[1]
    tmp_dir = os.path.join(TESTS_DIR, '.tmp_run')
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, 'test_input' + ext)
    shutil.copy2(input_path, tmp_path)

    try:
        with open(tmp_path, 'rb') as f:
            cb = f.read()
        replacements = load_config(CONFIG)
        is_kt = ext in ('.kt', '.kts')
        actual_bytes = run_pipeline(cb, replacements, is_kt, ext=ext)
        actual = actual_bytes.decode('utf-8', errors='replace')

        with open(expected_path, 'r') as f:
            expected = f.read()

        if actual == expected:
            return lang, 'PASS', ''
        diff = list(difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile='expected', tofile='actual', n=3,
        ))
        return lang, 'FAIL', ''.join(diff[:80])
    except Exception as e:
        return lang, 'ERROR', str(e)[:500]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    print("=" * 60)
    print("Dead Code Pruner - Multi-Language Test Suite")
    print("=" * 60)

    results = []
    for inp, exp in TEST_FILES:
        lang, status, detail = run_test(inp, exp)
        results.append((lang, status, detail))

        icon = {'PASS': '✔', 'FAIL': '✘', 'SKIP': '○', 'ERROR': '⚠'}[status]
        print(f"  {icon} {lang:8s} {status}")
        if detail and status != 'PASS':
            for line in detail.split('\n')[:20]:
                print(f"    {line}")

    print()
    passed = sum(1 for _, s, _ in results if s == 'PASS')
    failed = sum(1 for _, s, _ in results if s == 'FAIL')
    errors = sum(1 for _, s, _ in results if s == 'ERROR')
    skipped = sum(1 for _, s, _ in results if s == 'SKIP')
    total = len(results)
    print(f"Results: {passed}/{total} passed, {failed} failed, {errors} errors, {skipped} skipped")

    return 0 if failed == 0 and errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
