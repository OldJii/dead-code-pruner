"""Small grammar-neutral helpers used by language contract extractors."""

from __future__ import annotations

import re


def split_type_list(raw: str) -> list[str]:
    """Split a generic type list and return unqualified identifiers."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in raw:
        if char in '<([':
            depth += 1
        elif char in '>)]':
            depth = max(0, depth - 1)
        if char == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append(''.join(current).strip())

    names: list[str] = []
    for part in parts:
        part = re.sub(r'<[^>]*>', '', part).strip().rstrip(',')
        # Kotlin superclass entries invoke a constructor: ``Base()`` or
        # ``Base(arg)``.  Contract identity is the type before that call.
        part = re.sub(r'\([^()]*\)\s*$', '', part).strip()
        if not part or part.startswith('where '):
            continue
        part = part.split()[-1].rsplit('.', 1)[-1]
        if re.fullmatch(r'[A-Za-z_]\w*', part):
            names.append(part)
    return names


def balanced_body(content: str, open_brace: int) -> str | None:
    """Return a brace-delimited body while skipping comments and strings."""
    if open_brace < 0 or open_brace >= len(content) or content[open_brace] != '{':
        return None
    depth = 0
    i = open_brace
    n = len(content)
    while i < n:
        if content.startswith('//', i):
            end = content.find('\n', i + 2)
            i = n if end < 0 else end
            continue
        if content.startswith('/*', i):
            level = 1
            i += 2
            while i < n and level:
                if content.startswith('/*', i):
                    level += 1
                    i += 2
                elif content.startswith('*/', i):
                    level -= 1
                    i += 2
                else:
                    i += 1
            continue
        if content.startswith('"""', i) or content.startswith("'''", i):
            quote = content[i:i + 3]
            end = content.find(quote, i + 3)
            i = n if end < 0 else end + 3
            continue
        char = content[i]
        if char in ('"', "'", '`'):
            quote = char
            i += 1
            while i < n:
                if quote != '`' and content[i] == '\\':
                    i += 2
                    continue
                if content[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return content[open_brace + 1:i]
        i += 1
    return None


def declared_bodies(content: str, declaration: re.Pattern[str]):
    """Yield ``(name, body)`` for declarations matched through their ``{``."""
    for match in declaration.finditer(content):
        body = balanced_body(content, match.end() - 1)
        if body is not None:
            yield match.group(1), body
