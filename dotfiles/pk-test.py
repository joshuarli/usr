#!/usr/bin/env python3
"""Live tests for pk; only disposable subprocesses created by these tests are killed."""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PK = Path(os.environ.get("PK_SCRIPT", Path(__file__).parent / "base/.local/bin/pk"))


class PkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pk-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        bindir = self.path / "bin"
        bindir.mkdir()
        fz = bindir / "fz"
        fz.write_text(
            """#!/bin/sh
set -eu
if [ "${1:-}" = --help ]; then
    printf ' -m, --multi   Mark multiple candidates\\n'
    exit 0
fi
printf '%s\\n' "$*" >> "$PK_TEST_CALLS"
case "$PK_TEST_SELECTION" in
    CANCEL) exit 1 ;;
    ERROR) printf 'fz: terminal too small\n' >&2; exit 2 ;;
    QUERY) printf '%s\\n' "$PK_TEST_QUERY"; exit 0 ;;
    SPOOF) printf '%s  fake process\\n' "$PK_TEST_PID"; exit 0 ;;
    MIXED)
        awk -v pid="$PK_TEST_PID" '$1 == pid { print; exit }'
        printf '999999  invented process\\n'
        exit 0 ;;
esac
data=$(cat)
if [ "$PK_TEST_SELECTION" = DUP ]; then
    line=$(printf '%s\n' "$data" | awk -v pid="$PK_TEST_PID" '$1 == pid { print; exit }')
    printf '%s\n%s\n' "$line" "$line"
    exit 0
fi
for pid in $PK_TEST_SELECTION; do
    printf '%s\\n' "$data" | awk -v pid="$pid" '$1 == pid { print; found=1; exit } END { if (!found) exit 9 }'
done
"""
        )
        fz.chmod(0o755)
        ps = bindir / "ps"
        ps.write_text(
            """#!/bin/sh
set -eu
if [ -n "${PK_TEST_STALE_PID:-}" ]; then
    previous=
    for arg do
        if [ "$previous" = '-p' ] && [ "$arg" = "$PK_TEST_STALE_PID" ]; then
            "$PK_TEST_REAL_PS" "$@" | awk '{ $3 = "WRONG_START"; print }'
            exit 0
        fi
        previous=$arg
    done
fi
exec "$PK_TEST_REAL_PS" "$@"
"""
        )
        ps.chmod(0o755)
        self.env = dict(os.environ)
        self.env.update(
            PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
            PK_TEST_REAL_PS=shutil.which("ps"),
            PK_TEST_CALLS=str(self.path / "calls"),
            PK_TEST_SELECTION="CANCEL",
            PK_TEST_QUERY="sleep",
        )
        self.env.pop("PK_TEST_STALE_PID", None)
        self.procs = []
        self.addCleanup(self.kill_procs)

    def kill_procs(self):
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)

    def sleep(self):
        proc = subprocess.Popen(["sleep", "60"])
        self.procs.append(proc)
        return proc

    def ignores_term(self):
        proc = subprocess.Popen(
            [sys.executable, "-u", "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready'); time.sleep(60)"],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.procs.append(proc)
        self.addCleanup(proc.stdout.close)
        self.assertEqual(proc.stdout.readline().strip(), "ready")
        return proc

    def run_pk(self, *args, **env):
        return subprocess.run(
            [str(PK), *args],
            env={**self.env, **env},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def calls(self):
        return (self.path / "calls").read_text().splitlines()

    def test_single_selection_sends_term(self):
        proc = self.sleep()
        result = self.run_pk("sleep", PK_TEST_SELECTION=str(proc.pid))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"sent TERM to {proc.pid}", result.stdout)
        self.assertEqual(len(self.calls()), 1)
        self.assertIn("--multi", self.calls()[0])
        self.assertIn("--query=sleep", self.calls()[0])
        self.assertEqual(proc.wait(timeout=5), -signal.SIGTERM)

    def test_marked_multiple_processes_killed_in_one_picker(self):
        a, b = self.sleep(), self.sleep()
        result = self.run_pk("sleep", PK_TEST_SELECTION=f"{b.pid} {a.pid}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         [f"pk: sent TERM to {b.pid}", f"pk: sent TERM to {a.pid}"])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(a.wait(timeout=5), -signal.SIGTERM)
        self.assertEqual(b.wait(timeout=5), -signal.SIGTERM)

    def test_cancel_does_not_signal(self):
        proc = self.sleep()
        result = self.run_pk("sleep", PK_TEST_SELECTION="CANCEL")
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertIsNone(proc.poll())

    def test_picker_error_is_not_treated_as_cancel(self):
        proc = self.sleep()
        result = self.run_pk("sleep", PK_TEST_SELECTION="ERROR")
        self.assertEqual(result.returncode, 2)
        self.assertIn("fz: terminal too small", result.stderr)
        self.assertIsNone(proc.poll())

    def test_unmatched_query_echo_is_not_a_pid(self):
        proc = self.sleep()
        result = self.run_pk("nonexistent", PK_TEST_SELECTION="QUERY")
        self.assertEqual(result.returncode, 1)
        self.assertIn("rejected invalid", result.stderr)
        self.assertIsNone(proc.poll())

    def test_spoofed_row_is_rejected(self):
        proc = self.sleep()
        result = self.run_pk("sleep", PK_TEST_SELECTION="SPOOF", PK_TEST_PID=str(proc.pid))
        self.assertEqual(result.returncode, 1)
        self.assertIn("rejected invalid", result.stderr)
        self.assertIsNone(proc.poll())

    def test_mixed_valid_and_invalid_selection_is_all_rejected(self):
        proc = self.sleep()
        result = self.run_pk("sleep", PK_TEST_SELECTION="MIXED", PK_TEST_PID=str(proc.pid))
        self.assertEqual(result.returncode, 1)
        self.assertIn("rejected invalid", result.stderr)
        self.assertIsNone(proc.poll())

    def test_duplicate_pid_rejected_before_signaling(self):
        proc = self.sleep()
        result = self.run_pk("sleep", PK_TEST_SELECTION="DUP", PK_TEST_PID=str(proc.pid))
        self.assertEqual(result.returncode, 1)
        self.assertIn("rejected duplicate", result.stderr)
        self.assertIsNone(proc.poll())

    def test_multiword_query_reaches_fz_unchanged(self):
        result = self.run_pk("node", "server", PK_TEST_SELECTION="CANCEL")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--query=node server", self.calls()[0])

    def test_stale_pid_is_never_signaled(self):
        proc = self.sleep()
        result = self.run_pk("sleep", PK_TEST_SELECTION=str(proc.pid),
                             PK_TEST_STALE_PID=str(proc.pid))
        self.assertEqual(result.returncode, 1)
        self.assertIn("process exited or changed", result.stderr)
        self.assertIsNone(proc.poll())

    def test_force_sends_sigkill_without_automatic_escalation(self):
        proc = self.ignores_term()
        term = self.run_pk("python", PK_TEST_SELECTION=str(proc.pid))
        self.assertEqual(term.returncode, 0, term.stderr)
        self.assertIn(f"sent TERM to {proc.pid}", term.stdout)
        self.assertIsNone(proc.poll())
        killed = self.run_pk("-9", "python", PK_TEST_SELECTION=str(proc.pid))
        self.assertEqual(killed.returncode, 0, killed.stderr)
        self.assertIn(f"sent KILL to {proc.pid}", killed.stdout)
        self.assertEqual(proc.wait(timeout=5), -signal.SIGKILL)

    def test_requires_query(self):
        result = self.run_pk()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: pk", result.stderr)

    def test_help(self):
        result = self.run_pk("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Space marks", result.stdout)


if __name__ == "__main__":
    unittest.main()
