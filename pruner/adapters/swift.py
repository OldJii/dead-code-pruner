"""Swift / iOS language adapter.

Covers UIKit / SwiftUI lifecycle, Storyboard/XIB selector references,
Codable, and Objective-C interop.
"""

from __future__ import annotations

import re

from .base import BaseAdapter
from .callable_refs import CALLABLE_VALUE_PATTERNS
from .contract_utils import declared_bodies, split_type_list

_PROTECTED_NAMES: frozenset[str] = frozenset({
    # ── UIKit ViewController lifecycle ──
    'viewDidLoad', 'viewWillAppear', 'viewDidAppear',
    'viewWillDisappear', 'viewDidDisappear',
    'viewDidLayoutSubviews', 'viewWillLayoutSubviews',
    'viewWillTransition', 'didReceiveMemoryWarning',
    'prepare', 'loadView', 'viewSafeAreaInsetsDidChange',

    # ── UIKit UIView ──
    'layoutSubviews', 'draw', 'awakeFromNib',
    'hitTest', 'point', 'sizeThatFits', 'intrinsicContentSize',

    # ── UITableView / UICollectionView ──
    'tableView', 'collectionView', 'numberOfSections',
    'numberOfRows', 'numberOfRowsInSection',
    'cellForRowAt', 'cellForRow',
    'didSelectRowAt', 'didSelect',
    'heightForRowAt', 'sizeForItemAt',

    # ── UIApplication delegate ──
    'applicationDidFinishLaunching',
    'applicationWillResignActive', 'applicationDidEnterBackground',
    'applicationWillEnterForeground', 'applicationDidBecomeActive',
    'applicationWillTerminate', 'application',

    # ── Codable / NSCoding ──
    'encode', 'init', 'deinit',

    # ── SwiftUI ──
    'body', 'makeBody', 'makeUIView', 'updateUIView',
    'makeCoordinator',

    # ── Combine ──
    'receive',

    # ── Equatable / Hashable / Comparable ──
    'hash',
})

_LOCAL_BOOL = re.compile(
    rb'\blet\s+(\w{3,})\s*(?::\s*Bool\s*)?=\s*(true|false)\b')
_TYPE_DECL = re.compile(
    r'\b(?:final\s+)?(class|struct|actor|protocol)\s+(\w+)\s*([^\{]*)\{')
_PROTOCOL_BODY = re.compile(r'\bprotocol\s+(\w+)\b[^\{]*\{')
_PROTOCOL_METHOD = re.compile(r'(?m)^\s*(?:[\w@]+\s+)*func\s+(\w+)\s*\(')


class SwiftAdapter(BaseAdapter):

    @property
    def protected_names(self) -> frozenset[str]:
        return _PROTECTED_NAMES

    @property
    def reference_file_extensions(self) -> frozenset[str]:
        return frozenset({'.storyboard', '.xib', '.plist'})

    @property
    def local_boolean_patterns(self):
        return (_LOCAL_BOOL,)

    @property
    def implicit_reference_patterns(self):
        return CALLABLE_VALUE_PATTERNS

    @property
    def field_node_types(self) -> frozenset[str]:
        return frozenset({'property_declaration'})

    def field_traits(self, declaration, content: bytes) -> dict:
        raw = content[declaration.start_byte:declaration.end_byte]
        return {'final': b'let ' in raw}

    def parameter_count(self, declaration, content: bytes) -> int | None:
        params = [c for c in declaration.named_children if c.type == 'parameter']
        return len(params)

    def is_entry_point(self, record: dict) -> bool:
        name = record.get('name', '')
        if name in self.protected_names:
            return True
        mods = record.get('all_mods', set())
        if 'override' in mods:
            return True
        return False

    def compute_safe_to_inline(self, record: dict) -> bool:
        if self.is_entry_point(record):
            return False
        mods = record.get('all_mods', set())
        if 'private' in mods or 'fileprivate' in mods:
            return True
        return 'static' in mods

    def is_language_private(self, record: dict) -> bool:
        mods = record.get('all_mods', set()) or set()
        return 'private' in mods or 'fileprivate' in mods

    def contract_facts(self, content: str) -> dict:
        facts = super().contract_facts(content)
        for match in _TYPE_DECL.finditer(content):
            kind, name, tail = match.groups()
            if kind == 'protocol':
                facts['contracts'].add(name)
            tail = tail.strip()
            if tail.startswith(':'):
                parents = split_type_list(tail[1:])
                if parents:
                    facts['relations'][name] = set(parents)
        for name, body in declared_bodies(content, _PROTOCOL_BODY):
            facts['methods'][name] = {
                m.group(1) for m in _PROTOCOL_METHOD.finditer(body)
            }
        return facts
