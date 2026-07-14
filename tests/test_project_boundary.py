"""Project-boundary detection and open/closed-world cleanup tests."""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from pruner.analysis.project_boundary import detect_project_boundary  # noqa: E402
from pruner.config import load_boundary_options  # noqa: E402
from pruner.steps.dead_methods import phase2_step2_cleanup_dead_declarations  # noqa: E402
from pruner.steps.empty_cleanup import phase2_step5_cleanup_empty_artifacts  # noqa: E402
from pruner.transform import load_config  # noqa: E402


class ProjectBoundaryDetectionTests(unittest.TestCase):
    def test_unknown_project_falls_back_to_open_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            boundary = detect_project_boundary(tmp)
            self.assertEqual('open', boundary.world)
            self.assertIn('safe fallback', boundary.modules[0].reasons[0])

    def test_gradle_app_and_library_are_classified_per_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'settings.gradle').write_text(
                "include(':app', ':sdk')\n", encoding='utf-8')
            for module in ('app', 'sdk'):
                (root / module).mkdir()
            (root / 'app' / 'build.gradle').write_text(
                "plugins { id 'com.android.application' }\n",
                encoding='utf-8')
            (root / 'sdk' / 'build.gradle').write_text(
                "plugins { id 'com.android.library'; id 'maven-publish' }\n",
                encoding='utf-8')

            boundary = detect_project_boundary(str(root))
            self.assertEqual('mixed', boundary.world)
            self.assertEqual(
                'closed', boundary.world_for_file(str(root / 'app' / 'App.java')))
            self.assertEqual(
                'open', boundary.world_for_file(str(root / 'sdk' / 'Api.java')))

    def test_unpublished_gradle_library_is_internal_to_application(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'settings.gradle').write_text(
                "include(':app', ':feature')\n", encoding='utf-8')
            for module in ('app', 'feature'):
                (root / module).mkdir()
            (root / 'app' / 'build.gradle').write_text(
                "plugins { id 'com.android.application' }\n",
                encoding='utf-8')
            (root / 'feature' / 'build.gradle').write_text(
                "plugins { id 'com.android.library' }\n",
                encoding='utf-8')

            boundary = detect_project_boundary(str(root))
            self.assertEqual('closed', boundary.world)
            self.assertEqual(
                'closed', boundary.world_for_file(
                    str(root / 'feature' / 'InternalApi.java')))

    def test_root_go_executable_is_closed_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'go.mod').write_text(
                'module example.invalid/service\n', encoding='utf-8')
            (root / 'main.go').write_text(
                'package main\nfunc main() {}\n', encoding='utf-8')
            self.assertEqual('closed', detect_project_boundary(str(root)).world)

    def test_jvm_service_plugin_is_closed_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'build.gradle.kts').write_text(
                'plugins { id("org.springframework.boot") version "3.4.0" }\n',
                encoding='utf-8')
            self.assertEqual('closed', detect_project_boundary(str(root)).world)

    def test_deployment_manifest_closes_standalone_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Dockerfile').write_text(
                'FROM example.invalid/runtime\n', encoding='utf-8')
            self.assertEqual('closed', detect_project_boundary(str(root)).world)

    def test_open_signal_wins_executable_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Package.swift').write_text(
                'products: [.library(name: "Core", targets: ["Core"]), '
                '.executable(name: "Tool", targets: ["Tool"])]\n',
                encoding='utf-8')
            self.assertEqual('open', detect_project_boundary(str(root)).world)

    def test_config_supports_global_and_module_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'pruner.yaml'
            config.write_text(
                'project_boundary:\n'
                '  mode: auto\n'
                '  modules:\n'
                '    ":app": closed\n'
                '    ":sdk": open\n'
                'replacements: []\n',
                encoding='utf-8')
            mode, modules = load_boundary_options(str(config))
            self.assertEqual('auto', mode)
            self.assertEqual({':app': 'closed', ':sdk': 'open'}, modules)
            self.assertEqual([], load_config(str(config)))


class ProjectBoundaryCleanupTests(unittest.TestCase):
    JAVA_SOURCE = (
        'public class ApiSurface {\n'
        '  public static boolean publicConstant() { return true; }\n'
        '  public static void publicArbitrary() { System.out.println("x"); }\n'
        '  private static boolean privateConstant() { return true; }\n'
        '  private static void privateArbitrary() { System.out.println("x"); }\n'
        '  public static final String PUBLIC_FIELD = "public";\n'
        '  private static final String PRIVATE_FIELD = "private";\n'
        '}\n'
    )

    LANGUAGE_API_CASES = {
        '.kt': (
            'fun exportedHook(): Boolean = true\n'
            'private fun privateHook(): Boolean = true\n'
            'const val EXPORTED_VALUE = true\n'
            'private const val privateValue = true\n'),
        '.swift': (
            'public func exportedHook() -> Bool { true }\n'
            'private func privateHook() -> Bool { true }\n'
            'public let EXPORTED_VALUE = true\n'
            'private let privateValue = true\n'),
        '.dart': (
            'bool exportedHook() => true;\n'
            'bool _privateHook() => true;\n'
            'const bool EXPORTED_VALUE = true;\n'
            'const bool _privateValue = true;\n'),
    }

    def _clean_java(self, world: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'ApiSurface.java'
            source.write_text(self.JAVA_SOURCE, encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world=world)
            return source.read_text(encoding='utf-8')

    def test_open_world_preserves_public_api_and_removes_private_members(self):
        content = self._clean_java('open')
        self.assertIn('publicConstant()', content)
        self.assertIn('publicArbitrary()', content)
        self.assertIn('PUBLIC_FIELD', content)
        self.assertNotIn('privateConstant()', content)
        self.assertNotIn('privateArbitrary()', content)
        self.assertNotIn('PRIVATE_FIELD', content)

    def test_closed_world_removes_unreferenced_public_static_members(self):
        content = self._clean_java('closed')
        self.assertNotIn('publicConstant()', content)
        self.assertNotIn('publicArbitrary()', content)
        self.assertNotIn('PUBLIC_FIELD', content)
        self.assertNotIn('privateConstant()', content)
        self.assertNotIn('privateArbitrary()', content)
        self.assertNotIn('PRIVATE_FIELD', content)

    def test_language_api_surfaces_follow_the_same_world_policy(self):
        for extension, source_text in self.LANGUAGE_API_CASES.items():
            for world, exported_kept in (('open', True), ('closed', False)):
                with self.subTest(extension=extension, world=world), \
                        tempfile.TemporaryDirectory() as tmp:
                    source = Path(tmp) / ('surface' + extension)
                    source.write_text(source_text, encoding='utf-8')
                    with contextlib.redirect_stdout(io.StringIO()):
                        phase2_step2_cleanup_dead_declarations(tmp, world=world)
                    content = source.read_text(encoding='utf-8')
                    self.assertEqual(
                        exported_kept, 'exportedHook' in content)
                    self.assertEqual(
                        exported_kept, 'EXPORTED_VALUE' in content)
                    self.assertNotIn('privateHook', content)
                    self.assertNotIn('privateValue', content)

    def test_mixed_gradle_cleanup_does_not_leak_app_policy_into_sdk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'settings.gradle').write_text(
                "include ':app'\ninclude ':sdk'\n", encoding='utf-8')
            app = root / 'app'
            sdk = root / 'sdk'
            app.mkdir()
            sdk.mkdir()
            (app / 'build.gradle').write_text(
                "plugins { id 'com.android.application' }\n", encoding='utf-8')
            (sdk / 'build.gradle').write_text(
                "plugins { id 'com.android.library'; id 'maven-publish' }\n",
                encoding='utf-8')
            app_source = app / 'AppHooks.java'
            sdk_source = sdk / 'SdkHooks.java'
            app_source.write_text(
                'class AppHooks { public static boolean unused() { return true; } }\n',
                encoding='utf-8')
            sdk_source.write_text(
                'public class SdkHooks { public static boolean unused() { return true; } }\n',
                encoding='utf-8')

            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(str(root))
            self.assertNotIn('unused()', app_source.read_text(encoding='utf-8'))
            self.assertIn('unused()', sdk_source.read_text(encoding='utf-8'))

    def test_kotlin_generated_getters_protect_properties_from_java_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            properties = root / 'Properties.kt'
            properties.write_text(
                'val deferredLabel: String by lazy { "ready" }\n'
                'val isReady: Boolean = true\n'
                'val unusedLabel: String = "unused"\n',
                encoding='utf-8')
            (root / 'JavaConsumer.java').write_text(
                'class JavaConsumer {\n'
                '  String label = PropertiesKt.getDeferredLabel();\n'
                '  boolean ready = PropertiesKt.isReady();\n'
                '}\n',
                encoding='utf-8')

            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='closed')
            content = properties.read_text(encoding='utf-8')
            self.assertIn('deferredLabel', content)
            self.assertIn('isReady', content)
            self.assertNotIn('unusedLabel', content)

    def test_empty_public_class_is_preserved_open_and_removed_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'PublicSurface.java'
            source.write_text('public class PublicSurface {}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step5_cleanup_empty_artifacts(tmp, world='open')
            self.assertTrue(source.exists())
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step5_cleanup_empty_artifacts(tmp, world='closed')
            self.assertFalse(source.exists())

    def test_open_world_removes_language_private_empty_types(self):
        cases = {
            '.kt': 'private class PrivateEmpty {}\n',
            '.swift': 'private class PrivateEmpty {}\n',
            '.dart': 'class _PrivateEmpty {}\n',
        }
        for extension, source_text in cases.items():
            with self.subTest(extension=extension), \
                    tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / ('PrivateEmpty' + extension)
                source.write_text(source_text, encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()):
                    phase2_step5_cleanup_empty_artifacts(tmp, world='open')
                self.assertFalse(source.exists())

    def test_go_export_is_preserved_open_and_pruned_for_service(self):
        source_text = (
            'package main\n'
            'func main() {}\n'
            'func ExportedUnused() bool { return true }\n'
            'func privateUnused() bool { return true }\n')
        for world, exported_kept in (('open', True), ('closed', False)):
            with self.subTest(world=world), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'go.mod').write_text(
                    'module example.invalid/service\n', encoding='utf-8')
                source = root / 'main.go'
                source.write_text(source_text, encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()):
                    phase2_step2_cleanup_dead_declarations(tmp, world=world)
                content = source.read_text(encoding='utf-8')
                self.assertEqual(exported_kept, 'ExportedUnused()' in content)
                self.assertNotIn('privateUnused()', content)

    def test_dart_multiline_constant_span_and_metadata_are_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'constants.dart'
            source.write_text(
                "@pragma('vm:entry-point')\n"
                'const bool _runtimeValue = true;\n'
                'const bool\n'
                '    _unusedValue = true;\n',
                encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                phase2_step2_cleanup_dead_declarations(tmp, world='open')
            content = source.read_text(encoding='utf-8')
            self.assertIn('_runtimeValue', content)
            self.assertNotIn('_unusedValue', content)
            self.assertNotIn('const bool\n\n', content)


if __name__ == '__main__':
    unittest.main()
