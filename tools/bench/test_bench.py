#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "tools/bench/bench.py"
WORK = ROOT / ".work/tmp"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-I", str(script), *args], capture_output=True, text=True, timeout=120)


class BenchTests(unittest.TestCase):
    def test_a_run_whose_output_fails_validation_exits_nonzero_without_timings(self):
        WORK.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            copy = Path(tmp)
            (copy / "tools/bench").mkdir(parents=True)
            shutil.copy2(BENCH, copy / "tools/bench/bench.py")
            shim = copy / "dotfiles/base/.local/bin/pinact"
            shim.parent.mkdir(parents=True)
            shim.write_text("print('.github/workflows/ci.yml:7: actions/checkout@v4')\n", encoding="utf-8")
            result = run(copy / "tools/bench/bench.py", "--only", "pinact-check", "--rounds", "1")
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("pinact-check round 1: pinact --check printed findings", result.stderr)
            self.assertNotIn("pinact-check", result.stdout)
            self.assertEqual([], os.listdir(copy / ".work/bench"))

    def test_valid_runs_report_interleaved_wall_cpu_and_rss(self):
        result = run(BENCH, "--only", "pinact-check,todo-list", "--rounds", "2", "--json")
        self.assertEqual(0, result.returncode, result.stderr)
        rows = {row["name"]: row for row in json.loads(result.stdout)["workloads"]}
        self.assertEqual({"pinact-check", "todo-list"}, set(rows))
        for row in rows.values():
            self.assertEqual(2, row["rounds"])
            self.assertLessEqual(row["wall_min_ms"], row["wall_median_ms"])
            self.assertLessEqual(row["wall_median_ms"], row["wall_max_ms"])
            self.assertGreater(row["cpu_median_ms"], 0)
            self.assertGreater(row["maxrss_mib"], 1)


if __name__ == "__main__":
    unittest.main()
