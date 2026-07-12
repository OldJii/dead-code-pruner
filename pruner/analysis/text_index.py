"""Per-file comment/string span index for O(1) position queries.

Builds an interval list once per file content so repeated
``is_in_comment_or_string`` checks do not re-scan from the start.
Also provides helpers for safely removing standalone constant
expression statements without corrupting multi-line assignments.
"""

from __future__ import annotations


class TextIndex:
    """Interval index over comment and string literal spans."""

    __slots__ = ('_spans',)

    def __init__(self, content: str):
        self._spans: list[tuple[int, int]] = _build_spans(content)

    def covers(self, pos: int) -> bool:
        """Return ``True`` if *pos* falls inside a comment or string."""
        spans = self._spans
        lo, hi = 0, len(spans)
        while lo < hi:
            mid = (lo + hi) // 2
            s, e = spans[mid]
            if pos < s:
                hi = mid
            elif pos >= e:
                lo = mid + 1
            else:
                return True
        return False


def _build_spans(content: str) -> list[tuple[int, int]]:
    """Collect [start, end) spans for comments and string literals.

    Code inside Kotlin/Dart ``${…}`` and Swift ``\\(…)`` interpolations
    is treated as normal code (not covered by the enclosing string span).
    """
    spans: list[tuple[int, int]] = []
    n = len(content)
    i = 0
    while i < n:
        c = content[i]

        if c == '/' and i + 1 < n:
            c2 = content[i + 1]
            if c2 == '/':
                start = i
                i = content.find('\n', i + 2)
                if i == -1:
                    i = n
                spans.append((start, i))
                continue
            if c2 == '*':
                start = i
                end = content.find('*/', i + 2)
                i = end + 2 if end != -1 else n
                spans.append((start, i))
                continue

        if c in ('"', "'"):
            quote = c
            start = i
            i += 1
            while i < n:
                ch = content[i]
                if ch == '\\':
                    if quote == '"' and i + 1 < n and content[i + 1] == '(':
                        spans.append((start, i))
                        i = _skip_swift_interp(content, i + 2)
                        start = i
                        continue
                    i += 2
                    continue
                if ch == '$' and quote == '"' and i + 1 < n and content[i + 1] == '{':
                    spans.append((start, i))
                    i = _skip_brace_interp(content, i + 2)
                    start = i
                    continue
                if ch == quote:
                    i += 1
                    break
                i += 1
            if start < i:
                spans.append((start, i))
            continue

        i += 1

    return spans


def _skip_brace_interp(content: str, i: int) -> int:
    depth = 1
    n = len(content)
    while i < n and depth > 0:
        c = content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c in ('"', "'"):
            q = c
            i += 1
            while i < n and content[i] != q:
                if content[i] == '\\':
                    i += 1
                i += 1
        i += 1
    return i


def _skip_swift_interp(content: str, i: int) -> int:
    depth = 1
    n = len(content)
    while i < n and depth > 0:
        c = content[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c in ('"', "'"):
            q = c
            i += 1
            while i < n and content[i] != q:
                if content[i] == '\\':
                    i += 1
                i += 1
        i += 1
    return i


def is_continuation_of_assignment(lines: list[str], line_idx: int) -> bool:
    """Return ``True`` if *line_idx* continues a multi-line ``… =`` assignment.

    Prevents deleting ``false;`` / ``42;`` when they are the RHS of::

        boolean flag =
            false;
    """
    j = line_idx - 1
    while j >= 0 and lines[j].strip() == '':
        j -= 1
    if j < 0:
        return False
    prev = lines[j].rstrip()
    return prev.endswith('=')


def clean_standalone_literal_lines(content: str, literals: set[str]) -> str:
    """Remove lines whose stripped form is in *literals*, unless they continue
    a multi-line assignment.
    """
    if not literals:
        return content
    lines = content.split('\n')
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in literals and not is_continuation_of_assignment(lines, i):
            continue
        out.append(line)
    return '\n'.join(out)
