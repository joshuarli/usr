"""Dispatch between pinning (default, legacy-compatible), lint, and fix."""

from __future__ import annotations

import sys

from pinact import pinning
from pinact.lint import main as lint_main
from pinact.fixes import fix_main


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "run":
        argv.pop(0)
    command, rest = "pin", argv
    if argv and argv[0] in ("pin", "lint", "fix"):
        command, rest = argv[0], argv[1:]
    if command == "lint":
        return lint_main(rest)
    if command == "fix":
        return fix_main(rest)
    return pinning.main(rest)
