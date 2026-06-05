# dead-code-pruner

A static analysis tool that eliminates dead code produced by constant folding in Java/Kotlin projects. No IDE required — runs as a standalone Python script.

> **Keywords**: dead code elimination, constant folding, Java Kotlin refactoring, feature flag cleanup, boolean simplification, Android BuildConfig, static analysis, code cleanup pipeline.

## The Problem

Large projects accumulate boolean feature flags like `BuildConfig.IS_PRODUCTION`, `FeatureFlags.isLegacyMode()`, etc. When a flag becomes permanently `true` or `false`, the guarded code becomes dead — but manually cleaning it across thousands of files is tedious and error-prone.

## What This Tool Does

Given a config file that maps expressions to boolean values:

```yaml
replacements:
  - pattern: "BuildConfig.IS_PRODUCTION"
    value: true
```

The tool performs a 6-step pipeline that iterates until convergence:

1. **Constant replacement**: `BuildConfig.IS_PRODUCTION` → `true` (skips comments and strings)
2. **Simple boolean**: `!true` → `false`, `true == false` → `false`, etc.
3. **Compound boolean**: `true || expr` → `true`, `false && expr` → `false`, ternary simplification
4. **If-block elimination**: `if (true) { A } else { B }` → `A`, `if (false) { A }` → remove
5. **Constant method inlining**: Methods that only `return true/false` → inline at call sites
6. **Dead method cleanup**: Empty void methods and constant-returning boolean methods → remove definitions and call sites

Each step can produce new simplification opportunities for subsequent steps. The pipeline loops until no more changes are found.

## Quick Start

```bash
# 1. Create a config file
cp pruner.example.yaml pruner.yaml
# Edit pruner.yaml with your project's constants

# 2. Dry run to see what would change
python3 prune.py /path/to/your/project --dry-run

# 3. Run the full pipeline
python3 prune.py /path/to/your/project

# 4. Compile and verify
cd /path/to/your/project && ./gradlew compileDebugJavaWithJavac
```

## Configuration

### YAML format (recommended)

```yaml
# pruner.yaml
replacements:
  - pattern: "BuildConfig.IS_PRODUCTION"
    value: true
  - pattern: "FeatureFlags.isLegacyMode"
    value: false
  - pattern: "Config.ENABLE_OLD_UI"
    value: false

dead_methods:
  skip_method_patterns:
    - "__generated_"     # skip generated methods
  skip_dir_patterns:
    - "/test/"           # skip test directories
  skip_dirs:
    - "test_fixtures"    # skip specific directory names
```

### JSON format

```json
{
  "replacements": [
    { "pattern": "BuildConfig.IS_PRODUCTION", "value": true }
  ],
  "dead_methods": {
    "skip_method_patterns": [],
    "skip_dir_patterns": [],
    "skip_dirs": []
  }
}
```

## Usage

```bash
# Full pipeline
python3 prune.py .

# With custom config
python3 prune.py src/ --config my-config.yaml

# Run specific phase only
python3 prune.py . --phase 1    # constant folding + boolean simplification
python3 prune.py . --phase 2    # constant-returning method inlining
python3 prune.py . --phase 3    # dead method cleanup

# Dry run (scan only)
python3 prune.py . --dry-run

# Run individual steps
python3 step1_replace_constants.py /path/to/project --config pruner.yaml
python3 step3_compound_boolean.py /path/to/project
python3 step6_dead_methods.py /path/to/project --dry-run
```

## How It Works

### Pipeline Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              Phase 1 (loop)                 │
                    │  step1 → step2 → step3 → step4 → converge? │
                    └─────────────────────────────────────────────┘
                                       ↓
                    ┌─────────────────────────────────────────────┐
                    │              Phase 2 (loop)                 │
                    │  step5 → step2 → step3 → step4 → converge? │
                    └─────────────────────────────────────────────┘
                                       ↓
                    ┌─────────────────────────────────────────────┐
                    │              Phase 3 (loop)                 │
                    │  step6 → step2 → step3 → step4 → converge? │
                    └─────────────────────────────────────────────┘
```

### Step Details

| Step | Input | Output | Example |
|------|-------|--------|---------|
| step1 | `BuildConfig.IS_PRODUCTION` | `true` | Config-driven replacement |
| step2 | `!true` | `false` | Simple boolean algebra |
| step3 | `true \|\| A && B` | `true` | Respects operator precedence |
| step4 | `if (false) { X }` | *(removed)* | Block elimination with dead code removal |
| step5 | `isLocal()` where `isLocal() { return false; }` | `false` | Method inlining |
| step6 | `void doNothing() {}` | *(removed)* | Dead method + call site removal |

### Safety Mechanisms

- **Comment/string aware**: All replacements skip comments (`//`, `/* */`) and string literals
- **Operator precedence**: `true || A && B` correctly simplifies to `true`, not `B`
- **Overload-safe**: Method matching considers parameter count to avoid confusing overloads
- **Inheritance-aware**: step6 builds a class hierarchy and skips interface methods, abstract methods, `@Override` methods, and methods in classes that `implements` interfaces
- **Framework-safe**: Base/Abstract/Interface classes are excluded from aggressive cleanup
- **Chain-safe**: `method().subscribe()` chains are not broken by void call removal

## Requirements

- Python 3.8+
- No external dependencies (PyYAML optional, for YAML config; JSON config works without it)

## Limitations

- Designed for Java and Kotlin source files (`.java`, `.kt`)
- Does not perform semantic analysis — relies on pattern matching
- Cannot handle expressions assigned to intermediate variables (`boolean x = BuildConfig.FOO; if (x) ...`)
- Step6 dead method detection is conservative: only removes methods with truly empty bodies or single constant returns

## FAQ

**What problem does dead-code-pruner solve?**  
When feature flags like `BuildConfig.IS_PRODUCTION` become permanently `true` or `false`, guarded branches become dead code. This tool automates replacement, simplification, and removal across large Java/Kotlin codebases.

**Is it safe to run on production code?**  
Always run `--dry-run` first and verify with your compiler (`./gradlew compile...`). The tool is conservative (skips comments, strings, interfaces, `@Override`) but not a full semantic analyzer.

**Does it support Kotlin?**  
Yes — both `.java` and `.kt` files.

**Do I need external dependencies?**  
Python 3.8+ only. PyYAML is optional if you use YAML config; JSON config works without it.

**Can I run a single pipeline phase?**  
Yes — `python3 prune.py . --phase 1|2|3` or individual step scripts.

**Where can AI assistants read a structured summary?**  
See [`llms.txt`](./llms.txt) in this repository.

## License

MIT
