"""Project layout detection — discovers module boundaries for multi-module projects.

Handles Gradle (Android / JVM), Go modules, Dart/Flutter packages, Maven,
and Xcode workspaces.  Each source file is mapped to a *module identifier*
so that same-named methods in different modules are not conflated during
dead-code analysis.
"""

from __future__ import annotations

import os
import re


class ProjectLayout:
    """Lazily-detected project structure with file → module mapping."""

    __slots__ = ('root', '_modules', '_file_cache', '_kind')

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self._modules: list[_Module] | None = None
        self._file_cache: dict[str, str | None] = {}
        self._kind: str = 'unknown'

    @property
    def kind(self) -> str:
        """Project kind: ``'gradle'``, ``'go'``, ``'dart'``, ``'maven'``,
        ``'swiftpm'``, ``'xcode'``, or ``'single'``."""
        self._ensure_detected()
        return self._kind

    @property
    def modules(self) -> list[str]:
        """Human-readable module names."""
        self._ensure_detected()
        assert self._modules is not None
        return [m.name for m in self._modules]

    @property
    def module_entries(self) -> list[tuple[str, str]]:
        """Return ``(module name, absolute path)`` pairs for policy analysis."""
        self._ensure_detected()
        assert self._modules is not None
        return [(m.name, m.path) for m in self._modules]

    def get_module(self, filepath: str) -> str | None:
        """Return the module name for *filepath*, or ``None`` (single-module)."""
        abs_fp = os.path.abspath(filepath)
        if abs_fp in self._file_cache:
            return self._file_cache[abs_fp]
        self._ensure_detected()
        assert self._modules is not None
        result: str | None = None
        best_len = -1
        for mod in self._modules:
            if abs_fp.startswith(mod.path + os.sep) and len(mod.path) > best_len:
                result = mod.name
                best_len = len(mod.path)
        self._file_cache[abs_fp] = result
        return result

    def _ensure_detected(self):
        if self._modules is not None:
            return
        self._modules = []
        if self._try_gradle():
            self._kind = 'gradle'
        elif self._try_go():
            self._kind = 'go'
        elif self._try_dart():
            self._kind = 'dart'
        elif self._try_maven():
            self._kind = 'maven'
        elif self._try_swiftpm():
            self._kind = 'swiftpm'
        elif self._try_xcode():
            self._kind = 'xcode'
        else:
            self._kind = 'single'
            self._modules = [_Module(':root', self.root)]

    # ── Gradle ────────────────────────────────────────────────

    def _try_gradle(self) -> bool:
        for name in ('settings.gradle', 'settings.gradle.kts'):
            path = os.path.join(self.root, name)
            if os.path.isfile(path):
                self._parse_gradle_settings(path)
                return True
        if os.path.isfile(os.path.join(self.root, 'build.gradle')) or \
           os.path.isfile(os.path.join(self.root, 'build.gradle.kts')):
            self._modules = [_Module(':root', self.root)]
            return True
        return False

    def _parse_gradle_settings(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            self._modules = [_Module(':root', self.root)]
            return

        include_pat = re.compile(
            r'\binclude\s*(?:\((.*?)\)|([^\n]+))', re.S)
        module_pat = re.compile(r"['\"](:[\w:.-]+)['\"]")
        seen: set[str] = set()
        for statement in include_pat.finditer(content):
            payload = statement.group(1) or statement.group(2) or ''
            for module in module_pat.finditer(payload):
                mod_path_str = module.group(1)
                if mod_path_str in seen:
                    continue
                seen.add(mod_path_str)
                rel = mod_path_str.lstrip(':').replace(':', os.sep)
                abs_path = os.path.join(self.root, rel)
                if os.path.isdir(abs_path):
                    self._modules.append(_Module(mod_path_str, abs_path))

        if not self._modules:
            for entry in os.listdir(self.root):
                candidate = os.path.join(self.root, entry)
                if os.path.isdir(candidate):
                    if os.path.isfile(os.path.join(candidate, 'build.gradle')) or \
                       os.path.isfile(os.path.join(candidate, 'build.gradle.kts')):
                        self._modules.append(_Module(':' + entry, candidate))
            if not self._modules:
                self._modules = [_Module(':root', self.root)]

    # ── Go ────────────────────────────────────────────────────

    def _try_go(self) -> bool:
        work_file = os.path.join(self.root, 'go.work')
        if os.path.isfile(work_file):
            try:
                with open(work_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except OSError:
                content = ''
            paths = re.findall(r'(?m)^\s*use\s+([^\s#]+)', content)
            paths.extend(re.findall(r'(?m)^\s*(\.?\.?/[^\s#]+)\s*$', content))
            seen: set[str] = set()
            for raw in paths:
                rel = raw.strip('"\'').rstrip('/')
                candidate = os.path.abspath(os.path.join(self.root, rel))
                if candidate in seen or not os.path.isfile(os.path.join(candidate, 'go.mod')):
                    continue
                seen.add(candidate)
                name = os.path.relpath(candidate, self.root)
                self._modules.append(_Module(name, candidate))
            if not self._modules:
                self._modules = [_Module('root', self.root)]
            return True
        if os.path.isfile(os.path.join(self.root, 'go.mod')):
            self._modules = [_Module('root', self.root)]
            for entry in os.listdir(self.root):
                candidate = os.path.join(self.root, entry)
                if os.path.isdir(candidate) and \
                   os.path.isfile(os.path.join(candidate, 'go.mod')):
                    self._modules.append(_Module(entry, candidate))
            return True
        return False

    # ── Dart / Flutter ────────────────────────────────────────

    def _try_dart(self) -> bool:
        if os.path.isfile(os.path.join(self.root, 'pubspec.yaml')):
            self._modules = [_Module('root', self.root)]
            seen = {self.root}
            try:
                with open(os.path.join(self.root, 'pubspec.yaml'), 'r',
                          encoding='utf-8', errors='ignore') as f:
                    pubspec = f.read()
            except OSError:
                pubspec = ''
            workspace = re.search(
                r'(?ms)^workspace\s*:\s*\n((?:^[ \t]+-\s*[^\n]+\n?)*)',
                pubspec)
            if workspace:
                for raw in re.findall(r'(?m)^\s*-\s*([^#\s]+)', workspace.group(1)):
                    candidate = os.path.abspath(os.path.join(self.root, raw.strip('"\'')))
                    if (candidate not in seen
                            and os.path.isfile(os.path.join(candidate, 'pubspec.yaml'))):
                        seen.add(candidate)
                        self._modules.append(_Module(
                            os.path.relpath(candidate, self.root), candidate))
            packages_dir = os.path.join(self.root, 'packages')
            if os.path.isdir(packages_dir):
                for entry in os.listdir(packages_dir):
                    candidate = os.path.join(packages_dir, entry)
                    if candidate not in seen and os.path.isdir(candidate) and \
                       os.path.isfile(os.path.join(candidate, 'pubspec.yaml')):
                        seen.add(candidate)
                        self._modules.append(_Module(entry, candidate))
            return True
        return False

    # ── Maven ─────────────────────────────────────────────────

    def _try_maven(self) -> bool:
        if os.path.isfile(os.path.join(self.root, 'pom.xml')):
            self._modules = [_Module('root', self.root)]
            try:
                with open(os.path.join(self.root, 'pom.xml'), 'r',
                          encoding='utf-8', errors='ignore') as f:
                    pom = f.read()
            except OSError:
                pom = ''
            seen = {self.root}
            for raw in re.findall(r'<module>\s*([^<]+?)\s*</module>', pom):
                candidate = os.path.abspath(os.path.join(self.root, raw.strip()))
                if (candidate not in seen
                        and os.path.isfile(os.path.join(candidate, 'pom.xml'))):
                    seen.add(candidate)
                    self._modules.append(_Module(raw.strip(), candidate))
            for entry in os.listdir(self.root):
                candidate = os.path.join(self.root, entry)
                if candidate not in seen and os.path.isdir(candidate) and \
                   os.path.isfile(os.path.join(candidate, 'pom.xml')):
                    seen.add(candidate)
                    self._modules.append(_Module(entry, candidate))
            return True
        return False

    # ── Swift Package Manager ─────────────────────────────────

    def _try_swiftpm(self) -> bool:
        manifest = os.path.join(self.root, 'Package.swift')
        if not os.path.isfile(manifest):
            return False
        try:
            with open(manifest, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except OSError:
            self._modules = [_Module('root', self.root)]
            return True

        target_pattern = re.compile(
            r'\.(target|executableTarget)\s*\(\s*name\s*:\s*"([^"]+)"'
            r'(?P<body>.*?)(?=\n\s*\.(?:target|executableTarget|testTarget)\s*\(|\n\s*\]\s*\)|\Z)',
            re.S)
        seen: set[str] = set()
        for match in target_pattern.finditer(content):
            kind, name = match.group(1), match.group(2)
            path_match = re.search(r'\bpath\s*:\s*"([^"]+)"', match.group('body'))
            rel = path_match.group(1) if path_match else os.path.join('Sources', name)
            candidate = os.path.abspath(os.path.join(self.root, rel))
            if candidate in seen or not os.path.isdir(candidate):
                continue
            seen.add(candidate)
            prefix = 'swiftpm:executable' if kind == 'executableTarget' else 'swiftpm:target'
            self._modules.append(_Module(f'{prefix}:{name}', candidate))
        if not self._modules:
            self._modules = [_Module('root', self.root)]
        return True

    # ── Xcode ─────────────────────────────────────────────────

    def _try_xcode(self) -> bool:
        for entry in os.listdir(self.root):
            if entry.endswith('.xcworkspace') or entry.endswith('.xcodeproj'):
                self._modules = [_Module('root', self.root)]
                return True
        return False


class _Module:
    __slots__ = ('name', 'path')

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = os.path.abspath(path)

    def __repr__(self):
        return f'_Module({self.name!r}, {self.path!r})'
