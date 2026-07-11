# dead-code-pruner

Conservative multi-language dead-code elimination powered by tree-sitter.

dead-code-pruner is a static analysis and source cleanup tool for removing dead code after feature flag cleanup, boolean constant folding, and compile-time configuration changes. Give it a constant mapping and it folds configured flags, simplifies boolean/control-flow expressions, eliminates dead branches, inlines constant-return methods, removes safe dead methods, and protects dynamic framework entry points through iterative project-level analysis.

Built on [tree-sitter](https://tree-sitter.github.io/) for format-agnostic, comment-safe, multi-language analysis.

Keywords: dead code elimination, dead code cleanup, static analysis, tree-sitter, feature flag cleanup, boolean simplification, constant folding, Java dead code, Kotlin dead code, Android dead code cleanup, Go dead code, Swift dead code, iOS dead code, Dart dead code, Flutter dead code, refactoring automation.

## The Problem

Projects accumulate boolean feature flags (`AppConfig.IS_DEBUG`, `FeatureFlags.LEGACY_MODE`, compile-time constants, etc.). When a flag becomes permanently `true` or `false`, the guarded code is dead — but cleaning it manually across thousands of files is tedious and error-prone.

## What It Does

```yaml
# pruner.yaml
replacements:
  - pattern: "AppConfig.IS_DEBUG"
    value: false
```

The tool runs a **3-phase + cleanup pipeline** that loops until no more changes are found:

| Phase | Steps | Purpose |
|-------|-------|---------|
| **1** | Constant fold → local propagation → bool simplify → compound bool → if-block eliminate → unreachable removal → unused var cleanup | Replace flags and simplify control flow |
| **2** | Inline constant-return methods → cascade simplify | Remove `return true/false/null/"str"/42` helpers |
| **3** | Dead method cleanup → cascade simplify | Remove empty void methods and orphaned definitions |
| **Cleanup** | Empty class detection → reference check → removal | Remove classes left empty after method deletion |

Each phase can trigger new simplification opportunities in earlier steps — the pipeline converges automatically.

## Supported Ecosystems

| Ecosystem | Languages | Extensions |
|-----------|-----------|------------|
| Android | Java, Kotlin | `.java`, `.kt`, `.kts` |
| Java/Kotlin Server | Java, Kotlin | `.java`, `.kt`, `.kts` |
| Go Server | Go | `.go` |
| Swift iOS | Swift | `.swift` |
| Dart/Flutter | Dart | `.dart` |

## What Gets Cleaned

### Phase 1: Constant Folding + Expression Simplification

| Transformation | Before | After |
|---|---|---|
| Configured constant replacement | `if (BuildConfig.INTERNATIONAL)` | `if (false)` |
| Boolean negation folding | `!true`, `!false` | `false`, `true` |
| Boolean equality simplification | `true == false`, `x != x` | `false` |
| Compound boolean short-circuit | `true && expr`, `false \|\| expr` | `expr` |
| Compound boolean identity | `false && expr`, `true \|\| expr` | `false`, `true` |
| Ternary/conditional resolution | `true ? A : B`, `false ? A : B` | `A`, `B` |
| Dead if-branch elimination (true) | `if (true) { A } else { B }` | `A` |
| Dead if-branch elimination (false) | `if (false) { A } else { B }` | `B` |
| Dead if without else | `if (false) { ... }` | *(removed)* |
| Chained else-if collapse | `else if (true) { A } else ...` | `else { A }` |
| Unreachable code after if-exit | `if (true) { return; } dead();` | `return;` |
| Standalone unreachable removal | `return; deadCode(); moreCode();` | `return;` |
| Loop unreachable removal | `for (...) { break; dead(); }` | `for (...) { break; }` |
| Kotlin if-expression (return) | `return if (true) { A } else B` | `return A` |
| Kotlin if-expression (assignment) | `val x = if (false) A else B` | `val x = B` |
| Boolean-to-string concat | `true + ""` | `"true"` |
| Redundant paren unwrap | `(true)` | `true` |
| Local constant propagation | `final boolean isIntl = true; if (isIntl)` | `if (true)` → eliminated |
| Unused boolean var cleanup | `final boolean isIntl = true;` (no remaining uses) | *(removed)* |

### Phase 2: Constant-Return Method Inlining

| Transformation | Description |
|---|---|
| Boolean method inlining | `private fun isEnabled(): Boolean = true` → all `isEnabled()` replaced with `true` |
| String/int/null method inlining | `private static String getRegion() { return "intl"; }` → replaced with `"intl"` |
| Static method inlining | `static boolean isOldMode() { return false; }` → `ClassName.isOldMode()` replaced with `false` |
| Cascade simplification | After inlining, Phase 1 re-runs to simplify newly-constant expressions |
| Private method deletion | After all call sites are inlined, the now-orphaned method definition is removed |

Supported constant return types: `boolean`, `int`, `long`, `float`, `double`, `String`, `null`/`nil`, negative numeric literals.

### Phase 3: Dead Method Cleanup

| Transformation | Description |
|---|---|
| Empty void method removal | `private void doNothing() {}` → call sites removed, definition deleted |
| Orphaned constant method removal | Methods returning constants (`true`/`false`/`null`/`42`/`"text"`) with no remaining callers |
| Cross-file call-site removal | Same as above but across multiple files in the project |
| Cascade simplification | After removals, Phase 1 re-runs to simplify any affected control flow |

### Cleanup: Empty Class & File Removal

| Transformation | Description |
|---|---|
| Empty class detection | Classes with no remaining methods, fields, or inner classes |
| Cross-project reference check | Only removes classes not referenced by any other file in the project |
| Empty file deletion | Files left with only `package`/`import` declarations are deleted |

## What Is Explicitly Preserved

The tool is **conservative by design** — when in doubt, code is kept.

### Always Preserved

| Category | Examples | Reason |
|---|---|---|
| **Annotated methods** | `@Override`, `@Bean`, `@Test`, `@objc`, `@IBAction`, `@Composable` | Annotations indicate framework management |
| **Abstract / interface methods** | `abstract void process();` | Part of a contract |
| **Override methods** | `override fun onResume()` | Called by framework, not user code |
| **Native methods** | `native void jni_call();` | JNI/FFI binding |
| **Framework lifecycle methods** | `onCreate`, `viewDidLoad`, `build`, `main`, `init`, `ServeHTTP` | Language adapter protects them by name |
| **Go exported functions** | `func HandleRequest(...)` (uppercase) | Part of public API |
| **Dart private naming** | `_helper()` is treated as file-private but not force-deleted | Only deleted when provably unreferenced |
| **Dynamic references** | `#selector(doAction)`, `selector="tapHandler"` | Storyboard/XIB references are scanned |
| **Methods with parameters** | Any method requiring arguments | Not supported for inlining (no argument analysis) |
| **Public methods with callers** | Referenced from other files or via reflection | Cross-file reference analysis prevents deletion |
| **Multi-variant methods** | Same name returns different values in different source sets | Source-set conflict detection skips them |

### Language Adapter Protection

Each language has a dedicated adapter (`pruner/adapters/`) that defines:

- **Protected method names**: lifecycle hooks, framework callbacks, runtime-required entry points
- **Visibility rules**: Go unexported = safe, Dart `_` prefix = file-private, Swift `fileprivate` = file-scoped
- **Entry-point detection**: Go test functions (`Test*`, `Benchmark*`), main functions, interface implementations

## Quick Start

```bash
git clone https://github.com/OldJii/dead-code-pruner.git
cd dead-code-pruner

pip install -r requirements.txt

cp pruner.example.yaml /path/to/your/project/pruner.yaml
# Edit pruner.yaml with your project's constants

# Preview changes
python3 -m pruner /path/to/your/project --dry-run

# Run full pipeline
python3 -m pruner /path/to/your/project
```

## Usage

```bash
# Full pipeline (auto-discovers pruner.yaml)
python3 -m pruner .

# Explicit config
python3 -m pruner src/ --config pruner.yaml

# Dry run — scan and report only
python3 -m pruner . --dry-run

# Run specific phases
python3 -m pruner . --phases 1          # constant folding only
python3 -m pruner . --phases 1,2        # phases 1 + 2
```

## Configuration

### YAML (recommended)

```yaml
replacements:
  - pattern: "AppConfig.IS_DEBUG"
    value: false
  - pattern: "FeatureFlags.LEGACY_MODE"
    value: false
```

### Flat key-value format

```yaml
AppConfig.IS_DEBUG: false
FeatureFlags.LEGACY_MODE: false
```

### JSON

```json
{
  "replacements": [
    { "pattern": "AppConfig.IS_DEBUG", "value": false }
  ]
}
```

## Multi-Module Project Support

The tool automatically detects multi-module project layouts:

| Build System | Detection | Module Scope |
|---|---|---|
| **Gradle** (Android / JVM) | `settings.gradle` / `settings.gradle.kts` | Each `:module` is a separate scope |
| **Maven** | `pom.xml` with child modules | Each child `pom.xml` directory |
| **Go** | `go.mod` | Root module + nested `go.mod` directories |
| **Dart/Flutter** | `pubspec.yaml` | Root package + `packages/` sub-packages |
| **Xcode** | `.xcworkspace` / `.xcodeproj` | Single workspace scope |

Module awareness prevents same-named methods in different modules from being conflated during analysis. For example, `ModuleA:Utils.isEnabled()` and `ModuleB:Utils.isEnabled()` are tracked independently.

## Architecture

```
pruner/
├── cli.py              Command-line interface
├── pipeline.py         3-phase orchestrator with quality gate
├── transform.py        Single-file pipeline (steps 1–4)
├── validation.py       AST validation — rollback on new parse errors
├── lang.py             Language registry (tree-sitter parsers)
├── ui.py               Terminal output formatting (ANSI colors, progress bars)
├── ast_utils.py        Core AST manipulation
├── config.py           Configuration file discovery
├── adapters/           Language-specific safety rules
│   ├── base.py            Abstract adapter interface
│   ├── java_kotlin.py     Android / JVM server lifecycle & DI
│   ├── go.py              Go visibility & testing conventions
│   ├── swift.py           UIKit / SwiftUI / Storyboard safety
│   └── dart.py            Flutter widget lifecycle & naming
├── steps/              Transformation passes
│   ├── constant_fold.py    Step 1: constant replacement + local propagation
│   ├── bool_simplify.py    Step 2: simple boolean algebra
│   ├── compound_bool.py    Step 3: compound boolean + ternary
│   ├── if_blocks.py        Step 4: dead branch elimination
│   ├── unreachable.py      Step 1d: unreachable code removal
│   ├── kotlin_expr.py      Kotlin if-expression pre-pass
│   ├── method_inline.py    Step 5: constant method inlining (bool + non-bool)
│   ├── dead_methods.py     Step 6: dead method cleanup
│   └── empty_cleanup.py    Step 7: empty class & file cleanup
└── analysis/           Project-level analysis
    ├── method_scanner.py     AST method detection (adapter-aware)
    ├── project_scan.py       Unified single-pass project scan
    ├── project_layout.py     Multi-module project detection
    ├── ref_index.py          Cross-file reference index
    ├── class_hierarchy.py    Inheritance analysis
    └── code_edit.py          Call-site replacement & deletion
```

## Safety Mechanisms

- **AST-precise**: tree-sitter precisely distinguishes code from comments and strings
- **AST validation gate**: every transformation is validated — changes that introduce new parse errors are automatically rolled back
- **Language adapters**: each ecosystem has dedicated entry-point and visibility rules (lifecycle methods, annotations, naming conventions)
- **Annotation-safe**: any method with `@Annotation` is never deleted (framework/DI/AOP managed)
- **Chain-call aware**: instance methods called via `obj.field.method()` are detected via cross-file reference analysis
- **Inheritance-aware**: skips abstract, interface, and framework base-class methods
- **Overload-safe**: parameter count matching prevents confusing overloaded methods
- **Dangling reference check**: methods are only deleted after verifying no remaining call sites exist
- **Module-aware**: multi-module projects (Gradle, Go, Dart) track methods per module to avoid cross-module name collision
- **Quality gate**: pipeline summary reports rejected file edits and line change statistics
- **Conservative by design**: when in doubt, the method is kept

## Requirements

- Python 3.10+
- Dependencies: `pip install -r requirements.txt`

## Testing

```bash
python3 tests/run_tests.py           # 5-language step 1–4 tests
python3 tests/run_project_tests.py   # step 5 & 6 project-level tests
```

## Limitations

- Local constant propagation is limited to immutable boolean declarations (`final boolean`, `val`, `let`, `final bool`)
- Dead method detection is conservative — annotated, public, or potentially-referenced methods are preserved
- Only single-return-statement methods are inlined (no multi-statement constant-return analysis)
- Does not analyse method parameters for side effects
- Empty class removal requires no cross-file references (enum types are always preserved)

## License

MIT
