"""Terminal UI formatting — ANSI colors, progress bars, structured output.

Inspired by modern CLI tools (Cursor, Claude, cargo). Provides a
consistent visual language for the pipeline's terminal output.

All print helpers are centralized here so that the rest of the codebase
never writes raw ``print()`` calls for user-facing output.
"""

import os
import shutil
import sys
import unicodedata

_IS_TTY = sys.stdout.isatty()
_NO_COLOR = os.environ.get('NO_COLOR') is not None or not _IS_TTY
_progress_active = False
_progress_key = None


def _display_width(value: str) -> int:
    """Return the number of terminal columns used by plain *value*."""
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
               for ch in value)


def _truncate_columns(value: str, width: int) -> str:
    """Fit *value* into *width* terminal columns without splitting glyphs."""
    if width <= 0:
        return ''
    if _display_width(value) <= width:
        return value
    if width == 1:
        return '…'
    kept = []
    used = 0
    for ch in value:
        char_width = 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
        if used + char_width > width - 1:
            break
        kept.append(ch)
        used += char_width
    return ''.join(kept) + '…'


def _format_progress_line(current: int, total: int, label: str,
                          extra: str, indent: int, width: int) -> str:
    """Build a non-wrapping progress line for the current terminal width."""
    pad = ' ' * indent
    pct = current * 100 // total if total else 0
    count = f"{current}/{total}"
    suffix = '  '.join(part for part in (label, extra) if part)

    # Keep the counter and percentage readable even in narrow terminals.
    fixed = f"{pad}{pct:3d}%  {count}"
    if width >= 50:
        bar_width = min(20, max(10, width // 5))
        filled = bar_width * current // total if total else 0
        bar = '█' * filled + '░' * (bar_width - filled)
        fixed = f"{pad}{bar}  {fixed[len(pad):]}"
    available = max(0, width - _display_width(fixed))
    if available:
        suffix = _truncate_columns(suffix, max(0, available - 2))
        if suffix:
            fixed += f"  {suffix}"

    return _truncate_columns(fixed, width)


def _before_message():
    """Finish an in-place progress line before regular output."""
    global _progress_active, _progress_key
    if _progress_active:
        print()
        _progress_active = False
        _progress_key = None


class _C:
    """ANSI escape codes — disabled when NO_COLOR is set or stdout is not a tty."""
    RESET   = '' if _NO_COLOR else '\033[0m'
    BOLD    = '' if _NO_COLOR else '\033[1m'
    DIM     = '' if _NO_COLOR else '\033[2m'
    CYAN    = '' if _NO_COLOR else '\033[36m'
    GREEN   = '' if _NO_COLOR else '\033[32m'
    YELLOW  = '' if _NO_COLOR else '\033[33m'
    RED     = '' if _NO_COLOR else '\033[31m'
    B_CYAN  = '' if _NO_COLOR else '\033[1;36m'
    B_GREEN = '' if _NO_COLOR else '\033[1;32m'
    B_RED   = '' if _NO_COLOR else '\033[1;31m'
    B_YELLOW = '' if _NO_COLOR else '\033[1;33m'


def fmt_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m{s:.1f}s"


def banner(title: str, width: int = 62):
    _before_message()
    bar = '━' * width
    print(f"\n{_C.B_CYAN}{bar}{_C.RESET}")
    print(f"  {_C.BOLD}{title}{_C.RESET}")
    print(f"{_C.B_CYAN}{bar}{_C.RESET}")


def section(title: str):
    _before_message()
    print(f"\n{_C.CYAN}{'─' * 50}{_C.RESET}")
    print(f"  {_C.BOLD}{title}{_C.RESET}")
    print(f"{_C.CYAN}{'─' * 50}{_C.RESET}")


def round_header(round_num: int, label: str):
    """Render one convergence round inside the active top-level phase."""
    _before_message()
    print(f"\n{_C.DIM}───{_C.RESET} Round {round_num} · "
          f"{_C.CYAN}{label}{_C.RESET} {_C.DIM}───{_C.RESET}")


def stage(title: str, indent: int = 2):
    """Render a named stage inside the active round or section."""
    _before_message()
    print(f"\n{' ' * indent}{_C.DIM}Stage ·{_C.RESET} {_C.BOLD}{title}{_C.RESET}")


def kv(key: str, value, indent: int = 2):
    _before_message()
    pad = ' ' * indent
    print(f"{pad}{_C.DIM}{key}:{_C.RESET}  {value}")


def info(msg: str, indent: int = 2):
    _before_message()
    pad = ' ' * indent
    print(f"{pad}{msg}")


def success(msg: str, indent: int = 2):
    _before_message()
    pad = ' ' * indent
    print(f"{pad}{_C.B_GREEN}✔{_C.RESET} {msg}")


def warn(msg: str, indent: int = 2):
    _before_message()
    pad = ' ' * indent
    print(f"{pad}{_C.B_YELLOW}⚠{_C.RESET} {msg}")


def error(msg: str, indent: int = 2):
    _before_message()
    pad = ' ' * indent
    print(f"{pad}{_C.B_RED}✖{_C.RESET} {msg}", file=sys.stderr)


def dim(msg: str) -> str:
    return f"{_C.DIM}{msg}{_C.RESET}"


def bold(msg: str) -> str:
    return f"{_C.BOLD}{msg}{_C.RESET}"


def green(msg: str) -> str:
    return f"{_C.GREEN}{msg}{_C.RESET}"


def red(msg: str) -> str:
    return f"{_C.RED}{msg}{_C.RESET}"


def yellow(msg: str) -> str:
    return f"{_C.YELLOW}{msg}{_C.RESET}"


def cyan(msg: str) -> str:
    return f"{_C.CYAN}{msg}{_C.RESET}"


def progress(current: int, total: int, label: str = '', extra: str = '',
             indent: int = 2):
    global _progress_active, _progress_key
    # Tiny operations finish faster than a human can read intermediate
    # states; one final line is clearer and avoids visual noise.
    if total < 20 and current < total:
        return
    # Redirected output cannot update in place.  Emit only the final state
    # instead of flooding logs with one line per percentage update.
    if not _IS_TTY and current < total:
        return
    key = (label, indent, total)
    if _progress_active and _progress_key != key:
        # A new stage gets its own final line; updates within one stage keep
        # overwriting the same physical terminal row.
        print()
        _progress_active = False
    width = max(20, shutil.get_terminal_size(fallback=(80, 24)).columns)
    line = _format_progress_line(current, total, label, extra, indent, width)
    prefix = '\r\033[2K' if _IS_TTY else ''
    print(prefix + line, end='', flush=True)
    _progress_active = True
    _progress_key = key


def progress_done():
    global _progress_active, _progress_key
    if _progress_active:
        print()
    _progress_active = False
    _progress_key = None


def summary_table(rows: list[tuple[str, str]], indent: int = 2):
    """Print aligned key-value rows with dimmed separators."""
    if not rows:
        return
    _before_message()
    max_key = max(len(k) for k, _ in rows)
    pad = ' ' * indent
    for key, val in rows:
        print(f"{pad}{_C.DIM}{key:<{max_key}}{_C.RESET}  {val}")


def quality_badge(passed: bool) -> str:
    if passed:
        return f"{_C.B_GREEN}PASS{_C.RESET}"
    return f"{_C.B_RED}FAIL{_C.RESET}"
