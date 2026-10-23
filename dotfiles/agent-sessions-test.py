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

ROOT = Path(__file__).resolve().parents[1]
WORK_TMP = ROOT / ".work" / "tmp"
WORK_TMP.mkdir(parents=True, exist_ok=True)
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
            self.assertEqual(store.db.execute("PRAGMA user_version").fetchone()[0], 3)
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
            db.execute("PRAGMA user_version = 2")
        with Store(self.state) as store:
            self.assertEqual(store.db.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertEqual(store.db.execute("SELECT count(*) FROM events WHERE session='legacy-v2'").fetchone()[0], 2)
            self.assertEqual(store.db.execute("SELECT count(*) FROM unindexed_sources").fetchone()[0], 0)
            stats = store.refresh([self.transcripts], project=self.project_id)
            self.assertEqual(stats["events_added"], 0)
            self.assertEqual(stats["resets"], 0)
            self.assertEqual(stats["content_opens"], 0)
            self.assertEqual(stats["bytes_read"], 0)
            self.assertEqual(stats["git_processes"], 0)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
