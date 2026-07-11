"""Base language adapter — abstract interface for language-specific safety rules.

Language adapters encapsulate visibility analysis, framework entry-point
detection, and protected-symbol knowledge that varies across ecosystems.
The pruning pipeline queries the adapter before deleting or inlining any
method, ensuring language-idiomatic safety without hard-coding rules in
shared analysis modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """Contract that every language adapter must fulfil."""

    @property
    @abstractmethod
    def protected_names(self) -> frozenset[str]:
        """Method/function names that must never be deleted or inlined.

        These are lifecycle hooks, framework callbacks, or runtime-required
        symbols whose removal would break the application even if no
        explicit call site exists in user code.
        """

    @property
    @abstractmethod
    def protected_annotation_prefixes(self) -> frozenset[str]:
        """Annotation prefixes that mark a method as framework-managed.

        An annotation whose text starts with any of these prefixes causes the
        method to be excluded from dead-code candidates.  The current engine
        already skips *all* annotated methods; these prefixes are provided for
        future fine-grained filtering.
        """

    @property
    def reference_file_extensions(self) -> frozenset[str]:
        """Extra non-source file extensions to scan for dynamic references.

        E.g. ``.storyboard``, ``.xib``, ``.plist`` for Swift/iOS.
        """
        return frozenset()

    def is_entry_point(self, record: dict) -> bool:
        """Return ``True`` if *record* represents a framework entry point.

        *record* is the method-info dict produced by ``method_scanner``.
        Override this to implement language-specific heuristics beyond the
        ``protected_names`` list (e.g. Go exported functions, Swift @objc,
        Dart top-level ``main``).
        """
        return record.get('name', '') in self.protected_names

    def compute_safe_to_inline(self, record: dict) -> bool:
        """Determine whether *record* can be safely inlined/deleted.

        Returns ``True`` when the method's visibility guarantees it cannot be
        called from outside the declaring file.  Falls back to the generic
        private-or-static rule when no language-specific logic applies.
        """
        if self.is_entry_point(record):
            return False
        mods = record.get('all_mods', set())
        return 'private' in mods or 'static' in mods
