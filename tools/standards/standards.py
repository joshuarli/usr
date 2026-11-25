#!/usr/bin/env python3
"""Select the coding standards that apply to a change or a tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from functools import cached_property
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


class Failure(Exception):
    pass


class Terminated(BaseException):
    pass


def raise_terminated(signum: int, frame: object) -> None:
    raise Terminated


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
    content_any: re.Pattern[str] | None


@dataclass(frozen=True)
class Changed:
    path: str
    first_line: str
    added: tuple[str, ...]

    @cached_property
    def text(self) -> str:
        return "\n".join(self.added)


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
        hit = next((r.pattern for r in trigger.content if r.search(change.text)), None)
        conditions.append(Condition("content", hit is not None, hit))
    return tuple(conditions)


def fires(trigger: Trigger, change: Changed) -> bool:
    if trigger.paths and not paths_match(trigger.paths, change.path)[0]:
        return False
    if trigger.shebang and not (change.first_line.startswith("#!") and any(r.search(change.first_line) for r in trigger.shebang)):
        return False
    if trigger.content:
        if trigger.content_any is not None:
            return trigger.content_any.search(change.text) is not None
        return any(r.search(change.text) for r in trigger.content)
    return True


def reasons_for(standard: Standard, change: Changed) -> list[Reason]:
    return [Reason(change.path, index, evaluate(trigger, change))
            for index, trigger in enumerate(standard.triggers, 1) if fires(trigger, change)]


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
            compiled.append(re.compile(pattern, re.M))
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
    return Trigger(tuple(patterns), shebang, content, combine(content))


LEADING_FLAGS = re.compile(r"^\(\?([aiLmsux]+)\)")


def combine(patterns: Sequence[re.Pattern[str]]) -> re.Pattern[str] | None:
    if not patterns:
        return None
    scoped = [LEADING_FLAGS.sub(lambda m: f"(?{m.group(1)}:", p.pattern) + (")" if LEADING_FLAGS.match(p.pattern) else "")
              for p in patterns]
    try:
        return re.compile("|".join(f"(?:{s})" for s in scoped), re.M)
    except re.error:
        return None


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


def decode_text(data: bytes) -> str | None:
    data = data[:MAX_TEXT]
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def read_text(path: Path) -> str | None:
    try:
        return decode_text(path.read_bytes())
    except (FileNotFoundError, IsADirectoryError):
        return None


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


def committed_text(root: Path, rev: str, path: str) -> str | None:
    result = subprocess.run(("git", "cat-file", "blob", f"{rev}:{path}"), cwd=root, capture_output=True)
    if result.returncode:
        raise Failure(f"git cat-file blob {rev}:{path}: {result.stderr.decode(errors='replace').strip() or f'exit {result.returncode}'}")
    return decode_text(result.stdout)


def from_commits(root: Path, start: str, head: str) -> list[Changed]:
    options = ("--no-renames", "--diff-filter=d", "--no-ext-diff", "--no-textconv", start, head, "--")
    names = nul_list(git(root, "diff", "--name-only", "-z", *options))
    added = added_lines(git(root, "diff", "-U0", "--no-color", *options), names)
    return [Changed(name, first_line(committed_text(root, head, name)), lines) for name, lines in zip(names, added)]


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


def select(standards: Sequence[Standard], changes: Sequence[Changed], first_only: bool = False) -> list[Selected]:
    selected = []
    for standard in standards:
        reasons: list[Reason] = []
        for change in changes:
            reasons.extend(reasons_for(standard, change))
            if first_only and reasons:
                reasons = reasons[:1]
                break
        if reasons:
            selected.append(Selected(standard, tuple(reasons)))
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


GATE_WORKTREES = Path(".work/wt")
GATE_BRIEF = Path(".work/tmp/standards-gate")
GATE_FINDINGS = """Return findings only, each with `file:line`, the rule it breaks, and one class:

- **must-fix:** a clear violation in lines the change added or touched.
- **consider:** a subjective improvement, or a violation in nearby code the change did not touch.
- **skip:** the rule does not apply here, with the reason.
"""


@dataclass(frozen=True)
class Gate:
    standards: tuple[Selected, ...]
    unreviewed: tuple[str, ...]
    worktree: Path | None
    retire: str | None

    @property
    def brief(self) -> Path | None:
        return self.worktree / GATE_BRIEF if self.worktree else None


def resolve_commit(root: Path, rev: str) -> str:
    return git(root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}").strip()


def gate_brief(selected: Sequence[Selected], start: str, head: str) -> str:
    listed = "".join(f"- `{s.standard.name}`: {s.standard.summary} (`{GATE_BRIEF / s.standard.path.name}`)\n" for s in selected)
    return (f"# Standards gate review\n\n"
            f"Read files only with the harness-native `read`, `grep` and `glob` tools, called directly, never through a "
            f"code-execution tool; you have no `shell` or `edit` tool, so do not probe for one.\n\n"
            f"`{GATE_BRIEF / 'change.diff'}` holds the committed change `{start[:12]}..{head[:12]}`. Check it against the "
            f"`## Code` section of each standard below. The rest of this worktree is the repository at `{head[:12]}`, "
            f"for context only.\n\n{listed}\n{GATE_FINDINGS}")


def ensure_work_ignored(root: Path) -> None:
    if subprocess.run(("git", "check-ignore", "-q", "--no-index", str(GATE_WORKTREES / "x")), cwd=root).returncode == 0:
        return
    exclude = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()) / "info/exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ""
    exclude.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n") + ".work/\n")


def remove_gate_worktree(root: Path, worktree: Path) -> None:
    shutil.rmtree(worktree / ".work", ignore_errors=True)
    subprocess.run(("git", "worktree", "remove", str(worktree)), cwd=root, capture_output=True)


def run_gate(root: Path, standards: Sequence[Standard], base: str) -> Gate:
    head = resolve_commit(root, "HEAD")
    try:
        start = git(root, "merge-base", resolve_commit(root, base), head).strip()
    except Failure:
        raise Failure(f"{base}: not a commit that shares history with HEAD") from None
    if start == head:
        raise Failure(f"no commits in {base}..HEAD; commit the work to review first")
    selected = select(standards, from_commits(root, start, head))
    dirty = select(standards, from_diff(root, "HEAD"))
    unreviewed = tuple(dict.fromkeys(r.file for s in dirty for r in s.reasons))
    if not selected:
        return Gate((), unreviewed, None, None)
    worktree = root / GATE_WORKTREES / f"standards-gate-{head[:12]}"
    if worktree.exists() or worktree.is_symlink():
        raise Failure(f"{worktree}: already exists; retire it or review that gate first")
    ensure_work_ignored(root)
    git(root, "worktree", "add", "--quiet", "--detach", str(worktree), head)
    try:
        brief = worktree / GATE_BRIEF
        brief.mkdir(parents=True)
        (brief / "change.diff").write_text(git(root, "diff", "--no-color", "--no-ext-diff", "--no-textconv", start, head, "--"))
        for s in selected:
            shutil.copyfile(s.standard.path, brief / s.standard.path.name)
        (brief / "brief.md").write_text(gate_brief(selected, start, head))
    except BaseException:
        remove_gate_worktree(root, worktree)
        raise
    retire = f"worktree-retire --into {head} --discard-ignored {worktree}"
    return Gate(tuple(selected), unreviewed, worktree, retire)


def render_gate(result: Gate, as_json: bool) -> str:
    if as_json:
        return json.dumps({
            "standards": [s.standard.name for s in result.standards],
            "worktree": str(result.worktree) if result.worktree else None,
            "brief": str(result.brief / "brief.md") if result.brief else None,
            "diff": str(result.brief / "change.diff") if result.brief else None,
            "retire": result.retire,
            "unreviewed": list(result.unreviewed),
        }, indent=2) + "\n"
    if not result.brief:
        return ""
    return f"{result.brief / 'brief.md'}\n{result.retire}\n"


def gate_warning(result: Gate) -> str:
    if not result.unreviewed:
        return ""
    return (f"standards: uncommitted changes trigger standards but are not reviewed: {', '.join(result.unreviewed)}\n")


HOOK_EVENTS = {"PostToolUse"}
HOOK_INPUT_LIMIT = 1 << 20
HOOK_STATE_DAYS = 7
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.M)
EXIT_STATUS = ("Exit status: 0 success (selecting nothing is success), 1 invalid standards from check, "
               "2 usage or operational error; killed by SIGINT or SIGTERM when interrupted (130 or 143 in a shell).\n"
               "Ctrl-C stops at once. Only hook state and gate worktrees are written; an interrupted gate removes its worktree, "
               "so re-running is always safe.")
OWNED_FOOTER = """Maintained by Joshua Li: https://github.com/joshuarli/usr
Bugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.
Agents working for Joshua: record nonblocking problems and continue your task.
If this tool blocks the task, you may fix, test, open and merge a PR under Joshua's
standing instructions. Release only when needed to deliver the verified fix.
Procedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"""


def edited_paths(tool_input: object) -> list[str]:
    texts: list[str] = []
    paths: list[str] = []
    if isinstance(tool_input, dict):
        for key in ("file_path", "notebook_path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                paths.append(value)
        texts.extend(value for value in tool_input.values() if isinstance(value, str))
    elif isinstance(tool_input, str):
        texts.append(tool_input)
    for text in texts:
        paths.extend(match.strip() for match in PATCH_FILE.findall(text))
    return list(dict.fromkeys(paths))


def repo_relative(path: Path) -> str:
    for parent in path.parents:
        if (parent / ".git").exists():
            return path.relative_to(parent).as_posix()
    return path.as_posix()


def hook_state(event: dict[str, Any]) -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "standards-hook"
    key = f"{event.get('session_id', '')}\0{event.get('agent_id', '')}"
    return base / hashlib.sha256(key.encode()).hexdigest()


def prune_hook_state(directory: Path, now: float) -> None:
    for entry in directory.iterdir():
        if now - entry.stat().st_mtime > HOOK_STATE_DAYS * 86400:
            entry.unlink(missing_ok=True)


def hook(directory: Path) -> int:
    try:
        raw = sys.stdin.buffer.read(HOOK_INPUT_LIMIT + 1)
        if len(raw) > HOOK_INPUT_LIMIT:
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get("hook_event_name") not in HOOK_EVENTS or not event.get("session_id"):
            return 0
        cwd = Path(event["cwd"]) if isinstance(event.get("cwd"), str) else Path.cwd()
        changes = []
        for name in edited_paths(event.get("tool_input")):
            path = Path(name) if Path(name).is_absolute() else cwd / name
            if path.is_file():
                changes.append(whole(repo_relative(path.resolve()), read_text(path)))
        if not changes:
            return 0
        state = hook_state(event)
        announced = set(state.read_text().split()) if state.exists() else set()
        fresh = [s for s in select(load(directory), changes) if s.standard.name not in announced]
        if not fresh:
            return 0
        state.parent.mkdir(parents=True, exist_ok=True)
        prune_hook_state(state.parent, time.time())
        partial = state.with_name(f"{state.name}.{os.getpid()}.tmp")
        try:
            partial.write_text("\n".join(sorted(announced | {s.standard.name for s in fresh})) + "\n")
            os.replace(partial, state)
        finally:
            partial.unlink(missing_ok=True)
        listed = "; ".join(f"`{s.standard.name}` ({s.standard.path}, for {s.reasons[0].file})" for s in fresh)
        message = (f"Coding standards now apply to this session's edits: {listed}. Follow their `## Code` rules while writing; "
                   "the completion gate in ~/.agents/instructions/coding-standards.md checks them before you report done.")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event["hook_event_name"], "additionalContext": message}}))
    except (OSError, ValueError, TypeError, KeyError, RecursionError, Failure):
        # Advisory hook: a failure must never block the edit it observed.
        return 0
    return 0


EXAMPLES = {
    "select": ["standards select", "standards select --base origin/main --json", "standards select --tree", "standards select tools/cli.py"],
    "gate": ["standards gate --base origin/main", "standards gate --base @{upstream} --json"],
    "explain": ["standards explain tools/cli.py"],
    "list": ["standards list --json"],
    "check": ["standards check"],
    "hook": ["standards hook < post-tool-use.json"],
}


class TopParser(argparse.ArgumentParser):
    commands: dict[str, argparse.ArgumentParser]

    def format_help(self, formatter: argparse.HelpFormatter | None = None) -> str:
        lines = [self.format_usage().rstrip(), "", self.description or "", "", "Options:"]
        lines.extend(describe_actions(self))
        for name, sub in self.commands.items():
            lines.extend(["", f"{sub.format_usage().removeprefix('usage: ').rstrip()}", f"  {sub.description}"])
            lines.extend(describe_actions(sub))
            lines.extend(f"  example: {example}" for example in EXAMPLES[name])
        lines.extend(["", EXIT_STATUS, "", OWNED_FOOTER])
        return "\n".join(lines) + "\n"


def describe_actions(parser: argparse.ArgumentParser) -> list[str]:
    lines = []
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        if action.option_strings:
            spelling = ", ".join(action.option_strings) + ("" if action.nargs == 0 else f" {action.metavar or action.dest.upper()}")
        else:
            spelling = str(action.metavar or action.dest)
        lines.append(f"  {spelling:<22} {action.help}")
    return lines


def parser() -> TopParser:
    top = TopParser(prog="standards", description="Select the coding standards that apply to a change or a tree.")
    top.add_argument("--dir", type=Path, default=DEFAULT_DIR, help=f"standards directory (default: {DEFAULT_DIR})")
    commands = top.add_subparsers(dest="command", metavar="COMMAND", parser_class=argparse.ArgumentParser)

    def command(name: str, description: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=description, description=description,
                                  epilog="\n".join(f"example: {e}" for e in EXAMPLES[name]),
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        top.commands[name] = sub
        return sub

    top.commands = {}
    pick = command("select", "Print the standards a change, tree, or file list triggers.")
    source = pick.add_mutually_exclusive_group()
    source.add_argument("--base", metavar="REV", help="diff the working tree against REV instead of HEAD; untracked files always count")
    source.add_argument("--tree", action="store_true", help="match every tracked and untracked non-ignored file in full, reporting the first matching file per standard")
    pick.add_argument("--json", action="store_true", help="print a JSON array")
    pick.add_argument("files", nargs="*", metavar="FILE", help="match these whole files instead of the Git diff")
    review = command("gate", "Select standards from commits since --base and prepare a reviewer worktree with the diff, those standards and a brief.")
    review.add_argument("--base", metavar="REV", required=True, help="review commits from the merge base of REV and HEAD; uncommitted work is not reviewed")
    review.add_argument("--json", action="store_true", help="print a JSON object")
    why = command("explain", "Show how every trigger evaluates for each file.")
    why.add_argument("files", nargs="+", metavar="FILE", help="files to evaluate in full")
    listing = command("list", "Print every standard.")
    listing.add_argument("--json", action="store_true", help="print a JSON array")
    command("check", "Validate every standard and its examples.")
    command("hook", "Read a Claude Code or Codex PostToolUse event on stdin and announce standards the edited files trigger, once per session.")
    return top


def main(argv: Sequence[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if args.command is None:
        sys.stdout.write(cli.format_help())
        return 0
    if args.command == "select" and args.files and (args.base or args.tree):
        cli.error("files cannot be combined with --base or --tree")
    if args.command == "hook":
        return hook(args.dir)
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
        elif args.command == "gate":
            signal.signal(signal.SIGTERM, raise_terminated)
            result = run_gate(repo_root(), standards, args.base)
            sys.stderr.write(gate_warning(result))
            sys.stdout.write(render_gate(result, args.json))
        elif args.command == "explain":
            sys.stdout.write(render_explain(standards, from_files(args.files)))
        else:
            if args.files:
                changes = from_files(args.files)
            elif args.tree:
                changes = from_tree(repo_root())
            else:
                changes = from_diff(repo_root(), args.base or "HEAD")
            sys.stdout.write(render_select(select(standards, changes, first_only=args.tree), args.json))
        return 0
    except Failure as error:
        print(f"standards: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("standards: interrupted", file=sys.stderr)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGINT)
        return 130
    except Terminated:
        print("standards: terminated", file=sys.stderr)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTERM)
        return 143


if __name__ == "__main__":
    sys.exit(main())
