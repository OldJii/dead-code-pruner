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
from pruner.config import ReplacementRule
from pruner.analysis.project_scan import scan_project
from pruner.pipeline import run_full_pipeline
from pruner.steps.constant_fold import phase1_step1_replace_constants
from pruner.steps.dead_methods import (
    _batch_same_file_refs,
    phase2_step2_cleanup_dead_declarations,
)
from pruner.steps.method_inline import inline_boolean_methods_standalone
from pruner.transform import load_config, run_pipeline
from pruner.validation import validate_transformation


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
    def test_java_field_default_is_not_treated_as_a_global_replacement(self):
        source = (
            'class AdPreloadConfig {\n'
            '  private boolean enable = false;\n'
            '  boolean needPreload(boolean whitelistHit) {\n'
            '    return enable || whitelistHit;\n'
            '  }\n'
            '}\n').encode()
        self.assertEqual(source, run_pipeline(source, [], ext='.java'))

    def test_java_cleanup_does_not_partially_empty_nested_if_body(self):
        source = (
            'class Settings {\n'
            '  int innerThoughtShouldSetRedDot(String userId, long max) {\n'
            '    try {\n'
            '      long now = System.currentTimeMillis() / 1000;\n'
            '      if (now < max) {\n'
            '        long exposure = dao.getRedDotExposure(userId);\n'
            '        return exposure == 0L ? 1 : 0;\n'
            '      }\n'
            '      return 0;\n'
            '    } catch (Exception e) {\n'
            '      return 0;\n'
            '    }\n'
            '  }\n'
            '}\n').encode()
        self.assertEqual(source, run_pipeline(source, [], ext='.java'))

    def test_java_semantic_gate_rejects_empty_nonvoid_method_body(self):
        original = (
            'enum Status { DONE; boolean terminal() { return this == DONE; } }'
        ).encode()
        broken = 'enum Status { DONE; boolean terminal() { } }'.encode()
        self.assertEqual(
            original, validate_transformation(original, broken, '.java'))

    def test_java_method_rule_rewrites_only_safe_invocations_and_cascades(self):
        source = (
            'class Screen {\n'
            '  String render(String userId) {\n'
            '    boolean hit = config.hit(userId);\n'
            '    String text = hit ? selected() : fallback();\n'
            '    return text;\n'
            '  }\n'
            '  boolean hit(String userId) { return false; }\n'
            '}\n').encode()
        rule = ReplacementRule(
            'config.hit', 'true', 'method_call', arity=1)
        actual = run_pipeline(source, [rule], ext='.java').decode()
        self.assertNotIn('config.hit(userId)', actual)
        self.assertNotIn('boolean hit = true', actual)
        self.assertIn('String text = selected();', actual)
        self.assertIn('boolean hit(String userId)', actual)

    def test_java_method_rule_preserves_nested_argument_side_effects(self):
        source = (
            'class Screen { boolean render() { '
            'return config.hit(loadUser()); } }').encode()
        safe = ReplacementRule('config.hit', 'true', 'method_call', arity=1)
        forced = ReplacementRule(
            'config.hit', 'true', 'method_call', arity=1,
            discard_side_effects=True)
        self.assertEqual(source, run_pipeline(source, [safe], ext='.java'))
        self.assertNotIn(
            'loadUser()', run_pipeline(source, [forced], ext='.java').decode())

    def test_effectively_final_java_boolean_is_not_propagated_after_reassign(self):
        source = (
            'class Screen { boolean render(boolean enabled) {\n'
            '  boolean hit = true;\n'
            '  hit = enabled;\n'
            '  return hit;\n'
            '} }\n').encode()
        self.assertEqual(source, run_pipeline(source, [], ext='.java'))

    def test_method_rule_config_requires_explicit_unqualified_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'pruner.yaml'
            config.write_text(
                'method_replacements:\n'
                '  - method: "config.hit"\n'
                '    arity: 1\n'
                '    value: true\n', encoding='utf-8')
            rules = load_config(str(config))
            self.assertEqual('method_call', rules[0].kind)
            self.assertEqual(1, rules[0].arity)
            config.write_text(
                'method_replacements:\n'
                '  - method: hit\n'
                '    value: true\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'allow_unqualified'):
                load_config(str(config))
            config.write_text(
                'replacements:\n'
                '  - pattern: enable\n'
                '    value: false\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'non-constant symbol'):
                load_config(str(config))

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
                actual = phase1_step1_replace_constants(
                    source, [('FLAG', 'false')], ext)
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
                    phase2_step2_cleanup_dead_declarations(str(root))
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

        for cleanup in (
                inline_boolean_methods_standalone,
                phase2_step2_cleanup_dead_declarations):
            with self.subTest(cleanup=cleanup.__name__), \
                    tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / 'PageDescriptor.java'
                source.write_text(source_text, encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()):
                    if cleanup is phase2_step2_cleanup_dead_declarations:
                        cleanup(tmp, world='open')
                    else:
                        cleanup(tmp)
                content = source.read_text(encoding='utf-8')
                self.assertIn('getPageId()', content)
                self.assertIn('consume(getPageId())', content)
                self.assertNotIn('consume("page_offline")', content)
                if cleanup is phase2_step2_cleanup_dead_declarations:
                    self.assertNotIn('orphanLabel()', content)
                    self.assertNotIn('retired()', content)

    def test_non_jvm_callable_values_keep_their_definitions(self):
        cases = {
            '.go': (
                'callbacks.go',
                'package callbacks\n'
                'func retired() bool { return false }\n'
                'var Callback = retired\n',
                'func retired() bool'),
            '.swift': (
                'Callbacks.swift',
                'private func retired() -> Bool { false }\n'
                'public let callback: () -> Bool = retired\n',
                'func retired() -> Bool'),
            '.dart': (
                'callbacks.dart',
                'bool _retired() => false;\n'
                'final callback = _retired;\n',
                'bool _retired()'),
        }
        for extension, (filename, source_text, definition) in cases.items():
            with self.subTest(extension=extension), \
                    tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / filename
                source.write_text(source_text, encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()):
                    phase2_step2_cleanup_dead_declarations(tmp, world='open')
                self.assertIn(definition, source.read_text(encoding='utf-8'))

    def test_cross_file_callable_value_is_in_the_language_reference_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = root / 'retired.go'
            definition.write_text(
                'package callbacks\nfunc retired() bool { return false }\n',
                encoding='utf-8')
            (root / 'callback.go').write_text(
                'package callbacks\nvar Callback = retired\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='open')
            self.assertIn(
                'func retired() bool', definition.read_text(encoding='utf-8'))

    def test_go_return_function_value_is_detected_as_reference(self):
        """Regression: Go functions returned as values (``return handler``)
        must be detected as referenced.  Without this, the pruner would
        delete the function definition despite it being used as a value."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'dispatch.go').write_text(
                'package dispatch\n\n'
                'type Handler func(string) error\n\n'
                'func Default() Handler {\n'
                '\treturn fallbackHandler\n'
                '}\n\n'
                'func fallbackHandler(s string) error { return nil }\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'dispatch.go').read_text(encoding='utf-8')
            self.assertIn('func fallbackHandler', content)

    def test_go_exported_receiver_method_preserved_for_interface_satisfaction(self):
        """Regression: Go exported receiver methods that match well-known stdlib
        interface methods (Network, String) or appear in an in-project interface
        must be preserved even when unreferenced."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'impl.go').write_text(
                'package impl\n\n'
                'type myAddr struct{ network, addr string }\n\n'
                'func (a myAddr) Network() string { return a.network }\n'
                'func (a myAddr) String() string  { return a.addr }\n'
                'func (a myAddr) secret() string   { return "x" }\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'impl.go').read_text(encoding='utf-8')
            self.assertIn('func (a myAddr) Network()', content)
            self.assertIn('func (a myAddr) String()', content)

    def test_go_exported_receiver_method_preserved_for_external_contracts(self):
        """Exported receiver methods can satisfy undeclared external interfaces."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'widget.go').write_text(
                'package widget\n\n'
                'type Widget struct{ name string }\n\n'
                'func NewWidget(n string) Widget { return Widget{name: n} }\n\n'
                'func (w Widget) Name() string { return w.name }\n\n'
                'func (w Widget) DeprecatedLegacyFormat() string {\n'
                '\treturn "legacy:" + w.name\n'
                '}\n',
                encoding='utf-8')
            (root / 'main.go').write_text(
                'package widget\n\n'
                'func use() {\n'
                '\tw := NewWidget("a")\n'
                '\t_ = w.Name()\n'
                '}\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'widget.go').read_text(encoding='utf-8')
            self.assertIn('func NewWidget', content)
            self.assertIn('func (w Widget) Name()', content)
            self.assertIn('DeprecatedLegacyFormat', content)

    def test_go_generic_call_and_receiver_method_value_are_references(self):
        """Generic calls and bound method values must keep their declarations."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'helpers.go').write_text(
                'package sample\n\n'
                'type cache struct{}\n'
                'func newIndex[T any]() *T { return new(T) }\n'
                'func (c *cache) evict(key string) {}\n'
                'func (c *cache) setup() { register(c.evict) }\n',
                encoding='utf-8')
            (root / 'caller.go').write_text(
                'package sample\n\n'
                'func use() { _ = newIndex[string]() }\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'helpers.go').read_text(encoding='utf-8')
            self.assertIn('func newIndex[T any]', content)
            self.assertIn('func (c *cache) evict', content)

    def test_java_record_methods_are_detected_and_cross_file_refs_work(self):
        """Regression: Java records (``public record Foo(...)`` ) must be
        recognised as class-level declarations.  Methods on records must
        correctly find cross-file references."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'MyRecord.java').write_text(
                'public record MyRecord(String name) {\n'
                '  public static MyRecord of(String n) { return new MyRecord(n); }\n'
                '  private static void dead() {}\n'
                '}\n', encoding='utf-8')
            (root / 'Caller.java').write_text(
                'class Caller {\n'
                '  MyRecord create() { return MyRecord.of("x"); }\n'
                '}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            record_content = (root / 'MyRecord.java').read_text(encoding='utf-8')
            self.assertIn('public static MyRecord of', record_content)
            self.assertNotIn('dead()', record_content)

    def test_java_annotation_type_in_class_node_types(self):
        """Regression: ``annotation_type_declaration`` must be in
        ``JavaAdapter.class_node_types`` so that methods declared inside
        annotation types receive a correct ``class_name``."""
        from pruner.adapters.java import JavaAdapter
        adapter = JavaAdapter()
        self.assertIn('annotation_type_declaration', adapter.class_node_types)

    def test_java_annotation_type_not_deleted_when_referenced(self):
        """Annotation types that are referenced should not be deleted even
        though they have no regular method declarations."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'MyAnnotation.java').write_text(
                'public @interface MyAnnotation {\n'
                '  String value() default "";\n'
                '}\n', encoding='utf-8')
            (root / 'Usage.java').write_text(
                '@MyAnnotation(value = "test")\n'
                'class Usage {\n'
                '  void run() {}\n'
                '}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            self.assertTrue(
                (root / 'MyAnnotation.java').exists(),
                "annotation type file should not be deleted")

    def test_swift_multiline_return_is_not_treated_as_bare_exit(self):
        """Regression: Swift ``return`` followed by the value expression
        on the next line must not be treated as a bare exit.  Tree-sitter
        parses it as two sibling nodes, but the code is NOT unreachable."""
        source = (
            'func test() -> [String] {\n'
            '    return\n'
            '      ["a"]\n'
            '      + ["b"]\n'
            '}\n'
        ).encode()
        result = run_pipeline(source, ext='.swift')
        self.assertIn(b'["a"]', result)
        self.assertIn(b'["b"]', result)

    def test_swift_computed_property_multiline_return_is_preserved(self):
        source = (
            'struct Values {\n'
            '  var description: String {\n'
            '    return\n'
            '      values.map(String.init).joined(separator: ",")\n'
            '  }\n'
            '}\n'
        ).encode()
        result = run_pipeline(source, ext='.swift')
        self.assertIn(b'values.map', result)

    def test_swift_bare_return_followed_by_statement_is_unreachable(self):
        """Regression: code after a truly bare ``return`` in a void function
        must be deleted when the next sibling is a statement/declaration type,
        not an expression that could be a multi-line return continuation."""
        source = (
            'func cleanup() {\n'
            '    return\n'
            '    let x = 42\n'
            '    print(x)\n'
            '}\n'
        ).encode()
        result = run_pipeline(source, ext='.swift')
        self.assertNotIn(b'let x = 42', result)
        self.assertNotIn(b'print(x)', result)
        self.assertIn(b'return', result)

    def test_swift_void_return_followed_by_call_is_unreachable(self):
        source = (
            'func cleanup() {\n'
            '    return\n'
            '    print("dead")\n'
            '}\n'
        ).encode()
        result = run_pipeline(source, ext='.swift')
        self.assertNotIn(b'print', result)

    def test_swift_conditional_compilation_directives_are_preserved(self):
        """Regression: Swift ``#if``/``#else``/``#endif`` directives must not
        be removed by unreachable code elimination.  They are compile-time
        constructs that control cross-platform compilation."""
        source = (
            'func value() -> Int {\n'
            '    #if os(Windows)\n'
            '    return 1\n'
            '    #else\n'
            '    return 2\n'
            '    #endif\n'
            '}\n'
        ).encode()
        result = run_pipeline(source, ext='.swift')
        self.assertIn(b'#if os(Windows)', result)
        self.assertIn(b'#else', result)
        self.assertIn(b'#endif', result)
        self.assertIn(b'return 1', result)
        self.assertIn(b'return 2', result)

    def test_non_jvm_boolean_folding_keeps_left_operand_evaluation(self):
        cases = {
            '.go': b'package p\nvar a = side() && false\nvar b = side() || true\n',
            '.swift': b'let a = side() && false\nlet b = side() || true\n',
            '.dart': b'final a = side() && false;\nfinal b = side() || true;\n',
        }
        for extension, source in cases.items():
            with self.subTest(extension=extension):
                result = run_pipeline(source, ext=extension)
                self.assertIn(b'side() && false', result)
                self.assertIn(b'side() || true', result)

        # Java/Kotlin deliberately retain the established Android output.
        java = run_pipeline(
            b'class W { boolean a = side() && false; }', ext='.java')
        kotlin = run_pipeline(
            b'class W { val a = side() && false }', ext='.kt')
        self.assertIn(b'boolean a = false', java)
        self.assertIn(b'val a = false', kotlin)


    def test_dart_static_modifier_detected_on_methods_and_getters(self):
        """Regression: Dart ``static`` modifier appears as a direct child node
        of type ``'static'`` in the AST, not inside a ``modifiers`` wrapper.
        The scanner must detect it for both regular methods and getters."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'helper.dart').write_text(
                'class Helper {\n'
                '  static bool _isLocal(String x) {\n'
                '    return x.startsWith("10.");\n'
                '  }\n'
                '  static bool get useLegacy => false;\n'
                '}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'helper.dart').read_text(encoding='utf-8')
            self.assertNotIn('_isLocal', content)
            self.assertNotIn('useLegacy', content)

    def test_dart_private_unreferenced_methods_are_pruned(self):
        """Dart private (underscore-prefixed) methods should be prunable
        when unreferenced, since privacy is library-scoped."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'util.dart').write_text(
                'String greet() => "hello";\n'
                'String _unused() => "never called";\n',
                encoding='utf-8')
            (root / 'main.dart').write_text(
                'import "util.dart";\n'
                'void main() { print(greet()); }\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'util.dart').read_text(encoding='utf-8')
            self.assertIn('greet', content)
            self.assertNotIn('_unused', content)

    def test_dart_generic_private_function_call_is_preserved(self):
        """Generic invocations use ``name<T>(...)`` rather than ``name(...)``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'worker.dart'
            source.write_text(
                'void start() { run((value) => _worker<String>(value)); }\n'
                'String _worker<T>(T value) => value.toString();\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            self.assertIn('_worker<T>', source.read_text(encoding='utf-8'))

    def test_dart_generated_files_are_not_modified(self):
        """Regression: Dart files matching generated-code naming conventions
        (.g.dart, .freezed.dart, .gen.dart) must not have definitions deleted
        or code simplified, even though they are scanned for references."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'strings_en.g.dart').write_text(
                'class GeneratedStrings {\n'
                '  String get accept => "Accept";\n'
                '  String get cancel => "Cancel";\n'
                '  static void _unused() {}\n'
                '}\n', encoding='utf-8')
            (root / 'app.dart').write_text(
                'import "strings_en.g.dart";\n'
                'void main() {\n'
                '  final s = GeneratedStrings();\n'
                '  print(s.accept);\n'
                '}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'strings_en.g.dart').read_text(encoding='utf-8')
            self.assertIn('get accept', content)
            self.assertIn('get cancel', content)
            self.assertIn('_unused', content)

    def test_dart_generated_files_provide_references(self):
        """Generated Dart files must still be indexed for outgoing references
        so that symbols called only FROM generated code are preserved."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'helper.dart').write_text(
                'String _format(String s) => s.toUpperCase();\n',
                encoding='utf-8')
            (root / 'generated.g.dart').write_text(
                'import "helper.dart";\n'
                'String build() => _format("hello");\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'helper.dart').read_text(encoding='utf-8')
            self.assertIn('_format', content)

    def test_shell_variant_rewrite_preserves_dart_symbol(self):
        """A symbol selected by a build-variant sed rewrite is live."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'provider.dart').write_text(
                'final defaultProvider = Object();\n'
                'final fossProvider = Object();\n', encoding='utf-8')
            (root / 'page.dart').write_text(
                'void main() { print(defaultProvider); }\n', encoding='utf-8')
            (root / 'build_foss.sh').write_text(
                "sed -i 's/defaultProvider/fossProvider/g' page.dart\n",
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'provider.dart').read_text(encoding='utf-8')
            self.assertIn('fossProvider', content)

    # ── Annotation-string method references ─────────────────────

    def test_jvm_annotation_string_ref_preserves_method(self):
        """JUnit 5 @EnabledIf / @MethodSource reference methods by string
        argument — such methods must not be deleted as unreferenced."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Test.java').write_text(
                'import org.junit.jupiter.api.Test;\n'
                'import org.junit.jupiter.api.condition.EnabledIf;\n\n'
                'class TestCompression {\n'
                '    @EnabledIf("brotliAvailable")\n'
                '    @Test\n'
                '    void testBrotli() {}\n\n'
                '    private static boolean brotliAvailable() {\n'
                '        return true;\n'
                '    }\n\n'
                '    private static boolean unreferencedHelper() {\n'
                '        return false;\n'
                '    }\n'
                '}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'Test.java').read_text(encoding='utf-8')
            self.assertIn('brotliAvailable', content,
                          "@EnabledIf-referenced method must be preserved")
            self.assertNotIn('unreferencedHelper', content,
                             "truly unreferenced method should be deleted")

    def test_kotlin_annotation_string_ref_preserves_method(self):
        """Kotlin @MethodSource annotation references must also be detected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Test.kt').write_text(
                'import org.junit.jupiter.params.provider.MethodSource\n\n'
                'class ParamTest {\n'
                '    @MethodSource("dataProvider")\n'
                '    fun testData() {}\n\n'
                '    companion object {\n'
                '        @JvmStatic\n'
                '        private fun dataProvider() = listOf("a", "b")\n'
                '    }\n'
                '}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'Test.kt').read_text(encoding='utf-8')
            self.assertIn('dataProvider', content,
                          "@MethodSource-referenced method must be preserved")


    def test_swift_empty_struct_referenced_by_dot_self_preserved(self):
        """Swift struct referenced via Type.self must not be deleted as empty."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'main.swift').write_text(
                'struct Foo: ParsableCommand {}\n'
                'private struct Bar: ParsableCommand {}\n\n'
                'let types: [Any.Type] = [Foo.self, Bar.self]\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = (root / 'main.swift').read_text(encoding='utf-8')
            self.assertIn('Bar', content,
                          "Empty struct referenced via .self must be preserved")

    def test_kotlin_class_field_not_propagated(self):
        """Class-level val booleans must not be propagated as local constants."""
        code = (
            b'class Config(val enabled: Boolean = false) {\n'
            b'    fun render() = if (enabled) "on" else "off"\n'
            b'}\n'
        )
        result = run_pipeline(code, [], ext='.kt')
        self.assertIn(b'enabled', result,
                      "Class constructor param must not be propagated")
        self.assertIn(b'if (enabled)', result,
                      "if-expression using class param must be preserved")

    def test_java_boolean_field_is_not_treated_as_unused_local(self):
        """A nested-class field may be referenced outside its class body."""
        code = (
            b'class PackageManager {\n'
            b'    void update(SYNC sync, boolean success) {\n'
            b'        sync.success = success;\n'
            b'        if (!sync.success) throw new IllegalStateException();\n'
            b'    }\n'
            b'    private static final class SYNC {\n'
            b'        boolean success = false;\n'
            b'    }\n'
            b'}\n'
        )
        result = run_pipeline(code, [], ext='.java')
        self.assertIn(b'boolean success = false;', result)
        self.assertIn(b'sync.success = success;', result)

    def test_kotlin_private_infix_extension_call_is_preserved(self):
        """Infix calls do not use ``name(...)`` syntax but are real references."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'Lesson.kt'
            source.write_text(
                'class Lesson {\n'
                '  fun test() {\n'
                '    val pair = "custom content" withWeight 10\n'
                '    println(pair)\n'
                '  }\n'
                '  private infix fun String.withWeight(weight: Int): Pair<String, Int> {\n'
                '    return Pair(this, weight)\n'
                '  }\n'
                '}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            self.assertIn(
                'fun String.withWeight', source.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
