"""Cross-language parity tests for syntax, safety, and project cleanup."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from pruner.analysis.method_scanner import scan_method_definitions
from pruner.analysis.project_scan import scan_project
from pruner.pipeline import run_full_pipeline
from pruner.steps.constant_fold import step1_replace
from pruner.steps.dead_methods import _batch_same_file_refs, step6_project
from pruner.steps.method_inline import step5_project


SCANNER_CASES = {
    '.java': b'class W { private boolean dead(@A int x, String y) { return true; } }',
    '.kt': b'class W { private fun dead(@A x: Int, y: String = "x"): Boolean = true }',
    '.go': b'package p\nfunc dead(a, b int, c string) bool { return true }',
    '.swift': b'class W { private func dead(_ x: Int, y: String = "x") -> Bool { true } }',
    '.dart': b'class W { bool _dead(int x, [String y = "x"]) => true; }',
}

EXPECTED_ARITY = {'.java': 2, '.kt': 2, '.go': 3, '.swift': 2, '.dart': 2}

STRING_CASES = {
    '.java': b'class W { String s = """FLAG"""; boolean x = FLAG; }',
    '.kt': b'class W { val s = """FLAG"""; val x = FLAG }',
    '.go': b'package p\nvar s = `FLAG`\nvar x = FLAG',
    '.swift': b'let s = #"FLAG"#\nlet x = FLAG',
    '.dart': b'final s = r"FLAG";\nfinal x = FLAG;',
}

PROJECT_CASES = {
    '.java': {
        'Contract.java': 'interface Contract { boolean required(); }\n',
        'Base.java': 'abstract class Base { abstract boolean inherited(); }\n',
        'Worker.java': (
            'class Worker extends Base implements Contract {\n'
            '  public boolean required() { return false; }\n'
            '  public boolean inherited() { return false; }\n'
            '  @Keep private boolean reflected() { return true; }\n'
            '  private boolean dead() { return true; }\n'
            '  private static final int deadField = 1;\n'
            '  public static final int API_FIELD = 1;\n'
            '}\n'),
        'keep': ('required()', 'inherited()', 'reflected()', 'API_FIELD'),
        'remove': ('dead()', 'deadField'),
    },
    '.kt': {
        'Contract.kt': 'interface Contract { fun required(): Boolean }\n',
        'Base.kt': 'abstract class Base { abstract fun inherited(): Boolean }\n',
        'Worker.kt': (
            'class Worker : Base(), Contract {\n'
            '  override fun required(): Boolean = false\n'
            '  override fun inherited(): Boolean = false\n'
            '  @Keep private fun reflected(): Boolean = true\n'
            '  private fun dead(): Boolean = true\n'
            '  private val deadField = 1\n'
            '  val apiField = 1\n'
            '}\n'),
        'keep': ('required()', 'inherited()', 'reflected()', 'apiField'),
        'remove': ('dead()', 'deadField'),
    },
    '.go': {
        'contract.go': 'package parity\ntype Contract interface { required() bool }\n',
        'worker.go': (
            'package parity\ntype Worker struct{}\n'
            'func (Worker) required() bool { return false }\n'
            'func (Worker) dead() bool { return true }\n'
            'func init() {}\n'),
        'fields.go': 'package parity\nconst deadField = 1\nconst ExportedField = 1\n',
        'keep': ('required()', 'init()', 'ExportedField'),
        'remove': ('dead()', 'deadField'),
    },
    '.swift': {
        'Contract.swift': 'protocol Contract { func required() -> Bool }\n',
        'Worker.swift': (
            'class Worker: Contract {\n'
            '  func required() -> Bool { false }\n'
            '  @objc private func reflected() -> Bool { true }\n'
            '  private func dead() -> Bool { true }\n'
            '  private let deadField = 1\n'
            '  let apiField = 1\n'
            '}\n'),
        'keep': ('required()', 'reflected()', 'apiField'),
        'remove': ('dead()', 'deadField'),
    },
    '.dart': {
        'contract.dart': 'abstract class Contract { bool required(); }\n',
        'base.dart': 'abstract class Base { bool inherited(); }\n',
        'worker.dart': (
            'class Worker extends Base implements Contract {\n'
            '  @override bool required() => false;\n'
            '  @override bool inherited() => false;\n'
            "  @pragma('vm:entry-point') bool _reflected() => true;\n"
            '  bool _dead() => true;\n'
            '  final int _deadField = 1;\n'
            '  static const int apiField = 1;\n'
            '}\n'),
        'keep': ('required()', 'inherited()', '_reflected()', 'apiField'),
        'remove': ('_dead()', '_deadField'),
    },
}


class LanguageParityTests(unittest.TestCase):
    def test_scanner_detects_constant_methods_and_exact_arity(self):
        for ext, source in SCANNER_CASES.items():
            with self.subTest(ext=ext):
                methods = scan_method_definitions('/tmp/parity' + ext, source, ext)
                self.assertEqual(1, len(methods))
                self.assertEqual('boolean', methods[0]['kind'])
                self.assertEqual(EXPECTED_ARITY[ext], methods[0]['param_count'])

    def test_replacement_skips_each_language_string_form(self):
        for ext, source in STRING_CASES.items():
            with self.subTest(ext=ext):
                actual = step1_replace(source, [('FLAG', 'false')], ext)
                self.assertIn(b'false', actual)
                self.assertEqual(1, actual.count(b'FLAG'))

    def test_project_cleanup_preserves_contracts_and_runtime_entries(self):
        for ext, case in PROJECT_CASES.items():
            with self.subTest(ext=ext), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for name, content in case.items():
                    if isinstance(content, str):
                        (root / name).write_text(content, encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()):
                    step6_project(str(root))
                combined = '\n'.join(
                    path.read_text(encoding='utf-8')
                    for path in root.iterdir() if path.is_file())
                for symbol in case['keep']:
                    self.assertIn(symbol, combined)
                for symbol in case['remove']:
                    self.assertNotIn(symbol, combined)

    def test_incremental_scan_replaces_stale_contract_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = root / 'Contract.java'
            contract.write_text(
                'interface Contract { boolean required(); }\n', encoding='utf-8')
            (root / 'Worker.java').write_text(
                'class Worker implements Contract { '
                'public boolean required() { return false; } }\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                scan = scan_project(str(root))
            self.assertIn('required', scan.contracts.iface_methods['Contract'])
            contract.write_text('interface Contract {}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                scan.update_files({str(contract)})
            self.assertNotIn('required', scan.contracts.iface_methods['Contract'])

    def test_kotlin_trailing_lambda_calls_are_indexed(self):
        source = (
            'class LambdaDispatchSample {\n'
            '  fun release() { runOnWorker { println("release") } }\n'
            '  fun draw() { withExecutionScope { println("draw") } }\n'
            '  private fun runOnWorker(run: () -> Unit) { run() }\n'
            '  private fun withExecutionScope(draw: () -> Unit = {}) { draw() }\n'
            '}\n')
        path = '/tmp/LambdaDispatchSample.kt'
        methods = scan_method_definitions(path, source.encode(), '.kt')
        helpers = [
            m for m in methods
            if m['name'] in {'runOnWorker', 'withExecutionScope'}
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            live = _batch_same_file_refs(helpers, {path: source})
        self.assertEqual(2, len(live))

    def test_dry_run_executes_cascades_without_touching_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'Worker.java'
            original = (
                'class Worker {\n'
                '  private boolean dead() { return true; }\n'
                '}\n')
            source.write_text(original, encoding='utf-8')
            config = root / 'pruner.yaml'
            config.write_text('replacements: []\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                result = run_full_pipeline(str(root), str(config), dry_run=True)
            self.assertEqual(original, source.read_text(encoding='utf-8'))
            self.assertGreater(result['total']['changes'], 0)
            self.assertGreater(result['quality']['files_changed'], 0)

    def test_non_boolean_getter_is_not_constant_propagated(self):
        source_text = (
            'public class PageDescriptor {\n'
            '  private static String getPageId() { return "page_offline"; }\n'
            '  private static String orphanLabel() { return "unused"; }\n'
            '  private static boolean retired() { return false; }\n'
            '  public static void render() {\n'
            '    consume(getPageId());\n'
            '    if (retired()) { consume(orphanLabel()); }\n'
            '  }\n'
            '  public static void consume(String value) {}\n'
            '}\n')

        for cleanup in (step5_project, step6_project):
            with self.subTest(cleanup=cleanup.__name__), \
                    tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / 'PageDescriptor.java'
                source.write_text(source_text, encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()):
                    if cleanup is step6_project:
                        cleanup(tmp, world='open')
                    else:
                        cleanup(tmp)
                content = source.read_text(encoding='utf-8')
                self.assertIn('getPageId()', content)
                self.assertIn('consume(getPageId())', content)
                self.assertNotIn('consume("page_offline")', content)
                if cleanup is step6_project:
                    self.assertNotIn('orphanLabel()', content)
                    self.assertNotIn('retired()', content)


if __name__ == '__main__':
    unittest.main()
