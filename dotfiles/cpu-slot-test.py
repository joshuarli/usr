#!/usr/bin/env python3
"""cpu-slot pins jobs to disjoint CPUs from one pool and ends their whole process group."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "dotfiles/linux/.local/bin/cpu-slot"
POOL = 4


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f"/proc/{pid}/stat") as stat:
            return stat.read().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


@unittest.skipUnless(hasattr(os, "sched_setaffinity") and len(os.sched_getaffinity(0)) >= POOL, "needs Linux with 4 CPUs")
class CpuSlotTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch, prefix="cpu-slot-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.env = {**os.environ, "XDG_STATE_HOME": str(self.dir / "state"), "CPU_SLOT_TOTAL": str(POOL),
                    "CPU_SLOT_RESERVE": "0"}

    def run_slot(self, *args, timeout=60):
        return subprocess.run([str(TOOL), *args], capture_output=True, text=True, env=self.env, timeout=timeout)

    def start_slot(self, *args):
        proc = subprocess.Popen([str(TOOL), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env=self.env)
        self.addCleanup(self.stop, proc)
        return proc

    def stop(self, proc):
        if proc.poll() is None:
            proc.kill()
        proc.communicate()

    def wait_for(self, predicate, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return False

    def held(self):
        report = json.loads(self.run_slot("status", "--json").stdout)
        return [row for row in report["cpus"] if row["held"]]

    def test_command_runs_on_exactly_the_granted_cpus(self):
        script = "import os; print(sorted(os.sched_getaffinity(0))); print(os.environ['CPU_SLOT_CPUS'], os.environ['CPU_SLOT_COUNT'])"
        result = self.run_slot("run", "--cpus", "2", "--", sys.executable, "-c", script)
        self.assertEqual(result.returncode, 0, result.stderr)
        affinity, exported = result.stdout.splitlines()
        self.assertEqual(affinity, "[0, 1]")
        self.assertEqual(exported, "0,1 2")

    def test_concurrent_jobs_get_disjoint_cpus_and_a_third_waits(self):
        marker = self.dir / "release"
        script = ("import os, sys, time\n"
                  "print(','.join(map(str, sorted(os.sched_getaffinity(0)))), flush=True)\n"
                  f"while not os.path.exists({str(marker)!r}): time.sleep(0.05)\n")
        first = self.start_slot("run", "--cpus", "2", "--name", "first", "--", sys.executable, "-c", script)
        second = self.start_slot("run", "--cpus", "2", "--name", "second", "--", sys.executable, "-c", script)
        cpus_first = set(first.stdout.readline().strip().split(","))
        cpus_second = set(second.stdout.readline().strip().split(","))
        self.assertEqual(len(cpus_first), 2)
        self.assertEqual(len(cpus_second), 2)
        self.assertFalse(cpus_first & cpus_second)
        self.assertEqual(sorted(row["label"] for row in self.held()), ["first", "first", "second", "second"])

        started = self.dir / "third-started"
        third = self.start_slot("run", "--cpus", "1", "--", sys.executable, "-c", f"open({str(started)!r}, 'w').close()")
        time.sleep(1.0)
        self.assertFalse(started.exists(), "the third job ran while the pool was full")
        self.assertIsNone(third.poll())

        marker.touch()
        self.assertEqual(first.wait(20), 0)
        self.assertEqual(second.wait(20), 0)
        self.assertEqual(third.wait(20), 0)
        self.assertTrue(started.exists())
        self.assertEqual(self.held(), [])

    def test_timeout_ends_the_whole_process_group(self):
        pidfile = self.dir / "grandchild"
        script = f"sleep 300 & echo $! > {pidfile}; wait"
        result = self.run_slot("run", "--cpus", "1", "--timeout", "1", "--grace", "1", "--", "sh", "-c", script)
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertIn("timed out", result.stderr)
        grandchild = int(pidfile.read_text())
        self.assertTrue(self.wait_for(lambda: not alive(grandchild)), f"grandchild {grandchild} survived")
        self.assertEqual(self.held(), [])

    def test_background_processes_end_when_the_command_exits(self):
        pidfile = self.dir / "background"
        result = self.run_slot("run", "--cpus", "1", "--grace", "1", "--", "sh", "-c", f"sleep 300 & echo $! > {pidfile}")
        self.assertEqual(result.returncode, 0, result.stderr)
        background = int(pidfile.read_text())
        self.assertTrue(self.wait_for(lambda: not alive(background)), f"background {background} survived")

    def test_sigterm_to_cpu_slot_ends_the_group(self):
        pidfile = self.dir / "child"
        slot = self.start_slot("run", "--cpus", "1", "--grace", "1", "--", "sh", "-c",
                               f"sleep 300 & echo $! > {pidfile}; wait")
        self.assertTrue(self.wait_for(lambda: pidfile.exists() and pidfile.read_text().strip()))
        grandchild = int(pidfile.read_text())
        slot.send_signal(signal.SIGTERM)
        self.assertEqual(slot.wait(20), 128 + signal.SIGTERM)
        self.assertTrue(self.wait_for(lambda: not alive(grandchild)), f"grandchild {grandchild} survived")
        self.assertEqual(self.held(), [])

    def test_exit_status_passes_through(self):
        self.assertEqual(self.run_slot("run", "--cpus", "1", "--", "sh", "-c", "exit 7").returncode, 7)

    def test_request_larger_than_the_pool_is_a_usage_error(self):
        result = self.run_slot("run", "--cpus", str(POOL + 1), "--", "true", timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("exceeds the pool", result.stderr)

    def test_status_lists_holders_and_ignores_stale_metadata(self):
        state = self.dir / "state/cpu-slot"
        state.mkdir(parents=True)
        (state / "cpu-3.lock").touch()
        (state / "cpu-3.json").write_text(json.dumps({"pid": 1, "label": "stale", "since": 0}))
        release = self.dir / "go"
        holder = self.start_slot("run", "--cpus", "1", "--name", "holder", "--", sys.executable, "-c",
                                 f"import os, time\nprint('up', flush=True)\nwhile not os.path.exists({str(release)!r}): time.sleep(0.05)")
        self.assertEqual(holder.stdout.readline().strip(), "up")
        rows = self.held()
        self.assertEqual([(row["cpu"], row["label"], row["pid"]) for row in rows], [(0, "holder", holder.pid)])
        text = self.run_slot("status").stdout
        self.assertIn("1 held", text)
        self.assertIn("holder", text)
        release.touch()
        self.assertEqual(holder.wait(20), 0)


if __name__ == "__main__":
    unittest.main()
