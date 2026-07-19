# Real-World Project Validation Report

All five pinned projects were validated individually with
`scripts/validate_real_projects.py`. Each run compared the unmodified baseline
with the pruned tree, compiled the injected fixture before pruning, checked its
expected removals and preserved symbols, then rebuilt and retested the result.

## Summary

| Project | Boundary | Files | Result | Additional coverage |
|---|---:|---:|---|---|
| Javalin | open | 367 | PASS | Full multi-module Maven test; 305 existing API symbols preserved |
| Ktlint | open | 390 | PASS | Full Gradle test including CLI tests; 1,396 existing API symbols preserved |
| Restic | closed | 559 | PASS_WITH_BASELINE_FAILURES | `go build ./...`; FreeBSD/arm64 compile; failures exactly match two macOS xattr baseline failures |
| Swift Argument Parser | open | 166 | PASS_WITH_BASELINE_FAILURES | Full SwiftPM build/test; 247 API symbols preserved; failures exactly match 12 baseline manpage-output failures |
| LocalSend | closed | 373 | PASS | Flutter analyze/test plus the official proprietary-dependency removal variant before and after pruning |

## Regressions found by real-project validation

- Go generic calls, method values, implicit external-interface implementations,
  and exported receiver methods required conservative reference handling.
- Dart generated files must remain immutable while still contributing outgoing
  references.
- Shell release scripts can select otherwise unreferenced source symbols.
- Dart generic invocations such as `_worker<R, S, P>(...)` require a dedicated
  reference shape.
- Swift computed properties and value-returning functions can place the return
  expression on following lines; those expressions are not unreachable code.
- Kotlin class fields must not be treated as function-local constants.
- Java records and JVM annotation string references require explicit indexing.

Every compile regression discovered above has a focused test in
`tests/test_language_matrix.py` or the Java compile-regression fixture.

## Additional Android regression validation

A private 19,668-source-file, 29-module Android project was reset recursively
to its repository baseline, pruned to convergence, and built with
`./gradlew :app:assembleIntlGmsV8DxxDebug`. The build completed successfully
after 6 minutes 43 seconds (577 Gradle tasks). This validation added focused
regressions for Kotlin infix extension references and for ensuring Java/Kotlin
class boolean fields never enter the callable-local constant cleanup pipeline.

## Environment-qualified baseline failures

Restic has two macOS xattr failures in both baseline and pruned trees:
`TestNodeRestoreAt` and `TestOverwriteXattr`.

Swift Argument Parser has 12 GenerateManual golden-output failures in both
baseline and pruned trees: the single-page and multi-page cases for CountLines,
Color, Math, Repeat, Roll, and DefaultAsFlag. No new failure is accepted: the
validator requires exact equality with the configured baseline failure set.

## Known limitations

- Go exported receiver methods are conservatively retained because interfaces
  declared in dependencies and the standard library cannot be inferred fully
  from project syntax.
- Dart generated files are recognized by known suffixes and a generated-code
  header; non-standard generators may need an adapter update.
- Kotlin class-level boolean `val` fields are not propagated automatically; use
  an explicit replacement rule when their value is a known build fact.
- LocalSend validation compiles through Flutter analysis and test kernels,
  including its FOSS variant. APK packaging is excluded because the pinned
  upstream dependency graph mixes JVM targets 17 and 21 before pruning.
