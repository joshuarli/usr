#!/usr/bin/env python3
"""Time representative CLI journeys against scratch fixtures and validate every run."""
from __future__ import annotations

import argparse
import json
import os
import re
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "dotfiles/base/.local/bin"
WORK = ROOT / ".work/bench"
TICKETS = 200
UNPINNED = "name: added\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"
BROKEN_LINK = "missing-bench-target.md"
EDITED_DOC = "bench-notes.md"
MAXRSS_BYTES = 1 if sys.platform == "darwin" else 1024


class Invalid(Exception):
    pass


@dataclass(frozen=True)
class Run:
    argv: tuple[str, ...]
    cwd: Path
    env: dict[str, str]
    stdin: Optional[bytes] = None


@dataclass(frozen=True)
class Result:
    exit_code: int
    stdout: str
    stderr: str
    wall: float
    cpu: float
    maxrss: int


@dataclass(frozen=True)
class Workload:
    name: str
    journey: str
    prepare: Callable[[], Run]
    validate: Callable[[Result], None]


@dataclass
class Samples:
    wall: list[float] = field(default_factory=list)
    cpu: list[float] = field(default_factory=list)
    maxrss: list[int] = field(default_factory=list)


def measure(run: Run) -> Result:
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        code = 0
        try:
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            start = time.perf_counter()
            proc = subprocess.run(list(run.argv), cwd=run.cwd, env=run.env, input=run.stdin,
                                  stdin=None if run.stdin is not None else subprocess.DEVNULL, capture_output=True)
            wall = time.perf_counter() - start
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            payload = {
                "exit_code": proc.returncode,
                "stdout": proc.stdout.decode(errors="replace"),
                "stderr": proc.stderr.decode(errors="replace"),
                "wall": wall,
                "cpu": (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime),
                "maxrss": after.ru_maxrss * MAXRSS_BYTES,
            }
        except BaseException as error:
            payload = {"error": f"{type(error).__name__}: {error}"}
            code = 1
        with os.fdopen(write_fd, "w") as out:
            json.dump(payload, out)
        os._exit(code)
    os.close(write_fd)
    with os.fdopen(read_fd) as handle:
        data = json.loads(handle.read() or '{"error": "measurement process wrote nothing"}')
    os.waitpid(pid, 0)
    if "error" in data:
        raise Invalid(data["error"])
    return Result(**data)


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise Invalid(message)


def expect_exit(result: Result, code: int) -> None:
    expect(result.exit_code == code, f"exit {result.exit_code}, expected {code}: {(result.stderr or result.stdout)[-400:].strip()}")


def last_json(text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines() if line.strip()]
    expect(bool(lines), "no output")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise Invalid(f"last output line is not JSON: {error}") from None


def parse_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise Invalid(f"output is not JSON: {error}") from None


def symlinks(root: Path) -> int:
    return sum(1 for base, dirs, files in os.walk(root) for name in (*dirs, *files) if os.path.islink(os.path.join(base, name)))


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "core.fsmonitor=false", *args], cwd=cwd, check=True, capture_output=True)


def tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "-c", "core.fsmonitor=false", "ls-files", "-z"], cwd=root, check=True, capture_output=True).stdout
    return [os.fsdecode(path) for path in out.split(b"\0") if path]


def copy_tracked(src: Path, dst: Path) -> None:
    for rel in tracked(src):
        source, target = src / rel, dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            os.symlink(os.readlink(source), target)
        elif source.is_file():
            shutil.copy2(source, target)


def home_env(home: Path) -> dict[str, str]:
    return dict(os.environ, HOME=str(home), TARGET=str(home), NO_COLOR="1",
                XDG_CONFIG_HOME=str(home / ".config"), XDG_CACHE_HOME=str(home / ".cache"),
                XDG_DATA_HOME=str(home / ".local/share"), XDG_STATE_HOME=str(home / ".local/state"))


def backlog(source: str, count: int, prefix: str = "BEN") -> str:
    bodies = [block.split("\n", 1)[1] for block in re.split(r"(?m)^### ", source)[1:] if "\n" in block]
    titles = re.findall(r"(?m)^### [A-Z]+-\d+ · P\d · (.+)$", source)
    if not bodies or len(bodies) != len(titles):
        raise Invalid("TODO.md has no parseable tickets to seed the backlog fixture")
    tickets = []
    for number in range(1, count + 1):
        priority = f"P{number % 4 + 1}"
        index = (number - 1) % len(bodies)
        tickets.append((priority, number, f"### {prefix}-{number} · {priority} · {titles[index]}\n{bodies[index].rstrip()}\n"))
    tickets.sort()
    return f"Prefix: {prefix}\nNext: {count + 1}\n\n" + "\n".join(text for _, _, text in tickets)


class Fixture:
    def __init__(self, scratch: Path) -> None:
        self.scratch = scratch
        self.rounds = 0
        self.built: dict[str, Path] = {}
        self.expected_links = 0
        self.backlog_text = ""

    def fresh(self, name: str) -> Path:
        self.rounds += 1
        path = self.scratch / f"{name}-{self.rounds}"
        path.mkdir(parents=True)
        return path

    def once(self, name: str, build: Callable[[Path], None]) -> Path:
        if name not in self.built:
            path = self.scratch / name
            path.mkdir()
            build(path)
            self.built[name] = path
        return self.built[name]

    def linked_home(self) -> Path:
        def build(home: Path) -> None:
            empty = self.scratch / "plan-empty-home"
            empty.mkdir()
            plan = measure(Run(("/bin/sh", "sync", "plan", "--json"), ROOT, home_env(empty)))
            expect_exit(plan, 0)
            report = last_json(plan.stdout)
            expect(report.get("counts", {}).get("conflict") == 0, "sync plan of an empty home reports conflicts")
            links = next((t for t in report.get("tasks", []) if t["name"] == "links"), {})
            expect(links.get("state") == "apply", "sync plan of an empty home has no links to apply")
            self.expected_links = links["detail"].count("LINK: ")
            expect(self.expected_links > 0, "sync plan of an empty home lists no LINK actions")
            expect_exit(measure(Run(("/bin/sh", "sync", "links", "--json"), ROOT, home_env(home))), 0)
            expect(symlinks(home) == self.expected_links, "fixture home link count differs from the plan")
        return self.once("linked-home", build)

    def workflows(self) -> list[str]:
        def build(path: Path) -> None:
            for rel in tracked(ROOT):
                if rel.startswith(".github/workflows/") and rel.endswith(".yml"):
                    shutil.copy2(ROOT / rel, path / Path(rel).name)
            (path / "added.yml").write_text(UNPINNED, encoding="utf-8")
        return sorted(str(p) for p in self.once("workflows", build).glob("*.yml"))

    def docs(self) -> Path:
        def build(path: Path) -> None:
            copy_tracked(ROOT, path)
            (path / EDITED_DOC).write_text(f"# Notes\n\nSee [the missing page]({BROKEN_LINK}) and [the guide](README.md).\n", encoding="utf-8")
            git(path, "init", "-q")
            git(path, "add", "-A")
        return self.once("docs-tree", build)

    def backlog(self) -> Path:
        def build(path: Path) -> None:
            self.backlog_text = backlog((ROOT / "TODO.md").read_text(encoding="utf-8"), TICKETS)
            (path / "TODO.md").write_text(self.backlog_text, encoding="utf-8")
            git(path, "init", "-q")
            check = measure(Run(("python3", "-I", str(BIN / "todo"), "check", "--json"), path, dict(os.environ)))
            expect_exit(check, 0)
            expect(parse_json(check.stdout).get("ok") is True, f"generated backlog fails todo check: {check.stdout[:400]}")
        return self.once("backlog", build)

    def links_home(self) -> Run:
        self.linked_home()
        return Run(("/bin/sh", "sync", "links", "--json"), ROOT, home_env(self.fresh("links-home")))

    def todo_copy(self) -> Run:
        self.backlog()
        path = self.fresh("backlog-edit")
        (path / "TODO.md").write_text(self.backlog_text, encoding="utf-8")
        git(path, "init", "-q")
        ticket = {"priority": "P2", "title": "benchmark added ticket", "area": "Bench", "where": "tools/bench/bench.py",
                  "problem": "A representative ticket body.", "recommendation": "Keep it.", "fix_with": "none", "effort": "S"}
        return Run(("python3", "-I", str(BIN / "todo"), "add", "--json", "-"), path, dict(os.environ), json.dumps(ticket).encode())


def workloads(f: Fixture) -> tuple[Workload, ...]:
    def links_valid(r: Result) -> None:
        expect_exit(r, 0)
        report = last_json(r.stdout)
        expect(report.get("counts", {}).get("failed") == 0, f"sync links reports failures: {report.get('counts')}")
        expect(report["tasks"][0]["state"] == "applied", f"links task is {report['tasks'][0]['state']}, expected applied")
        made = symlinks(f.scratch / f"links-home-{f.rounds}")
        expect(made == f.expected_links, f"sync links made {made} links, plan expected {f.expected_links}")

    def plan_valid(r: Result) -> None:
        expect_exit(r, 0)
        report = last_json(r.stdout)
        expect(report.get("counts", {}).get("conflict") == 0, f"sync plan reports conflicts: {report.get('counts')}")
        links = next((t for t in report.get("tasks", []) if t["name"] == "links"), {})
        expect(links.get("state") == "current", f"links task is {links.get('state')}, expected current")

    def pins_valid(r: Result) -> None:
        expect_exit(r, 0)
        expect(r.stdout.strip() == "", f"pinact --check printed findings: {r.stdout[:400]}")

    def lint_valid(r: Result) -> None:
        expect_exit(r, 1)
        findings = parse_json(r.stdout)
        unpinned = [x for x in findings if x.get("id") == "unpinned-uses"]
        expect(len(unpinned) == 1 and unpinned[0].get("filepath", "").endswith("added.yml") and unpinned[0].get("line") == 7,
               f"expected one unpinned-uses finding at added.yml:7, got {unpinned}")

    def docs_valid(r: Result) -> None:
        expect_exit(r, 1)
        findings = [parse_json(line) for line in r.stdout.splitlines() if line.strip()]
        errors = [x for x in findings if x.get("severity") == "error"]
        expect(any(x.get("code") == "L001" and x.get("file") == EDITED_DOC and x.get("target") == BROKEN_LINK for x in errors),
               f"expected L001 for {BROKEN_LINK} in {EDITED_DOC}, got {errors[:3]}")
        expect(re.search(r"files checked: [1-9]", r.stderr) is not None, f"mdtool checked no files: {r.stderr[-200:]}")

    def list_valid(r: Result) -> None:
        expect_exit(r, 0)
        data = parse_json(r.stdout)
        expect(len(data.get("tickets", [])) == TICKETS and data.get("next") == TICKETS + 1,
               f"todo list returned {len(data.get('tickets', []))} tickets and Next {data.get('next')}")

    def check_valid(r: Result) -> None:
        expect_exit(r, 0)
        data = parse_json(r.stdout)
        expect(data.get("ok") is True and data.get("errors") == [], f"todo check: {r.stdout[:400]}")

    def add_valid(r: Result) -> None:
        expect_exit(r, 0)
        expected = f"BEN-{TICKETS + 1}"
        expect(parse_json(r.stdout).get("id") == expected, f"todo add returned {r.stdout[:200]}, expected {expected}")
        text = (f.scratch / f"backlog-edit-{f.rounds}/TODO.md").read_text(encoding="utf-8")
        expect(f"Next: {TICKETS + 2}\n" in text and f"### {expected} · P2 ·" in text, "todo add did not write the ticket and advance Next")

    env = dict(os.environ, NO_COLOR="1")
    pinact, mdtool, todo = str(BIN / "pinact"), str(BIN / "mdtool"), str(BIN / "todo")
    return (
        Workload("sync-links", "apply layer links into an empty scratch home",
                 f.links_home, links_valid),
        Workload("sync-plan", "preview reconciliation of a linked scratch home",
                 lambda: Run(("/bin/sh", "sync", "plan", "--json"), ROOT, home_env(f.linked_home())), plan_valid),
        Workload("pinact-check", "offline pin check of the repository workflows",
                 lambda: Run(("python3", "-I", pinact, "--check"), ROOT, env), pins_valid),
        Workload("pinact-lint", "lint the repository workflows plus one added unpinned workflow",
                 lambda: Run(("python3", "-I", pinact, "lint", "--format", "json", *f.workflows()), f.scratch, env), lint_valid),
        Workload("mdtool-check", "audit a copy of the tracked tree after a doc edit adds a broken link",
                 lambda: Run(("python3", "-I", mdtool, "check", "--json", "--root", str(f.docs())), f.docs(), env), docs_valid),
        Workload("todo-list", f"list a {TICKETS}-ticket backlog as JSON",
                 lambda: Run(("python3", "-I", todo, "list", "--json"), f.backlog(), env), list_valid),
        Workload("todo-check", f"validate a {TICKETS}-ticket backlog",
                 lambda: Run(("python3", "-I", todo, "check", "--json"), f.backlog(), env), check_valid),
        Workload("todo-add", f"file one ticket into a {TICKETS}-ticket backlog",
                 f.todo_copy, add_valid),
    )


def bench(selected: Sequence[Workload], rounds: int) -> dict[str, Samples]:
    samples = {w.name: Samples() for w in selected}
    for index in range(rounds):
        shift = index % len(selected)
        for workload in (*selected[shift:], *selected[:shift]):
            result = measure(workload.prepare())
            try:
                workload.validate(result)
            except Invalid as error:
                raise Invalid(f"{workload.name} round {index + 1}: {error}") from None
            entry = samples[workload.name]
            entry.wall.append(result.wall)
            entry.cpu.append(result.cpu)
            entry.maxrss.append(result.maxrss)
    return samples


def summary(name: str, journey: str, s: Samples) -> dict[str, object]:
    return {"name": name, "journey": journey, "rounds": len(s.wall),
            "wall_median_ms": round(statistics.median(s.wall) * 1000, 1),
            "wall_min_ms": round(min(s.wall) * 1000, 1), "wall_max_ms": round(max(s.wall) * 1000, 1),
            "cpu_median_ms": round(statistics.median(s.cpu) * 1000, 1),
            "maxrss_mib": round(max(s.maxrss) / 1048576, 1)}


def render(rows: list[dict[str, object]]) -> str:
    head = f"{'workload':<14} {'rounds':>6} {'wall p50':>10} {'wall range':>19} {'cpu p50':>10} {'max rss':>9}"
    lines = [head]
    for r in rows:
        spread = f"{r['wall_min_ms']}-{r['wall_max_ms']} ms"
        lines.append(f"{r['name']:<14} {r['rounds']:>6} {str(r['wall_median_ms']) + ' ms':>10} {spread:>19} "
                     f"{str(r['cpu_median_ms']) + ' ms':>10} {str(r['maxrss_mib']) + ' MiB':>9}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="bench.py", description="Time representative sync, pinact, mdtool and todo journeys on scratch fixtures under .work/bench; every run's output is validated.")
    parser.add_argument("--rounds", type=int, default=5, help="interleaved rounds per workload (default: 5)")
    parser.add_argument("--only", default="", help="comma-separated workload names to run")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of a table")
    parser.add_argument("--keep", action="store_true", help="keep the scratch fixture directory")
    parser.add_argument("--list", action="store_true", help="list workload names and journeys")
    args = parser.parse_args(argv)
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")
    WORK.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="run-", dir=WORK))
    fixture = Fixture(scratch)
    try:
        available = workloads(fixture)
        if args.list:
            for w in available:
                print(f"{w.name:<14} {w.journey}")
            return 0
        names = [n for n in args.only.split(",") if n]
        unknown = sorted(set(names) - {w.name for w in available})
        if unknown:
            parser.error(f"unknown workload: {', '.join(unknown)}")
        selected = tuple(w for w in available if not names or w.name in names)
        try:
            samples = bench(selected, args.rounds)
        except Invalid as error:
            print(f"bench: invalid run: {error}", file=sys.stderr)
            return 1
        rows = [summary(w.name, w.journey, samples[w.name]) for w in selected]
        if args.json:
            print(json.dumps({"schema": 1, "host": os.uname().nodename, "cpus": os.cpu_count(),
                              "load": os.getloadavg(), "workloads": rows}, indent=2))
        else:
            print(render(rows))
            print(f"load average at end: {' '.join(f'{x:.1f}' for x in os.getloadavg())}; {os.cpu_count()} CPUs")
        return 0
    finally:
        if args.keep:
            print(f"fixture kept: {scratch}", file=sys.stderr)
        else:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
