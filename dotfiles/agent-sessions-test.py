#!/usr/bin/env python3
import importlib.util
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORK_TMP = ROOT / ".work" / "tmp"
WORK_TMP.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "dotfiles" / "base" / ".local" / "bin"))
MODULE_PATH = ROOT / "dotfiles" / "base" / ".local" / "bin" / "agent_session_store.py"
SPEC = importlib.util.spec_from_file_location("agent_session_store", MODULE_PATH)
STORE_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = STORE_MODULE
SPEC.loader.exec_module(STORE_MODULE)
Store = STORE_MODULE.Store
StoreError = STORE_MODULE.StoreError
normalize = STORE_MODULE.normalize
project_identity = STORE_MODULE.project_identity
redact = STORE_MODULE.redact
rebuild_index = STORE_MODULE.rebuild_index
CLI_PATH = ROOT / "dotfiles" / "base" / ".local" / "bin" / "agent-sessions"


def metadata(session, cwd, parent=None, source="cli", thread_source="user"):
    payload = {"id": session, "cwd": str(cwd), "source": source, "thread_source": thread_source}
    if parent:
        payload["parent_thread_id"] = parent
    return {"type": "session_meta", "payload": payload}


def message(text, role="user", timestamp="2026-10-23T12:00:00Z"):
    return {
        "type": "response_item",
        "timestamp": timestamp,
        "payload": {"type": "message", "role": role, "content": [{"type": "input_text", "text": text}]},
    }


def line(obj):
    return (json.dumps(obj, separators=(",", ":")) + "\n").encode()


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.transcripts = self.root / "sessions"
        self.transcripts.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.project_id = project_identity(self.project)

    def tearDown(self):
        self.temp.cleanup()

    def transcript(self, session="s1", cwd=None, records=(), root=None, name=None):
        path_root = Path(root) if root else self.transcripts
        path_root.mkdir(parents=True, exist_ok=True)
        path = path_root / (name or ("rollout-" + session + ".jsonl"))
        path.write_bytes(b"".join(line(record) for record in (metadata(session, cwd or self.project), *records)))
        return path

    def test_normalize_keeps_text_call_provenance_and_unknown_variants(self):
        codex = normalize({
            "type": "response_item", "timestamp": "now",
            "payload": {"type": "custom_tool_call", "name": "Read", "call_id": "c1", "input": {"path": "src/main.py"}},
        })[0]
        self.assertEqual(codex["kind"], "tool-call")
        self.assertEqual(codex["call_id"], "c1")
        self.assertIn("src/main.py", codex["text"])
        unknown = normalize({"type": "response_item", "payload": {"type": "future_event", "detail": "retained"}})[0]
        self.assertEqual(unknown["kind"], "response_item:future_event")
        self.assertIn("retained", unknown["text"])
        self.assertEqual(normalize({"type": "user", "content": "hello"}, "claude")[0]["text"], "hello")
        self.assertEqual(normalize({"type": "user", "content": ["hello"]}, "grok")[0]["text"], "hello")
        self.assertEqual(normalize({"payload": {"event": {"kind": "model_user_messages", "messages": ["hello"]}}}, "muse")[0]["text"], "hello")

    def test_project_refresh_limits_body_reads_and_preserves_other_project(self):
        other = self.root / "other"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        self.transcript("a1", self.project, [message("almanacneedle")])
        self.transcript("b1", other, [message("unrelatedneedle")], name="rollout-b1.jsonl")
        with Store(self.state) as store:
            first = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(first["sessions_indexed"], 1)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 1)
            self.assertEqual(store.search("almanacneedle", self.project_id)[0]["session"], "a1")
            self.assertEqual(store.search("unrelatedneedle", self.project_id), [])
            other_id = project_identity(other)
            second = store.refresh([self.transcripts], project=other_id)
            self.assertGreater(second["content_opens"], 0)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 2)
            self.assertEqual(store.search("almanacneedle", other_id), [])

    def test_projects_refresh_reuses_metadata_for_shared_roots(self):
        others = []
        project_ids = [self.project_id]
        for index in range(2):
            project = self.root / ("other-%d" % index)
            project.mkdir()
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            others.append(project)
            project_ids.append(project_identity(project))
        for index, project in enumerate((self.project, *others)):
            self.transcript("shared-%d" % index, project, [message("sharedneedle%d" % index)])
        with Store(self.state) as store:
            first = store.refresh([self.transcripts], projects=project_ids)
            self.assertEqual(first["sessions_seen"], 3)
            self.assertEqual(first["sessions_indexed"], 3)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 3)
            before = store.db.total_changes
            noop = store.refresh([self.transcripts], projects=iter(project_ids))
            self.assertEqual(noop["stat_operations"], 3)
            self.assertEqual(noop["content_opens"], 0)
            self.assertEqual(noop["bytes_read"], 0)
            self.assertEqual(noop["git_processes"], 0)
            self.assertEqual(noop["sqlite_changes"], 0)
            self.assertEqual(store.db.total_changes, before)
            selected = store.refresh([self.transcripts], projects={project_ids[1]})
            self.assertEqual(selected["sessions_seen"], 3)
            self.assertEqual(selected["sessions_indexed"], 1)
            self.assertEqual(selected["skipped_project"], 2)
            self.assertEqual(selected["content_opens"], 0)
            with self.assertRaisesRegex(ValueError, "either project or projects"):
                store.refresh([self.transcripts], project=project_ids[0], projects=project_ids)
            moved = self.root / "moved"
            moved.mkdir()
            subprocess.run(["git", "init", "-q", str(moved)], check=True)
            moved_path = self.transcripts / "rollout-shared-0.jsonl"
            moved_path.write_bytes(line(metadata("shared-0", moved)) + line(message("movedneedle")))
            moved_stats = store.refresh([self.transcripts], projects={project_ids[0]})
            self.assertEqual(moved_stats["deleted"], 1)
            self.assertIsNone(store.db.execute("SELECT 1 FROM sessions WHERE id='shared-0'").fetchone())

    def test_unindexed_header_cache_avoids_disabled_and_worker_content_reads(self):
        other_projects = []
        project_ids = [self.project_id]
        for index in range(2):
            project = self.root / ("cache-project-%d" % index)
            project.mkdir()
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            other_projects.append(project)
            project_ids.append(project_identity(project))
        projects = [self.project, *other_projects]
        for project_index, project in enumerate(projects):
            for session_index in range(2):
                self.transcript(
                    "cached-%d-%d" % (project_index, session_index),
                    project,
                    [message("cachemarker%d%d" % (project_index, session_index))],
                )
        worker = self.transcripts / "rollout-cache-worker.jsonl"
        worker.write_bytes(
            line(metadata("cache-worker", self.project, source={"learning_worker": True}))
            + line(message("workerbodymustnotindex"))
        )
        with Store(self.state) as store:
            first = store.refresh([self.transcripts], projects={project_ids[0]})
            self.assertEqual(first["sessions_indexed"], 2)
            self.assertEqual(first["skipped_learning_workers"], 1)
            self.assertEqual(first["content_opens"], 9)
            self.assertEqual(first["git_processes"], 3)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 2)
            self.assertEqual(store.db.execute("SELECT count(*) FROM unindexed_sources").fetchone()[0], 5)
            self.assertEqual(store.search("workerbodymustnotindex"), [])
            self.assertEqual(store.search("cachemarker10"), [])
            noop = store.refresh([self.transcripts], projects={project_ids[0]})
            self.assertEqual(noop["content_opens"], 0)
            self.assertEqual(noop["bytes_read"], 0)
            self.assertEqual(noop["git_processes"], 0)
            self.assertEqual(noop["sqlite_changes"], 0)
            self.assertEqual(noop["stat_operations"], 7)
            enabled = store.refresh([self.transcripts], projects={project_ids[1]})
            self.assertEqual(enabled["sessions_indexed"], 2)
            self.assertEqual(enabled["content_opens"], 2)
            self.assertEqual(enabled["git_processes"], 0)
            self.assertEqual(store.db.execute("SELECT count(*) FROM unindexed_sources").fetchone()[0], 3)
            self.assertEqual(len(store.search("cachemarker10", project_ids[1])), 1)
            self.assertEqual(store.search("cachemarker20"), [])
            self.assertEqual(store.search("workerbodymustnotindex"), [])

    def test_append_partial_malformed_and_noop_refresh(self):
        path = self.transcript("append", records=[message("firstneedle")])
        partial = json.dumps(message("secondneedle"), separators=(",", ":")).encode()
        with path.open("ab") as stream:
            stream.write(partial)
        with Store(self.state) as store:
            first = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(first["partial_files"], 1)
            self.assertEqual(first["content_opens"], 2)
            self.assertEqual(store.db.execute("SELECT partial_bytes FROM sessions WHERE id='append'").fetchone()[0], len(partial))
            self.assertEqual(store.db.execute("SELECT count(*) FROM events WHERE session='append'").fetchone()[0], 2)
            partial_noop = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(partial_noop["partial_files"], 1)
            self.assertEqual(partial_noop["content_opens"], 0)
            self.assertEqual(partial_noop["bytes_read"], 0)
            self.assertEqual(partial_noop["sqlite_changes"], 0)
            with path.open("ab") as stream:
                stream.write(b"\nnot-json\n")
            second = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(second["events_added"], 1)
            self.assertEqual(second["content_opens"], 3)
            self.assertEqual(second["malformed_lines"], 1)
            row = store.db.execute("SELECT malformed_lines, partial_bytes, coverage FROM sessions WHERE id='append'").fetchone()
            self.assertEqual(tuple(row), (1, 0, "degraded"))
            changes = store.db.total_changes
            noop = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(noop["events_added"], 0)
            self.assertEqual(noop["content_opens"], 0)
            self.assertEqual(noop["bytes_read"], 0)
            self.assertEqual(noop["git_processes"], 0)
            self.assertEqual(noop["sqlite_changes"], 0)
            self.assertEqual(store.db.total_changes, changes)
            self.assertEqual(noop["malformed_lines"], 0)
            self.assertEqual(store.db.execute("SELECT count(*) FROM events WHERE session='append'").fetchone()[0], 3)

    def test_incomplete_index_progress_retries_with_matching_metadata(self):
        self.transcript("interrupted", records=[message("recoverme")])
        with Store(self.state) as store:
            store.refresh([self.transcripts], project=self.project_id)
            with store.db:
                store.db.execute("DELETE FROM events WHERE session='interrupted'")
                store.db.execute(
                    "UPDATE sessions SET indexed_bytes=0, checkpoint_position=NULL, checkpoint_digest=NULL, partial_bytes=0 "
                    "WHERE id='interrupted'"
                )
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(stats["resets"], 0)
            self.assertEqual(stats["events_added"], 2)
            self.assertEqual(stats["content_opens"], 1)
            self.assertEqual(store.db.execute("SELECT indexed_bytes=file_size FROM sessions WHERE id='interrupted'").fetchone()[0], 1)
            self.assertEqual(len(store.search("recoverme", self.project_id)), 1)

    def test_append_after_eof_before_final_stat_is_read_next_refresh(self):
        path = self.transcript("eof-race", records=[message("beforeappend")])
        appended = line(message("afterappend"))
        original_fstat = STORE_MODULE._fstat_source
        did_append = [False]

        def append_before_final_stat(stream, stats):
            if not did_append[0] and stream.tell() == path.stat().st_size:
                with path.open("ab") as source:
                    source.write(appended)
                did_append[0] = True
            return original_fstat(stream, stats)

        with Store(self.state) as store:
            STORE_MODULE._fstat_source = append_before_final_stat
            try:
                first = store.refresh([self.transcripts], project=self.project_id)
            finally:
                STORE_MODULE._fstat_source = original_fstat
            self.assertTrue(did_append[0])
            self.assertEqual(first["events_added"], 2)
            progress = store.db.execute(
                "SELECT indexed_bytes, partial_bytes, file_size FROM sessions WHERE id='eof-race'"
            ).fetchone()
            self.assertLess(progress["indexed_bytes"] + progress["partial_bytes"], progress["file_size"])
            second = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(second["events_added"], 1)
            self.assertEqual(len(store.search("afterappend", self.project_id)), 1)

    def test_same_size_rewrite_with_restored_mtime_resets_index(self):
        path = self.transcript("rewrite", records=[message("oldneedle")])
        with Store(self.state) as store:
            store.refresh([self.transcripts], project=self.project_id)
            previous = path.stat()
            changed = path.read_bytes().replace(b"oldneedle", b"newneedle")
            path.write_bytes(changed)
            os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(stats["resets"], 1)
            self.assertGreater(stats["content_opens"], 0)
            self.assertEqual(store.search("oldneedle", self.project_id), [])
            self.assertEqual(len(store.search("newneedle", self.project_id)), 1)

    def test_replacement_archive_move_deletion_and_evidence_digest(self):
        path = self.transcript("move", records=[message("oldneedle")])
        archived = self.root / "archive"
        archived.mkdir()
        with Store(self.state) as store:
            store.refresh([self.transcripts, archived], project=self.project_id)
            old = store.search("oldneedle", self.project_id)[0]
            evidence = store.resolve_evidence(old["session"], old["position"], old["digest"])
            self.assertEqual(evidence["text"], "oldneedle")
            path.write_bytes(line(metadata("move", self.project)) + line(message("newneedle")))
            stats = store.refresh([self.transcripts, archived], project=self.project_id)
            self.assertEqual(stats["resets"], 1)
            self.assertEqual(store.search("oldneedle", self.project_id), [])
            self.assertEqual(len(store.search("newneedle", self.project_id)), 1)
            archived_path = archived / path.name
            path.rename(archived_path)
            stats = store.refresh([self.transcripts, archived], project=self.project_id)
            self.assertEqual(stats["resets"], 1)
            self.assertEqual(store.db.execute("SELECT source_path FROM sessions WHERE id='move'").fetchone()[0], str(archived_path.resolve()))
            archived_path.unlink()
            stats = store.refresh([self.transcripts, archived], project=self.project_id)
            self.assertEqual(stats["deleted"], 1)
            self.assertEqual(store.db.execute("SELECT count(*) FROM events").fetchone()[0], 0)

    def test_parent_source_and_learning_worker_filter(self):
        self.transcript(
            "child",
            records=[message("childneedle")],
            name="rollout-child.jsonl",
        )
        child_path = self.transcripts / "rollout-child.jsonl"
        child_path.write_bytes(
            line(metadata("child", self.project, source={"subagent": {"thread_spawn": {"depth": 1, "parent_thread_id": "root"}}}, thread_source="subagent"))
            + line(message("childneedle"))
        )
        worker = self.transcripts / "rollout-worker.jsonl"
        worker.write_bytes(line(metadata("worker", self.project, source={"learning_worker": True})) + line(message("secretworker")))
        with Store(self.state) as store:
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(stats["skipped_learning_workers"], 1)
            row = store.db.execute("SELECT source, parent, thread_source FROM sessions WHERE id='child'").fetchone()
            self.assertEqual(row["thread_source"], "subagent")
            self.assertEqual(row["parent"], "root")
            self.assertIn('"subagent"', row["source"])
            self.assertEqual(len(store.search("childneedle", self.project_id)), 1)
            self.assertEqual(store.search("secretworker", self.project_id), [])

    def test_rebuild_preserves_learning_tables_and_newer_schema_is_not_destroyed(self):
        self.transcript("s1", records=[message("keepneedle")])
        with Store(self.state) as store:
            store.db.execute("CREATE TABLE learning_hints (id TEXT PRIMARY KEY, text TEXT)")
            store.db.execute("INSERT INTO learning_hints VALUES ('h1', 'keep')")
            store.refresh([self.transcripts], project=self.project_id)
        rebuild_index(self.state)
        with Store(self.state) as store:
            self.assertEqual(store.db.execute("SELECT text FROM learning_hints WHERE id='h1'").fetchone()[0], "keep")
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)
        path = Store.database_path(self.state)
        with sqlite3.connect(path) as db:
            db.execute("PRAGMA user_version = 99")
        with self.assertRaisesRegex(StoreError, "newer"):
            Store(self.state)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute("SELECT text FROM learning_hints WHERE id='h1'").fetchone()[0], "keep")

    @staticmethod
    def downgrade_v4_columns(db, sessions=True):
        db.execute("ALTER TABLE events DROP COLUMN outcome")
        db.execute("DROP TABLE forgotten_sessions")
        if sessions:
            for column in ("native_id", "ancestry", "recognized_events", "unrecognized_events"):
                db.execute("ALTER TABLE sessions DROP COLUMN " + column)

    def test_schema_v1_migrates_metadata_without_rebuilding_index(self):
        self.transcript("legacy", records=[message("legacyevidence")])
        with Store(self.state) as store:
            store.db.execute("CREATE TABLE learning_hints (id TEXT PRIMARY KEY, text TEXT)")
            store.db.execute("INSERT INTO learning_hints VALUES ('h1', 'keep')")
            store.refresh([self.transcripts], project=self.project_id)
        path = Store.database_path(self.state)
        with sqlite3.connect(path) as db:
            db.execute("PRAGMA foreign_keys = OFF")
            db.execute("PRAGMA legacy_alter_table = ON")
            self.downgrade_v4_columns(db, sessions=False)
            db.execute("DROP INDEX sessions_project_updated")
            db.execute("DROP INDEX sessions_parent")
            db.execute("DROP TABLE unindexed_sources")
            db.execute("ALTER TABLE sessions RENAME TO sessions_v2")
            db.execute(
                "CREATE TABLE sessions ("
                "id TEXT PRIMARY KEY, project TEXT, cwd TEXT NOT NULL, parent TEXT, source TEXT, "
                "thread_source TEXT, harness TEXT NOT NULL, source_path TEXT NOT NULL, updated REAL NOT NULL, "
                "file_size INTEGER NOT NULL, file_mtime_ns INTEGER NOT NULL, file_dev INTEGER NOT NULL, "
                "file_ino INTEGER NOT NULL, indexed_bytes INTEGER NOT NULL DEFAULT 0, header_digest TEXT NOT NULL, "
                "checkpoint_position INTEGER, checkpoint_digest TEXT, malformed_lines INTEGER NOT NULL DEFAULT 0, "
                "partial_bytes INTEGER NOT NULL DEFAULT 0, coverage TEXT NOT NULL DEFAULT 'complete')"
            )
            db.execute(
                "INSERT INTO sessions SELECT id, project, cwd, parent, source, thread_source, harness, source_path, updated, "
                "file_size, file_mtime_ns, file_dev, file_ino, indexed_bytes, header_digest, checkpoint_position, "
                "checkpoint_digest, malformed_lines, partial_bytes, coverage FROM sessions_v2"
            )
            db.execute("DROP TABLE sessions_v2")
            db.execute("CREATE INDEX sessions_project_updated ON sessions(project, updated DESC)")
            db.execute("CREATE INDEX sessions_parent ON sessions(parent)")
            db.execute("PRAGMA user_version = 1")
        with Store(self.state) as store:
            self.assertEqual(store.db.execute("PRAGMA user_version").fetchone()[0], 4)
            self.assertIsNone(store.db.execute("SELECT file_ctime_ns FROM sessions WHERE id='legacy'").fetchone()[0])
            self.assertEqual(store.db.execute("SELECT text FROM learning_hints WHERE id='h1'").fetchone()[0], "keep")
            self.assertEqual(store.db.execute("SELECT count(*) FROM events WHERE session='legacy'").fetchone()[0], 2)
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(stats["events_added"], 0)
            self.assertEqual(stats["resets"], 0)
            self.assertGreater(stats["content_opens"], 0)
            self.assertEqual(store.db.execute("SELECT file_ctime_ns FROM sessions WHERE id='legacy'").fetchone()[0], self.transcripts.joinpath("rollout-legacy.jsonl").stat().st_ctime_ns)

    def test_schema_v2_migrates_unindexed_header_cache(self):
        self.transcript("legacy-v2", records=[message("v2evidence")])
        with Store(self.state) as store:
            store.refresh([self.transcripts], project=self.project_id)
        path = Store.database_path(self.state)
        with sqlite3.connect(path) as db:
            db.execute("DROP TABLE unindexed_sources")
            self.downgrade_v4_columns(db)
            db.execute("PRAGMA user_version = 2")
        with Store(self.state) as store:
            self.assertEqual(store.db.execute("PRAGMA user_version").fetchone()[0], 4)
            self.assertEqual(store.db.execute("SELECT count(*) FROM events WHERE session='legacy-v2'").fetchone()[0], 2)
            self.assertEqual(store.db.execute("SELECT count(*) FROM unindexed_sources").fetchone()[0], 0)
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(stats["events_added"], 0)
            self.assertEqual(stats["resets"], 0)
            self.assertEqual(stats["content_opens"], 0)
            self.assertEqual(stats["bytes_read"], 0)
            self.assertEqual(stats["git_processes"], 0)

    def test_populated_v3_database_from_the_previous_release_migrates_in_place(self):
        ref = "6e301c4"
        shown = subprocess.run(["git", "-C", str(ROOT), "show", ref + ":dotfiles/base/.local/bin/agent_session_store.py"], capture_output=True)
        if shown.returncode:
            self.skipTest("previous release revision is not available in this checkout")
        old_path = self.root / "agent_session_store_v3.py"
        old_path.write_bytes(shown.stdout)
        spec = importlib.util.spec_from_file_location("agent_session_store_v3", old_path)
        old = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = old
        spec.loader.exec_module(old)
        self.transcript("legacy-a", records=[message("legacyneedle one"), message("legacyneedle two", "assistant")])
        self.transcript("legacy-b", records=[message("another legacyneedle")])
        with old.Store(self.state) as store:
            store.db.execute("CREATE TABLE learning_hints (id TEXT PRIMARY KEY, text TEXT)")
            store.db.execute("INSERT INTO learning_hints VALUES ('h1', 'keep')")
            store.db.commit()
            store.refresh([self.transcripts], project=self.project_id)
            before = [tuple(row) for row in store.db.execute("SELECT session, position, digest, kind FROM events ORDER BY session, position")]
        with Store(self.state) as store:
            self.assertEqual(store.db.execute("PRAGMA user_version").fetchone()[0], 4)
            after = [tuple(row) for row in store.db.execute("SELECT session, position, digest, kind FROM events ORDER BY session, position")]
            self.assertEqual(before, after)
            self.assertEqual(store.db.execute("SELECT text FROM learning_hints").fetchone()[0], "keep")
            rows = store.db.execute("SELECT id, native_id, ancestry, coverage, recognized_events FROM sessions ORDER BY id").fetchall()
            self.assertEqual([(row["id"], row["native_id"], row["ancestry"], row["coverage"]) for row in rows], [("legacy-a", "legacy-a", "known", "complete"), ("legacy-b", "legacy-b", "known", "complete")])
            self.assertTrue(all(row["recognized_events"] > 0 for row in rows))
            hit = store.search("legacyneedle", self.project_id)[0]
            self.assertEqual(store.resolve_evidence(hit["session"], hit["position"], hit["digest"])["session"], hit["session"])
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual((stats["resets"], stats["events_added"], stats["bytes_read"]), (0, 0, 0))

    def test_git_worktrees_share_project_identity(self):
        repo = self.root / "git-repo"
        worktree = self.root / "git-worktree"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        (repo / "file").write_text("one")
        subprocess.run(["git", "-C", str(repo), "add", "file"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb", "other", str(worktree)], check=True)
        self.assertEqual(project_identity(repo), project_identity(worktree))

    def test_cli_search_redacts_credentials_and_supports_regex(self):
        token = "ghp_1234567890abcdefghijklmnop"
        self.transcript("cli", records=[message("needle Authorization: Bearer " + token)])
        result = subprocess.run(
            [sys.executable, "-I", str(CLI_PATH), "search", "needle", "--state-dir", str(self.state), "--root", str(self.transcripts)],
            cwd=self.project,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertIn("matches=1", result.stdout)
        self.assertNotIn(token, result.stdout)
        self.assertIn("[REDACTED]", result.stdout)
        self.assertIn("byte=", result.stdout)
        self.assertIn('project="' + str(self.project) + '"', result.stdout)
        with Store(self.state) as store:
            matches = store.search("needle.*Bearer", self.project_id, regex=True)
            self.assertEqual(len(matches), 1)
            position = store.search("needle", self.project_id)[0]["position"]
        shown = subprocess.run(
            [sys.executable, "-I", str(CLI_PATH), "show", "cli", "--position", str(position), "--before", "0", "--after", "0", "--kind", "user", "--since", "2026-10-22", "--state-dir", str(self.state), "--root", str(self.transcripts), "--project", str(self.project)],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertIn("kind=user", shown.stdout)
        recent = subprocess.run(
            [sys.executable, "-I", str(CLI_PATH), "recent", "--kind", "user", "--since", "2026-10-22", "--state-dir", str(self.state), "--root", str(self.transcripts), "--project", str(self.project)],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertIn("sessions=1", recent.stdout)
        doctor = subprocess.run(
            [sys.executable, "-I", str(CLI_PATH), "doctor", "--state-dir", str(self.state)],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertIn("ok sqlite=", doctor.stdout)

    def test_redact_removes_common_secret_assignments(self):
        self.assertEqual(redact("api_key=sk-this-is-a-long-secret-value"), "api_key=[REDACTED]")
        self.assertEqual(redact("Authorization: Bearer abc123"), "Authorization=[REDACTED]")

    def test_state_permissions_and_symlinks_are_rejected(self):
        with Store(self.state) as store:
            self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(store.path.stat().st_mode), 0o600)
        target = self.root / "state-target"
        target.mkdir()
        link = self.root / "state-link"
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(StoreError, "symlink"):
            Store(link)
        known = self.transcript("outside", records=[message("leakmarker")])
        with Store(self.state) as store:
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions WHERE id='outside'").fetchone()[0], 1)
        external = self.root / "outside.jsonl"
        external.write_bytes(line(metadata("outside", self.project)) + line(message("leakmarker")))
        known.unlink()
        known.symlink_to(external)
        with Store(self.state) as store:
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertGreater(stats["unreadable"], 0)
            self.assertEqual(store.db.execute("SELECT coverage FROM sessions WHERE id='outside'").fetchone()[0], "degraded")
            hit = store.search("leakmarker", self.project_id)[0]
            with self.assertRaises(StoreError):
                store.resolve_evidence(hit["session"], hit["position"], hit["digest"])


class HarnessIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.project_id = project_identity(self.project)
        self.roots = {name: self.root / "roots" / name for name in ("codex", "claude", "muse", "grok")}
        for path in self.roots.values():
            path.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, records):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join(line(record) for record in records))
        return path

    def codex(self, session, text, cwd=None):
        return self.write(self.roots["codex"] / ("rollout-" + session + ".jsonl"), [metadata(session, cwd or self.project), message(text)])

    def claude(self, session, records, directory=None, sidechain=False):
        base = {"sessionId": session, "cwd": str(self.project), "isSidechain": sidechain}
        path = (self.roots["claude"] / "-proj" / (directory or "") / (session + ".jsonl"))
        return self.write(path, [dict(base, **record) for record in records])

    def grok(self, session, records, primary=True):
        directory = self.roots["grok"] / "%2Fproj" / session
        self.write(directory / "chat_history.jsonl", records)
        self.write(directory / "summary.json", [{"info": {"id": session, "cwd": str(self.project)}}])
        if primary:
            self.write(directory / "events.jsonl", [{"type": "turn_started", "session_relationship": "primary"}])
        return directory / "chat_history.jsonl"

    def muse(self, session, records):
        meta = {"payload": {"kind": "metadata", "record": {"workspace_root": str(self.project)}}}
        return self.write(self.roots["muse"] / "2026" / "10" / "20" / session / "session.jsonl", [meta, *records])

    def refresh(self, store, **kwargs):
        return store.refresh({name: [path] for name, path in self.roots.items()}, project=self.project_id, **kwargs)

    def test_identical_native_ids_stay_distinct_per_harness(self):
        self.codex("shared", "codexneedle")
        self.claude("shared", [{"type": "user", "message": {"role": "user", "content": "claudeneedle"}}])
        self.grok("shared", [{"type": "user", "content": [{"type": "text", "text": "grokneedle"}]}])
        with Store(self.state) as store:
            self.refresh(store)
            ids = {row["id"]: row["harness"] for row in store.db.execute("SELECT id, harness FROM sessions")}
            self.assertEqual(ids, {"shared": "codex", "claude:shared": "claude", "grok:shared": "grok"})
            for needle, expected in (("codexneedle", "shared"), ("claudeneedle", "claude:shared"), ("grokneedle", "grok:shared")):
                hits = store.search(needle, self.project_id)
                self.assertEqual([hit["session"] for hit in hits], [expected])
                evidence = store.resolve_evidence(hits[0]["session"], hits[0]["position"], hits[0]["digest"])
                self.assertEqual(evidence["session"], expected)

    def test_codex_id_that_looks_qualified_cannot_collide(self):
        self.codex("claude:abc", "codexprefixneedle")
        self.claude("abc", [{"type": "user", "message": {"role": "user", "content": "claudeabcneedle"}}])
        with Store(self.state) as store:
            self.refresh(store)
            ids = sorted(row[0] for row in store.db.execute("SELECT id FROM sessions"))
            self.assertEqual(ids, ["claude:abc", "codex:claude:abc"])
            self.assertEqual(store.search("codexprefixneedle", self.project_id)[0]["session"], "codex:claude:abc")

    def test_claude_tool_events_keep_call_ids_and_explicit_outcomes(self):
        self.claude("tools", [
            {"type": "user", "message": {"role": "user", "content": "run the focused test"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "pytest -q tests/test_x.py"}}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "1 failed", "is_error": True}]}},
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": [{"type": "text", "text": "skill body injected by harness"}]}},
        ])
        with Store(self.state) as store:
            self.refresh(store)
            rows = store.db.execute("SELECT kind, call_id, outcome FROM events WHERE session = 'claude:tools' ORDER BY position").fetchall()
            self.assertEqual([tuple(row) for row in rows], [("user", None, None), ("tool-call", "toolu_1", None), ("tool-output", "toolu_1", "error"), ("context", None, None)])

    def test_sidechain_parent_is_known_and_muse_ancestry_is_not_invented(self):
        self.claude("main", [{"type": "user", "message": {"role": "user", "content": "root work"}}])
        self.claude("agent-a1", [{"type": "user", "message": {"role": "user", "content": "child work"}}], directory="main/subagents", sidechain=True)
        self.muse("m1", [{"recorded_at": 1792018406398112, "payload": {"event": {"kind": "model_user_messages", "messages": ["muse prompt"]}}}])
        self.grok("g-primary", [{"type": "user", "content": "grok prompt"}])
        self.grok("g-unknown", [{"type": "user", "content": "grok other"}], primary=False)
        with Store(self.state) as store:
            self.refresh(store)
            rows = {row["id"]: row for row in store.db.execute("SELECT id, parent, ancestry, thread_source FROM sessions")}
            self.assertEqual((rows["claude:main"]["ancestry"], rows["claude:main"]["parent"]), ("known", None))
            self.assertEqual((rows["claude:agent-a1"]["parent"], rows["claude:agent-a1"]["thread_source"]), (None, "subagent"))
            self.assertEqual(rows["muse:m1"]["ancestry"], "unknown")
            self.assertEqual(rows["grok:g-primary"]["ancestry"], "known")
            self.assertEqual(rows["grok:g-unknown"]["ancestry"], "unknown")

    def test_unrecognized_format_is_reported_instead_of_an_empty_success(self):
        self.muse("future", [{"recorded_at": 1, "payload": {"event": {"kind": "model_v9_turn", "data": "x"}}}])
        self.claude("newer", [{"type": "turn_v7", "message": {"role": "user", "content": "new shape"}}])
        with Store(self.state) as store:
            self.refresh(store)
            coverage = {row["id"]: row["coverage"] for row in store.db.execute("SELECT id, coverage FROM sessions")}
            self.assertEqual(coverage, {"muse:future": "unsupported", "claude:newer": "unsupported"})
            kinds = {(row["harness"], row["kind"]) for row in store.unrecognized_kinds()}
            self.assertEqual(kinds, {("muse", "unknown:model_v9_turn"), ("claude", "unknown:turn_v7")})
            summary = {row["harness"]: row for row in store.coverage()}
            self.assertEqual(summary["muse"]["unsupported"], 1)

    def test_unchanged_refresh_reads_no_bodies_for_any_harness(self):
        self.codex("c1", "alpha")
        self.claude("cl1", [{"type": "user", "message": {"role": "user", "content": "beta"}}])
        self.grok("g1", [{"type": "user", "content": "gamma"}])
        self.muse("m1", [{"recorded_at": 1792018406398112, "payload": {"event": {"kind": "model_user_messages", "messages": ["delta"]}}}])
        with Store(self.state) as store:
            first = self.refresh(store)
            self.assertEqual(first["sessions_indexed"], 4)
            again = self.refresh(store)
            self.assertEqual((again["content_opens"], again["bytes_read"], again["git_processes"], again["sqlite_changes"]), (0, 0, 0, 0))

    def test_symlinked_transcripts_and_directories_are_not_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.write(outside / "leak.jsonl", [{"type": "user", "sessionId": "leak", "cwd": str(self.project), "message": {"role": "user", "content": "leakneedle"}}])
        (self.roots["claude"] / "-proj").mkdir()
        os.symlink(outside / "leak.jsonl", self.roots["claude"] / "-proj" / "linked.jsonl")
        os.symlink(outside, self.roots["claude"] / "linked-dir")
        with Store(self.state) as store:
            stats = self.refresh(store)
            self.assertEqual(store.search("leakneedle", self.project_id), [])
            self.assertEqual(stats["sessions_indexed"], 0)

    def test_transcript_growing_between_discovery_and_indexing_is_indexed_not_fatal(self):
        path = self.claude("live", [{"type": "user", "message": {"role": "user", "content": "firstneedle"}}])
        original = STORE_MODULE._metadata

        def grow_after_header(*args, **kwargs):
            result = original(*args, **kwargs)
            with open(path, "ab") as stream:
                stream.write(line({"type": "user", "sessionId": "live", "cwd": str(self.project), "message": {"role": "user", "content": "secondneedle"}}))
            return result

        with Store(self.state) as store, mock.patch.object(STORE_MODULE, "_metadata", grow_after_header):
            self.refresh(store)
            self.assertEqual(len(store.search("firstneedle", self.project_id)), 1)
            self.assertEqual(len(store.search("secondneedle", self.project_id)), 1)

    def test_crash_while_indexing_rolls_back_and_the_next_refresh_completes(self):
        records = [{"type": "user", "message": {"role": "user", "content": "needle%d" % index}} for index in range(6)]
        self.claude("crashy", records)
        calls = {"count": 0}
        original = STORE_MODULE.normalize

        def explode(obj, harness="codex"):
            calls["count"] += 1
            if calls["count"] == 4:
                raise KeyboardInterrupt("simulated crash")
            return original(obj, harness)

        with Store(self.state) as store:
            with mock.patch.object(STORE_MODULE, "normalize", explode), self.assertRaises(KeyboardInterrupt):
                self.refresh(store)
            self.assertEqual(store.db.execute("SELECT count(*) FROM events").fetchone()[0], 0)
            stats = self.refresh(store)
            self.assertEqual(stats["events_added"], 6)
            self.assertEqual(store.db.execute("SELECT coverage FROM sessions").fetchone()[0], "complete")

    def test_partial_tail_is_flagged_then_indexed_once_the_line_completes(self):
        path = self.claude("tail", [{"type": "user", "message": {"role": "user", "content": "whole"}}])
        full = line({"type": "user", "sessionId": "tail", "cwd": str(self.project), "message": {"role": "user", "content": "latecomer"}})
        with open(path, "ab") as stream:
            stream.write(full[:25])
        with Store(self.state) as store:
            self.refresh(store)
            self.assertEqual(store.db.execute("SELECT coverage, partial_bytes > 0 FROM sessions").fetchone()[:], ("degraded", 1))
            self.assertEqual(store.search("latecomer", self.project_id), [])
            with open(path, "ab") as stream:
                stream.write(full[25:])
            self.refresh(store)
            self.assertEqual(len(store.search("latecomer", self.project_id)), 1)
            self.assertEqual(store.db.execute("SELECT coverage FROM sessions").fetchone()[0], "complete")

    def test_truncated_or_replaced_transcript_resets_instead_of_keeping_stale_events(self):
        records = [{"type": "user", "message": {"role": "user", "content": "oldneedle%d" % index}} for index in range(5)]
        path = self.claude("shrink", records)
        with Store(self.state) as store:
            self.refresh(store)
            self.assertEqual(len(store.search("oldneedle4", self.project_id)), 1)
            path.write_bytes(path.read_bytes()[: len(path.read_bytes()) // 3])
            stats = self.refresh(store)
            self.assertEqual(stats["resets"], 1)
            self.assertEqual(store.search("oldneedle4", self.project_id), [])
            replacement = self.root / "replacement.jsonl"
            replacement.write_bytes(b"".join(line(dict(record, sessionId="shrink", cwd=str(self.project))) for record in [{"type": "user", "message": {"role": "user", "content": "newneedle"}}]))
            os.replace(replacement, path)
            stats = self.refresh(store)
            self.assertEqual(stats["resets"], 1)
            self.assertEqual(len(store.search("newneedle", self.project_id)), 1)
            self.assertEqual(store.search("oldneedle0", self.project_id), [])

    def test_archived_move_keeps_one_session_and_valid_evidence(self):
        path = self.claude("moved", [{"type": "user", "message": {"role": "user", "content": "movedneedle"}}])
        with Store(self.state) as store:
            self.refresh(store)
            hit = store.search("movedneedle", self.project_id)[0]
            archive = self.roots["claude"] / "-archive"
            archive.mkdir()
            os.replace(path, archive / path.name)
            self.refresh(store)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 1)
            moved = store.search("movedneedle", self.project_id)[0]
            self.assertEqual(store.resolve_evidence(moved["session"], moved["position"], moved["digest"])["session"], hit["session"])

    def test_two_files_with_one_session_identity_index_once(self):
        self.claude("twin", [{"type": "user", "message": {"role": "user", "content": "twinneedle"}}])
        copy = self.roots["claude"] / "-proj" / "copy" / "twin.jsonl"
        copy.parent.mkdir(parents=True)
        copy.write_bytes((self.roots["claude"] / "-proj" / "twin.jsonl").read_bytes())
        with Store(self.state) as store:
            self.refresh(store)
            self.assertEqual(store.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 1)
            self.assertEqual(len(store.search("twinneedle", self.project_id)), 1)

    def test_corrupt_database_is_refused_and_left_untouched(self):
        with Store(self.state) as store:
            self.claude("c", [{"type": "user", "message": {"role": "user", "content": "x " * 5000}}])
            self.refresh(store)
        path = Store.database_path(self.state)
        data = bytearray(path.read_bytes())
        for offset in range(4096, len(data) - 4096, 4096):
            data[offset:offset + 64] = b"\xff" * 64
        path.write_bytes(bytes(data))
        before = path.read_bytes()
        with self.assertRaises(StoreError):
            with Store(self.state) as store:
                store.refresh({name: [root] for name, root in self.roots.items()})
                store.search("x", None)
                store.db.execute("PRAGMA integrity_check").fetchall()
                raise StoreError("integrity")
        self.assertEqual(path.read_bytes()[:16], before[:16])

    def test_deleted_harness_source_is_removed_from_the_index(self):
        path = self.claude("gone", [{"type": "user", "message": {"role": "user", "content": "goneneedle"}}])
        with Store(self.state) as store:
            self.refresh(store)
            self.assertEqual(len(store.search("goneneedle", self.project_id)), 1)
            path.unlink()
            stats = self.refresh(store)
            self.assertEqual(stats["deleted"], 1)
            self.assertEqual(store.search("goneneedle", self.project_id), [])

    def test_cli_indexes_selected_harness_with_named_root(self):
        self.claude("cli1", [{"type": "user", "message": {"role": "user", "content": "clineedle"}}])
        self.codex("cx", "clineedle")
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "search", "clineedle", "--state-dir", str(self.state), "--project", str(self.project),
             "--root", "claude=" + str(self.roots["claude"]), "--root", str(self.roots["codex"]), "--harness", "claude"],
            check=True, capture_output=True, text=True)
        self.assertIn("session=claude:cli1", result.stdout)
        self.assertIn("harness=claude", result.stdout)
        self.assertNotIn("session=cx", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
