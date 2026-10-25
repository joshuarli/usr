"""Provisional ``pinact lint`` JSON surface for the repomod probe lane.

Status is provisional: rule coverage grows in later campaign items, but the
record shape, stable IDs, deterministic order, and exit codes are already the
repomod contract and must not change without a coordinated update. Each record
holds ``filepath`` (repo-relative when the file lives in a Git checkout),
1-based ``line`` and ``column`` of the finding, stable ``id``, ``severity``,
human ``message``, and ``fixable``. JSON mode writes only the array to
stdout. Exit 0 means clean, 1 means findings remain, 2 means the invocation
was invalid or a file could not be processed at all.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from pinact import pinning

UNPINNED_USES = "unpinned-uses"
INVALID_USES = "invalid-uses"

KEY_COLUMN = re.compile(r"(?P<prefix>[ \t]*(?:-[ \t]+)?['\"]?)uses")
FINDING_LINE = re.compile(r":(\d+):")


@dataclass(frozen=True, slots=True)
class Finding:
    filepath: str
    line: int
    column: int
    id: str
    severity: str
    message: str
    fixable: bool


def _display(path: Path) -> str:
    text = str(path)
    if not os.path.isabs(text):
        return text
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            text=True, capture_output=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return text
    top = proc.stdout.strip()
    if not top:
        return text
    try:
        return os.path.relpath(text, top)
    except ValueError:
        return text


def _column(source: str, index: int) -> int:
    body, _ = pinning.split_line(source.splitlines(keepends=True)[index])
    body = body.removeprefix("\ufeff") if index == 0 else body
    match = KEY_COLUMN.match(body)
    if not match:
        return 1
    return len(match["prefix"]) + 1


def lint_files(files: list[Path]) -> tuple[list[Finding], str | None]:
    try:
        targets = files or pinning.discover()
    except pinning.PinError as exc:
        return [], f"pinact: {exc}"
    findings: list[Finding] = []
    for path in targets:
        try:
            source, uses = pinning.scan(path, refresh=False)
        except pinning.PinError as exc:
            detail = str(exc)
            if not FINDING_LINE.search(detail):
                return [], f"pinact: {exc}"
            match = FINDING_LINE.search(detail)
            findings.append(Finding(
                filepath=_display(path),
                line=int(match[1]) if match else 1,
                column=1,
                id=INVALID_USES,
                severity="error",
                message=detail,
                fixable=False,
            ))
            continue
        for use in uses:
            findings.append(Finding(
                filepath=_display(path),
                line=use.index + 1,
                column=_column(source, use.index),
                id=UNPINNED_USES,
                severity="error",
                message=f"{use.repo}@{use.ref} is not pinned to an immutable commit SHA",
                fixable=True,
            ))
    findings.sort(key=lambda item: (item.filepath, item.line, item.column, item.id, item.message))
    return findings, None


def render_json(findings: list[Finding]) -> str:
    return json.dumps([asdict(item) for item in findings], indent=2, sort_keys=True) + "\n"


def render_text(findings: list[Finding]) -> str:
    lines = [
        f"{item.filepath}:{item.line}:{item.column}: {item.id} [{item.severity}] {item.message}"
        for item in findings
    ]
    return "".join(line + "\n" for line in lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint GitHub Actions workflow files.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("files", nargs="*", type=Path, help="YAML files (default: discover workflows and actions)")
    args = parser.parse_args(argv)
    findings, error = lint_files(args.files)
    if error is not None:
        print(error, file=sys.stderr)
        return 2
    if args.format == "json":
        sys.stdout.write(render_json(findings))
    else:
        sys.stdout.write(render_text(findings))
    return 1 if findings else 0
