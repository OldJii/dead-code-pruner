"""Base language adapter — abstract interface for language-specific safety rules.

Language adapters encapsulate visibility analysis, framework entry-point
detection, and protected-symbol knowledge that varies across ecosystems.
The pruning pipeline queries the adapter before deleting or inlining any
method, ensuring language-idiomatic safety without hard-coding rules in
shared analysis modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Pattern


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
    def reference_file_extensions(self) -> frozenset[str]:
        """Extra non-source file extensions to scan for dynamic references.

        E.g. ``.storyboard``, ``.xib``, ``.plist`` for Swift/iOS.
        """
        return frozenset()

    @property
    def method_node_types(self) -> frozenset[str]:
        """tree-sitter declaration nodes that represent callable bodies."""
        return frozenset({'method_declaration', 'function_declaration',
                          'function_definition', 'method_definition'})

    @property
    def class_node_types(self) -> frozenset[str]:
        """tree-sitter declaration nodes that introduce a named type."""
        return frozenset({'class_declaration', 'class_definition',
                          'object_declaration', 'interface_declaration',
                          'enum_declaration'})

    @property
    def field_node_types(self) -> frozenset[str]:
        """Primary declaration nodes for removable fields/constants."""
        return frozenset({'field_declaration', 'property_declaration',
                          'const_declaration'})

    def field_names(self, declaration, content: bytes) -> list[str] | None:
        """Return declared names, or ``None`` for the shared extractor."""
        return None

    def field_traits(self, declaration, content: bytes) -> dict:
        """Return language-derived ``private/static/final`` flags."""
        return {}

    def is_generated_source(self, filepath: str) -> bool:
        """Whether *filepath* is machine-generated and must not be modified.

        Generated files are still scanned for references (callers) but are
        excluded from transformations and definition deletions.
        """
        return False

    def field_reference_names(self, declaration, content: bytes,
                              name: str) -> frozenset[str]:
        """Return source or generated symbols that can reference a field.

        Most languages expose the declaration name directly.  Adapters may
        add compiler-generated accessor names used by cross-language callers.
        """
        return frozenset({name})

    def field_is_implicitly_referenced(self, declaration, content: bytes,
                                       name: str) -> bool:
        """Whether generated code or a runtime contract consumes a field.

        This is deliberately separate from declaration annotations.  A field
        can be unannotated while its enclosing type generates a constructor,
        participates in serialization, or is populated through reflection.
        """
        return False

    def field_exposes_generated_api(self, declaration, content: bytes,
                                    name: str) -> bool:
        """Whether the field produces an externally callable generated API.

        Open-world modules must preserve these fields even when the generated
        accessor is absent from source and therefore cannot be indexed.
        """
        return False

    def field_initializer_has_effects(self, declaration, content: bytes,
                                      name: str) -> bool:
        """Whether deleting the declaration may drop observable evaluation."""
        return False

    def field_declaration_span(self, declaration, content: bytes) -> tuple[int, int]:
        """Return byte bounds for the complete removable declaration."""
        return declaration.start_byte, declaration.end_byte

    @property
    def preserve_branch_scope(self) -> bool:
        """Keep braces when eliminating a branch that declares variables."""
        return True

    @property
    def uses_structural_contracts(self) -> bool:
        """Whether interface conformance is implicit rather than declared."""
        return False

    @property
    def local_boolean_patterns(self) -> tuple[Pattern[bytes], ...]:
        """Regexes for immutable local booleans, with name/value groups."""
        return ()

    def local_boolean_is_propagatable(
            self, root, content: bytes, name: bytes, declaration_start: int,
            declaration_end: int, scope_end: int) -> bool:
        """Whether a matched boolean is a local immutable/effectively-final value."""
        return True

    def phase1_step5_simplify_language_expressions(
            self, content: bytes) -> bytes:
        """Apply syntax unique to this language before branch elimination."""
        return content

    def replace_configured_calls(self, content: bytes, rules: list) -> bytes:
        """Apply language-aware configured call replacements.

        Call syntax and evaluation order are language contracts, so the
        shared constant-folding step delegates the operation to adapters.
        Unsupported languages conservatively leave the source unchanged.
        """
        return content

    def preserves_transformation_semantics(
            self, original: bytes, transformed: bytes) -> bool:
        """Reject a syntactically valid transformation that breaks a language contract."""
        return True

    def parameter_count(self, declaration, content: bytes) -> int | None:
        """Return source-level arity, or ``None`` for shared fallback logic."""
        return None

    def accepts_method_node(self, declaration) -> bool:
        """Filter grammar helper nodes that would duplicate a declaration."""
        return True

    def method_name(self, declaration, content: bytes) -> str | None:
        """Return a name when the grammar nests it below the declaration."""
        return None

    def method_body(self, declaration):
        """Return a body node when it is not a child of the declaration."""
        return None

    def declaration_end_byte(self, declaration, body) -> int:
        """Return the byte end of the complete callable declaration."""
        return declaration.end_byte

    def return_type_text(self, declaration, content: bytes) -> str | None:
        """Return the declared return type for non-standard grammars."""
        return None

    def declaring_type(self, declaration, content: bytes) -> str | None:
        """Return a declaring type not represented by AST nesting.

        Go receiver methods are the main example.  Nested class-like
        declarations are resolved by the shared scanner.
        """
        return None

    def contract_facts(self, content: str) -> dict:
        """Extract language-specific type hierarchy and contract facts.

        The result uses three stable keys: ``contracts``, ``relations`` and
        ``methods``.  Keeping extraction
        here prevents grammar-specific regexes from leaking into the shared
        project graph.
        """
        return {
            'contracts': set(),
            'relations': {},
            'methods': {},
        }

    def is_entry_point(self, record: dict) -> bool:
        """Return ``True`` if *record* represents a framework entry point.

        *record* is the method-info dict produced by ``method_scanner``.
        Override this to implement language-specific heuristics beyond the
        ``protected_names`` list (e.g. Go exported functions, Swift @objc,
        Dart top-level ``main``).
        """
        return record.get('name', '') in self.protected_names

    def compute_safe_to_inline(self, record: dict) -> bool:
        """Return language-level eligibility for call rewriting/deletion.

        This answers syntax and dispatch questions only.  The project-boundary
        policy separately decides whether an externally visible declaration
        may be deleted.  The generic rule supports private and static calls
        because both can be resolved precisely by the shared reference index.
        """
        if self.is_entry_point(record):
            return False
        mods = record.get('all_mods', set())
        return 'private' in mods or 'static' in mods

    def is_language_private(self, record: dict) -> bool:
        """Whether external source consumers cannot name this declaration.

        Project-boundary policy uses this stricter visibility predicate in
        open-world modules.  ``static`` describes ownership, not visibility,
        and therefore does not make a declaration private.
        """
        return 'private' in (record.get('all_mods', set()) or set())

    def can_prune_unreferenced_nonconstant(self, record: dict) -> bool:
        """Whether zero-reference proof is sufficient for a real method body.

        Constant-return and empty callables are handled by the normal
        call-site rewrite pipeline.  Removing an arbitrary body is a stronger
        operation: languages with implicit calls, callable values, selectors,
        or framework dispatch need language-specific proof before opting in.
        The conservative default therefore preserves the declaration.
        """
        return False

    @property
    def implicit_call_patterns(self) -> tuple[Pattern[str], ...]:
        """Language-only call forms not covered by ``name(...)``/``::name``.

        Every pattern must expose the referenced callable name as group 1.
        """
        return ()

    @property
    def implicit_reference_patterns(self) -> tuple[Pattern[str], ...]:
        """Language-only callable-value forms not covered by call syntax.

        Swift, Dart, and Go can pass a function or method without invoking it,
        for example ``let callback = helper``.  Every pattern must expose the
        referenced callable name as group 1.  The shared scanner keeps these
        references in a language-keyed index so they cannot affect another
        language's deletion decisions.
        """
        return ()
