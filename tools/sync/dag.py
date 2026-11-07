"""Small dependency executor; task functions own their platform-specific effects."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from typing import Callable, Literal


@dataclass(frozen=True)
class Probe:
    current: bool
    detail: str = ""
    conflict: bool = False


@dataclass(frozen=True)
class Task:
    name: str
    needs: tuple[str, ...]
    probe: Callable[[], Probe] = field(compare=False, repr=False)
    apply: Callable[[], None] = field(compare=False, repr=False)
    verify: Callable[[], Probe] = field(compare=False, repr=False)
    resources: frozenset[str] = frozenset()
    reconcile: bool = False


@dataclass(frozen=True)
class Result:
    name: str
    state: Literal["current", "applied", "blocked", "failed"]
    detail: str = ""


class GraphError(ValueError):
    pass


class Graph:
    def __init__(self, tasks: list[Task]):
        self.tasks = {task.name: task for task in tasks}
        if len(self.tasks) != len(tasks):
            raise GraphError("duplicate task name")
        missing = sorted({dep for task in tasks for dep in task.needs if dep not in self.tasks})
        if missing:
            raise GraphError(f"missing task prerequisites: {', '.join(missing)}")
        try:
            tuple(TopologicalSorter({name: task.needs for name, task in self.tasks.items()}).static_order())
        except CycleError as exc:
            raise GraphError(f"task dependency cycle: {exc.args[1]}") from exc

    def select(self, targets: list[str]) -> "Graph":
        selected: set[str] = set()

        def visit(name: str) -> None:
            if name not in self.tasks:
                raise GraphError(f"unknown task {name!r}")
            if name in selected:
                return
            selected.add(name)
            for dep in self.tasks[name].needs:
                visit(dep)

        for name in targets:
            visit(name)
        return Graph([task for name, task in self.tasks.items() if name in selected])

    def order(self) -> list[Task]:
        names = TopologicalSorter({name: task.needs for name, task in self.tasks.items()}).static_order()
        return [self.tasks[name] for name in names]

    def inspect(self) -> list[tuple[Task, Probe]]:
        return [(task, task.probe()) for task in self.order()]

    def _priority(self) -> dict[str, int]:
        dependents: dict[str, list[str]] = {name: [] for name in self.tasks}
        for name, task in self.tasks.items():
            for dependency in task.needs:
                dependents[dependency].append(name)
        height: dict[str, int] = {}

        def measure(name: str) -> int:
            if name not in height:
                height[name] = 1 + max((measure(child) for child in dependents[name]), default=-1)
            return height[name]

        return {name: measure(name) for name in self.tasks}

    def run(self, jobs: int = 4) -> list[Result]:
        if jobs < 1:
            raise GraphError("jobs must be positive")
        priority = self._priority()
        sorter = TopologicalSorter({name: task.needs for name, task in self.tasks.items()})
        sorter.prepare()
        ready: list[str] = sorted(sorter.get_ready(), key=lambda name: (-priority[name], name))
        running: dict[Future[Result], Task] = {}
        busy: set[str] = set()
        finished: dict[str, Result] = {}

        def execute(task: Task) -> Result:
            try:
                previous = task.probe()
                if previous.conflict:
                    return Result(task.name, "failed", previous.detail)
                if previous.current and not task.reconcile:
                    return Result(task.name, "current", previous.detail)
                task.apply()
                actual = task.verify()
                if actual.conflict or not actual.current:
                    return Result(task.name, "failed", actual.detail or "postcondition not satisfied")
                return Result(task.name, "applied", actual.detail)
            except Exception as exc:
                return Result(task.name, "failed", f"{type(exc).__name__}: {exc}")

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            while ready or running:
                made_progress = False
                for name in tuple(ready):
                    task = self.tasks[name]
                    bad = [d for d in task.needs if finished[d].state in ("blocked", "failed")]
                    if bad:
                        ready.remove(name)
                        finished[name] = Result(name, "blocked", "failed prerequisites: " + ", ".join(bad))
                        sorter.done(name)
                        ready.extend(sorter.get_ready())
                        ready.sort(key=lambda item: (-priority[item], item))
                        made_progress = True
                        continue
                    if len(running) < jobs and not (busy & task.resources):
                        ready.remove(name)
                        busy.update(task.resources)
                        running[pool.submit(execute, task)] = task
                        made_progress = True
                if running:
                    done, _ = wait(running, return_when=FIRST_COMPLETED)
                    for future in done:
                        task = running.pop(future)
                        busy.difference_update(task.resources)
                        finished[task.name] = future.result()
                        sorter.done(task.name)
                        ready.extend(sorter.get_ready())
                        ready.sort(key=lambda item: (-priority[item], item))
                elif ready and not made_progress:
                    raise GraphError("scheduler cannot make progress")
        return [finished[task.name] for task in self.order()]
