# dead-code-pruner

`dead-code-pruner` is a conservative source-level dead-code cleanup tool powered by [tree-sitter](https://tree-sitter.github.io/).

Give it a set of expressions that are permanently `true` or `false`. It propagates those facts through the source tree, simplifies the resulting control flow, and removes declarations and files that become provably unused.

The tool currently understands Java, Kotlin, Go, Swift, and Dart. It is designed for Android, JVM services, Go services, iOS, and Flutter repositories, including multi-module projects.

## What It Can Clean

Starting from configured constants, the tool can produce source changes such as:

- Replace retired feature flags and compile-time conditions with boolean literals.
- Simplify boolean expressions, negations, equality checks, short-circuit expressions, ternaries, and language-specific conditional expressions.
- Remove dead `if` branches and code that becomes unreachable after `return`, `throw`, `break`, or `continue`.
- Propagate immutable local booleans and remove their declarations after all uses disappear.
- Inline zero-argument methods that always return `true` or `false`, then continue cleaning the newly exposed branches.
- Remove empty methods, unused constant-return helpers, and their safe call sites.
- Remove unused immutable fields when project-wide references and project-boundary rules prove that deletion is safe.
- Remove unreferenced empty classes and source files left with no declarations.
- Repeat cascading cleanup until no further source changes can be derived.

For example, a retired feature can collapse across multiple files into the remaining live path:

```diff
diff --git a/LegacyFeatureController.java b/LegacyFeatureController.java
--- a/LegacyFeatureController.java
+++ b/LegacyFeatureController.java
@@
 final class LegacyFeatureController {
-    private static final boolean RETIRED_DEFAULT = false;
-
-    private boolean isLegacyMode() {
-        return false;
-    }
-
-    private void recordLegacyExposure() {}
-
     void render() {
-        final boolean legacyEnabled = FeatureFlags.LEGACY_MODE;
-        recordLegacyExposure();
-        if (!legacyEnabled
-                && (LegacyFeatureController.RETIRED_DEFAULT || isLegacyMode())) {
-            RetiredFeature.renderLegacy();
-            return;
-            unreachableLegacyCleanup();
-        } else {
-            renderCurrent();
-        }
+        renderCurrent();
     }
 }

diff --git a/LegacyScreen.kt b/LegacyScreen.kt
--- a/LegacyScreen.kt
+++ b/LegacyScreen.kt
@@
-val title = if (false) legacyTitle else currentTitle
+val title = currentTitle

diff --git a/RetiredFeature.java b/RetiredFeature.java
deleted file mode 100644
--- a/RetiredFeature.java
+++ /dev/null
@@
-package com.example.legacy;
-
-final class RetiredFeature {
-    static void renderLegacy() {}
-}
```

The cleanup is intentionally conservative. Annotated declarations, framework entry points, contracts, overrides, dynamic references, and public APIs that may be used outside the scanned repository are preserved unless the tool can prove they are safe to remove.

## Usage

Python 3.10 or newer is required.

```bash
git clone https://github.com/OldJii/dead-code-pruner.git
cd dead-code-pruner
pip install -r requirements.txt
cp pruner.example.yaml pruner.yaml
```

Edit `pruner.yaml` and replace the examples with the constants retired in your project:

```yaml
project_boundary:
  mode: auto

replacements:
  - pattern: "FeatureFlags.LEGACY_MODE"
    value: false
  - pattern: "BuildConfig.CURRENT_VARIANT"
    value: true

# Java method calls are matched as invocation AST nodes, not text. The
# receiver and optional arity prevent unrelated overloads from matching.
method_replacements:
  - method: "chatInteractionModeGrayConfig.hit"
    arity: 1
    value: true
```

Method-call rules never rewrite declarations. By default they also skip a
call when removing it would discard a nested call, assignment, object
creation, update, lambda, or array access from its receiver or arguments.
Use `discard_side_effects: true` only when that behavior is intentional.
Unqualified method names are rejected unless the rule explicitly sets
`allow_unqualified: true`.

The same opt-in is required for unqualified, non-constant symbol names such
as `enable`. Uppercase constant names such as `FEATURE_FLAG` remain supported
without it. This prevents a configuration-field default from accidentally
rewriting every same-named local or member across a service repository.

Run the cleanup against a project directory:

```bash
python3 -m pruner /path/to/your/project --config pruner.yaml
```

Run it on a separate Git branch, inspect the resulting diff, and compile and test the target project before merging the changes.

## Using It Outside Android

The implementation includes language adapters and tests for Java, Kotlin, Go, Swift, and Dart, but its large-scale production use has so far been validated only on Android projects.

For a non-Android repository, start with a fork. If a language construct is not handled correctly, use the failing source as a small reproducible fixture, ask an AI coding agent to analyze the AST or reference-resolution gap, and add an input/expected-output test before adjusting the adapter or cleanup rule. Once the new case and the existing suites all pass, the behavior is fixed as a repeatable rule and the cleanup can be applied to the target repository with confidence.

Run the complete test set after extending the tool:

```bash
python3 tests/run_tests.py
python3 tests/run_project_tests.py
python3 tests/test_language_matrix.py
python3 tests/test_project_boundary.py
```

## How It Works

tree-sitter parses source files into syntax trees, allowing the tool to distinguish expressions, declarations, calls, comments, strings, and control-flow boundaries without relying on fragile text replacement.

The tool first simplifies each file from the configured boolean facts. It then builds project-level indexes for declarations, references, inheritance, contracts, generated accessors, and dynamic entry points. Only declarations with no remaining safe reference are removed. Modified files are analyzed again, allowing one deletion to expose the next until the project reaches a stable result.

Language adapters supply the syntax and framework rules for each ecosystem, while project-boundary detection preserves externally visible APIs in libraries and permits broader cleanup in applications and deployed services.

The main pipeline has two phases:

1. **Source simplification** runs eight syntax-level steps in source order and repeats them per file until that file is stable.
2. **Project cleanup** scans the project once, removes provably dead declarations, reruns source simplification on changed files, refreshes those files in the project index, and repeats until stable. It then removes unreferenced empty classes and files.

Project-wide boolean-method inlining is also exposed as a standalone utility for focused integrations, but it is not a separate pipeline phase.

## License

MIT
