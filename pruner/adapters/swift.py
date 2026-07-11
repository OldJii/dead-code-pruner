"""Swift / iOS language adapter.

Covers UIKit / SwiftUI lifecycle, Storyboard/XIB selector references,
Codable, and Objective-C interop.
"""

from __future__ import annotations

from .base import BaseAdapter

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

_PROTECTED_ANNOTATION_PREFIXES: frozenset[str] = frozenset({
    '@objc', '@IBAction', '@IBOutlet', '@IBDesignable', '@IBInspectable',
    '@available', '@discardableResult',
    '@Published', '@State', '@Binding', '@ObservedObject',
    '@EnvironmentObject', '@StateObject', '@Environment',
    '@main', '@UIApplicationMain',
    '@testable',
})


class SwiftAdapter(BaseAdapter):

    @property
    def protected_names(self) -> frozenset[str]:
        return _PROTECTED_NAMES

    @property
    def protected_annotation_prefixes(self) -> frozenset[str]:
        return _PROTECTED_ANNOTATION_PREFIXES

    @property
    def reference_file_extensions(self) -> frozenset[str]:
        return frozenset({'.storyboard', '.xib', '.plist'})

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
