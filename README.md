# dead-code-pruner

Conservative multi-language dead-code elimination powered by tree-sitter.

dead-code-pruner is a static analysis and source cleanup tool for removing dead code after feature flag cleanup, boolean constant folding, and compile-time configuration changes. Give it a constant mapping and it folds configured flags, simplifies boolean/control-flow expressions, eliminates dead branches, inlines constant-return methods, removes safe dead methods, and protects dynamic framework entry points through iterative project-level analysis.

Built on [tree-sitter](https://tree-sitter.github.io/) for format-agnostic, comment-safe, multi-language analysis.

Keywords: dead code elimination, dead code cleanup, static analysis, tree-sitter, feature flag cleanup, boolean simplification, constant folding, Java dead code, Kotlin dead code, Android dead code cleanup, Swift dead code, iOS dead code, TypeScript dead code, refactoring automation.

## The Problem

Projects accumulate boolean feature flags (`AppConfig.IS_DEBUG`, `FeatureFlags.LEGACY_MODE`, compile-time constants, etc.). When a flag becomes permanently `true` or `false`, the guarded code is dead — but cleaning it manually across thousands of files is tedious and error-prone.

## What It Does

```yaml
# pruner.yaml
replacements:
  - pattern: "AppConfig.IS_DEBUG"
    value: false
```

The tool runs a **3-phase pipeline** that loops until no more changes are found:

| Phase | Steps | Purpose |
|-------|-------|---------|
| **1** | Constant fold → bool simplify → compound bool → if-block eliminate | Replace flags and simplify control flow |
| **2** | Inline constant-return methods → cascade simplify | Remove `return true/false` helpers |
| **3** | Dead method cleanup → cascade simplify | Remove empty void methods and orphaned definitions |

Each phase can trigger new simplification opportunities in earlier steps — the pipeline converges automatically.

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

Shortcut entry point (equivalent to `python3 -m pruner`):

```bash
python3 run_pruner.py . --config pruner.yaml
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

## Supported Languages

Java, Kotlin, Go, C, C++, JavaScript, TypeScript, Rust, Swift, C# — and any language with a tree-sitter grammar (add one line in `pruner/lang.py`).

## Architecture

```
pruner/
├── cli.py              Command-line interface
├── pipeline.py         3-phase orchestrator with progress output
├── transform.py        Single-file pipeline (steps 1–4)
├── lang.py             Language registry (tree-sitter parsers)
├── ast_utils.py        Core AST manipulation
├── steps/
│   ├── constant_fold.py    Step 1: constant replacement
│   ├── bool_simplify.py    Step 2: simple boolean algebra
│   ├── compound_bool.py    Step 3: compound boolean + ternary
│   ├── if_blocks.py        Step 4: dead branch elimination
│   ├── kotlin_expr.py      Kotlin if-expression pre-pass
│   ├── method_inline.py    Step 5: constant method inlining
│   └── dead_methods.py     Step 6: dead method cleanup
└── analysis/
    ├── method_scanner.py     AST method detection
    ├── project_scan.py       Unified single-pass project scan
    ├── ref_index.py          Cross-file reference index
    ├── class_hierarchy.py    Inheritance analysis
    └── code_edit.py          Call-site replacement & deletion
```

## Safety Mechanisms

- **AST-precise**: tree-sitter precisely distinguishes code from comments and strings
- **Annotation-safe**: any method with `@Annotation` is never deleted (framework/DI/AOP managed)
- **Chain-call aware**: instance methods called via `obj.field.method()` are detected via cross-file reference analysis
- **Inheritance-aware**: skips abstract, interface, and framework base-class methods
- **Overload-safe**: parameter count matching prevents confusing overloaded methods
- **Conservative by design**: when in doubt, the method is kept

## Requirements

- Python 3.10+
- Dependencies: `pip install -r requirements.txt`

## Testing

```bash
python3 tests/run_tests.py           # 10-language step 1–4 tests
python3 tests/run_project_tests.py   # step 5 & 6 project-level tests
```

## Limitations

- Cannot fold through intermediate variables (`bool x = FLAG; if (x) ...`)
- Some languages share a C-family parser; edge-case syntax may use dedicated pre-passes
- Dead method detection is conservative — annotated, public, or potentially-referenced methods are preserved

## License

MIT
