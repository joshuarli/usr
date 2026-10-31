#!/usr/bin/env python3
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK_TMP = ROOT / ".work" / "tmp"
WORK_TMP.mkdir(parents=True, exist_ok=True)
SRC_DIR = ROOT / "tools" / "agent-memory" / "src"
sys.path.insert(0, str(SRC_DIR))
SPEC = importlib.util.spec_from_file_location("agent_session_store", SRC_DIR / "agent_memory" / "store.py")
assert SPEC is not None
STORE_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = STORE_MODULE
SPEC.loader.exec_module(STORE_MODULE)
Store = STORE_MODULE.Store
project_identity = STORE_MODULE.project_identity

ARCHIVE_SPEC = importlib.util.spec_from_file_location("agent_memory_archive", SRC_DIR / "agent_memory" / "archive.py")
ARCHIVE = importlib.util.module_from_spec(ARCHIVE_SPEC)
assert ARCHIVE_SPEC.loader is not None
sys.modules[ARCHIVE_SPEC.name] = ARCHIVE
ARCHIVE_SPEC.loader.exec_module(ARCHIVE)

TRANSFER_SPEC = importlib.util.spec_from_file_location("agent_memory_transfer", SRC_DIR / "agent_memory" / "transfer.py")
TRANSFER = importlib.util.module_from_spec(TRANSFER_SPEC)
assert TRANSFER_SPEC.loader is not None
sys.modules[TRANSFER_SPEC.name] = TRANSFER
TRANSFER_SPEC.loader.exec_module(TRANSFER)

LINE = ('{"timestamp":"2026-10-30T00:00:00Z","type":"response_item","payload":'
        '{"type":"message","role":"user","content":[{"type":"input_text","text":"%s"}]}}\n')


def line(text):
    return LINE % text


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temp.name)
        self.source_state = self.root / "source"
        self.central_state = self.root / "central"
        self.sessions = self.root / "sessions"
        self.sessions.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.project_id = project_identity(self.project)
        self.path = self.sessions / "rollout-a.jsonl"
        self.path.write_text(
            json.dumps({"timestamp": "2026-10-30T00:00:00Z", "type": "session_meta",
                        "payload": {"id": "a", "cwd": str(self.project)}}, separators=(",", ":")) + "\n"
            + line("alpha") + line("bravo", ))

    def tearDown(self):
        self.temp.cleanup()

    def capture(self):
        store = Store(self.source_state)
        store.refresh([self.sessions], project=self.project_id)
        return store

    def sync(self, source, remote="central", origin=None, label="test", attempts=3):
        origin = origin or ARCHIVE.origin_for(source.db)
        return TRANSFER.local_sync(source, self.central_state, remote, origin, label, attempts)

    def test_duplicate_delivery_is_idempotent_and_acks(self):
        source = self.capture()
        first = self.sync(source)
        self.assertEqual(len(first["delivered"]), 1)
        second = self.sync(source)
        self.assertEqual(second["delivered"], [])
        central = Store(self.central_state)
        self.assertEqual(central.db.execute("SELECT count(*) FROM archive_generation").fetchone()[0], 1)
        self.assertEqual(central.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 1)
        self.assertEqual(central.db.execute("SELECT count(*) FROM events").fetchone()[0], 3)

    def test_dropped_acknowledgement_is_retried_and_duplicate_ingest_is_a_noop(self):
        source = self.capture()
        original = source.mark_durable

        def drop_once(generation, remote, remote_id):
            raise OSError("acknowledgement lost")

        source.mark_durable = drop_once
        with self.assertRaises(TRANSFER.TransferError):
            self.sync(source, attempts=1)
        source.mark_durable = original
        delivered = self.sync(source)
        self.assertEqual(len(delivered["delivered"]), 1)
        central = Store(self.central_state)
        self.assertEqual(central.db.execute("SELECT count(*) FROM archive_generation").fetchone()[0], 1)
        durable = source.db.execute("SELECT count(*) FROM transfer_generation WHERE durable_at IS NOT NULL").fetchone()[0]
        self.assertEqual(durable, 1)

    def test_corrupted_object_is_rejected_and_nothing_is_indexed(self):
        source = self.capture()
        original = source.read_object_bytes
        source.read_object_bytes = lambda digest: original(digest)[:-1] + b"X"
        with self.assertRaises(TRANSFER.TransferError):
            self.sync(source, attempts=1)
        central = Store(self.central_state)
        self.assertEqual(central.db.execute("SELECT count(*) FROM archive_generation").fetchone()[0], 0)
        self.assertEqual(central.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)


    def serve_in_thread(self, allowed, exchange):
        left, right = socket.socketpair()
        left.settimeout(20)
        failure = {}

        def serve():
            try:
                with Store(self.central_state) as central:
                    with right.makefile("rb") as instream, right.makefile("wb") as outstream:
                        TRANSFER.receiver(central, instream, outstream, allowed_origins=allowed)
            except BaseException as exc:  # noqa: BLE001
                failure["error"] = exc

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            with left.makefile("rb") as instream, left.makefile("wb") as outstream:
                return exchange(instream, outstream)
        finally:
            left.close()
            thread.join(timeout=20)

    def test_protocol_mismatch_is_refused_before_writing(self):
        def exchange(instream, outstream):
            TRANSFER.write_message(outstream, {"type": "hello", "protocol": 99, "origin": "x"})
            return TRANSFER.read_message(instream)

        reply = self.serve_in_thread(["x"], exchange)
        self.assertEqual(reply["type"], "error")

    def test_untrusted_origin_is_refused(self):
        def exchange(instream, outstream):
            TRANSFER.write_message(outstream, {"type": "hello", "protocol": 1, "origin": "stranger"})
            return TRANSFER.read_message(instream)

        reply = self.serve_in_thread(["allowed"], exchange)
        self.assertEqual(reply["type"], "error")
        self.assertIn("not allowed", reply["message"])

    def test_central_query_returns_verified_evidence_without_the_source(self):
        source = self.capture()
        self.sync(source)
        central = Store(self.central_state)
        self.path.unlink()
        rows = TRANSFER.handle_query(central, "search", {"query": "alpha"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["evidence"]["text"], "alpha")
        self.assertEqual(rows[0]["session"], "a@" + ARCHIVE.origin_for(source.db))
        self.assertEqual(rows[0]["origin_host"], ARCHIVE.origin_for(source.db))

    def test_tombstone_beats_a_replayed_generation(self):
        source = self.capture()
        self.sync(source)
        source.forget_session("codex:a", 2000.0)
        self.sync(source)
        central = Store(self.central_state)
        self.assertEqual(central.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)
        self.assertEqual(central.db.execute("SELECT count(*) FROM tombstone").fetchone()[0], 1)
        for row in source.db.execute("SELECT id FROM archive_generation").fetchall():
            source.db.execute("DELETE FROM archive_generation WHERE id = ?", (row["id"],))
        source.db.execute("DELETE FROM transfer_generation")
        source.refresh([self.sessions], project=self.project_id)
        with self.assertRaises(TRANSFER.TransferError):
            self.sync(source, attempts=1)
        central = Store(self.central_state)
        self.assertEqual(central.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)

    def test_same_native_id_from_two_origins_is_kept_separate(self):
        source = self.capture()
        origin_one = ARCHIVE.origin_for(source.db)
        self.sync(source, origin=origin_one)
        other_state = self.root / "other-source"
        other = Store(other_state)
        origin_two = ARCHIVE.ensure_identity(other.db, label="other", regenerate=True)[0]
        other.refresh([self.sessions], project=self.project_id)
        self.sync(other, origin=origin_two)
        central = Store(self.central_state)
        ids = sorted(row[0] for row in central.db.execute("SELECT id FROM sessions"))
        self.assertEqual(ids, sorted(["a@" + origin_one, "a@" + origin_two]))
        self.assertEqual(central.db.execute("SELECT count(*) FROM archive_generation").fetchone()[0], 2)

    def test_offline_backlog_persists_and_reports(self):
        source = self.capture()
        self.assertEqual(source.pending_transfers("central"), 1)
        with self.assertRaises((TRANSFER.TransferError, OSError)):
            tree = self.root / "not-a-store"
            tree.write_text("x")
            TRANSFER.local_sync(source, tree, "central", ARCHIVE.origin_for(source.db), "t", attempts=1)
        self.assertEqual(source.pending_transfers("central"), 1)
        attempt = source.db.execute("SELECT attempts, last_error FROM transfer_generation WHERE remote='central'").fetchone()
        self.assertGreaterEqual(attempt["attempts"], 1)
        self.assertTrue(attempt["last_error"])

    def test_forgetting_a_received_session_tombstones_its_own_origin(self):
        source = self.capture()
        self.sync(source)
        central = Store(self.central_state)
        peer = ARCHIVE.origin_for(source.db)
        session = central.db.execute("SELECT id FROM sessions").fetchone()[0]
        self.assertTrue(session.endswith("@" + peer))
        central.forget_session(session, 3000.0)
        self.assertTrue(central.is_tombstoned(peer, "codex", "a"))
        central.reindex_generations()
        self.assertEqual(central.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)
        self.assertEqual(central.search("alpha", None), [])

    def test_a_corrupt_central_object_is_never_acknowledged_as_durable(self):
        source = self.capture()
        self.sync(source)
        central = Store(self.central_state)
        digest = central.db.execute("SELECT digest FROM archive_generation_object LIMIT 1").fetchone()[0]
        object_path = ARCHIVE.object_path(central.archive_dir, digest)
        data = bytearray(object_path.read_bytes())
        data[0:1] = b"X"
        object_path.write_bytes(bytes(data))
        with source.db:
            source.db.execute("DELETE FROM transfer_generation")
        with self.assertRaises(TRANSFER.TransferError):
            self.sync(source, attempts=1)
        durable = source.db.execute("SELECT count(*) FROM transfer_generation WHERE durable_at IS NOT NULL").fetchone()[0]
        self.assertEqual(durable, 0)

    def test_conflicting_sizes_for_one_digest_are_refused(self):
        def exchange(instream, outstream):
            TRANSFER.write_message(outstream, {"type": "hello", "protocol": 1, "origin": "peer"})
            TRANSFER.read_message(instream)
            TRANSFER.write_message(outstream, {"type": "generation", "origin_host": "peer", "harness": "codex",
                                               "native_id": "x", "source_path": "/x", "source_digest": "d",
                                               "source_size": 2, "captured_at": 1.0,
                                               "chunks": [{"digest": "aa", "size": 1, "offset": 0},
                                                          {"digest": "aa", "size": 2, "offset": 1}],
                                               "artifacts": []})
            return TRANSFER.read_message(instream)

        reply = self.serve_in_thread(["peer"], exchange)
        self.assertEqual(reply["type"], "error")
        self.assertIn("conflicting", reply["message"])

    def test_central_memory_records_carry_origin_evidence_and_no_authority(self):
        from agent_memory.learning import Learner

        source = self.capture()
        self.sync(source)
        central = Store(self.central_state)
        Learner(central)
        with central.db:
            central.db.execute(
                "INSERT INTO learning_experiences (project, kind, claim, applies_when, identifiers, fingerprint, basis, "
                "detector, revision, worktree, observed_at, captured_at, validity, tags, state) "
                "VALUES ('git:canary','gotcha','imported claim','cond','[]','fp','deterministic','det','r','w',10,10,'[]','','retained')")
            central.db.execute(
                "INSERT INTO learning_experience_sources (experience, session, position, digest, role) "
                "VALUES (1, 'a@peer', 0, 'digest', 'trigger')")
        rows = TRANSFER.handle_query(central, "memory", {"limit": 5})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record"], "experience:1")
        self.assertIn("not an instruction", rows[0]["authority"])
        self.assertEqual(rows[0]["sources"][0]["session"], "a@peer")

    def test_objects_are_compressed_and_still_verify(self):
        source = self.capture()
        self.sync(source)
        central = Store(self.central_state)
        generation = central.db.execute("SELECT id FROM archive_generation").fetchone()[0]
        self.assertEqual(ARCHIVE.verify_generation(central.db, central.archive_dir, generation), 1)
        rows = TRANSFER.handle_query(central, "search", {"query": "alpha"})
        self.assertEqual(rows[0]["evidence"]["text"], "alpha")
        original = b"alpha\n" * 4096
        packed = TRANSFER.compress(original)
        self.assertLess(len(packed), len(original))
        self.assertEqual(TRANSFER.decompress(packed, len(original)), original)

    def test_a_compressed_object_that_inflates_past_its_declared_size_is_refused(self):
        payload = TRANSFER.compress(b"x" * 100000)

        def exchange(instream, outstream):
            TRANSFER.write_message(outstream, {"type": "hello", "protocol": 1, "origin": "peer",
                                               "compression": ["zlib"]})
            ready = TRANSFER.read_message(instream)
            self.assertEqual(ready["compression"], "zlib")
            TRANSFER.write_message(outstream, {"type": "generation", "origin_host": "peer", "harness": "codex",
                                               "native_id": "bomb", "source_path": "/x", "source_digest": "d",
                                               "source_size": 4, "captured_at": 1.0,
                                               "chunks": [{"digest": "a" * 64, "size": 4, "offset": 0}],
                                               "artifacts": []})
            need = TRANSFER.read_message(instream)
            self.assertEqual(need["digests"], ["a" * 64])
            TRANSFER.write_message(outstream, {"type": "object", "digest": "a" * 64, "encoding": "zlib"})
            TRANSFER.write_blob(outstream, payload)
            return TRANSFER.read_message(instream)

        reply = self.serve_in_thread(["peer"], exchange)
        self.assertEqual(reply["type"], "error")
        self.assertIn("declared size", reply["message"])

    def test_a_corrupt_compressed_payload_is_refused(self):
        def exchange(instream, outstream):
            TRANSFER.write_message(outstream, {"type": "hello", "protocol": 1, "origin": "peer",
                                               "compression": ["zlib"]})
            TRANSFER.read_message(instream)
            TRANSFER.write_message(outstream, {"type": "generation", "origin_host": "peer", "harness": "codex",
                                               "native_id": "corrupt", "source_path": "/x", "source_digest": "d",
                                               "source_size": 4, "captured_at": 1.0,
                                               "chunks": [{"digest": "b" * 64, "size": 4, "offset": 0}],
                                               "artifacts": []})
            TRANSFER.read_message(instream)
            TRANSFER.write_message(outstream, {"type": "object", "digest": "b" * 64, "encoding": "zlib"})
            TRANSFER.write_blob(outstream, b"not zlib at all")
            return TRANSFER.read_message(instream)

        reply = self.serve_in_thread(["peer"], exchange)
        self.assertEqual(reply["type"], "error")
        self.assertIn("decompress", reply["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
