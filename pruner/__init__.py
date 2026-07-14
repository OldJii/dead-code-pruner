"""dead-code-pruner — AST-based dead code elimination.

Public API::

    from pruner.transform import load_config, process_file, run_pipeline
    from pruner.steps import (
        inline_boolean_methods_standalone,
        phase2_step2_cleanup_dead_declarations,
    )
    from pruner.pipeline import run_full_pipeline
"""
