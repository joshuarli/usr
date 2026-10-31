#!/usr/bin/env python3
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
WORK_TMP = ROOT / ".work" / "tmp"
WORK_TMP.mkdir(parents=True, exist_ok=True)
SRC_DIR = ROOT / "tools" / "agent-memory" / "src"
sys.path.insert(0, str(SRC_DIR))
MODULE_PATH = SRC_DIR / "agent_memory" / "store.py"
SPEC = importlib.util.spec_from_file_location("agent_session_store", MODULE_PATH)
assert SPEC is not None
STORE_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = STORE_MODULE
SPEC.loader.exec_module(STORE_MODULE)
Store = STORE_MODULE.Store
StoreError = STORE_MODULE.StoreError
project_identity = STORE_MODULE.project_identity

ARCHIVE_SPEC = importlib.util.spec_from_file_location("agent_memory_archive", SRC_DIR / "agent_memory" / "archive.py")
assert ARCHIVE_SPEC is not None
ARCHIVE = importlib.util.module_from_spec(ARCHIVE_SPEC)
assert ARCHIVE_SPEC.loader is not None
sys.modules[ARCHIVE_SPEC.name] = ARCHIVE
ARCHIVE_SPEC.loader.exec_module(ARCHIVE)

LINE = ('{"timestamp":"2026-10-30T00:00:00Z","type":"response_item","payload":'
        '{"type":"message","role":"user","content":[{"type":"input_text","text":"%s"}]}}\n')


def line(text):
    return LINE % text


def header(cwd, session="a"):
    return json.dumps({"timestamp": "2026-10-30T00:00:00Z", "type": "session_meta",
                       "payload": {"id": session, "cwd": str(cwd)}}, separators=(",", ":")) + "\n"


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.sessions = self.root / "sessions"
        self.sessions.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.project_id = project_identity(self.project)
        self.path = self.sessions / "rollout-a.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, text):
        self.path.write_text(header(self.project) + line(text))

    def refresh(self, store):
        return store.refresh([self.sessions], project=self.project_id)

    def generations(self, store):
        return store.db.execute("SELECT count(*) FROM archive_generation").fetchone()[0]

    def test_unchanged_refresh_reads_no_content_and_captures_nothing(self):
        self.write("alpha")
        with Store(self.state) as store:
            first = self.refresh(store)
            self.assertEqual(first["archived"], 1)
            before = self.generations(store)
            noop = self.refresh(store)
            self.assertEqual((noop["bytes_read"], noop["content_opens"]), (0, 0))
            self.assertEqual(self.generations(store), before)
            self.assertEqual(noop["archive_bytes"], 0)

    def test_append_writes_only_the_delta_and_keeps_both_generations(self):
        self.path.write_text(header(self.project) + line("x" * 4090))
        with self.path.open("a") as stream:
            while self.path.stat().st_size < 4 * 1024 * 1024:
                stream.write(line("x" * 4090))
        with Store(self.state) as store:
            self.refresh(store)
            first = self.generations(store)
            appended = line("one more line")
            with self.path.open("a") as stream:
                stream.write(appended)
            stats = self.refresh(store)
            self.assertEqual(self.generations(store), first + 1)
            self.assertLessEqual(stats["archive_bytes"], len(appended) + 65536)
            self.assertLessEqual(stats["bytes_read"], len(appended) + 65536)
            self.assertEqual(stats["archive_objects"], 1)

    def test_equal_size_rewrite_with_restored_timestamp_creates_a_generation(self):
        self.write("alpha")
        with Store(self.state) as store:
            self.refresh(store)
            first = self.generations(store)
            info = self.path.stat()
            rewritten = self.path.read_text().replace('"alpha"', '"bravo"')
            self.assertEqual(len(rewritten.encode()), info.st_size)
            self.path.write_text(rewritten)
            os.utime(self.path, ns=(info.st_atime_ns, info.st_mtime_ns))
            stats = self.refresh(store)
            self.assertEqual(stats["resets"], 1)
            self.assertEqual(self.generations(store), first + 1)
            hit = store.search("bravo", self.project_id)[0]
            self.assertEqual(store.resolve_evidence(hit["session"], hit["position"], hit["digest"])["text"], "bravo")
            old = store.db.execute("SELECT min(id) FROM archive_generation").fetchone()[0]
            self.assertEqual(ARCHIVE.read_generation(store.db, store.archive_dir, old).count(b"alpha"), 1)

    def test_truncation_keeps_the_previous_generation(self):
        self.write("first version body")
        with Store(self.state) as store:
            self.refresh(store)
            first = self.generations(store)
            self.path.write_text(header(self.project) + line("short"))
            stats = self.refresh(store)
            self.assertEqual(self.generations(store), first + 1)
            self.assertEqual(stats["resets"], 1)
            oldest = store.db.execute("SELECT min(id) FROM archive_generation").fetchone()[0]
            self.assertIn(b"first version body", ARCHIVE.read_generation(store.db, store.archive_dir, oldest))

    def test_capture_refuses_a_symlink_and_a_directory_source(self):
        self.write("alpha")
        with Store(self.state) as store:
            self.refresh(store)
            link = self.sessions / "link.jsonl"
            link.symlink_to(self.path)
            with self.assertRaises(OSError):
                ARCHIVE.capture(store.db, store.archive_dir, "codex", "linked", link)
            directory = self.sessions / "dir.jsonl"
            directory.mkdir()
            with self.assertRaises(OSError):
                ARCHIVE.capture(store.db, store.archive_dir, "codex", "dir", directory)

    def test_interrupted_publication_leaves_no_partial_generation(self):
        self.write("alpha")
        with Store(self.state) as store:
            self.refresh(store)
            first = self.generations(store)
            with self.path.open("a") as stream:
                stream.write(line("beta"))
            with mock.patch.object(ARCHIVE, "_fsync_directory", side_effect=OSError("disk gone")):
                with self.assertRaises(OSError):
                    ARCHIVE.capture(store.db, store.archive_dir, "codex", "a", self.path)
            self.assertEqual(self.generations(store), first)
            with self.path.open("a") as stream:
                stream.write(line("gamma"))
            store.refresh([self.sessions], project=self.project_id)
            self.assertEqual(self.generations(store), first + 1)
            newest = store.db.execute("SELECT max(id) FROM archive_generation").fetchone()[0]
            self.assertIn(b"gamma", ARCHIVE.read_generation(store.db, store.archive_dir, newest))

    def test_disk_full_is_reported_and_keeps_the_previous_generation(self):
        self.write("alpha")
        with Store(self.state) as store:
            self.refresh(store)
            first = self.generations(store)
            with self.path.open("a") as stream:
                stream.write(line("beta"))
            original = os.write
            calls = {"n": 0}

            def failing(descriptor, data):
                calls["n"] += 1
                if calls["n"] > 0:
                    raise OSError(28, "No space left on device")
                return original(descriptor, data)

            with mock.patch.object(ARCHIVE.os, "write", side_effect=failing):
                stats = self.refresh(store)
            self.assertGreaterEqual(stats["archive_errors"], 1)
            self.assertEqual(self.generations(store), first)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 1)
            self.assertTrue(any(p.name.startswith(".tmp.") is False for p in (self.state / "archive" / "objects").rglob("*")))

    def test_concurrent_collectors_publish_distinct_objects(self):
        self.write("alpha")
        results = []

        def collect():
            with Store(self.state) as store:
                store.refresh([self.sessions], project=self.project_id)
                results.append(store.db.execute("SELECT count(*) FROM archive_generation").fetchone()[0])

        threads = [threading.Thread(target=collect) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 3)
        with Store(self.state) as store:
            self.assertEqual(self.generations(store), 1)
            digests = [row[0] for row in store.db.execute("SELECT digest FROM archive_object")]
            self.assertEqual(len(digests), len(set(digests)))
            for digest in digests:
                self.assertTrue(ARCHIVE.object_path(store.archive_dir, digest).is_file())

    def test_capture_never_links_the_source_and_works_on_another_filesystem(self):
        self.write("alpha")
        other = self.root / "other-state"
        with Store(other) as store:
            self.refresh(store)
            source_info = self.path.stat()
            digest = store.db.execute("SELECT digest FROM archive_object").fetchone()[0]
            object_info = ARCHIVE.object_path(store.archive_dir, digest).stat()
            self.assertNotEqual((source_info.st_dev, source_info.st_ino), (object_info.st_dev, object_info.st_ino))
            self.assertEqual(source_info.st_ino, self.path.stat().st_ino)

    def test_evidence_resolves_from_the_generation_after_source_deletion(self):
        self.write("surviving evidence")
        with Store(self.state) as store:
            self.refresh(store)
            hit = store.search("surviving", self.project_id)[0]
            expected = store.resolve_evidence(hit["session"], hit["position"], hit["digest"])["text"]
            self.path.unlink()
            stats = self.refresh(store)
            self.assertEqual(stats["sessions_seen"], 0)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 1)
            self.assertEqual(store.resolve_evidence(hit["session"], hit["position"], hit["digest"])["text"], expected)

    def test_forget_removes_the_generation_and_records_a_tombstone(self):
        self.write("forget me")
        with Store(self.state) as store:
            self.refresh(store)
            session = store.db.execute("SELECT id FROM sessions").fetchone()[0]
            digest = store.db.execute("SELECT digest FROM archive_object").fetchone()[0]
            store.forget_session(session, 1000.0)
            self.assertEqual(self.generations(store), 0)
            self.assertFalse(ARCHIVE.object_path(store.archive_dir, digest).exists())
            self.assertEqual(store.db.execute("SELECT count(*) FROM tombstone").fetchone()[0], 1)
            self.refresh(store)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
