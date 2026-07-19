# Dead-code-pruner Architecture

## Pipeline Overview

Two-phase, tree-sitter-based dead-code cleanup tool for Java, Kotlin, Go, Swift, and Dart.

### Phase 1: Source Simplification (per-file convergence)

Steps 1–8 run per file in a convergence loop until no changes remain:

1. **Replace configured constants** — text patterns → boolean literals, skipping strings/comments/declarations
2. **Propagate local constants** — `final boolean x = false` → replace all uses of `x` within its callable scope
3. **Simplify booleans** — `!true → false`, `false == x → !x`, etc.
4. **Simplify compound expressions** — `true && expr → expr`, ternary resolution
5. **Language-specific expressions** — Kotlin `when`/`let`/`also`, etc.
6. **Eliminate dead branches** — `if (false) { ... }` removal
7. **Remove unreachable code** — code after `return`/`throw`/`break`/`continue`
8. **Clean unused bool vars** — remove declarations with no remaining uses; shares Step 2's callable-local eligibility policy so fields cannot be misclassified

### Phase 2: Project Cleanup (iterative convergence)

1. **Unified project scan** — methods, fields, references, contracts, type hierarchy
2. **Dead declaration cleanup** — call-site rewriting → definition deletion → field cleanup
3. **Phase 1 cascade** — re-run Phase 1 on modified files
4. **Refresh scan** — incremental update of project indices
5. **Empty class/file cleanup** — remove unreferenced empty types and import-only files

### Language Adapters

Each language adapter (`pruner/adapters/`) provides:
- Protected names (lifecycle, framework hooks)
- Contract detection (interface/protocol methods)
- Field handling (visibility, generated APIs, Lombok)
- Entry point detection
- Safe-to-inline decisions
- Callable value patterns (Go/Swift/Dart function references)

### Project Boundary Detection

`pruner/analysis/project_boundary.py` classifies modules as:
- **closed** — application/service, all callers are within scan boundary
- **open** — library, external consumers may exist

Heuristics: Gradle plugins, Maven packaging, Swift Package.swift products, pubspec.yaml, go.mod, deployment manifests.

### Generated File Protection

Files identified as machine-generated are indexed for outgoing references but
excluded from all transformations and definition deletions.

Detection is adapter-specific:
- **Dart**: filename suffixes (`.g.dart`, `.freezed.dart`, `.gen.dart`,
  `.mapper.dart`) and the `GENERATED CODE` header comment.

### Safety Guarantees

1. AST validation — re-parse after transformation, rollback if new errors appear
2. Contract graph — preserve interface/protocol method implementations
3. Reference index — cross-file reference checking before deletion
4. Dynamic reference detection — string literals, reflection patterns
5. Annotation preservation — never delete annotated declarations
6. Override preservation — never delete override/implement methods
7. Generated file protection — never modify machine-generated source files
8. Conditional compilation — preserve `#if`/`#else`/`#endif` preprocessor directives
9. Go structural typing — preserve exported receiver methods that may satisfy external interfaces
10. Callable value detection — detect function/method references in assignments, arguments, and returns
11. Build-variant references — retain symbols selected by explicit shell-script rewrites

## Supported Language Matrix

| Language | Extensions | Ecosystems | Key Safety Features |
|----------|-----------|------------|-------------------|
| Java | `.java` | Android, JVM services, Maven, Gradle | Lombok, annotations, Serializable, Spring/JPA |
| Kotlin | `.kt`, `.kts` | Android, JVM services, Gradle | JVM accessors, trailing lambdas, infix calls, companion objects |
| Go | `.go` | Go services, CLI tools | Structural interfaces, exported symbols, init/main |
| Swift | `.swift` | iOS, macOS, SwiftPM | Protocols, @objc, UIKit lifecycle, storyboard refs |
| Dart | `.dart` | Flutter, Dart packages | Widget lifecycle, underscore privacy, abstract classes |

## File Structure

```
pruner/
  pipeline.py          # Two-phase orchestrator
  transform.py         # Phase 1 per-file pipeline
  cli.py               # CLI entry point
  config.py            # YAML config loading
  lang.py              # Language registry (tree-sitter parsers)
  validation.py        # AST error detection and rollback
  ast_utils.py         # Shared tree-sitter utilities
  ui.py                # Console output formatting
  adapters/
    base.py            # Abstract adapter interface
    java.py            # Java adapter (Lombok, annotations)
    kotlin.py          # Kotlin adapter (JVM interop)
    go.py              # Go adapter (structural interfaces)
    swift.py           # Swift adapter (protocols, UIKit)
    dart.py            # Dart adapter (Flutter lifecycle)
    jvm_common.py      # Shared JVM protected names
    java_calls.py      # Java method-call replacement
    java_validation.py # Java semantic validation
    callable_refs.py   # Cross-language callable-value patterns
    contract_utils.py  # Shared contract extraction
  analysis/
    project_scan.py    # Unified single-pass project scanner
    project_boundary.py # Open/closed world detection
    project_layout.py  # Module discovery (Gradle, Maven, SwiftPM, etc.)
    contracts.py       # Type hierarchy and contract graph
    method_scanner.py  # Method definition scanner
    field_scanner.py   # Field/constant scanner
    ref_index.py       # Reference index (calls, types, dynamic)
    text_index.py      # Text-level reference search
    code_edit.py       # Call-site rewriting and deletion
  steps/
    constant_fold.py   # Steps 1, 2, 8
    bool_simplify.py   # Step 3
    compound_bool.py   # Step 4
    kotlin_expr.py     # Step 5 (Kotlin)
    if_blocks.py       # Step 6
    unreachable.py     # Step 7
    dead_methods.py    # Phase 2 Step 2
    empty_cleanup.py   # Phase 2 Step 5
    method_inline.py   # Standalone boolean method inlining
```
