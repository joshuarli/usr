#!/usr/bin/env python3
"""cpu-guard stops a command's whole process tree when it burns more CPU than allowed."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "dotfiles/base/.local/bin/cpu-guard"
loader = importlib.machinery.SourceFileLoader("cpu_guard", str(TOOL))
spec = importlib.util.spec_from_loader("cpu_guard", loader)
guard = importlib.util.module_from_spec(spec)
sys.modules["cpu_guard"] = guard
loader.exec_module(guard)

SPIN = "while True: pass"
SPAWN = """
import os, subprocess, sys
for _ in range(2):
    child = subprocess.Popen([sys.executable, "-c", "while True: pass"], start_new_session=True)
    with open(sys.argv[1], "a") as pids:
        pids.write(f"{child.pid}\\n")
while True: pass
"""


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    if sys.platform.startswith("linux"):
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            return False
        return stat[stat.rindex(")") + 2] != "Z"
    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return result.returncode == 0 and not result.stdout.strip().startswith("Z")


class ParseTests(unittest.TestCase):
    def test_ps_time_formats(self):
        for text, seconds in [("0:01.23", 1.23), ("84:29.40", 5069.4), ("1:02:03", 3723.0),
                              ("2-03:04:05", 2 * 86400 + 3 * 3600 + 4 * 60 + 5)]:
            with self.subTest(text=text):
                self.assertAlmostEqual(guard.parse_ps_time(text), seconds)

    def test_ps_rows_keep_spaced_start_and_command(self):
        procs = guard.parse_ps("  12     1   1:02.50 Sun Nov 15 09:12:37 2026     cargo test --quiet\n")
        self.assertEqual(procs[12], guard.Proc(12, 1, 62.5, "Sun Nov 15 09:12:37 2026", "cargo test --quiet"))

    def test_proc_stat_with_parentheses_in_the_command_name(self):
        fields = ["R", "7"] + ["0"] * 9 + ["250", "50"] + ["0"] * 6 + ["4242"] + ["0"] * 20
        stat = "99 (a) (b) " + " ".join(fields)
        self.assertEqual(guard.parse_proc_stat(99, stat, 100), guard.Proc(99, 7, 3.0, "4242", "a) (b"))


class DetectorTests(unittest.TestCase):
    def proc(self, cpu: float, pid: int = 10) -> dict[int, "guard.Proc"]:
        return {pid: guard.Proc(pid, 1, cpu, "s", "x")}

    def test_tree_average_trips_only_after_a_full_window_above_the_limit(self):
        detector = guard.Detector(cores=2, window=4, spin=None)
        self.assertIsNone(detector.observe(0, self.proc(0)))
        self.assertIsNone(detector.observe(2, self.proc(6)))
        self.assertIn("cores over", detector.observe(4, self.proc(12)))

    def test_load_at_the_limit_passes(self):
        detector = guard.Detector(cores=3, window=4, spin=None)
        for now in range(0, 20, 2):
            self.assertIsNone(detector.observe(now, self.proc(now * 3.0)))

    def test_spin_needs_one_process_at_a_full_core_for_the_whole_period(self):
        detector = guard.Detector(cores=64, window=4, spin=3)
        self.assertIsNone(detector.observe(0, self.proc(0)))
        self.assertIsNone(detector.observe(2, self.proc(2)))
        self.assertIsNone(detector.observe(3, self.proc(2.2)))
        self.assertIsNone(detector.observe(5, self.proc(4.2)))
        self.assertIn("held a full core", detector.observe(7, self.proc(6.2)))


class GuardTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch, prefix="cpu-guard-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_guard(self, *args: str, timeout: float = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=timeout)

    def test_help_names_the_maintainer_and_support_route(self):
        result = self.run_guard("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Maintained by Joshua Li: https://github.com/joshuarli/usr", result.stdout)
        self.assertIn("dotfiles/base/.agents/instructions/owned-tools.md", result.stdout)

    def test_status_passes_through(self):
        self.assertEqual(self.run_guard("--", "sh", "-c", "exit 3").returncode, 3)
        self.assertEqual(self.run_guard("--", str(self.dir / "missing")).returncode, 127)
        self.assertEqual(self.run_guard("--cores", "0", "--", "true").returncode, 125)

    def test_a_tree_over_its_core_limit_is_stopped_including_detached_grandchildren(self):
        pids = self.dir / "pids"
        started = time.monotonic()
        result = self.run_guard("--cores", "1.5", "--window", "2", "--interval", "0.25", "--grace", "1", "--",
                                sys.executable, "-c", SPAWN, str(pids))
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertIn("cores over", result.stderr)
        self.assertLess(time.monotonic() - started, 15)
        spawned = [int(line) for line in pids.read_text().split()]
        self.assertEqual(len(spawned), 2)
        self.assertFalse([pid for pid in spawned if alive(pid)])

    def test_a_single_spinner_is_stopped_by_spin_even_under_the_core_limit(self):
        result = self.run_guard("--cores", "64", "--spin", "2", "--interval", "0.25", "--",
                                sys.executable, "-c", SPIN)
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertIn("held a full core", result.stderr)

    def test_light_work_completes(self):
        result = self.run_guard("--cores", "1", "--window", "1", "--spin", "5", "--interval", "0.25", "--",
                                "sh", "-c", "sleep 2; echo done")
        self.assertEqual((result.returncode, result.stdout), (0, "done\n"), result.stderr)

    def test_leftover_descendants_are_stopped_when_the_command_exits(self):
        pidfile = self.dir / "sleeper"
        result = self.run_guard("--interval", "0.25", "--grace", "1", "--",
                                "sh", "-c", f"sleep 300 & echo $! > {pidfile}; sleep 1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("leftover", result.stderr)
        self.assertFalse(alive(int(pidfile.read_text())))

    def test_a_signal_to_the_guard_stops_the_tree(self):
        pidfile = self.dir / "sleeper"
        process = subprocess.Popen([sys.executable, str(TOOL), "--interval", "0.25", "--grace", "1", "--",
                                    "sh", "-c", f"sleep 300 & echo $! > {pidfile}; wait"],
                                   stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 10
        while not (pidfile.exists() and pidfile.read_text().strip()) and time.monotonic() < deadline:
            time.sleep(0.1)
        time.sleep(0.5)
        process.send_signal(signal.SIGTERM)
        self.assertEqual(process.wait(timeout=15), 128 + signal.SIGTERM)
        self.assertFalse(alive(int(pidfile.read_text())))


if __name__ == "__main__":
    unittest.main()
