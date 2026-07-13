"""Project-boundary detection for closed- and open-world cleanup.

Dead-reference proof has different meaning in an application and a published
library.  An application or deployed service normally owns every source-level
caller, while a library can be called by consumers outside the scanned tree.
This module centralises that distinction and keeps build-system heuristics out
of member-cleanup code.

Automatic detection is deliberately asymmetric: strong application/service
evidence selects ``closed``; publishing evidence selects ``open`` and wins
conflicts.  Unpublished modules inside a closed Gradle build share its closed
boundary, while standalone libraries and missing or ambiguous layouts remain
``open``.  Explicit global and per-module overrides handle metadata that cannot
describe the deployment boundary completely.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re

from .project_layout import ProjectLayout

AUTO = 'auto'
CLOSED = 'closed'
OPEN = 'open'
WORLD_MODES = frozenset({AUTO, CLOSED, OPEN})


@dataclass(frozen=True)
class ModuleBoundary:
    name: str
    path: str
    world: str
    reasons: tuple[str, ...]
    explicit: bool = False


class ProjectBoundary:
    """Immutable file-to-world mapping, with longest-module-path matching."""

    __slots__ = ('root', 'modules', 'fallback', '_ordered')

    def __init__(self, root: str, modules: list[ModuleBoundary], *,
                 fallback: ModuleBoundary | None = None):
        self.root = os.path.abspath(root)
        self.modules = tuple(modules)
        self.fallback = fallback or self.modules[0]
        self._ordered = tuple(sorted(
            self.modules, key=lambda item: len(item.path), reverse=True))

    @property
    def world(self) -> str:
        worlds = {module.world for module in self.modules}
        if len(worlds) == 1:
            return next(iter(worlds))
        return 'mixed'

    def module_for_file(self, filepath: str) -> ModuleBoundary:
        absolute = os.path.abspath(filepath)
        for module in self._ordered:
            if absolute == module.path or absolute.startswith(module.path + os.sep):
                return module
        return self.fallback

    def world_for_file(self, filepath: str) -> str:
        return self.module_for_file(filepath).world

    def allows_external_api_pruning(self, filepath: str) -> bool:
        return self.world_for_file(filepath) == CLOSED

    def summary(self) -> str:
        counts = {OPEN: 0, CLOSED: 0}
        for module in self.modules:
            counts[module.world] += 1
        if self.world != 'mixed':
            return f"{self.world} ({len(self.modules)} module(s))"
        return (f"mixed ({counts[CLOSED]} closed, "
                f"{counts[OPEN]} open module(s))")


def _read(path: str, limit: int = 512_000) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
            return handle.read(limit)
    except OSError:
        return ''


def _first_existing(path: str, names: tuple[str, ...]) -> str:
    for name in names:
        candidate = os.path.join(path, name)
        if os.path.isfile(candidate):
            return _read(candidate)
    return ''


def _gradle_evidence(path: str) -> tuple[list[str], list[str]]:
    text = _first_existing(path, ('build.gradle.kts', 'build.gradle'))
    if not text:
        return [], []
    closed: list[str] = []
    opened: list[str] = []
    closed_patterns = (
        ('com.android.application', 'Android application plugin'),
        ('org.springframework.boot', 'Spring Boot application plugin'),
        ('io.quarkus', 'Quarkus application plugin'),
        ('io.micronaut.application', 'Micronaut application plugin'),
        ('io.ktor.plugin', 'Ktor application plugin'),
        ('com.google.cloud.tools.jib', 'containerized JVM application'),
        ('libs.plugins.android.application', 'Android application plugin alias'),
        ('applicationId', 'Android application id'),
        ('bootJar', 'executable boot archive'),
    )
    open_patterns = (
        ('maven-publish', 'Maven publishing plugin'),
        ('publishing {', 'publishing configuration'),
        ('com.vanniktech.maven.publish', 'Maven publishing plugin'),
    )
    for needle, reason in closed_patterns:
        if needle in text:
            closed.append(reason)
    if re.search(r"\b(?:id\s*\(?\s*['\"]application['\"]|apply\s+plugin:\s*['\"]application['\"])", text):
        closed.append('JVM application plugin')
    for needle, reason in open_patterns:
        if needle in text:
            opened.append(reason)
    return closed, opened


def _gradle_library_evidence(path: str) -> list[str]:
    """Return weak library signals that depend on the enclosing build.

    Android/Java library plugins describe compilation shape, not necessarily
    an external API boundary.  They are open for a standalone library build,
    but internal when an application/service in the same Gradle build owns all
    consumers and no publishing signal is present.
    """
    text = _first_existing(path, ('build.gradle.kts', 'build.gradle'))
    if not text:
        return []
    reasons: list[str] = []
    for needle, reason in (
        ('com.android.library', 'Android library plugin'),
        ('java-library', 'Java library plugin'),
        ('libs.plugins.android.library', 'Android library plugin alias'),
    ):
        if needle in text:
            reasons.append(reason)
    return reasons


def _maven_evidence(path: str) -> tuple[list[str], list[str]]:
    text = _read(os.path.join(path, 'pom.xml'))
    if not text:
        return [], []
    closed: list[str] = []
    opened: list[str] = []
    for needle, reason in (
        ('spring-boot-maven-plugin', 'Spring Boot executable'),
        ('quarkus-maven-plugin', 'Quarkus executable'),
        ('micronaut-maven-plugin', 'Micronaut executable'),
        ('<packaging>war</packaging>', 'deployable web archive'),
    ):
        if needle in text:
            closed.append(reason)
    for needle, reason in (
        ('maven-source-plugin', 'published source archive'),
        ('maven-javadoc-plugin', 'published API documentation'),
        ('nexus-staging-maven-plugin', 'repository publishing'),
    ):
        if needle in text:
            opened.append(reason)
    return closed, opened


def _swift_evidence(path: str) -> tuple[list[str], list[str]]:
    closed: list[str] = []
    opened: list[str] = []
    package = _read(os.path.join(path, 'Package.swift'))
    if '.library(' in package:
        opened.append('Swift package library product')
    if '.executable(' in package or '.executableTarget(' in package:
        closed.append('Swift executable product')
    try:
        entries = os.listdir(path)
    except OSError:
        entries = []
    if any(name.endswith('.podspec') for name in entries):
        opened.append('CocoaPods specification')
    for name in entries:
        if not name.endswith('.xcodeproj'):
            continue
        project = _read(os.path.join(path, name, 'project.pbxproj'))
        if 'com.apple.product-type.framework' in project:
            opened.append('Xcode framework product')
        if 'com.apple.product-type.application' in project:
            closed.append('Xcode application product')
    if os.path.isfile(os.path.join(path, 'main.swift')):
        closed.append('Swift executable entry point')
    return closed, opened


def _dart_evidence(path: str) -> tuple[list[str], list[str]]:
    pubspec = _read(os.path.join(path, 'pubspec.yaml'))
    if not pubspec:
        return [], []
    closed: list[str] = []
    opened: list[str] = []
    has_main = os.path.isfile(os.path.join(path, 'lib', 'main.dart'))
    has_platform = any(os.path.isdir(os.path.join(path, name))
                       for name in ('android', 'ios', 'web', 'macos', 'windows', 'linux'))
    if has_main and has_platform:
        closed.append('Flutter application entry point')
    if not has_main and os.path.isdir(os.path.join(path, 'lib')):
        opened.append('Dart package library surface')
    if re.search(r'(?m)^\s*publish_to\s*:\s*(?!["\']?none\b)', pubspec):
        opened.append('publishable Dart package')
    return closed, opened


def _go_evidence(path: str) -> tuple[list[str], list[str]]:
    if not os.path.isfile(os.path.join(path, 'go.mod')):
        return [], []
    root_main = False
    try:
        names = os.listdir(path)
    except OSError:
        names = []
    for name in names:
        if not name.endswith('.go') or name.endswith('_test.go'):
            continue
        text = _read(os.path.join(path, name), 128_000)
        if (re.search(r'(?m)^\s*package\s+main\b', text)
                and re.search(r'\bfunc\s+main\s*\(', text)):
            root_main = True
            break
    if root_main:
        return ['Go executable at module root'], []
    return [], []


def _deployment_evidence(path: str) -> list[str]:
    markers = (
        'Dockerfile', 'Procfile', 'app.yaml', 'service.yaml',
        'serverless.yml', 'serverless.yaml', 'vercel.json', 'fly.toml',
    )
    if any(os.path.isfile(os.path.join(path, marker)) for marker in markers):
        return ['deployment manifest']
    return []


def _classify_module(name: str, path: str, *, enclosing_gradle_closed: bool = False
                     ) -> ModuleBoundary:
    closed: list[str] = []
    opened: list[str] = []
    for detector in (_gradle_evidence, _maven_evidence, _swift_evidence,
                     _dart_evidence, _go_evidence):
        detected_closed, detected_open = detector(path)
        closed.extend(detected_closed)
        opened.extend(detected_open)
    closed.extend(_deployment_evidence(path))

    # Publishing evidence always wins: a module can be executable and expose a
    # supported library product at the same time, and consumers remain unseen.
    if opened:
        return ModuleBoundary(name, os.path.abspath(path), OPEN,
                              tuple(dict.fromkeys(opened)))
    if closed:
        return ModuleBoundary(name, os.path.abspath(path), CLOSED,
                              tuple(dict.fromkeys(closed)))
    weak_library = _gradle_library_evidence(path)
    if enclosing_gradle_closed:
        return ModuleBoundary(
            name, os.path.abspath(path), CLOSED,
            ('internal module of closed-world Gradle build',))
    if weak_library:
        return ModuleBoundary(name, os.path.abspath(path), OPEN,
                              tuple(dict.fromkeys(weak_library)))
    return ModuleBoundary(name, os.path.abspath(path), OPEN,
                          ('no conclusive closed-world evidence; safe fallback',))


def _has_closed_evidence(path: str) -> bool:
    for detector in (_gradle_evidence, _maven_evidence, _swift_evidence,
                     _dart_evidence, _go_evidence):
        closed, _ = detector(path)
        if closed:
            return True
    return bool(_deployment_evidence(path))


def _normalise_mode(mode: str | None) -> str:
    value = (mode or AUTO).strip().lower()
    if value not in WORLD_MODES:
        raise ValueError(
            f"invalid project boundary mode {mode!r}; expected auto, closed, or open")
    return value


def detect_project_boundary(
        root: str, *, layout: ProjectLayout | None = None,
        mode: str = AUTO,
        module_overrides: dict[str, str] | None = None) -> ProjectBoundary:
    """Detect the external-consumer boundary for every project module."""
    absolute_root = os.path.abspath(root)
    mode = _normalise_mode(mode)
    overrides = {str(key): _normalise_mode(value)
                 for key, value in (module_overrides or {}).items()}
    if any(value == AUTO for value in overrides.values()):
        raise ValueError('module boundary overrides must be closed or open')

    if layout is None:
        layout = ProjectLayout(absolute_root)
    entries = list(layout.module_entries)
    has_root_module = any(
        os.path.abspath(path) == absolute_root for _, path in entries)
    enclosing_gradle_closed = (
        layout.kind == 'gradle'
        and any(_has_closed_evidence(path) for _, path in entries)
    )

    def resolve(name: str, path: str) -> ModuleBoundary:
        rel = os.path.relpath(path, absolute_root)
        override = overrides.get(name)
        if override is None:
            override = overrides.get(rel)
        selected = override or (mode if mode != AUTO else None)
        if selected:
            return ModuleBoundary(
                name, os.path.abspath(path), selected,
                ('explicit project boundary',), True)
        return _classify_module(
            name, path, enclosing_gradle_closed=enclosing_gradle_closed)

    modules = [resolve(name, path) for name, path in entries]
    fallback = None if has_root_module else resolve(':root', absolute_root)
    return ProjectBoundary(absolute_root, modules, fallback=fallback)


def language_private(record: dict) -> bool:
    """Return whether a declaration is hidden by its language visibility."""
    from ..adapters import get_adapter

    filepath = record.get('filepath', '')
    adapter = get_adapter(os.path.splitext(filepath)[1].lower())
    if adapter:
        return adapter.is_language_private(record)
    return bool(record.get('is_private'))


def boundary_allows_record(record: dict, boundary: ProjectBoundary | None) -> bool:
    """Allow public/API deletion only inside a closed-world module."""
    if boundary is None or boundary.allows_external_api_pruning(
            record.get('filepath', '')):
        return True
    return language_private(record)


__all__ = [
    'AUTO', 'CLOSED', 'OPEN', 'WORLD_MODES', 'ModuleBoundary',
    'ProjectBoundary', 'detect_project_boundary', 'language_private',
    'boundary_allows_record',
]
