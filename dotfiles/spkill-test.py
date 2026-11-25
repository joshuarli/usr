#!/usr/bin/env python3
"""Live tests for spkill; only disposable subprocesses created by these tests are signaled."""

import os
import signal
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path

SPKILL = Path(os.environ.get("SPKILL_SCRIPT", Path(__file__).parent / "base/.local/bin/spkill"))


def spkill(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-I", str(SPKILL), *args], capture_output=True, text=True, timeout=30)


class SpkillTests(unittest.TestCase):
    def setUp(self):
        self.marker = f"spkill-test-{uuid.uuid4().hex}"

    def sleeper(self, marker: str | None = None) -> subprocess.Popen[bytes]:
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", marker or self.marker],
                                stderr=subprocess.DEVNULL)
        self.addCleanup(self.reap, proc)
        deadline = time.monotonic() + 10
        while spkill("--list", marker or self.marker).returncode != 0:
            self.assertLess(time.monotonic(), deadline, "sleeper never became visible")
            time.sleep(0.05)
        return proc

    @staticmethod
    def reap(proc: subprocess.Popen[bytes]) -> None:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
        if proc.stdout:
            proc.stdout.close()

    def test_signals_match_and_spares_the_shell_running_it(self):
        target = self.sleeper()
        shell = subprocess.run(
            ["/bin/sh", "-c", f'"{sys.executable}" -I "{SPKILL}" --wait 10 "{self.marker}"; echo "shell survived $?"'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(shell.stdout.strip(), "shell survived 0", shell.stderr)
        self.assertEqual(target.wait(timeout=10), -signal.SIGTERM)
        self.assertIn(f"sent SIGTERM to {target.pid} ", shell.stderr)

    def test_list_is_a_self_safe_pgrep(self):
        target = self.sleeper()
        listed = spkill("--list", self.marker)
        self.assertEqual(listed.returncode, 0)
        self.assertEqual([line.split()[0] for line in listed.stdout.splitlines()], [str(target.pid)])
        self.assertIsNone(target.poll(), "--list must not signal")
        absent = subprocess.run(
            ["/bin/sh", "-c", f'"{sys.executable}" -I "{SPKILL}" --list "{self.marker}-absent"'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual((absent.returncode, absent.stdout), (1, ""))

    def test_named_and_numbered_signals(self):
        first = self.sleeper(self.marker + "-a")
        self.assertEqual(spkill("-KILL", "--wait", "10", self.marker + "-a").returncode, 0)
        self.assertEqual(first.wait(timeout=10), -signal.SIGKILL)
        second = self.sleeper(self.marker + "-b")
        self.assertEqual(spkill("-s", "2", "--wait", "10", self.marker + "-b").returncode, 0)
        self.assertEqual(second.wait(timeout=10), -signal.SIGINT)

    def test_wait_times_out_on_an_ignored_signal(self):
        proc = subprocess.Popen([
            sys.executable, "-c",
            "import signal, time; signal.signal(signal.SIGUSR1, signal.SIG_IGN); print('ready', flush=True); time.sleep(60)",
            self.marker,
        ], stdout=subprocess.PIPE)
        self.addCleanup(self.reap, proc)
        stdout = proc.stdout
        assert stdout is not None
        self.assertEqual(stdout.readline().strip(), b"ready")
        result = spkill("-USR1", "--wait", "0.5", self.marker)
        self.assertEqual(result.returncode, 3)
        self.assertIn("still running", result.stderr)
        self.assertIsNone(proc.poll())

    def test_no_match_exits_one(self):
        self.assertEqual(spkill(self.marker + "-nothing").returncode, 1)

    def test_refuses_unsafe_patterns_and_bad_usage(self):
        for args in ([""], [" "], [".*"], ["a|"], ["-NOPE", "x"], ["--wait", "soon", "x"], ["x", "y"], ["("]):
            with self.subTest(args=args):
                result = spkill(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("usage: spkill", result.stderr)

    def test_refuses_many_matches_without_flag(self):
        procs = [self.sleeper(f"{self.marker}-{i}") for i in range(21)]
        refused = spkill(self.marker)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("21 processes match", refused.stderr)
        self.assertTrue(all(p.poll() is None for p in procs))
        self.assertEqual(spkill("--many", "--wait", "10", self.marker).returncode, 0)
        self.assertTrue(all(p.wait(timeout=10) == -signal.SIGTERM for p in procs))

    def test_help(self):
        result = spkill("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("never matches itself or any of its", result.stdout)
        self.assertIn("Maintained by Joshua Li: https://github.com/joshuarli/usr", result.stdout)


if __name__ == "__main__":
    unittest.main()
