"""narrate — tiny terminal narration so a scenario reads like a walkthrough.

Colour is used sparingly and disables itself when stdout is not a TTY (so piped
output and CI logs stay clean). This is presentation only — never assertion logic.
"""
from __future__ import annotations

import os
import sys

_TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _TTY else s


def banner(title: str, subtitle: str = "") -> None:
    line = "═" * max(len(title) + 2, 60)
    print(_c("36", line))
    print(_c("1;37", "  " + title))
    if subtitle:
        print(_c("36", "  " + subtitle))
    print(_c("36", line))


_step = 0
def step(msg: str) -> None:
    global _step
    _step += 1
    print(_c("1;36", f"\n[{_step}] ") + _c("1;37", msg))


def say(msg: str) -> None:
    print("    " + msg)


def ok(msg: str) -> None:
    print("    " + _c("32", "✓ ") + msg)


def deny(msg: str) -> None:
    print("    " + _c("31", "✗ ") + msg)


def honest(msg: str) -> None:
    """A caveat, stated plainly — what this shows vs what it stands in for."""
    print("    " + _c("33", "note: ") + _c("33", msg))


def result(passed: bool, msg: str) -> None:
    tag = _c("1;32", " PASS ") if passed else _c("1;31", " FAIL ")
    print("\n" + tag + " " + msg)
    if not passed:
        sys.exit(1)
