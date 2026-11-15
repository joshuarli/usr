"""Human and JSON rendering of sync task states, for one host or many."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Iterable, TextIO

# Plan/doctor states come from probes; apply states from dag.Result.
PLAN_STATES = ("conflict", "apply", "check", "current")
APPLY_STATES = ("failed", "blocked", "applied", "current")
QUIET = frozenset({"current", "check"})
LABELS = {"current": "current", "check": "checked", "apply": "to apply", "conflict": "conflict",
          "applied": "applied", "failed": "failed", "blocked": "blocked"}
COLORS = {"conflict": "31", "failed": "31", "blocked": "33", "apply": "33",
          "applied": "32", "current": "2", "check": "2"}
DETAIL_PREFIXES = ("LINK:", "CONFLICT:", "PRUNE:")


@dataclass(frozen=True)
class TaskLine:
    name: str
    state: str
    detail: str


def use_color(stream: TextIO) -> bool:
    return stream.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def paint(text: str, code: str, color: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if color else text


def counts(lines: Iterable[TaskLine], states: tuple[str, ...]) -> dict[str, int]:
    tally = dict.fromkeys(states, 0)
    for line in lines:
        tally[line.state] = tally.get(line.state, 0) + 1
    return tally


def summary(tally: dict[str, int], color: bool) -> str:
    parts = [paint(f"{n} {LABELS.get(state, state)}{'s' if state == 'conflict' and n != 1 else ''}", COLORS.get(state, "0"), color)
             for state, n in tally.items() if n and state not in QUIET]
    settled = sum(n for state, n in tally.items() if state in QUIET)
    if settled:
        parts.append(f"{settled} up to date")
    return " · ".join(parts) if parts else "nothing to do"


def healthy(tally: dict[str, int]) -> bool:
    return not any(tally.get(state, 0) for state in ("conflict", "failed", "blocked"))


def task_rows(lines: list[TaskLine], show_all: bool, color: bool, indent: str = "  ") -> list[str]:
    shown = [line for line in lines if show_all or line.state not in QUIET]
    if not shown:
        return []
    width = max(len(line.name) for line in shown)
    rows = []
    for line in shown:
        details = [part for part in line.detail.split("; ") if part.startswith(DETAIL_PREFIXES)]
        head = line.detail if not details else f"{len(details)} change{'s' if len(details) != 1 else ''}"
        state = paint(f"{line.state:<8}", COLORS.get(line.state, "0"), color)
        rows.append(f"{indent}{state}  {line.name:<{width}}  {head}")
        rows.extend(f"{indent}{'':<8}  {'':<{width}}  {part}" for part in details)
    return rows


def render(command: str, host: str, lines: list[TaskLine], show_all: bool, stream: TextIO | None = None) -> None:
    out = sys.stdout if stream is None else stream
    color = use_color(out)
    states = APPLY_STATES if command in ("apply", "tools", "links", "bridge") else PLAN_STATES
    tally = counts(lines, states)
    print(paint(f"sync {command}", "1", color) + f"  {host}", file=out)
    for row in task_rows(lines, show_all, color):
        print(row, file=out)
    mark = paint("✓", "32", color) if healthy(tally) else paint("✗", "31", color)
    print(f"  {mark} {summary(tally, color)}", file=out)


def render_json(command: str, host: str, lines: list[TaskLine], stream: TextIO | None = None) -> None:
    out = sys.stdout if stream is None else stream
    states = APPLY_STATES if command in ("apply", "tools", "links", "bridge") else PLAN_STATES
    print(json.dumps({"schema": 1, "command": command, "host": host,
                      "tasks": [asdict(line) for line in lines], "counts": counts(lines, states)}), file=out)
