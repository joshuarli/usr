#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "base/.local/bin/cleanup-sessions"
OLD = time.time() - 10 * 86400
NEW = time.time() - 3600


def touch(path: Path, mtime: float, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.utime(path, (mtime, mtime))
    return path


def age(path: Path, mtime: float) -> Path:
    for base, dirs, files in os.walk(path):
        for name in dirs + files:
            os.utime(os.path.join(base, name), (mtime, mtime), follow_symlinks=False)
    os.utime(path, (mtime, mtime))
    return path


class CleanupSessionsTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ.get("TMPDIR", "."))
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="cleanup-sessions-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "")}
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], env=env, capture_output=True, text=True)

    def opencode(self) -> Path:
        path = self.home / ".local/share/opencode/opencode.db"
        path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE session_v2 (id TEXT PRIMARY KEY, time_updated INTEGER NOT NULL);
                CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES session_v2(id) ON DELETE CASCADE);
            """)
            db.executemany("INSERT INTO session_v2 VALUES (?, ?)", [("old", int(OLD * 1000)), ("new", int(NEW * 1000))])
            db.executemany("INSERT INTO session_message VALUES (?, ?)", [("m1", "old"), ("m2", "new")])
        db.close()
        return path

    def test_removes_only_sessions_older_than_the_default_week_in_every_harness(self):
        uuid = "0880a3d6-8239-4673-871b-11ec8a5e787c"
        old = [
            touch(self.home / f".claude/projects/-repo/{uuid}.jsonl", OLD),
            touch(self.home / ".codex/sessions/2026/11/01/rollout-a.jsonl", OLD),
            touch(self.home / ".pi/agent/sessions/--repo--/a.jsonl", OLD),
            touch(self.home / ".commandcode/projects/repo/a.jsonl", OLD),
            touch(self.home / ".gemini/antigravity-cli/conversations/a.db", OLD),
        ]
        touch(self.home / f".claude/projects/-repo/{uuid}/subagents/a.jsonl", OLD)
        old_dir = age(self.home / f".claude/projects/-repo/{uuid}", OLD)
        touch(self.home / ".local/share/muse/sessions/2026/11/01/s1/session.jsonl", OLD)
        old_muse = age(self.home / ".local/share/muse/sessions/2026/11/01/s1", OLD)
        kept = [
            touch(self.home / ".claude/projects/-repo/new.jsonl", NEW),
            touch(self.home / ".codex/sessions/2026/11/19/rollout-b.jsonl", NEW),
            touch(self.home / ".pi/agent/sessions/--repo--/b.jsonl", NEW),
            touch(self.home / ".claude/projects/-repo/memory/MEMORY.md", OLD),
            touch(self.home / ".codex/config.toml", OLD),
        ]
        db = self.opencode()

        result = self.run_script("--json")

        self.assertEqual(0, result.returncode, result.stderr)
        report = {row["harness"]: row for row in json.loads(result.stdout)["harnesses"]}
        self.assertEqual(2, report["claude"]["removed"])
        self.assertEqual(1, report["opencode"]["removed"])
        for path in [*old, old_dir, old_muse]:
            self.assertFalse(path.exists(), path)
        for path in kept:
            self.assertTrue(path.exists(), path)
        self.assertFalse((self.home / ".codex/sessions/2026/11/01").exists())
        self.assertTrue((self.home / ".codex/sessions").is_dir())
        with sqlite3.connect(db) as conn:
            self.assertEqual([("new",)], conn.execute("SELECT id FROM session_v2").fetchall())
            self.assertEqual([("m2",)], conn.execute("SELECT id FROM session_message").fetchall())
        conn.close()

    def test_a_session_directory_with_a_recent_file_is_kept(self):
        session = self.home / ".local/share/muse/sessions/2026/11/01/s1"
        touch(session / "old.jsonl", OLD)
        touch(session / "session.jsonl", NEW)
        os.utime(session, (OLD, OLD))

        result = self.run_script()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((session / "old.jsonl").exists())

    def test_dry_run_reports_without_removing(self):
        path = touch(self.home / ".pi/agent/sessions/--repo--/a.jsonl", OLD, "abcd")
        db = self.opencode()

        result = self.run_script("--dry-run")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("pi: would remove 1 entries, 4 B", result.stdout)
        self.assertIn("opencode: would remove 1 sessions", result.stdout)
        self.assertTrue(path.exists())
        with sqlite3.connect(db) as conn:
            self.assertEqual(2, conn.execute("SELECT count(*) FROM session_v2").fetchone()[0])
        conn.close()

    def test_unqualified_copilot_state_is_preserved_and_reported(self):
        paths = [
            touch(self.home / ".copilot/session-state/old/session.jsonl", OLD),
            touch(self.home / ".copilot/session-store.db", OLD),
            touch(self.home / ".copilot/settings.json", OLD),
        ]
        result = self.run_script("--json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("copilot", json.loads(result.stdout)["not_covered"])
        for path in paths:
            self.assertEqual("x", path.read_text())
        self.assertIn("copilot", self.run_script("--dry-run").stdout)
        self.assertIn("Copilot", self.run_script("--help").stdout)

    def test_age_argument_moves_the_cutoff(self):
        path = touch(self.home / ".pi/agent/sessions/--repo--/a.jsonl", NEW)

        self.run_script("14d")
        self.assertTrue(path.exists())
        self.run_script("30m")
        self.assertFalse(path.exists())

    def test_symlinked_entries_and_roots_are_never_followed(self):
        outside = self.home / "outside"
        target = touch(outside / "keep.jsonl", OLD)
        sessions = self.home / ".pi/agent/sessions/--repo--"
        sessions.mkdir(parents=True)
        (sessions / "link.jsonl").symlink_to(target)
        (self.home / ".codex").mkdir()
        (self.home / ".codex/sessions").symlink_to(outside, target_is_directory=True)

        result = self.run_script()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(target.exists())
        self.assertTrue((sessions / "link.jsonl").is_symlink())

    def test_invalid_age_is_a_usage_error(self):
        for value in ("0d", "7", "7y", "-1d"):
            with self.subTest(value=value):
                result = self.run_script(value)
                self.assertEqual(2, result.returncode)
                self.assertIn("invalid age", result.stderr)


if __name__ == "__main__":
    unittest.main()
