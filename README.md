# dead-code-pruner

Conservative multi-language dead-code elimination powered by tree-sitter.

dead-code-pruner is a static analysis and source cleanup tool for removing dead code after feature flag cleanup, boolean constant folding, and compile-time configuration changes. Give it a constant mapping and it folds configured flags, simplifies boolean/control-flow expressions, eliminates dead branches, inlines constant-return methods, removes provably-unused methods and fields, and protects dynamic framework entry points through iterative project-level analysis.

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

The tool runs a **3-phase + cleanup pipeline**. Per-file work reaches a fixed point internally; project-level cleanup then iterates only over files changed by the previous round:

| Phase | Steps | Purpose |
|-------|-------|---------|
| **1** | Constant fold → local propagation → bool simplify → compound bool → if-block eliminate → unreachable removal → unused var cleanup | One project pass; every file converges internally |
| **2** | Constant-return method inlining → cascade simplify | Available as an isolated phase; merged into Phase 3 in the default full run |
| **3** | Unified scan → constant/empty and adapter-approved method cleanup → private field cleanup → incremental re-scan | Remove declarations and converge project-wide without repeated full scans |
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
| Local constant propagation | `final boolean isPrimary = true; if (isPrimary)` | `if (true)` → eliminated |
| Unused boolean var cleanup | `final boolean isPrimary = true;` (no remaining uses) | *(removed)* |

### Phase 2: Constant-Return Method Inlining

| Transformation | Description |
|---|---|
| Boolean method inlining | `private fun isEnabled(): Boolean = true` → all `isEnabled()` replaced with `true` |
| String/int/null method inlining | `private static String getRegion() { return "primary"; }` → replaced with `"primary"` |
| Static method inlining | `static boolean isOldMode() { return false; }` → `ClassName.isOldMode()` replaced with `false` |
| Cascade simplification | After inlining, Phase 1 re-runs to simplify newly-constant expressions |
| Private method deletion | After all call sites are inlined, the now-orphaned method definition is removed |

Supported inlined return types: `boolean`, `int`, `long`, `float`, `double`, `String`, and negative numeric literals. `null`/`nil` returns are detected but not substituted at call sites because the required target type is not inferred.

### Phase 3: Dead Member Cleanup

| Transformation | Description |
|---|---|
| Empty void method removal | `private void doNothing() {}` → call sites removed, definition deleted |
| Orphaned constant method removal | Methods returning constants (`true`/`false`/`null`/`42`/`"text"`) with no remaining callers |
| Cross-file call-site removal | Same as above but across multiple files in the project |
| Unused field removal | Unreferenced fields are removed only after project-wide reference and safety checks |
| Multi-variable declaration safety | `int used, unused;` is kept unless every declarator can be removed safely |
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
| **Annotated members** | `@Override`, `@Bean`, `@LongLinkObs`, `@objc`, `@IBAction`, `@Composable` | Methods and fields may be generated, injected, or framework-managed |
| **Abstract / interface methods** | `abstract void process();` | Part of a contract |
| **Override methods** | `override fun onResume()` | Called by framework, not user code |
| **Native methods** | `native void jni_call();` | JNI/FFI binding |
| **Framework lifecycle methods** | `onCreate`, `viewDidLoad`, `build`, `main`, `init`, `ServeHTTP` | Language adapter protects them by name |
| **Go exported functions** | `func HandleRequest(...)` (uppercase) | Part of public API |
| **Dart private naming** | `_helper()` is library-private | Constant/empty cleanup is supported; arbitrary bodies remain unless the adapter can prove every reference form |
| **Dynamic references** | `#selector(doAction)`, `android:onClick`, XML `action`/`selector` attributes | Layout, Storyboard, and generated callback references are scanned |
| **Static and inherited calls** | Java/Kotlin static imports and calls through subclasses | Project indexes resolve imported and transitively inherited members |
| **Short symbol names** | Methods such as `d()`, `e()`, or `bs()` | Short names participate in the same reference checks as other symbols |
| **Calls with parameters** | `helper(expensiveArg())` | Call sites are never substituted; arbitrary definitions require explicit adapter approval before zero-reference deletion |
| **Public methods with callers** | Referenced from other files or via reflection | Cross-file reference analysis prevents deletion |
| **Multi-variant methods** | Same name returns different values in different source sets | Source-set conflict detection skips them |

### Language Adapter Protection

Each language has a dedicated adapter (`pruner/adapters/`) that owns:

- **Protected method names**: lifecycle hooks, framework callbacks, runtime-required entry points
- **Visibility rules**: Go unexported = safe, Dart `_` prefix = file-private, Swift `fileprivate` = file-scoped
- **Syntax normalization**: exact parameter arity, receiver/declaring type, callable and field node shapes
- **Contract extraction**: Java/Kotlin interfaces, Go structural interfaces, Swift protocols, Dart abstract/implements relationships
- **Language transforms**: immutable local booleans, Kotlin `if` expressions, and branch-scope rules

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
│   ├── java.py            Java / Android syntax, contracts, and entry points
│   ├── kotlin.py          Kotlin syntax, contracts, and if expressions
│   ├── jvm_common.py      Callbacks shared by Java and Kotlin
│   ├── contract_utils.py  Grammar-neutral contract parsing helpers
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
    ├── field_scanner.py      Conservative unused-field detection
    ├── contracts.py          Incremental per-file contract graph
    ├── project_scan.py       Unified single-pass project scan
    ├── project_layout.py     Multi-module project detection
    ├── ref_index.py          Cross-file reference index
    ├── text_index.py         Compact textual and dynamic-reference index
    └── code_edit.py          Call-site replacement & deletion
```

## Safety Mechanisms

- **AST-precise**: tree-sitter precisely distinguishes code from comments and strings
- **Language-native literals**: Java/Kotlin text blocks, Go raw strings, Swift extended strings, Dart raw strings, and interpolation boundaries are protected
- **AST validation gate**: every transformation is validated — changes that introduce new parse errors are automatically rolled back
- **Per-file rollback**: project-level method, field, and empty-class edits are parsed again before being committed to disk
- **Language adapters**: each ecosystem has dedicated entry-point and visibility rules (lifecycle methods, annotations, naming conventions)
- **Annotation-safe**: annotated methods and fields are never deleted (framework/DI/AOP/generated-code managed)
- **Chain-call aware**: instance methods called via `obj.field.method()` are detected via cross-file reference analysis
- **Inheritance-aware**: skips abstract, interface, and framework base-class methods, and resolves inherited static calls transitively
- **Import-aware**: Java and Kotlin static imports are indexed before removing member declarations
- **Dynamic-resource aware**: Android XML callbacks/actions and Apple selector references protect their source declarations
- **Overload-safe**: parameter count matching prevents confusing overloaded methods
- **Declaration-safe**: comments cannot bind to the following declaration, and multi-variable fields are removed atomically
- **Java switch-safe**: shared switch-scope declarations are preserved or hoisted when a constant branch exits early
- **Dangling reference check**: methods are only deleted after verifying no remaining call sites exist
- **Module-aware**: multi-module projects (Gradle, Go, Dart) track methods per module to avoid cross-module name collision
- **Exact dry-run**: runs the real converging pipeline in an isolated copy, including cascades, without writing through source-tree symlinks
- **Synthetic fixtures only**: tests and documentation use generic packages, identifiers, paths, scenarios, and measurements; source material from external projects must be anonymized before inclusion
- **Quality gate**: pipeline summary reports rejected file edits and line change statistics
- **Conservative by design**: when in doubt, the method is kept

## Performance and Progress

- Phase 1 processes the project once because each file already converges internally; Phase 3 parses project sources through one unified scan and incrementally refreshes changed files.
- CPU-heavy scans use parallel workers on sufficiently large projects, while incremental rounds only revisit changed files.
- Output has one hierarchy—Phase → Round → Stage—and every percentage stage continuously rewrites one terminal line. Redirected output emits only the final state for each stage.
- Runtime depends on project size, filesystem cache, and convergence rounds; large initial scans use multiple processes and later rounds only revisit modified files.

## Requirements

- Python 3.10+
- Dependencies: `pip install -r requirements.txt`

## Testing

```bash
python3 tests/run_tests.py           # 5-language step 1–4 tests
python3 tests/run_project_tests.py   # 14 project-level safety and cleanup suites
python3 tests/test_language_matrix.py # 5-language syntax/safety/project parity matrix
python3 tests/test_ui.py             # in-place progress and hierarchy rendering
```

## Limitations

- Local propagation is limited to immutable booleans (`final boolean`, Kotlin `val`, Go `const`, Swift `let`, Dart `final`/`const`)
- Dead member detection is conservative — annotated, public, generated, dynamically referenced, or otherwise ambiguous declarations are preserved
- Only single-return-statement methods are inlined (no multi-statement constant-return analysis)
- Does not analyse method parameters for side effects
- Empty class removal requires no cross-file references (enum types are always preserved)

## License

MIT
