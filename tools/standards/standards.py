#!/usr/bin/env python3
"""Select the coding standards that apply to a change or a tree."""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "dotfiles/base/.agents/standards"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FENCE = "+++"
TOP_KEYS = {"name", "summary", "trigger", "examples"}
TRIGGER_KEYS = ("paths", "shebang", "content")
EXAMPLE_KEYS = {"match", "skip"}
REQUIRED_SECTION = "## Code"
MAX_TEXT = 1 << 20
FOOTER = "Maintained by Joshua Li: https://github.com/joshuarli/usr"


class Failure(Exception):
    pass


@dataclass(frozen=True)
class PathPattern:
    source: str
    negated: bool
    anchored: bool
    dir_only: bool
    regex: re.Pattern[str]


@dataclass(frozen=True)
class Trigger:
    paths: tuple[PathPattern, ...]
    shebang: tuple[re.Pattern[str], ...]
    content: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Changed:
    path: str
    first_line: str
    added: tuple[str, ...]


@dataclass(frozen=True)
class Example:
    change: Changed
    expect: bool


@dataclass(frozen=True)
class Standard:
    name: str
    summary: str
    path: Path
    triggers: tuple[Trigger, ...]
    examples: tuple[Example, ...]


@dataclass(frozen=True)
class Condition:
    kind: str
    matched: bool
    pattern: str | None


@dataclass(frozen=True)
class Reason:
    file: str
    trigger: int
    conditions: tuple[Condition, ...]


@dataclass(frozen=True)
class Selected:
    standard: Standard
    reasons: tuple[Reason, ...]


def glob_regex(pattern: str) -> str:
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == n:
            out.append("/.*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        elif pattern[i] == "[":
            end = pattern.find("]", i + 2)
            if end < 0:
                out.append(re.escape("["))
                i += 1
                continue
            body = pattern[i + 1:end]
            if body.startswith("!"):
                body = "^" + body[1:]
            out.append("[" + body.replace("\\", "\\\\") + "]")
            i = end + 1
        elif pattern[i] == "\\" and i + 1 < n:
            out.append(re.escape(pattern[i + 1]))
            i += 2
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "".join(out)


def compile_path(source: str) -> PathPattern:
    body = source
    negated = body.startswith("!")
    if negated:
        body = body[1:]
    dir_only = body.endswith("/")
    body = body.rstrip("/")
    anchored = "/" in body
    body = body.lstrip("/")
    if not body:
        raise ValueError("empty pattern")
    return PathPattern(source, negated, anchored, dir_only, re.compile(glob_regex(body)))


def pattern_hits(pattern: PathPattern, path: str) -> bool:
    parts = path.split("/")
    if pattern.anchored:
        candidates = ["/".join(parts[:k]) for k in range(1, len(parts))]
    else:
        candidates = parts[:-1]
    if not pattern.dir_only:
        candidates.append(path if pattern.anchored else parts[-1])
    return any(pattern.regex.fullmatch(candidate) for candidate in candidates)


def paths_match(patterns: Sequence[PathPattern], path: str) -> tuple[bool, str | None]:
    matched, decider = False, None
    for pattern in patterns:
        if pattern_hits(pattern, path):
            matched, decider = not pattern.negated, pattern.source
    return matched, decider


def evaluate(trigger: Trigger, change: Changed) -> tuple[Condition, ...]:
    conditions = []
    if trigger.paths:
        matched, decider = paths_match(trigger.paths, change.path)
        conditions.append(Condition("paths", matched, decider))
    if trigger.shebang:
        hit = next((r.pattern for r in trigger.shebang if change.first_line.startswith("#!") and r.search(change.first_line)), None)
        conditions.append(Condition("shebang", hit is not None, hit))
    if trigger.content:
        hit = next((r.pattern for r in trigger.content if any(r.search(line) for line in change.added)), None)
        conditions.append(Condition("content", hit is not None, hit))
    return tuple(conditions)


def reasons_for(standard: Standard, change: Changed) -> list[Reason]:
    reasons = []
    for index, trigger in enumerate(standard.triggers, 1):
        conditions = evaluate(trigger, change)
        if all(c.matched for c in conditions):
            reasons.append(Reason(change.path, index, conditions))
    return reasons


def split_frontmatter(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").split("\n")
    if not lines or lines[0] != FENCE:
        raise Failure(f"{path}: missing {FENCE} TOML frontmatter")
    try:
        end = lines.index(FENCE, 1)
    except ValueError:
        raise Failure(f"{path}: unterminated frontmatter") from None
    return "\n".join(lines[1:end]), "\n".join(lines[end + 1:])


def string_list(path: Path, where: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise Failure(f"{path}: {where} must be a non-empty list of non-empty strings")
    return [str(item) for item in value]


def regexes(path: Path, where: str, value: Any) -> tuple[re.Pattern[str], ...]:
    compiled = []
    for pattern in string_list(path, where, value):
        try:
            compiled.append(re.compile(pattern))
        except re.error as error:
            raise Failure(f"{path}: invalid {where} regex {pattern!r}: {error}") from None
    return tuple(compiled)


def load_trigger(path: Path, index: int, table: Any) -> Trigger:
    where = f"trigger {index}"
    if not isinstance(table, dict):
        raise Failure(f"{path}: {where} must be a table")
    unknown = {str(key) for key in table} - set(TRIGGER_KEYS)
    if unknown:
        raise Failure(f"{path}: {where} has unknown keys {sorted(unknown)}; allowed: {', '.join(TRIGGER_KEYS)}")
    if not table:
        raise Failure(f"{path}: {where} needs at least one of {', '.join(TRIGGER_KEYS)}")
    patterns: list[PathPattern] = []
    if "paths" in table:
        for source in string_list(path, f"{where} paths", table["paths"]):
            try:
                patterns.append(compile_path(source))
            except (ValueError, re.error) as error:
                raise Failure(f"{path}: {where} invalid path pattern {source!r}: {error}") from None
        if all(p.negated for p in patterns):
            raise Failure(f"{path}: {where} paths need at least one positive pattern")
    shebang = regexes(path, f"{where} shebang", table["shebang"]) if "shebang" in table else ()
    content = regexes(path, f"{where} content", table["content"]) if "content" in table else ()
    return Trigger(tuple(patterns), shebang, content)


def example_change(path: Path, item: Any) -> Changed:
    if isinstance(item, str) and item:
        return Changed(item, "", ())
    if (isinstance(item, dict) and set(item) <= {"path", "text"} and isinstance(item.get("path"), str) and item["path"]
            and isinstance(item.get("text", ""), str)):
        return whole(item["path"], item.get("text", ""))
    raise Failure(f"{path}: an example must be a path string or a {{path, text}} table, got {item!r}")


def load_one(path: Path) -> Standard:
    header, body = split_frontmatter(path)
    try:
        data = tomllib.loads(header)
    except tomllib.TOMLDecodeError as error:
        raise Failure(f"{path}: invalid TOML frontmatter: {error}") from None
    unknown = set(data) - TOP_KEYS
    if unknown:
        raise Failure(f"{path}: unknown frontmatter keys {sorted(unknown)}; allowed: {', '.join(sorted(TOP_KEYS))}")
    name, summary = data.get("name"), data.get("summary")
    if not isinstance(name, str) or name != path.stem or not NAME.fullmatch(name):
        raise Failure(f"{path}: name must equal the file name {path.stem!r}")
    if not isinstance(summary, str) or not summary:
        raise Failure(f"{path}: summary is required")
    tables = data.get("trigger")
    if not isinstance(tables, list) or not tables:
        raise Failure(f"{path}: needs at least one [[trigger]] table")
    triggers = tuple(load_trigger(path, index, table) for index, table in enumerate(tables, 1))
    table = data.get("examples")
    if not isinstance(table, dict) or set(table) - EXAMPLE_KEYS or not table.get("match"):
        raise Failure(f"{path}: [examples] needs a non-empty match list and an optional skip list")
    examples = []
    for key, expect in (("match", True), ("skip", False)):
        items = table.get(key, [])
        if not isinstance(items, list):
            raise Failure(f"{path}: examples.{key} must be a list")
        examples.extend(Example(example_change(path, item), expect) for item in items)
    if not any(line.strip() == REQUIRED_SECTION for line in body.split("\n")):
        raise Failure(f"{path}: body needs a {REQUIRED_SECTION!r} section")
    return Standard(name, summary, path, triggers, tuple(examples))


def load(directory: Path) -> tuple[Standard, ...]:
    files = sorted(directory.glob("*.md"))
    if not files:
        raise Failure(f"{directory}: no standards found")
    return tuple(load_one(path) for path in files)


def verify_examples(standard: Standard) -> list[str]:
    errors = []
    for example in standard.examples:
        hit = bool(reasons_for(standard, example.change))
        if hit != example.expect:
            want = "match" if example.expect else "skip"
            errors.append(f"{standard.path}: example {example.change.path!r} should {want} but {'matched' if hit else 'did not match'}")
    return errors


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


def whole(path: str, text: str | None) -> Changed:
    return Changed(path, first_line(text), tuple(text.split("\n")) if text else ())


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


def nul_list(text: str) -> list[str]:
    return [name for name in text.split("\0") if name]


def repo_root() -> Path:
    return Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())


def from_diff(root: Path, base: str) -> list[Changed]:
    options = ("--no-renames", "--diff-filter=d", "--no-ext-diff", "--no-textconv", base, "--")
    names = nul_list(git(root, "diff", "--name-only", "-z", *options))
    added = added_lines(git(root, "diff", "-U0", "--no-color", *options), names)
    changed = [Changed(name, first_line(read_text(root / name)), lines) for name, lines in zip(names, added)]
    changed.extend(whole(name, read_text(root / name)) for name in nul_list(git(root, "ls-files", "-z", "--others", "--exclude-standard")))
    return changed


def from_tree(root: Path) -> list[Changed]:
    names = nul_list(git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"))
    return [whole(name, read_text(root / name)) for name in dict.fromkeys(names) if (root / name).is_file()]


def from_files(files: Iterable[str]) -> list[Changed]:
    changed = []
    for name in files:
        path = Path(name)
        if not path.is_file():
            raise Failure(f"{name}: not a file")
        changed.append(whole(path.as_posix(), read_text(path)))
    return changed


def select(standards: Sequence[Standard], changes: Sequence[Changed]) -> list[Selected]:
    selected = []
    for standard in standards:
        reasons = tuple(r for change in changes for r in reasons_for(standard, change))
        if reasons:
            selected.append(Selected(standard, reasons))
    return selected


def describe(conditions: Sequence[Condition]) -> str:
    return ", ".join(f"{c.kind} {c.pattern}" if c.matched else f"{c.kind} no match" for c in conditions)


def render_select(selected: Sequence[Selected], as_json: bool) -> str:
    if as_json:
        return json.dumps([{
            "name": s.standard.name, "path": str(s.standard.path), "summary": s.standard.summary,
            "reasons": [{"file": r.file, "trigger": r.trigger,
                         "conditions": [{"kind": c.kind, "pattern": c.pattern} for c in r.conditions]} for r in s.reasons],
        } for s in selected], indent=2) + "\n"
    lines = []
    for s in selected:
        first = s.reasons[0]
        more = f" (+{len(s.reasons) - 1} more)" if len(s.reasons) > 1 else ""
        lines.append(f"{s.standard.name}\t{s.standard.path}\t{first.file}: trigger {first.trigger}: {describe(first.conditions)}{more}\n")
    return "".join(lines)


def render_explain(standards: Sequence[Standard], changes: Sequence[Changed]) -> str:
    lines = []
    for change in changes:
        lines.append(f"{change.path}\n")
        for standard in standards:
            for index, trigger in enumerate(standard.triggers, 1):
                conditions = evaluate(trigger, change)
                verdict = "selects" if all(c.matched for c in conditions) else "misses"
                lines.append(f"  {standard.name} trigger {index}: {verdict} ({describe(conditions)})\n")
    return "".join(lines)


def render_list(standards: Sequence[Standard], as_json: bool) -> str:
    if as_json:
        return json.dumps([{"name": s.name, "path": str(s.path), "summary": s.summary} for s in standards], indent=2) + "\n"
    return "".join(f"{s.name}\t{s.path}\t{s.summary}\n" for s in standards)


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="standards", description="Select the coding standards that apply to a change or a tree.",
        epilog="Exit status: 0 success (selecting nothing is success), 1 invalid standards from check, 2 usage or operational error, killed by SIGINT when interrupted (130 in a shell).\n"
               f"Ctrl-C stops at once; standards writes nothing, so re-running is always safe.\n\n{FOOTER}",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    top.add_argument("--dir", type=Path, default=DEFAULT_DIR, help=f"standards directory (default: {DEFAULT_DIR})")
    commands = top.add_subparsers(dest="command", required=True, metavar="COMMAND")
    pick = commands.add_parser("select", help="print the standards a change, tree, or file list triggers")
    source = pick.add_mutually_exclusive_group()
    source.add_argument("--base", help="diff the working tree against REV instead of HEAD; untracked files always count")
    source.add_argument("--tree", action="store_true", help="match every tracked and untracked non-ignored file in full")
    pick.add_argument("--json", action="store_true", help="print a JSON array")
    pick.add_argument("files", nargs="*", help="match these whole files instead of the Git diff")
    why = commands.add_parser("explain", help="show how every trigger evaluates for each file")
    why.add_argument("files", nargs="+", help="files to evaluate in full")
    listing = commands.add_parser("list", help="print every standard")
    listing.add_argument("--json", action="store_true", help="print a JSON array")
    commands.add_parser("check", help="validate every standard and its examples")
    return top


def main(argv: Sequence[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if args.command == "select" and args.files and (args.base or args.tree):
        cli.error("files cannot be combined with --base or --tree")
    try:
        if args.command == "check":
            try:
                standards = load(args.dir)
            except Failure as error:
                print(f"standards: {error}", file=sys.stderr)
                return 1
            errors = [error for standard in standards for error in verify_examples(standard)]
            for error in errors:
                print(f"standards: {error}", file=sys.stderr)
            if errors:
                return 1
            print(f"{len(standards)} standards ok")
            return 0
        standards = load(args.dir)
        if args.command == "list":
            sys.stdout.write(render_list(standards, args.json))
        elif args.command == "explain":
            sys.stdout.write(render_explain(standards, from_files(args.files)))
        else:
            if args.files:
                changes = from_files(args.files)
            elif args.tree:
                changes = from_tree(repo_root())
            else:
                changes = from_diff(repo_root(), args.base or "HEAD")
            sys.stdout.write(render_select(select(standards, changes), args.json))
        return 0
    except Failure as error:
        print(f"standards: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("standards: interrupted", file=sys.stderr)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGINT)
        return 130


if __name__ == "__main__":
    sys.exit(main())
