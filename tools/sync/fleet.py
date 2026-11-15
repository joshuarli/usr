"""`sync hosts`: pull and sync every usr machine named in the tailnet policy.

The fleet is the `hosts` map of `tailscale/policy.json` (name -> tailnet
IP). The machine whose tailnet IP is listed runs locally; every other host
runs over SSH by its MagicDNS name, in parallel, each with its own `~/usr`.

  pull   fetch and fast-forward `main` (never merges, rebases or stashes)
  plan   fetch, then `sync plan` (read-only apart from the fetch)
  doctor fetch, then `sync doctor`
  apply  pull, then `sync` on each host whose pull succeeded
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TextIO

from report import APPLY_STATES, PLAN_STATES, TaskLine, counts, healthy, paint, summary, task_rows, use_color

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "tailscale/policy.json"
COMMANDS = ("pull", "plan", "doctor", "apply")
TIMEOUTS = {"pull": 120, "plan": 300, "doctor": 300, "apply": 1800}
SSH = ("ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8")
PREAMBLE = 'export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"; cd "$HOME/usr" 2>/dev/null || { echo "repo=missing"; exit 0; }; '

# Prints key=value lines; never merges, rebases, stashes or resets.
REPO_SCRIPT = r'''
echo "before=$(git rev-parse --short=7 HEAD)"
echo "branch=$(git symbolic-ref --short -q HEAD || echo HEAD)"
echo "dirty=$(git status --porcelain | wc -l | tr -d ' ')"
if ! git fetch -q origin 2>/dev/null; then echo "fetch=failed"; exit 0; fi
echo "behind=$(git rev-list --count HEAD..origin/main)"
echo "ahead=$(git rev-list --count origin/main..HEAD)"
'''
PULL_SCRIPT = REPO_SCRIPT + r'''
if [ "$(git symbolic-ref --short -q HEAD)" = main ] && [ "$(git rev-list --count origin/main..HEAD)" = 0 ] && [ "$(git rev-list --count HEAD..origin/main)" != 0 ]; then
  if git merge --ff-only -q origin/main >/dev/null 2>&1; then echo "pull=updated"; else echo "pull=blocked"; fi
fi
echo "after=$(git rev-parse --short=7 HEAD)"
'''

Runner = Callable[["Host", str, int], "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class Host:
    name: str
    ip: str
    local: bool


@dataclass
class Outcome:
    host: Host
    repo: dict[str, str] = field(default_factory=dict)
    sync: dict[str, Any] | None = None
    error: str | None = None


def read_policy(path: Path = POLICY) -> dict[str, Any]:
    text = path.read_text()
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def local_ips() -> set[str]:
    try:
        out = subprocess.run(["tailscale", "ip"], capture_output=True, text=True, timeout=10, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def fleet(policy: dict[str, Any], mine: set[str], only: list[str]) -> list[Host]:
    hosts = policy.get("hosts")
    if not isinstance(hosts, dict) or not hosts:
        raise ValueError(f"{POLICY.relative_to(ROOT)} has no hosts map; add the usr machines there")
    unknown = [name for name in only if name not in hosts]
    if unknown:
        raise ValueError(f"not in the tailnet policy hosts: {', '.join(unknown)}")
    return [Host(name, str(ip), str(ip) in mine) for name, ip in hosts.items() if not only or name in only]


def ssh_runner(host: Host, script: str, timeout: int) -> subprocess.CompletedProcess[str]:
    if host.local:
        return subprocess.run(["sh", "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    return subprocess.run([*SSH, host.name, PREAMBLE + script], capture_output=True, text=True, timeout=timeout, check=False)


def parse_pairs(text: str) -> dict[str, str]:
    pairs = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and re.fullmatch(r"[a-z]+", key):
            pairs[key] = value.strip()
    return pairs


def last_json(text: str) -> dict[str, Any] | None:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                value = json.loads(line)
            except ValueError:
                return None
            return value if isinstance(value, dict) and value.get("schema") == 1 else None
    return None


def visit(host: Host, command: str, run: Runner) -> Outcome:
    outcome = Outcome(host)
    try:
        repo = run(host, PULL_SCRIPT if command in ("pull", "apply") else REPO_SCRIPT, TIMEOUTS["pull"])
    except subprocess.TimeoutExpired:
        outcome.error = "timed out"
        return outcome
    if repo.returncode == 255 and not repo.stdout:
        outcome.error = "unreachable"
        return outcome
    if command == "apply" and repo.returncode != 0:
        outcome.error = f"repository update failed (exit {repo.returncode})"
        return outcome
    outcome.repo = parse_pairs(repo.stdout)
    if command == "apply" and not outcome.repo:
        outcome.error = "repository update check produced no output"
        return outcome
    if command == "pull" or outcome.repo.get("repo") == "missing":
        return outcome
    if command == "apply" and not repo_text(outcome.repo)[1]:
        return outcome
    sync_command = "apply" if command == "apply" else command
    try:
        result = run(host, f"sh sync {sync_command} --json", TIMEOUTS[command])
    except subprocess.TimeoutExpired:
        outcome.error = f"sync {sync_command} timed out"
        return outcome
    outcome.sync = last_json(result.stdout)
    if outcome.sync is None:
        tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or [f"exit {result.returncode}"]
        outcome.error = f"sync {sync_command}: {tail[0][:160]}"
    return outcome


def repo_text(repo: dict[str, str]) -> tuple[str, bool]:
    if repo.get("repo") == "missing":
        return "no ~/usr", False
    parts: list[str] = []
    ok = True
    if repo.get("fetch") == "failed":
        parts.append("fetch failed")
        ok = False
    elif repo.get("pull") == "updated":
        parts.append(f"updated {repo.get('before')}→{repo.get('after')}")
    elif repo.get("pull") == "blocked":
        parts.append("pull blocked by local changes")
        ok = False
    elif repo.get("branch") != "main":
        parts.append(f"on {repo.get('branch')}, not main")
        ok = False
    else:
        behind, ahead = int(repo.get("behind", "0") or 0), int(repo.get("ahead", "0") or 0)
        if behind and ahead:
            parts.append(f"diverged ({ahead} ahead, {behind} behind)")
            ok = False
        elif behind:
            parts.append(f"{behind} behind")
        elif ahead:
            parts.append(f"{ahead} unpushed")
        else:
            parts.append("up to date")
    dirty = int(repo.get("dirty", "0") or 0)
    if dirty:
        parts.append(f"{dirty} local change{'s' if dirty != 1 else ''}")
    return ", ".join(parts), ok


def sync_lines(sync: dict[str, Any]) -> list[TaskLine]:
    return [TaskLine(str(t.get("name")), str(t.get("state")), str(t.get("detail", ""))) for t in sync.get("tasks", []) if isinstance(t, dict)]


def render(command: str, outcomes: list[Outcome], show_all: bool, stream: TextIO | None = None) -> bool:
    out = sys.stdout if stream is None else stream
    color = use_color(out)
    states = APPLY_STATES if command == "apply" else PLAN_STATES
    rows: list[tuple[str, str, str, str]] = []
    details: list[tuple[str, list[str]]] = []
    all_ok = True
    for outcome in outcomes:
        label = outcome.host.name + ("*" if outcome.host.local else "")
        if outcome.error is not None and not outcome.repo:
            rows.append((label, "-", paint(outcome.error, "31", color), ""))
            all_ok = False
            continue
        revision = outcome.repo.get("after") or outcome.repo.get("before") or "-"
        repo, repo_ok = repo_text(outcome.repo)
        all_ok &= repo_ok
        if command == "pull":
            sync_cell = ""
        elif outcome.error is not None:
            sync_cell = paint(outcome.error, "31", color)
            all_ok = False
        elif outcome.sync is None:
            sync_cell = paint("skipped", "33", color)
        else:
            lines = sync_lines(outcome.sync)
            tally = counts(lines, states)
            ok = healthy(tally)
            all_ok &= ok
            mark = paint("✓", "32", color) if ok else paint("✗", "31", color)
            sync_cell = f"{mark} {summary(tally, color)}"
            shown = task_rows(lines, show_all, color, indent="  ")
            if shown:
                details.append((outcome.host.name, shown))
        rows.append((label, revision, repo if repo_ok else paint(repo, "33", color), sync_cell))
    print(paint(f"sync hosts {command}", "1", color), file=out)
    headers = ("host", "revision", "repo", "" if command == "pull" else "sync")
    plain = [tuple(re.sub(r"\033\[[0-9;]*m", "", cell) for cell in row) for row in rows]
    widths = [max(len(headers[i]), *(len(row[i]) for row in plain)) for i in range(3)]
    print("  " + paint("  ".join(h.ljust(widths[i]) if i < 3 else h for i, h in enumerate(headers)).rstrip(), "2", color), file=out)
    for row, bare in zip(rows, plain):
        cells = [row[i] + " " * (widths[i] - len(bare[i])) for i in range(3)] + [row[3]]
        print("  " + "  ".join(cells).rstrip(), file=out)
    if any(outcome.host.local for outcome in outcomes):
        print(paint("  * this machine", "2", color), file=out)
    for name, shown in details:
        print(file=out)
        print(paint(name, "1", color), file=out)
        for line in shown:
            print(line, file=out)
    return all_ok


def main(argv: list[str], run: Runner = ssh_runner, policy: dict[str, Any] | None = None, mine: set[str] | None = None) -> int:
    args = [arg for arg in argv if arg != "--all"]
    show_all = len(args) != len(argv)
    command = args.pop(0) if args and args[0] in COMMANDS else "plan"
    if any(arg.startswith("-") for arg in args):
        raise ValueError("usage: sync hosts [pull|plan|doctor|apply] [HOST...] [--all]")
    hosts = fleet(policy if policy is not None else read_policy(), local_ips() if mine is None else mine, args)
    with ThreadPoolExecutor(max_workers=len(hosts)) as pool:
        outcomes = list(pool.map(lambda host: visit(host, command, run), hosts))
    return 0 if render(command, outcomes, show_all) else 1
