"""SHA pinning for GitHub Actions ``uses:`` references.

Discovery walks the YAML node tree from ``yaml.compose_all`` with
``Loader=yaml.BaseLoader``, so positions come from compose marks while every
byte outside the rewritten ``uses:`` line survives untouched. Block-scalar
bodies, comments, flow-style text inside plain scalars, and merge-key targets
are never separate nodes, so they are never treated as invocations. The
composer shares anchored nodes across aliases, so the walk visits each
composite node once: recursion stays bounded and merge constructs are
preserved rather than expanded. Files the composer cannot parse are rejected.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pinact._vendor import yaml
from pinact._vendor.yaml.composer import ComposerError
from pinact._vendor.yaml.nodes import MappingNode, ScalarNode, SequenceNode

SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+\Z")
USES = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>(?:-[ \t]+)?(?:uses|'uses'|\"uses\")"
    r"[ \t]*:[ \t]*)(?P<value>.*)$"
)
SCALAR = re.compile(r"^[ \t]*(?:-[ \t]+)?[^:#]+:[ \t]*[>|][+-]?[1-9]?[+-]?[ \t]*(?:#.*)?$")
INLINE = re.compile(r"[{,][ \t]*(?:uses|'uses'|\"uses\")[ \t]*:")
VALUE = re.compile(
    r"^(?P<quote>['\"]?)(?P<action>[^ \t#'\"]+)(?P=quote)"
    r"(?P<gap>[ \t]*)(?P<comment>#.*)?$"
)
VERSION = re.compile(r"(?:\#\s*)(?P<ref>v?\d[0-9A-Za-z._+/-]*)(?:\s|$)")
PIN_MARKER = re.compile(r"\[pin:(?P<ref>[^\]\s]+)\]$")
SCOPE = re.compile(r"^[ \t]*(?:-[ \t]+)?(?P<name>[a-zA-Z_][a-zA-Z0-9_-]*)[ \t]*:[ \t]*(?:#.*)?$")
NON_ACTION = {"with", "env", "inputs", "outputs", "secrets", "permissions", "matrix", "concurrency"}


class PinError(Exception):
    """A workflow cannot be safely processed."""


@dataclass(frozen=True, slots=True)
class Use:
    index: int
    repo: str
    ref: str
    spec: str
    prefix: str
    quote: str
    gap: str
    comment: str


def split_line(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def valid_ref(ref: str) -> bool:
    return (
        bool(ref)
        and not ref.startswith("-")
        and not ref.endswith(".")
        and ".." not in ref
        and "@{" not in ref
        and all(
            part and not part.startswith(".") and not part.endswith(".lock")
            for part in ref.split("/")
        )
        and not re.search(r"[\x00-\x20\x7f~^:?*\[\\]", ref)
    )


def parse_action(spec: str) -> tuple[str, str] | None:
    if spec.startswith(("./", "docker://")):
        return None
    if spec.count("@") != 1:
        raise PinError(f"invalid remote action: {spec!r}")
    name, ref = spec.rsplit("@", 1)
    parts = name.split("/")
    if len(parts) < 2 or not all(REPO.fullmatch(part) and part not in (".", "..") for part in parts[:2]):
        raise PinError(f"invalid GitHub action name: {name!r}")
    if any(part in ("", ".", "..") for part in parts[2:]):
        raise PinError(f"invalid GitHub action path: {name!r}")
    if not valid_ref(ref):
        raise PinError(f"invalid Git ref: {ref!r}")
    return "/".join(parts[:2]), ref


def version_comment(comment: str) -> str | None:
    if match := PIN_MARKER.search(comment):
        return match["ref"]
    if match := VERSION.match(comment):
        return match["ref"]
    return None


def pin_comment(comment: str, ref: str) -> str:
    if not comment:
        return f"# {ref}"
    if version_comment(comment) == ref:
        return comment
    return f"{comment.rstrip()} [pin:{ref}]"


def discover() -> list[Path]:
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PinError("cannot discover files outside a Git repository; pass filenames") from exc
    paths = (Path(os.fsdecode(p)) for p in output.split(b"\0") if p)
    return sorted({p for p in paths if (p.is_file() or p.is_symlink()) and (
        (len(p.parts) == 3 and p.parts[:2] == (".github", "workflows") and p.suffix in (".yml", ".yaml"))
        or p.name in ("action.yml", "action.yaml")
    )})


def _collect(node: object, scoped: bool, flowing: bool,
             found: list[tuple[int, bool, bool]], seen: set[int]) -> None:
    if isinstance(node, MappingNode):
        if id(node) in seen:
            return
        seen.add(id(node))
        nested = flowing or node.flow_style is True
        for key, value in node.value:
            name = key.value if isinstance(key, ScalarNode) else None
            if name == "uses" and isinstance(key, ScalarNode):
                found.append((key.start_mark.line, nested, scoped))
            _collect(value, scoped or name in NON_ACTION, nested, found, seen)
    elif isinstance(node, SequenceNode):
        if id(node) in seen:
            return
        seen.add(id(node))
        nested = flowing or node.flow_style is True
        for item in node.value:
            _collect(item, scoped, nested, found, seen)


def scan(path: Path, refresh: bool, include_pinned: bool = False) -> tuple[str, list[Use]]:
    if path.is_symlink():
        raise PinError(f"{path}: refusing to modify a symlink")
    try:
        with path.open(encoding="utf-8", newline="") as f:
            source = f.read()
    except (OSError, UnicodeError) as exc:
        raise PinError(f"{path}: {exc}") from exc
    try:
        documents = list(yaml.compose_all(source, Loader=yaml.BaseLoader))
    except ComposerError as exc:
        raise PinError(f"{path}: unresolvable anchor: {exc}") from exc
    except yaml.YAMLError as exc:
        raise PinError(f"{path}: invalid YAML: {exc}") from exc
    found: list[tuple[int, bool, bool]] = []
    for document in documents:
        if document is not None:
            _collect(document, False, False, found, set())
    lines = source.splitlines(keepends=True)
    uses = []
    for index, flowing, scoped in sorted(found):
        if flowing:
            raise PinError(f"{path}:{index + 1}: unsupported inline uses syntax")
        if scoped:
            continue
        body, _ = split_line(lines[index])
        body = body.removeprefix("\ufeff") if index == 0 else body
        match = USES.fullmatch(body)
        if not match:
            continue
        value = VALUE.fullmatch(match["value"])
        if not value:
            raise PinError(f"{path}:{index + 1}: unsupported uses value")
        spec = value["action"]
        parsed = parse_action(spec)
        if parsed is None:
            continue
        repo, ref = parsed
        if SHA.fullmatch(ref):
            tag = version_comment(value["comment"] or "")
            if not include_pinned and not (refresh and tag):
                continue
        if SHA.fullmatch(ref) and refresh and tag:
            ref = tag
            if not valid_ref(ref):
                raise PinError(f"{path}:{index + 1}: invalid version annotation")
        uses.append(Use(index, repo, ref, spec, match["indent"] + match["key"],
                         value["quote"], value["gap"], value["comment"] or ""))
    return source, uses


def resolve(references: dict[str, set[str]], allow_branches: bool) -> dict[tuple[str, str], str]:
    resolved = {}
    for repo, refs in sorted(references.items()):
        patterns = []
        for ref in sorted(refs):
            patterns += [f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}", f"refs/heads/{ref}"]
        try:
            proc = subprocess.run(
                ["git", "ls-remote", f"https://github.com/{repo}.git", *patterns],
                text=True, capture_output=True, timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PinError(f"cannot resolve {repo}: {exc}") from exc
        if proc.returncode:
            detail = proc.stderr.strip() or f"git exited {proc.returncode}"
            raise PinError(f"cannot resolve {repo}: {detail}")
        advertised = {}
        for line in proc.stdout.splitlines():
            try:
                sha, name = line.split("\t", 1)
            except ValueError as exc:
                raise PinError(f"malformed git response from {repo}") from exc
            if not SHA.fullmatch(sha):
                raise PinError(f"invalid object ID from {repo}: {sha!r}")
            advertised[name] = sha
        for ref in refs:
            tag, peeled, branch = (advertised.get(f"refs/tags/{ref}"),
                                    advertised.get(f"refs/tags/{ref}^{{}}"),
                                    advertised.get(f"refs/heads/{ref}"))
            if tag and branch:
                raise PinError(f"{repo}@{ref}: ambiguous tag and branch")
            if tag:
                resolved[repo, ref] = peeled or tag
            elif branch and allow_branches:
                resolved[repo, ref] = branch
            elif branch:
                raise PinError(f"{repo}@{ref}: branch ref; pass --allow-branches to pin")
            else:
                raise PinError(f"{repo}@{ref}: ref not found")
    return resolved


def write_file(path: Path, original: str, content: str) -> None:
    with path.open(encoding="utf-8", newline="") as f:
        if f.read() != original:
            raise PinError(f"{path}: changed while resolving refs; retry")
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Pin GitHub Actions to immutable commits using git, without third-party packages.")
    parser.add_argument("--check", action="store_true", help="offline check; never writes or uses network")
    parser.add_argument("--refresh", action="store_true", help="re-resolve pinned version comments")
    parser.add_argument("--allow-branches", action="store_true", help="permit mutable branch refs")
    parser.add_argument("files", nargs="*", type=Path, help="YAML files (default: discover workflows and actions)")
    args = parser.parse_args(argv)
    if args.check and args.refresh:
        parser.error("--check and --refresh are mutually exclusive")
    try:
        files = args.files or discover()
        changes = {}
        requested = defaultdict(set)
        unpinned = []
        for path in files:
            source, uses = scan(path, refresh=args.refresh)
            changes[path] = (source, uses)
            if args.check:
                unpinned.extend(f"{path}:{use.index + 1}: {use.repo}@{use.ref}" for use in uses)
            else:
                for use in uses:
                    requested[use.repo].add(use.ref)
        if args.check:
            for item in unpinned:
                print(item, file=sys.stderr)
            return 1 if unpinned else 0
        shas = resolve(requested, args.allow_branches)
        modified = 0
        for path, (source, uses) in changes.items():
            if not uses:
                continue
            lines = source.splitlines(keepends=True)
            for use in uses:
                _, newline = split_line(lines[use.index])
                bom = "\ufeff" if use.index == 0 and lines[0].startswith("\ufeff") else ""
                name, previous = use.spec.rsplit("@", 1)
                annotation = (use.comment if SHA.fullmatch(previous)
                              else pin_comment(use.comment, use.ref))
                separator = use.gap or (" " if annotation else "")
                lines[use.index] = (bom + use.prefix + use.quote + name + "@"
                                    + shas[use.repo, use.ref] + use.quote
                                    + separator + annotation + newline)
            updated = "".join(lines)
            if updated != source:
                write_file(path, source, updated)
                modified += 1
                print(f"pinned {path} ({len(uses)} refs)")
        print(f"{modified} file(s) updated")
        return 0
    except PinError as exc:
        print(f"pinact: {exc}", file=sys.stderr)
        return 2
