"""Analysis package — project scanning, editing, and safety helpers."""

from .ref_index import (
    build_ref_index, collect_files, is_in_comment_or_string, clear_text_index_cache,
    iter_dynamic_reference_names, iter_type_identifiers,
)
from .code_edit import (
    clean_standalone_booleans, delete_line_ranges, has_cross_file_refs,
    replace_calls_in_content, remove_void_calls_in_content,
)
from .project_scan import scan_project, semantic_method_key
from .contracts import ContractGraph, is_safe_to_remove

__all__ = [
    'build_ref_index', 'collect_files', 'is_in_comment_or_string',
    'clear_text_index_cache',
    'iter_dynamic_reference_names', 'iter_type_identifiers',
    'clean_standalone_booleans', 'delete_line_ranges', 'has_cross_file_refs',
    'replace_calls_in_content', 'remove_void_calls_in_content',
    'scan_project', 'semantic_method_key',
    'ContractGraph', 'is_safe_to_remove',
]
