#!/usr/bin/env python3
"""Select the coding standards that apply to a change."""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Sequence

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "dotfiles/base/.agents/standards"
SCALARS = ("name", "summary")
LISTS = ("paths", "shebang", "content")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_TEXT = 1 << 20
FOOTER = "Maintained by Joshua Li: https://github.com/joshuarli/usr"

Trigger = Literal["path", "shebang", "content"]


class Failure(Exception):
    pass


@dataclass(frozen=True)
class Standard:
    name: str
    summary: str
    path: Path
    paths: tuple[str, ...]
    shebang: tuple[re.Pattern[str], ...]
    content: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Changed:
    path: str
    first_line: str
    added: tuple[str, ...]


@dataclass(frozen=True)
class Reason:
    file: str
    trigger: Trigger
    pattern: str


@dataclass(frozen=True)
class Selected:
    standard: Standard
    reasons: tuple[Reason, ...]


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def frontmatter(path: Path) -> dict[str, str | list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise Failure(f"{path}: missing frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise Failure(f"{path}: unterminated frontmatter") from None
    fields: dict[str, str | list[str]] = {}
    current: list[str] | None = None
    for number, line in enumerate(lines[1:end], 2):
        if line.startswith("  - ") and current is not None:
            current.append(unquote(line[4:].strip()))
            continue
        key, sep, value = line.partition(":")
        if not sep or key not in (*SCALARS, *LISTS) or key in fields:
            raise Failure(f"{path}:{number}: expected one of {', '.join((*SCALARS, *LISTS))} once, got {line!r}")
        if key in LISTS:
            if value.strip():
                raise Failure(f"{path}:{number}: {key} must be a list of '  - ' items")
            current = []
            fields[key] = current
        else:
            current = None
            fields[key] = unquote(value.strip())
    return fields


def compile_all(path: Path, key: str, patterns: Sequence[str]) -> tuple[re.Pattern[str], ...]:
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as error:
            raise Failure(f"{path}: invalid {key} regex {pattern!r}: {error}") from None
    return tuple(compiled)


def load_one(path: Path) -> Standard:
    fields = frontmatter(path)
    name, summary = fields.get("name"), fields.get("summary")
    if not isinstance(name, str) or name != path.stem or not NAME.fullmatch(name):
        raise Failure(f"{path}: name must equal the file name {path.stem!r}")
    if not isinstance(summary, str) or not summary:
        raise Failure(f"{path}: summary is required")
    lists = {key: fields.get(key, []) for key in LISTS}
    for key, items in lists.items():
        assert isinstance(items, list)
        if (key in fields and not items) or any(not item for item in items):
            raise Failure(f"{path}: {key} items must be non-empty")
    if not any(lists.values()):
        raise Failure(f"{path}: needs at least one of {', '.join(LISTS)}")
    return Standard(name, summary, path, tuple(lists["paths"]),
                    compile_all(path, "shebang", lists["shebang"]), compile_all(path, "content", lists["content"]))


def load(directory: Path) -> tuple[Standard, ...]:
    files = sorted(directory.glob("*.md"))
    if not files:
        raise Failure(f"{directory}: no standards found")
    return tuple(load_one(path) for path in files)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(("git", *args), cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise Failure(f"git {' '.join(args)}: {result.stderr.strip() or f'exit {result.returncode}'}")
    return result.stdout


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()[:MAX_TEXT]
    except (FileNotFoundError, IsADirectoryError):
        return None
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def first_line(text: str | None) -> str:
    return text.split("\n", 1)[0] if text else ""


def added_lines(diff: str, names: Sequence[str]) -> list[tuple[str, ...]]:
    sections: list[list[str]] = []
    in_hunk = False
    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            sections.append([])
            in_hunk = False
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line.startswith("+"):
            sections[-1].append(line[1:])
    if len(sections) != len(names):
        raise Failure(f"git diff listed {len(names)} files but printed {len(sections)} patches")
    return [tuple(section) for section in sections]


def from_diff(root: Path, base: str) -> list[Changed]:
    options = ("--no-renames", "--diff-filter=d", "--no-ext-diff", "--no-textconv", base, "--")
    names = [n for n in git(root, "diff", "--name-only", "-z", *options).split("\0") if n]
    added = added_lines(git(root, "diff", "-U0", "--no-color", *options), names)
    changed = [Changed(name, first_line(read_text(root / name)), lines) for name, lines in zip(names, added)]
    for name in (n for n in git(root, "ls-files", "-z", "--others", "--exclude-standard").split("\0") if n):
        text = read_text(root / name)
        changed.append(Changed(name, first_line(text), tuple(text.split("\n")) if text else ()))
    return changed


def from_files(files: Iterable[str]) -> list[Changed]:
    changed = []
    for name in files:
        path = Path(name)
        if not path.is_file():
            raise Failure(f"{name}: not a file")
        text = read_text(path)
        changed.append(Changed(path.as_posix(), first_line(text), tuple(text.split("\n")) if text else ()))
    return changed


def path_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, f"*/{pattern}")


def reason_for(standard: Standard, change: Changed) -> Reason | None:
    for pattern in standard.paths:
        if path_matches(change.path, pattern):
            return Reason(change.path, "path", pattern)
    for regex in standard.shebang:
        if change.first_line.startswith("#!") and regex.search(change.first_line):
            return Reason(change.path, "shebang", regex.pattern)
    for regex in standard.content:
        if any(regex.search(line) for line in change.added):
            return Reason(change.path, "content", regex.pattern)
    return None


def select(standards: Sequence[Standard], changes: Sequence[Changed]) -> list[Selected]:
    selected = []
    for standard in standards:
        reasons = tuple(r for r in (reason_for(standard, change) for change in changes) if r)
        if reasons:
            selected.append(Selected(standard, reasons))
    return selected


def render_select(selected: Sequence[Selected], as_json: bool) -> str:
    if as_json:
        return json.dumps([{
            "name": s.standard.name, "path": str(s.standard.path), "summary": s.standard.summary,
            "reasons": [{"file": r.file, "trigger": r.trigger, "pattern": r.pattern} for r in s.reasons],
        } for s in selected], indent=2) + "\n"
    lines = []
    for s in selected:
        first = s.reasons[0]
        more = f" (+{len(s.reasons) - 1} more)" if len(s.reasons) > 1 else ""
        lines.append(f"{s.standard.name}\t{s.standard.path}\t{first.file}: {first.trigger} {first.pattern}{more}\n")
    return "".join(lines)


def render_list(standards: Sequence[Standard], as_json: bool) -> str:
    if as_json:
        return json.dumps([{"name": s.name, "path": str(s.path), "summary": s.summary} for s in standards], indent=2) + "\n"
    return "".join(f"{s.name}\t{s.path}\t{s.summary}\n" for s in standards)


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="standards", description="Select the coding standards that apply to a change.",
        epilog=f"Exit status: 0 success (selecting nothing is success), 1 invalid standards from check, 2 usage or operational error, 130 interrupted.\n\n{FOOTER}",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    top.add_argument("--dir", type=Path, default=DEFAULT_DIR, help=f"standards directory (default: {DEFAULT_DIR})")
    commands = top.add_subparsers(dest="command", required=True, metavar="COMMAND")
    pick = commands.add_parser("select", help="print the standards a change triggers")
    pick.add_argument("--base", default="HEAD", help="diff the working tree against REV (default: HEAD); untracked files always count")
    pick.add_argument("--json", action="store_true", help="print a JSON array")
    pick.add_argument("files", nargs="*", help="match these whole files instead of the Git diff")
    listing = commands.add_parser("list", help="print every standard")
    listing.add_argument("--json", action="store_true", help="print a JSON array")
    commands.add_parser("check", help="validate every standard's frontmatter")
    return top


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "check":
            try:
                standards = load(args.dir)
            except Failure as error:
                print(f"standards: {error}", file=sys.stderr)
                return 1
            print(f"{len(standards)} standards ok")
            return 0
        standards = load(args.dir)
        if args.command == "list":
            sys.stdout.write(render_list(standards, args.json))
            return 0
        if args.files:
            changes = from_files(args.files)
        else:
            root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
            changes = from_diff(root, args.base)
        sys.stdout.write(render_select(select(standards, changes), args.json))
        return 0
    except Failure as error:
        print(f"standards: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("standards: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
