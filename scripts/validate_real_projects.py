#!/usr/bin/env python3
"""Real-world project validation for dead-code-pruner.

Validates pruner safety and effectiveness against real open-source projects.
Each project is cloned at a fixed commit, receives controlled dead-code
fixtures, and is cleaned + compiled + tested to prove correctness.

Usage:
    python3 scripts/validate_real_projects.py [project_name]
    python3 scripts/validate_real_projects.py --all
"""

import argparse
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

PRUNER_ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(tempfile.gettempdir()) / "dead-code-pruner-validation"


@dataclass
class ProjectSpec:
    name: str
    repo: str
    commit: str
    language: str
    extensions: tuple[str, ...]
    build_cmd: list[str]
    test_cmd: list[str]
    world: str = "closed"
    timeout: int = 600
    env: dict = field(default_factory=dict)
    subdir: str = ""
    allowed_test_failures: frozenset[str] = frozenset()
    variant_prepare_cmd: list[str] = field(default_factory=list)
    variant_build_cmd: list[str] = field(default_factory=list)
    variant_subdir: str = ""


PROJECTS = {
    "javalin": ProjectSpec(
        name="javalin",
        repo="https://github.com/javalin/javalin.git",
        commit="6600d23a36eca699d57cca14110c3fb181222ed9",
        language="java",
        extensions=(".java", ".kt"),
        build_cmd=["./mvnw", "-T", "1C", "compile", "-q", "-DskipTests"],
        test_cmd=["./mvnw", "-T", "1C", "test",
                  "-Dsurefire.useSystemClassLoader=false"],
        world="open",
        timeout=600,
    ),
    "ktlint": ProjectSpec(
        name="ktlint",
        repo="https://github.com/pinterest/ktlint.git",
        commit="947ff8dd5557598e031fe595db3186f6b4926f1d",
        language="kotlin",
        extensions=(".kt", ".kts"),
        build_cmd=["./gradlew", "compileKotlin", "-q", "--no-daemon",
                    "-x", "test"],
        test_cmd=["./gradlew", "test", "--no-daemon",
                  "-x", "shadowJarExecutable"],
        world="open",
        timeout=900,
        env={"JAVA_HOME": "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"},
    ),
    "restic": ProjectSpec(
        name="restic",
        repo="https://github.com/restic/restic.git",
        commit="d4088aa09ba78d3c93d81505bfab9cacf13f5168",
        language="go",
        extensions=(".go",),
        build_cmd=["sh", "-c",
                   "go build ./... && GOOS=freebsd GOARCH=arm64 "
                   "go test -c -o /tmp/restic-freebsd.test ./internal/fs"],
        test_cmd=["go", "test", "-count=1", "-short", "./cmd/...", "./internal/..."],
        world="closed",
        timeout=600,
        env={
            "PATH": str(WORK_DIR / "bin") + ":" + os.environ.get("PATH", ""),
            "RESTIC_TEST_FUSE": "0",
        },
        allowed_test_failures=frozenset({"TestNodeRestoreAt", "TestOverwriteXattr"}),
    ),
    "swift-argument-parser": ProjectSpec(
        name="swift-argument-parser",
        repo="https://github.com/apple/swift-argument-parser.git",
        commit="2f77f2fccb6e84fecff338c37b199e33e7dfd119",
        language="swift",
        extensions=(".swift",),
        build_cmd=["swift", "build"],
        test_cmd=["swift", "test"],
        world="open",
        timeout=600,
        allowed_test_failures=frozenset({
            "testCountLinesSinglePageManual", "testCountLinesMultiPageManual",
            "testColorSinglePageManual", "testColorMultiPageManual",
            "testMathSinglePageManual", "testMathMultiPageManual",
            "testRepeatSinglePageManual", "testRepeatMultiPageManual",
            "testRollSinglePageManual", "testRollMultiPageManual",
            "testDefaultAsFlagSinglePageManual", "testDefaultAsFlagMultiPageManual",
        }),
    ),
    "localsend": ProjectSpec(
        name="localsend",
        repo="https://github.com/localsend/localsend.git",
        commit="1ec28463b5cb43c9f7f061f3a76966bcd121cf5c",
        language="dart",
        extensions=(".dart",),
        build_cmd=["flutter", "analyze", "--no-fatal-warnings"],
        test_cmd=["flutter", "test"],
        world="closed",
        subdir="app",
        timeout=600,
        variant_prepare_cmd=["sh", "support/scripts/remove_proprietary_dependencies.sh"],
        variant_build_cmd=["sh", "-c",
                           "flutter pub get && flutter analyze --no-fatal-warnings && flutter test"],
        variant_subdir="app",
    ),
}


@dataclass
class StepResult:
    name: str
    passed: bool
    command: str = ""
    exit_code: int = -1
    elapsed: float = 0.0
    log: str = ""
    reason: str = ""


@dataclass
class ValidationResult:
    project: str
    world: str = "closed"
    steps: list = field(default_factory=list)
    fixture_removals: dict = field(default_factory=dict)
    fixture_preserved: dict = field(default_factory=dict)
    non_fixture_diff: str = ""
    api_diff: str = ""
    errors: list[str] = field(default_factory=list)
    file_count: int = 0
    passed: bool = False
    baseline_failures: set[str] = field(default_factory=set)

    def add_step(self, step: StepResult):
        self.steps.append(step)
        if not step.passed:
            reason = step.reason or f"{step.name} failed (exit {step.exit_code})"
            self.errors.append(reason)

    def all_steps_passed(self) -> bool:
        return all(s.passed for s in self.steps)


def run_cmd(cmd, cwd, timeout=300, env=None):
    """Run a command and return (exit_code, stdout, stderr, elapsed)."""
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    t0 = time.time()
    process = None
    try:
        process = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=merged_env, start_new_session=True)
        stdout, stderr = process.communicate(timeout=timeout)
        elapsed = time.time() - t0
        return process.returncode, stdout, stderr, elapsed
    except subprocess.TimeoutExpired as exc:
        _terminate_process_group(process)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        stderr += f"\nTimeout after {timeout}s"
        return 124, stdout, stderr, time.time() - t0
    except KeyboardInterrupt:
        if process is not None:
            _terminate_process_group(process)
        raise
    except Exception as e:
        return 1, "", str(e), time.time() - t0


def _terminate_process_group(process: subprocess.Popen) -> None:
    """Stop a command and all children spawned in its process group."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()


def _log_excerpt(output: str, limit: int = 4000) -> str:
    """Keep both command context and the final diagnostic lines."""
    if len(output) <= limit:
        return output
    diagnostic_lines = [
        line for line in output.splitlines()
        if re.search(r'(?i)(?:error:|\bfailed\b|\bfailure\b|unexpected)', line)
        and not re.search(r'0 failures? \(0 unexpected\)', line)
    ]
    diagnostics = "\n".join(diagnostic_lines)
    head = limit // 5
    tail = limit // 2
    middle = diagnostics[-(limit - head - tail):]
    return (output[:head] + "\n... diagnostics ...\n" + middle
            + "\n... output tail ...\n" + output[-tail:])


def run_variant_check(project_dir: Path, spec: ProjectSpec):
    """Build a mutating project variant in an isolated temporary copy."""
    if not spec.variant_prepare_cmd or not spec.variant_build_cmd:
        return 0, "", "", 0.0
    with tempfile.TemporaryDirectory(prefix=f"{spec.name}-variant-") as tmp:
        copy_root = Path(tmp) / spec.name
        shutil.copytree(
            project_dir, copy_root,
            ignore=shutil.ignore_patterns(
                '.git', 'build', '.dart_tool', '.gradle', '.build'))
        # Upstream release scripts commonly use GNU ``sed -i``.  Adapt only
        # that invocation syntax in the disposable copy on macOS.
        if sys.platform == 'darwin' and spec.variant_prepare_cmd[-1].endswith('.sh'):
            script = copy_root / spec.variant_prepare_cmd[-1]
            if script.exists():
                text = script.read_text(encoding='utf-8')
                script.write_text(text.replace('sed -i ', "sed -i '' "),
                                  encoding='utf-8')
        start = time.time()
        code, out1, err1, _ = run_cmd(
            spec.variant_prepare_cmd, str(copy_root),
            timeout=spec.timeout, env=spec.env)
        if code != 0:
            return code, out1, err1, time.time() - start
        variant_dir = copy_root / spec.variant_subdir if spec.variant_subdir else copy_root
        code, out2, err2, _ = run_cmd(
            spec.variant_build_cmd, str(variant_dir),
            timeout=spec.timeout, env=spec.env)
        return code, out1 + out2, err1 + err2, time.time() - start


_GO_FAIL_PATTERN = re.compile(r'--- FAIL:\s+(\S+)')
_SWIFT_FAIL_PATTERN = re.compile(
    r"Test Case '.*\s(test[A-Za-z0-9_]+)\]' failed")


def _extract_test_failures(output: str, language: str) -> set[str]:
    """Extract top-level failing test names from test output."""
    if language == "go":
        return {m.group(1).split('/')[0] for m in _GO_FAIL_PATTERN.finditer(output)}
    if language == "swift":
        return set(_SWIFT_FAIL_PATTERN.findall(output))
    return set()


def _ensure_python_symlink():
    """Ensure ``python`` is available for projects whose tests call it."""
    bin_dir = WORK_DIR / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    link = bin_dir / "python"
    if not link.exists():
        python3 = shutil.which("python3")
        if python3:
            link.symlink_to(python3)


def clone_project(spec: ProjectSpec) -> Path:
    """Clone project to fixed commit from scratch."""
    project_dir = WORK_DIR / spec.name
    if project_dir.exists():
        shutil.rmtree(project_dir)

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    exit_code, _, stderr, _ = run_cmd(
        ["git", "clone", "--depth=500", spec.repo, str(project_dir)],
        str(WORK_DIR), timeout=180)
    if exit_code != 0:
        raise RuntimeError(f"Clone failed: {stderr}")
    exit_code, _, stderr, _ = run_cmd(
        ["git", "checkout", spec.commit], str(project_dir))
    if exit_code != 0:
        raise RuntimeError(f"Checkout {spec.commit} failed: {stderr}")
    return project_dir


# ── Exported symbol collection (for open-world API safety) ──────────


def _collect_exported_symbols(project_dir: Path, spec: ProjectSpec) -> set[str]:
    """Collect public/exported symbol names from source files."""
    symbols: set[str] = set()
    work_dir = project_dir / spec.subdir if spec.subdir else project_dir
    for ext in spec.extensions:
        for fpath in work_dir.rglob(f"*{ext}"):
            if ".git" in str(fpath) or "test" in str(fpath).lower():
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            language = {
                '.java': 'java', '.kt': 'kotlin', '.kts': 'kotlin',
                '.go': 'go', '.swift': 'swift', '.dart': 'dart',
            }.get(fpath.suffix.lower(), spec.language)
            relative = fpath.relative_to(work_dir)
            symbols.update(
                f"{relative}:{name}"
                for name in _extract_public_symbols(content, language))
    return symbols


def _extract_public_symbols(content: str, language: str) -> set[str]:
    """Extract public/exported symbols from source content."""
    symbols: set[str] = set()
    if language == "java":
        for m in re.finditer(
                r'(?:public|protected)\s+(?:static\s+)?(?:final\s+)?'
                r'(?:abstract\s+)?(?:[\w<>\[\]?,\s]+\s+)(\w+)\s*[({;]',
                content):
            symbols.add(m.group(1))
    elif language == "kotlin":
        for m in re.finditer(
                r'(?:public|internal)\s+(?:(?:open|abstract|final|override|inline|suspend|'
                r'operator|infix)\s+)*(?:fun|val|var|class|interface|object|typealias)\s+'
                r'(?:<[^>]+>\s*)?(\w+)', content):
            symbols.add(m.group(1))
        for m in re.finditer(
                r'^(?:fun|val|var|class|interface|object|typealias)\s+'
                r'(?:<[^>]+>\s*)?(\w+)', content, re.MULTILINE):
            symbols.add(m.group(1))
    elif language == "go":
        for m in re.finditer(r'\bfunc\s+(?:\([^)]*\)\s*)?([A-Z]\w*)\s*\(', content):
            symbols.add(m.group(1))
        for m in re.finditer(r'\btype\s+([A-Z]\w*)\s+', content):
            symbols.add(m.group(1))
        for m in re.finditer(r'\b(?:var|const)\s+([A-Z]\w*)\s', content):
            symbols.add(m.group(1))
    elif language == "swift":
        for m in re.finditer(
                r'\b(?:public|open)\s+(?:(?:static|class|final|override)\s+)*'
                r'(?:func|var|let|class|struct|enum|protocol|typealias)\s+(\w+)',
                content):
            symbols.add(m.group(1))
    elif language == "dart":
        for m in re.finditer(r'^(?!_)(\w+)\s*[({=;]', content, re.MULTILINE):
            name = m.group(1)
            if not name.startswith('_') and name[0].islower():
                symbols.add(name)
    return symbols


# ── Fixture injection ───────────────────────────────────────────────


def inject_fixture(project_dir: Path, spec: ProjectSpec) -> dict:
    """Inject controlled dead-code fixtures into the project."""
    fixture_info = {"injected_files": [], "expected_removals": [],
                    "expected_preserved": [], "replacements": []}
    injectors = {
        "java": _inject_java_fixture,
        "kotlin": _inject_kotlin_fixture,
        "go": _inject_go_fixture,
        "swift": _inject_swift_fixture,
        "dart": _inject_dart_fixture,
    }
    injector = injectors.get(spec.language)
    if injector:
        injector(project_dir, spec, fixture_info)
    return fixture_info


def _inject_java_fixture(project_dir: Path, spec: ProjectSpec, info: dict):
    target = project_dir / "javalin" / "src" / "main" / "java" / "io" / "javalin"
    if not target.exists():
        return
    fixture = target / "DeadCodeFixture.java"
    fixture.write_text(
        'package io.javalin;\n\n'
        'final class DeadCodeFixture {\n'
        '    private static final boolean RETIRED_FLAG = false;\n\n'
        '    static String resolve(String input) {\n'
        '        if (RETIRED_FLAG) {\n'
        '            return legacyResolve(input);\n'
        '        } else {\n'
        '            return input.trim();\n'
        '        }\n'
        '    }\n\n'
        '    private static String legacyResolve(String input) {\n'
        '        return input.toLowerCase();\n'
        '    }\n\n'
        '    private static boolean isRetired() { return false; }\n\n'
        '    static boolean isActive() { return true; }\n'
        '}\n',
        encoding='utf-8')
    info["injected_files"].append(str(fixture))
    info["expected_removals"].extend(["RETIRED_FLAG", "legacyResolve", "isRetired"])
    info["expected_preserved"].extend(["resolve", "isActive"])
    info["replacements"].append({"pattern": "RETIRED_FLAG", "value": False})


def _inject_kotlin_fixture(project_dir: Path, spec: ProjectSpec, info: dict):
    target = None
    for d in (project_dir / "ktlint-rule-engine").rglob("kotlin"):
        if "src" in str(d) and "main" in str(d):
            target = d / "com" / "pinterest" / "ktlint"
            target.mkdir(parents=True, exist_ok=True)
            break
    if target is None:
        target = project_dir

    fixture = target / "DeadCodeFixture.kt"
    fixture.write_text(
        'package com.pinterest.ktlint\n\n'
        'internal object DeadCodeFixture {\n'
        '    private const val RETIRED_FLAG = false\n\n'
        '    internal fun resolve(input: String): String {\n'
        '        val retiredMode = RETIRED_FLAG\n'
        '        return if (retiredMode) {\n'
        '            legacyResolve(input)\n'
        '        } else {\n'
        '            input.trim()\n'
        '        }\n'
        '    }\n\n'
        '    private fun legacyResolve(input: String): String = input.lowercase()\n\n'
        '    private fun isRetired(): Boolean = false\n\n'
        '    internal fun isActive(): Boolean = true\n'
        '}\n',
        encoding='utf-8')
    info["injected_files"].append(str(fixture))
    info["expected_removals"].extend(["RETIRED_FLAG", "legacyResolve", "isRetired"])
    info["expected_preserved"].extend(["resolve", "isActive"])
    info["replacements"].append({"pattern": "RETIRED_FLAG", "value": False})


def _inject_go_fixture(project_dir: Path, spec: ProjectSpec, info: dict):
    target = project_dir / "internal" / "deadfixture"
    target.mkdir(parents=True, exist_ok=True)
    fixture = target / "fixture.go"
    fixture.write_text(
        'package deadfixture\n\n'
        'const retiredFlag = false\n\n'
        'func Resolve(input string) string {\n'
        '\tif retiredFlag {\n'
        '\t\treturn legacyResolve(input)\n'
        '\t}\n'
        '\treturn input\n'
        '}\n\n'
        'func legacyResolve(input string) string {\n'
        '\treturn input\n'
        '}\n\n'
        'func isRetired() bool { return false }\n',
        encoding='utf-8')
    info["injected_files"].append(str(fixture))
    info["expected_removals"].extend(["retiredFlag", "legacyResolve", "isRetired"])
    info["expected_preserved"].extend(["Resolve"])
    info["replacements"].append({"pattern": "retiredFlag", "value": False})

    fixture_test = target / "fixture_test.go"
    fixture_test.write_text(
        'package deadfixture\n\n'
        'import "testing"\n\n'
        'func TestResolve(t *testing.T) {\n'
        '\tif got := Resolve("hello"); got != "hello" {\n'
        '\t\tt.Errorf("Resolve() = %q, want %q", got, "hello")\n'
        '\t}\n'
        '}\n',
        encoding='utf-8')
    info["injected_files"].append(str(fixture_test))


def _inject_swift_fixture(project_dir: Path, spec: ProjectSpec, info: dict):
    target = project_dir / "Sources" / "ArgumentParser" / "Utilities"
    if not target.exists():
        target = project_dir / "Sources" / "ArgumentParser"
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
    fixture = target / "DeadCodeFixture.swift"
    fixture.write_text(
        'internal struct DeadCodeFixture {\n'
        '    private static let retiredFlag = false\n\n'
        '    static func resolve(_ input: String) -> String {\n'
        '        if retiredFlag {\n'
        '            return legacyResolve(input)\n'
        '        } else {\n'
        '            return input.trimmingCharacters(in: .whitespaces)\n'
        '        }\n'
        '    }\n\n'
        '    private static func legacyResolve(_ input: String) -> String {\n'
        '        return input.lowercased()\n'
        '    }\n\n'
        '    private static func isRetired() -> Bool { false }\n\n'
        '    static func isActive() -> Bool { true }\n'
        '}\n',
        encoding='utf-8')
    info["injected_files"].append(str(fixture))
    info["expected_removals"].extend(["retiredFlag", "legacyResolve", "isRetired"])
    info["expected_preserved"].extend(["resolve", "isActive"])
    info["replacements"].append({"pattern": "retiredFlag", "value": False})


def _inject_dart_fixture(project_dir: Path, spec: ProjectSpec, info: dict):
    base = project_dir / spec.subdir if spec.subdir else project_dir
    target = base / "lib" / "util"
    if not target.exists():
        target = base / "lib"
    if not target.exists():
        return
    fixture = target / "dead_code_fixture.dart"
    fixture.write_text(
        'const bool _retiredFlag = false;\n\n'
        'String resolve(String input) {\n'
        '  if (_retiredFlag) {\n'
        '    return _legacyResolve(input);\n'
        '  } else {\n'
        '    return input.trim();\n'
        '  }\n'
        '}\n\n'
        'String _legacyResolve(String input) {\n'
        '  return input.toLowerCase();\n'
        '}\n\n'
        'bool _isRetired() => false;\n',
        encoding='utf-8')
    info["injected_files"].append(str(fixture))
    info["expected_removals"].extend([
        "_retiredFlag", "_legacyResolve", "_isRetired"
    ])
    info["expected_preserved"].extend(["resolve"])
    info["replacements"].append({"pattern": "_retiredFlag", "value": False})


# ── Pruner invocation ───────────────────────────────────────────────


def run_pruner(project_dir: Path, spec: ProjectSpec,
               fixture_info: dict | None = None
               ) -> tuple[int, str, str, float]:
    """Run the pruner on a project directory."""
    # Scan the repository root even when build commands run in a subproject.
    # Release scripts and workspace packages outside that subdirectory can
    # carry semantic references required by alternate build variants.
    target = str(project_dir)
    tmp_config = WORK_DIR / f"{spec.name}_pruner.yaml"

    replacements = fixture_info.get("replacements", []) if fixture_info else []
    lines = [
        f'project_boundary:\n  mode: {spec.world}\n',
        'replacements:\n',
    ]
    for r in replacements:
        val = str(r["value"]).lower()
        pat = r["pattern"]
        entry = f'  - pattern: "{pat}"\n    value: {val}\n'
        if '.' not in pat and not re.fullmatch(r'[A-Z][A-Z0-9_]*', pat):
            entry += '    allow_unqualified: true\n'
        lines.append(entry)
    if not replacements:
        lines[-1] = 'replacements: []\n'
    tmp_config.write_text(''.join(lines), encoding='utf-8')

    cmd = [
        sys.executable, "-m", "pruner",
        target,
        "--config", str(tmp_config),
        "--world", spec.world,
    ]
    env = {"PYTHONPATH": str(PRUNER_ROOT)}
    return run_cmd(cmd, str(PRUNER_ROOT), timeout=600, env=env)


# ── Fixture result checks ──────────────────────────────────────────


def check_fixture_results(project_dir: Path, spec: ProjectSpec,
                          fixture_info: dict) -> tuple[dict, dict, list[str]]:
    """Check fixture cleanup results: removals and preserved symbols."""
    removals = {}
    preserved = {}
    errors = []

    for fpath_str in fixture_info.get("injected_files", []):
        fpath = Path(fpath_str)
        if not fpath.exists():
            for symbol in fixture_info.get("expected_preserved", []):
                preserved[symbol] = "file_deleted"
                errors.append(f"Fixture file deleted: {fpath.name}")
            for symbol in fixture_info.get("expected_removals", []):
                removals[symbol] = "file_deleted"
            continue

        if fpath.suffix == ".go" and fpath.stem.endswith("_test"):
            continue

        content = fpath.read_text(encoding="utf-8", errors="ignore")

        for symbol in fixture_info.get("expected_removals", []):
            if symbol in content:
                removals[symbol] = "NOT_REMOVED"
                errors.append(f"Expected removal '{symbol}' still in {fpath.name}")
            else:
                removals[symbol] = "removed"

        for symbol in fixture_info.get("expected_preserved", []):
            if symbol in content:
                preserved[symbol] = "present"
            else:
                preserved[symbol] = "MISSING"
                errors.append(f"Expected preserved '{symbol}' missing from {fpath.name}")

    return removals, preserved, errors


def get_non_fixture_diff(project_dir: Path, fixture_info: dict) -> str:
    """Get diff of non-fixture files to review for false positives."""
    exit_code, stdout, _, _ = run_cmd(
        ["git", "diff", "--stat"], str(project_dir))
    if exit_code != 0:
        return ""

    fixture_files = set()
    for fp in fixture_info.get("injected_files", []):
        fixture_files.add(Path(fp).name)

    non_fixture_lines = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        fname = line.split("|")[0].strip().split("/")[-1] if "|" in line else ""
        if fname and fname not in fixture_files:
            non_fixture_lines.append(line.strip())

    return "\n".join(non_fixture_lines)


# ── Validation lifecycle ────────────────────────────────────────────


def validate_project(spec: ProjectSpec) -> ValidationResult:
    """Full validation lifecycle for one project."""
    result = ValidationResult(project=spec.name, world=spec.world)
    print(f"\n{'='*60}")
    print(f"  Validating: {spec.name} ({spec.language}, world={spec.world})")
    print(f"{'='*60}")

    # Step 1: Clone
    print(f"  [1/10] Cloning at {spec.commit[:12]}...")
    try:
        project_dir = clone_project(spec)
    except Exception as e:
        result.add_step(StepResult("clone", False, log=str(e),
                                   reason=f"Clone failed: {e}"))
        return result
    result.add_step(StepResult("clone", True))

    work_dir = project_dir / spec.subdir if spec.subdir else project_dir

    result.file_count = sum(
        1 for ext in spec.extensions
        for _ in project_dir.rglob(f"*{ext}")
        if ".git" not in str(_))

    # Step 1b: Language-specific setup (e.g. flutter pub get)
    if spec.language == "dart":
        print(f"  [1b/10] Running flutter pub get...")
        exit_code, _, stderr, _ = run_cmd(
            ["flutter", "pub", "get"], str(work_dir), timeout=300, env=spec.env)
        if exit_code != 0:
            result.add_step(StepResult("flutter_pub_get", False,
                                       command="flutter pub get",
                                       exit_code=exit_code, log=stderr[:2000],
                                       reason=f"flutter pub get failed (exit {exit_code})"))
            return result
        print(f"    OK")

    # Step 2: Baseline build
    print(f"  [2/10] Baseline build...")
    cmd_str = " ".join(spec.build_cmd)
    exit_code, stdout, stderr, elapsed = run_cmd(
        spec.build_cmd, str(work_dir), timeout=spec.timeout, env=spec.env)
    step = StepResult("baseline_build", exit_code == 0,
                      command=cmd_str, exit_code=exit_code,
                      elapsed=elapsed, log=(stderr or stdout)[:2000])
    if exit_code != 0:
        step.reason = f"Baseline build failed (exit {exit_code})"
    result.add_step(step)
    if exit_code != 0:
        print(f"    FAIL (exit {exit_code})")
        return result
    print(f"    OK ({elapsed:.1f}s)")

    # Step 3: Baseline test
    print(f"  [3/10] Baseline test...")
    cmd_str = " ".join(spec.test_cmd)
    exit_code, stdout, stderr, elapsed = run_cmd(
        spec.test_cmd, str(work_dir), timeout=spec.timeout, env=spec.env)
    baseline_test_output = stdout + "\n" + stderr
    baseline_failures: set[str] = set()
    baseline_test_passed = exit_code == 0
    if exit_code != 0:
        baseline_failures = _extract_test_failures(
            baseline_test_output, spec.language)
        if (spec.allowed_test_failures
                and baseline_failures == set(spec.allowed_test_failures)):
            baseline_test_passed = True
            result.baseline_failures = baseline_failures
            print(f"    LIMITED: {len(baseline_failures)} approved environment failure(s)")
            for f in sorted(baseline_failures)[:3]:
                print(f"      - {f}")
        else:
            print(f"    FAIL (exit {exit_code})")
    else:
        print(f"    OK ({elapsed:.1f}s)")
    step = StepResult("baseline_test", baseline_test_passed,
                      command=cmd_str, exit_code=exit_code,
                      elapsed=elapsed, log=_log_excerpt(baseline_test_output))
    if not baseline_test_passed:
        step.reason = f"Baseline test failed (exit {exit_code})"
    result.add_step(step)
    if not baseline_test_passed:
        return result

    if spec.variant_prepare_cmd:
        print("  [3b/10] Baseline variant build...")
        exit_code, stdout, stderr, elapsed = run_variant_check(project_dir, spec)
        step = StepResult(
            "baseline_variant", exit_code == 0,
            command=(" ".join(spec.variant_prepare_cmd) + " && "
                     + " ".join(spec.variant_build_cmd)),
            exit_code=exit_code, elapsed=elapsed,
            log=_log_excerpt(stdout + stderr),
            reason=("Baseline variant build failed" if exit_code else ""))
        result.add_step(step)
        if exit_code != 0:
            return result

    # Step 4: Collect pre-cleanup API (for open-world projects)
    pre_api: set[str] = set()
    if spec.world == "open":
        print(f"  [4/10] Collecting pre-cleanup public API...")
        pre_api = _collect_exported_symbols(project_dir, spec)
        print(f"    {len(pre_api)} exported symbols")
    else:
        print(f"  [4/10] Skipped (closed-world)")
    result.add_step(StepResult("api_snapshot", True))

    # Step 5: Inject fixtures
    print(f"  [5/10] Injecting controlled dead-code fixtures...")
    fixture_info = inject_fixture(project_dir, spec)
    injected_count = len(fixture_info.get("injected_files", []))
    print(f"    Injected {injected_count} fixture file(s)")
    result.add_step(StepResult("fixture_inject", injected_count > 0))
    if injected_count == 0:
        result.errors.append("No fixtures injected")
        return result

    # Step 6: Verify fixtures compile (fixture build)
    print(f"  [6/10] Fixture build verification...")
    exit_code, stdout, stderr, elapsed = run_cmd(
        spec.build_cmd, str(work_dir), timeout=spec.timeout, env=spec.env)
    step = StepResult("fixture_build", exit_code == 0,
                      command=" ".join(spec.build_cmd), exit_code=exit_code,
                      elapsed=elapsed, log=(stderr or stdout)[:2000])
    if exit_code != 0:
        step.reason = f"Fixture build failed (exit {exit_code})"
    result.add_step(step)
    if exit_code != 0:
        print(f"    FAIL: Fixtures don't compile")
        return result
    print(f"    OK ({elapsed:.1f}s)")

    # Step 7: Run pruner
    print(f"  [7/10] Running dead-code-pruner (world={spec.world})...")
    exit_code, stdout, stderr, elapsed = run_pruner(
        project_dir, spec, fixture_info)
    cmd_str = f"python3 -m pruner --world {spec.world}"
    step = StepResult("pruner_run", exit_code == 0,
                      command=cmd_str, exit_code=exit_code,
                      elapsed=elapsed, log=(stdout + "\n" + stderr)[:3000])
    if exit_code != 0:
        step.reason = f"Pruner failed (exit {exit_code})"
    result.add_step(step)
    if exit_code != 0:
        print(f"    FAIL (exit {exit_code})")
    else:
        print(f"    OK ({elapsed:.1f}s)")

    # Step 8: Safety checks
    print(f"  [8/10] Safety verification...")
    removals, preserved, safety_errors = check_fixture_results(
        project_dir, spec, fixture_info)
    result.fixture_removals = removals
    result.fixture_preserved = preserved
    result.non_fixture_diff = get_non_fixture_diff(project_dir, fixture_info)

    fixture_pass = (
        all(v in ("removed", "file_deleted") for v in removals.values())
        and all(v == "present" for v in preserved.values())
        and not safety_errors
    )
    step = StepResult("safety_check", fixture_pass,
                      log="\n".join(safety_errors) if safety_errors else "All checks passed")
    if not fixture_pass:
        step.reason = "Fixture safety check failed: " + "; ".join(safety_errors[:3])
    result.add_step(step)
    if safety_errors:
        for e in safety_errors[:5]:
            print(f"    WARN: {e}")
    else:
        print(f"    OK")

    # API safety check (open-world)
    if spec.world == "open" and pre_api:
        post_api = _collect_exported_symbols(project_dir, spec)
        fixture_symbols = set(fixture_info.get("expected_removals", []))
        lost_api = (pre_api - post_api) - fixture_symbols
        api_safe = len(lost_api) == 0
        api_log = (f"Lost {len(lost_api)} non-fixture API symbols: "
                   + ", ".join(sorted(lost_api)[:10])) if lost_api else "API preserved"
        result.api_diff = api_log
        step = StepResult("api_safety", api_safe, log=api_log)
        if not api_safe:
            step.reason = api_log
        result.add_step(step)
        if not api_safe:
            print(f"    API FAIL: {api_log}")
        else:
            print(f"    API OK ({len(post_api)} symbols preserved)")
    else:
        result.add_step(StepResult("api_safety", True, log="closed-world, skipped"))

    # Step 9: Post-pruning build
    print(f"  [9/10] Post-pruning build...")
    exit_code, stdout, stderr, elapsed = run_cmd(
        spec.build_cmd, str(work_dir), timeout=spec.timeout, env=spec.env)
    step = StepResult("post_build", exit_code == 0,
                      command=" ".join(spec.build_cmd), exit_code=exit_code,
                      elapsed=elapsed, log=(stderr or stdout)[:2000])
    if exit_code != 0:
        step.reason = f"Post-pruning build failed (exit {exit_code})"
    result.add_step(step)
    if exit_code != 0:
        print(f"    BUILD FAIL (exit {exit_code})")
    else:
        print(f"    Build OK ({elapsed:.1f}s)")

    # Step 10: Post-pruning test
    print(f"  [10/10] Post-pruning test...")
    exit_code, stdout, stderr, elapsed = run_cmd(
        spec.test_cmd, str(work_dir), timeout=spec.timeout, env=spec.env)
    post_test_output = stdout + "\n" + stderr
    post_test_passed = exit_code == 0
    if not post_test_passed and baseline_failures:
        post_failures = _extract_test_failures(
            post_test_output, spec.language)
        if post_failures == baseline_failures:
            post_test_passed = True
            print(f"    Test OK (same {len(post_failures)} platform-specific "
                  f"failure(s) as baseline, {elapsed:.1f}s)")
        else:
            print(f"    Test failures differ from baseline:")
            for f in sorted(post_failures ^ baseline_failures)[:5]:
                print(f"      - {f}")
    step = StepResult("post_test", post_test_passed,
                      command=" ".join(spec.test_cmd), exit_code=exit_code,
                      elapsed=elapsed, log=_log_excerpt(post_test_output))
    if not post_test_passed:
        step.reason = f"Post-pruning test failed (exit {exit_code})"
    result.add_step(step)
    if not post_test_passed:
        print(f"    TEST FAIL (exit {exit_code})")
    elif exit_code == 0:
        print(f"    Test OK ({elapsed:.1f}s)")

    if spec.variant_prepare_cmd:
        print("  [10b/10] Post-pruning variant build...")
        exit_code, stdout, stderr, elapsed = run_variant_check(project_dir, spec)
        step = StepResult(
            "post_variant", exit_code == 0,
            command=(" ".join(spec.variant_prepare_cmd) + " && "
                     + " ".join(spec.variant_build_cmd)),
            exit_code=exit_code, elapsed=elapsed,
            log=_log_excerpt(stdout + stderr),
            reason=("Post-pruning variant build failed" if exit_code else ""))
        result.add_step(step)

    result.passed = result.all_steps_passed()
    return result


# ── Reporting ───────────────────────────────────────────────────────


def print_summary(results: list[ValidationResult]):
    print(f"\n{'='*60}")
    print("  VALIDATION SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = ("PASS_WITH_BASELINE_FAILURES"
                  if r.passed and r.baseline_failures
                  else "PASS" if r.passed else "FAIL")
        icon = "\u2714" if r.passed else "\u2718"
        print(f"  {icon} {r.project:25s} {status}  "
              f"(world={r.world}, files={r.file_count})")
        if not r.passed:
            for e in r.errors[:5]:
                print(f"      {e[:100]}")
        if r.fixture_removals:
            for sym, status_val in r.fixture_removals.items():
                tag = "\u2714" if status_val in ("removed", "file_deleted") else "\u2718"
                print(f"      {tag} removal: {sym} \u2192 {status_val}")
        if r.fixture_preserved:
            for sym, status_val in r.fixture_preserved.items():
                tag = "\u2714" if status_val == "present" else "\u2718"
                print(f"      {tag} preserve: {sym} \u2192 {status_val}")

    passed = sum(1 for r in results if r.passed)
    print(f"\n  {passed}/{len(results)} projects passed")
    return passed == len(results)


def generate_reports(results: list[ValidationResult]):
    """Generate JSON and Markdown reports from validation results."""
    docs_dir = PRUNER_ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    json_data = []
    for r in results:
        steps_data = [
            {
                "name": s.name,
                "passed": s.passed,
                "command": s.command,
                "exit_code": s.exit_code,
                "elapsed": round(s.elapsed, 2),
                "log": s.log,
                "reason": s.reason,
            }
            for s in r.steps
        ]
        json_data.append({
            "project": r.project,
            "world": r.world,
            "passed": r.passed,
            "baseline_failures": sorted(r.baseline_failures),
            "file_count": r.file_count,
            "steps": steps_data,
            "fixture_removals": r.fixture_removals,
            "fixture_preserved": r.fixture_preserved,
            "non_fixture_diff": r.non_fixture_diff,
            "api_diff": r.api_diff,
            "errors": r.errors,
        })

    json_path = docs_dir / "validation_results.json"
    json_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')

    md_lines = ["# Real-World Project Validation Report\n"]
    md_lines.append(f"Generated from `scripts/validate_real_projects.py`.\n")

    passed = sum(1 for r in results if r.passed)
    md_lines.append(f"## Summary: {passed}/{len(results)} projects passed\n")

    for r in results:
        status = ("PASS_WITH_BASELINE_FAILURES \u26a0"
                  if r.passed and r.baseline_failures
                  else "PASS \u2714" if r.passed else "FAIL \u2718")
        spec = PROJECTS.get(r.project)
        md_lines.append(f"### {r.project} \u2014 {status}\n")
        if spec:
            md_lines.append(f"- **Repository**: {spec.repo}")
            md_lines.append(f"- **Commit**: `{spec.commit}`")
            md_lines.append(f"- **Language**: {spec.language}")
        md_lines.append(f"- **Boundary mode**: {r.world}")
        md_lines.append(f"- **Source files**: {r.file_count}")
        if r.baseline_failures:
            md_lines.append("- **Approved environment failures**: "
                            + ", ".join(sorted(r.baseline_failures)))
        md_lines.append("")

        md_lines.append("#### Steps\n")
        md_lines.append("| Step | Status | Exit Code | Elapsed | Command |")
        md_lines.append("|------|--------|-----------|---------|---------|")
        for s in r.steps:
            s_status = "\u2714" if s.passed else "\u2718"
            cmd_display = s.command[:60] if s.command else "\u2014"
            md_lines.append(
                f"| {s.name} | {s_status} | {s.exit_code} | "
                f"{s.elapsed:.1f}s | `{cmd_display}` |")
        md_lines.append("")

        if r.fixture_removals:
            md_lines.append("#### Fixture Results\n")
            md_lines.append("| Symbol | Expected | Result |")
            md_lines.append("|--------|----------|--------|")
            for sym, val in r.fixture_removals.items():
                md_lines.append(f"| {sym} | removal | {val} |")
            for sym, val in r.fixture_preserved.items():
                md_lines.append(f"| {sym} | preserve | {val} |")
            md_lines.append("")

        if r.non_fixture_diff:
            md_lines.append("#### Non-fixture diff\n")
            md_lines.append("```")
            md_lines.append(r.non_fixture_diff)
            md_lines.append("```\n")

        if r.api_diff:
            md_lines.append(f"#### API Safety\n")
            md_lines.append(f"{r.api_diff}\n")

        if r.errors:
            md_lines.append("#### Errors\n")
            for e in r.errors:
                md_lines.append(f"- {e}")
            md_lines.append("")

    md_lines.append("## Known Limitations\n")
    md_lines.append("- Go exported receiver methods are conservatively retained because "
                    "dependency and standard-library interfaces cannot be inferred completely "
                    "from project syntax alone.")
    md_lines.append("- Generated Dart files are identified by filename suffix and "
                    "header comment; non-standard generators may not be detected.")
    md_lines.append("- Kotlin class-level `val` booleans are not propagated "
                    "(only function-local `val` booleans are); use `replacements` "
                    "config for class-level constants.")
    md_lines.append("- LocalSend validation runs Flutter analysis and tests, including "
                    "the official proprietary-dependency removal variant; Android APK "
                    "packaging is excluded because its pinned dependency graph currently "
                    "mixes JVM targets 17 and 21 before pruning.")
    md_lines.append("")

    md_path = docs_dir / "REAL_WORLD_VALIDATION.md"
    md_path.write_text("\n".join(md_lines), encoding='utf-8')

    print(f"\n  Reports generated:")
    print(f"    {json_path}")
    print(f"    {md_path}")


def main():
    parser = argparse.ArgumentParser(description="Validate dead-code-pruner")
    parser.add_argument("project", nargs="?", help="Project to validate")
    parser.add_argument("--all", action="store_true",
                        help="Validate all projects")
    parser.add_argument("--list", action="store_true",
                        help="List available projects")
    args = parser.parse_args()

    if args.list:
        for name, spec in PROJECTS.items():
            print(f"  {name:25s} {spec.language:8s} world={spec.world:6s} {spec.repo}")
        return 0

    _ensure_python_symlink()

    if args.all:
        specs = list(PROJECTS.values())
    elif args.project:
        if args.project not in PROJECTS:
            print(f"Unknown project: {args.project}")
            print(f"Available: {', '.join(PROJECTS)}")
            return 1
        specs = [PROJECTS[args.project]]
    else:
        parser.print_help()
        return 1

    results = []
    for spec in specs:
        try:
            results.append(validate_project(spec))
        finally:
            shutil.rmtree(WORK_DIR / spec.name, ignore_errors=True)
            (WORK_DIR / f"{spec.name}_pruner.yaml").unlink(missing_ok=True)
    all_passed = print_summary(results)
    generate_reports(results)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
