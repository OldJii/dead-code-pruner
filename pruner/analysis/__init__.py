"""Static analysis modules — method scanning, reference indexing, class hierarchy."""

from .method_scanner import scan_methods
from .ref_index import build_ref_index, collect_files, is_in_comment_or_string
from .class_hierarchy import enhance_safety, is_framework_class
from .code_edit import (
    replace_calls_in_content, remove_void_calls_in_content,
    clean_standalone_booleans, delete_line_ranges, has_cross_file_refs,
    verify_no_dangling_calls,
)
from .project_scan import scan_project, ProjectScanResult
from .project_layout import ProjectLayout

__all__ = [
    'scan_methods', 'build_ref_index', 'collect_files',
    'is_in_comment_or_string',
    'enhance_safety', 'is_framework_class',
    'replace_calls_in_content', 'remove_void_calls_in_content',
    'clean_standalone_booleans', 'delete_line_ranges', 'has_cross_file_refs',
    'verify_no_dangling_calls',
    'scan_project', 'ProjectScanResult', 'ProjectLayout',
]
