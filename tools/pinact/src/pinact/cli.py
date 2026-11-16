"""Dispatch between pinning (default, legacy-compatible), lint, and fix."""

from __future__ import annotations

import sys

from pinact import pinning
from pinact.lint import main as lint_main, build_parser as lint_parser
from pinact.fixes import fix_main, build_parser as fix_parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in (["-h"], ["--help"]):
        parsers = (("pin", pinning.build_parser()), ("lint", lint_parser()), ("fix", fix_parser()), ("run", pinning.build_parser()))
        footer = pinning.build_parser(primary=True).epilog.strip()
        print("usage: pinact [run] [pin|lint|fix] [options] [files ...]\n\nPin and audit GitHub Actions workflows.\n")
        print("Common options:\n  -h, --help: show help\n")
        for name, parser in parsers:
            parser.prog = "pinact " + name
            print(parser.format_usage().replace(" [-h]", "").rstrip())
            print("  " + parser.description)
            for action in parser._actions:
                if action.dest != "help":
                    print(f"  {', '.join(action.option_strings) or action.dest}: {action.help or action.dest}")
            print()
        print("Examples:\n  pinact pin --check\n  pinact lint --format json\n  pinact fix --diff\n  pinact run --check\n")
        print(footer)
        return 0
    was_run = bool(argv and argv[0] == "run")
    if was_run:
        argv.pop(0)
    command, rest = "pin", argv
    if argv and argv[0] in ("pin", "lint", "fix"):
        command, rest = argv[0], argv[1:]
    if command == "lint":
        return lint_main(rest)
    if command == "fix":
        return fix_main(rest)
    return pinning.main(rest, primary=(not was_run and (not argv or argv[0] not in ("pin", "lint", "fix"))))
