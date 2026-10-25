"""Dispatch between pinning (default, legacy-compatible) and lint."""

from __future__ import annotations

import sys

from pinact import pinning
from pinact.lint import main as lint_main


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "run":
        argv.pop(0)
    command, rest = "pin", argv
    if argv and argv[0] in ("pin", "lint"):
        command, rest = argv[0], argv[1:]
    elif argv and argv[0] == "fix":
        print("pinact: the fix command arrives with a later campaign item", file=sys.stderr)
        return 2
    if command == "lint":
        return lint_main(rest)
    return pinning.main(rest)
