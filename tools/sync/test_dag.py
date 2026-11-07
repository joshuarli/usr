"""Tests for the shared planner and scheduler; no home or network effects."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import threading
import time
import unittest

from dag import Graph, GraphError, Probe, Task


class DagTests(unittest.TestCase):
    def test_select_closure_and_order(self):
        nodes = [Task("bridge", ("node", "claude"), lambda: Probe(False), lambda: None, lambda: Probe(True)),
                 Task("node", (), lambda: Probe(True), lambda: None, lambda: Probe(True)),
                 Task("claude", (), lambda: Probe(True), lambda: None, lambda: Probe(True)),
                 Task("irrelevant", (), lambda: Probe(True), lambda: None, lambda: Probe(True))]
        tasks = Graph(nodes).select(["bridge"]).order()
        names = [t.name for t in tasks]
        self.assertEqual(set(names), {"bridge", "node", "claude"})
        self.assertGreater(names.index("bridge"), names.index("node"))
        self.assertGreater(names.index("bridge"), names.index("claude"))

    def test_cycle_and_undeclared_dependencies(self):
        with self.assertRaisesRegex(GraphError, "cycle"):
            Graph([Task("a", ("b",), lambda: Probe(True), lambda: None, lambda: Probe(True)),
                   Task("b", ("a",), lambda: Probe(True), lambda: None, lambda: Probe(True))])
        with self.assertRaisesRegex(GraphError, "missing task prerequisites"):
            Graph([Task("a", ("b",), lambda: Probe(True), lambda: None, lambda: Probe(True))])

    def test_failed_precondition_blocks_descendants(self):
        called = []
        t = Task("bad", (), lambda: Probe(False, "foreign link", True), lambda: called.append(1), lambda: Probe(True))
        child = Task("after", ("bad",), lambda: Probe(False), lambda: called.append(2), lambda: Probe(True))
        results = {r.name: r.state for r in Graph([t, child]).run()}
        self.assertEqual(results, {"bad": "failed", "after": "blocked"})
        self.assertEqual(called, [])

    def test_resource_exclusion_but_other_tasks_can_run(self):
        active = 0
        maximum = 0
        lock = threading.Lock()
        def apply():
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
        def t(name):
            return Task(name, (), lambda: Probe(True), apply, lambda: Probe(True),
                        frozenset({"installer"}), reconcile=True)
        values = Graph([t("a"), t("b"), t("c")]).run(jobs=3)
        self.assertEqual(maximum, 1)
        self.assertTrue(all(r.state == "applied" for r in values))

    def test_probes_are_read_only_and_postcondition_checked(self):
        changes = []
        task = Task("write", (), lambda: Probe(False), lambda: changes.append(1), lambda: Probe(False, "still missing"))
        graph = Graph([task])
        self.assertFalse(graph.inspect()[0][1].current)
        self.assertEqual(changes, [])
        result = graph.run()[0]
        self.assertEqual(result.state, "failed")
        self.assertIn("still missing", result.detail)

    def test_current_task_is_not_reapplied(self):
        called = []
        task = Task("ok", (), lambda: Probe(True), lambda: called.append(1), lambda: Probe(True))
        self.assertEqual(Graph([task]).run()[0].state, "current")
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
