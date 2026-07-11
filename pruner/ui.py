"""Terminal UI formatting — ANSI colors, progress bars, structured output.

Inspired by modern CLI tools (Cursor, Claude, cargo). Provides a
consistent visual language for the pipeline's terminal output.

All print helpers are centralized here so that the rest of the codebase
never writes raw ``print()`` calls for user-facing output.
"""

import os
import sys
import time

_NO_COLOR = os.environ.get('NO_COLOR') is not None or not sys.stdout.isatty()


class _C:
    """ANSI escape codes — disabled when NO_COLOR is set or stdout is not a tty."""
    RESET   = '' if _NO_COLOR else '\033[0m'
    BOLD    = '' if _NO_COLOR else '\033[1m'
    DIM     = '' if _NO_COLOR else '\033[2m'
    CYAN    = '' if _NO_COLOR else '\033[36m'
    GREEN   = '' if _NO_COLOR else '\033[32m'
    YELLOW  = '' if _NO_COLOR else '\033[33m'
    RED     = '' if _NO_COLOR else '\033[31m'
    MAGENTA = '' if _NO_COLOR else '\033[35m'
    BLUE    = '' if _NO_COLOR else '\033[34m'
    WHITE   = '' if _NO_COLOR else '\033[37m'
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
    bar = '━' * width
    print(f"\n{_C.B_CYAN}{bar}{_C.RESET}")
    print(f"  {_C.BOLD}{title}{_C.RESET}")
    print(f"{_C.B_CYAN}{bar}{_C.RESET}")


def section(title: str):
    print(f"\n{_C.CYAN}{'─' * 50}{_C.RESET}")
    print(f"  {_C.BOLD}{title}{_C.RESET}")
    print(f"{_C.CYAN}{'─' * 50}{_C.RESET}")


def phase_header(phase: int, label: str, round_num: int):
    print(f"\n{_C.DIM}───{_C.RESET} Phase {phase} · round {round_num}: "
          f"{_C.CYAN}{label}{_C.RESET} {_C.DIM}───{_C.RESET}")


def kv(key: str, value, indent: int = 2):
    pad = ' ' * indent
    print(f"{pad}{_C.DIM}{key}:{_C.RESET}  {value}")


def info(msg: str, indent: int = 2):
    pad = ' ' * indent
    print(f"{pad}{msg}")


def success(msg: str, indent: int = 2):
    pad = ' ' * indent
    print(f"{pad}{_C.B_GREEN}✔{_C.RESET} {msg}")


def warn(msg: str, indent: int = 2):
    pad = ' ' * indent
    print(f"{pad}{_C.B_YELLOW}⚠{_C.RESET} {msg}")


def error(msg: str, indent: int = 2):
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
    pad = ' ' * indent
    pct = current * 100 // total if total else 0
    bar_width = 20
    filled = bar_width * current // total if total else 0
    bar = '█' * filled + '░' * (bar_width - filled)
    parts = [f"\r{pad}{_C.DIM}{bar}{_C.RESET} {pct:3d}%  {current}/{total}"]
    if label:
        parts.append(f"  {_C.DIM}{label}{_C.RESET}")
    if extra:
        parts.append(f"  {extra}")
    print(''.join(parts), end='', flush=True)


def progress_done():
    print()


def summary_table(rows: list[tuple[str, str]], indent: int = 2):
    """Print aligned key-value rows with dimmed separators."""
    if not rows:
        return
    max_key = max(len(k) for k, _ in rows)
    pad = ' ' * indent
    for key, val in rows:
        print(f"{pad}{_C.DIM}{key:<{max_key}}{_C.RESET}  {val}")


def quality_badge(passed: bool) -> str:
    if passed:
        return f"{_C.B_GREEN}PASS{_C.RESET}"
    return f"{_C.B_RED}FAIL{_C.RESET}"
