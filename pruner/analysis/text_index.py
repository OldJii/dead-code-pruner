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
                depth = 1
                i += 2
                while i < n and depth:
                    if content.startswith('/*', i):
                        depth += 1
                        i += 2
                    elif content.startswith('*/', i):
                        depth -= 1
                        i += 2
                    else:
                        i += 1
                spans.append((start, i))
                continue

        # Go raw strings.  Backticks are not interpolation containers.
        if c == '`':
            end = content.find('`', i + 1)
            end = n if end < 0 else end + 1
            spans.append((i, end))
            i = end
            continue

        # Swift extended string delimiters: #"..."#, ##"""..."""##.
        if c == '#':
            hash_end = i
            while hash_end < n and content[hash_end] == '#':
                hash_end += 1
            if hash_end < n and content[hash_end] in ('"', "'"):
                hashes = content[i:hash_end]
                quote = content[hash_end]
                delimiter = quote * (3 if content.startswith(quote * 3, hash_end) else 1)
                string_spans, i = _scan_string(
                    content, i, hash_end + len(delimiter), delimiter + hashes,
                    swift_interp='\\' + hashes + '(', brace_interp=False,
                    escapes=False)
                spans.extend(string_spans)
                continue

        if c in ('"', "'"):
            delimiter = c * (3 if content.startswith(c * 3, i) else 1)
            raw_prefix = i > 0 and content[i - 1] in ('r', 'R')
            string_spans, i = _scan_string(
                content, i, i + len(delimiter), delimiter,
                swift_interp='\\(', brace_interp=not raw_prefix,
                escapes=not raw_prefix)
            spans.extend(string_spans)
            continue

        i += 1

    return spans


def _scan_string(content: str, start: int, position: int, closing: str, *,
                 swift_interp: str, brace_interp: bool,
                 escapes: bool) -> tuple[list[tuple[int, int]], int]:
    """Scan one string and expose interpolation expressions as code gaps."""
    spans: list[tuple[int, int]] = []
    span_start = start
    n = len(content)
    i = position
    while i < n:
        if content.startswith(closing, i):
            i += len(closing)
            spans.append((span_start, i))
            return spans, i
        if swift_interp and content.startswith(swift_interp, i):
            spans.append((span_start, i))
            i = _skip_swift_interp(content, i + len(swift_interp))
            span_start = i
            continue
        if brace_interp and content.startswith('${', i):
            spans.append((span_start, i))
            i = _skip_brace_interp(content, i + 2)
            span_start = i
            continue
        if escapes and content[i] == '\\':
            i += 2
        else:
            i += 1
    if span_start < n:
        spans.append((span_start, n))
    return spans, n


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
