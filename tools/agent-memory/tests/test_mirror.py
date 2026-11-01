#!/usr/bin/env python3
"""Mirror protocol parity, configuration, and pooled-client behavior."""
import hashlib
import http.client
import json
import os
import select
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
WORK_TMP = ROOT / ".work" / "tmp"
WORK_TMP.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools" / "agent-memory" / "src"))

from agent_memory import archive as archive_module  # noqa: E402
from agent_memory import mirror  # noqa: E402
from agent_memory import mirror_crypto  # noqa: E402
from agent_memory import types as types_module  # noqa: E402
from agent_memory.store import Store  # noqa: E402

FIXTURE = json.loads((ROOT / "tools" / "agent-memory" / "tests" / "fixtures" / "mirror_protocol.json").read_text())
DIGEST = "a" * 64
OTHER = "b" * 64
CIPHER = "c" * 64


def archive_object(root, data):
    digest = hashlib.sha256(data).hexdigest()
    path = archive_module.object_path(root, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return digest, len(data)


def prepared_for(data, encoding="identity", ciphertext=b"synthetic ciphertext", compress_cpu_ms=1.0,
                 encrypt_cpu_ms=2.0):
    digest = hashlib.sha256(data).hexdigest()
    payload = data if encoding == "identity" else b"compressed"
    return mirror_crypto.PreparedObject(
        plaintext_digest=digest,
        plaintext_size=len(data),
        encoding=encoding,
        compressed_size=len(payload),
        ciphertext=ciphertext,
        ciphertext_digest=hashlib.sha256(ciphertext).hexdigest(),
        ciphertext_size=len(ciphertext),
        compress_cpu_ms=compress_cpu_ms,
        encrypt_cpu_ms=encrypt_cpu_ms,
    )


class FakeUploadClient:
    def __init__(self, known=None, tracker=None):
        self.known = list(known or [])
        self.tracker = tracker
        self.puts = []
        self.closed = False

    def missing(self, origin, objects):
        requested = {digest for digest, _size in objects}
        known = [row for row in self.known if row["plaintext_digest"] in requested]
        present = {row["plaintext_digest"] for row in known}
        return {
            "protocol": 1, "origin": origin,
            "missing": [{"plaintext_digest": digest, "size": size}
                        for digest, size in objects if digest not in present],
            "known": known,
        }

    def put_object(self, prepared):
        if self.tracker is not None:
            with self.tracker.lock:
                self.tracker.active += 1
                self.tracker.peak = max(self.tracker.peak, self.tracker.active)
            time.sleep(0.03)
            with self.tracker.lock:
                self.tracker.active -= 1
                self.tracker.puts.append(prepared)
        else:
            self.puts.append(prepared)
        return {"stored": True, "object": {
            "plaintext_digest": prepared.plaintext_digest,
            "plaintext_size": prepared.plaintext_size,
            "encoding": prepared.encoding,
            "ciphertext_digest": prepared.ciphertext_digest,
            "ciphertext_size": prepared.ciphertext_size,
        }}

    def close(self):
        self.closed = True


class SequenceFactory:
    def __init__(self, *clients):
        self.clients = list(clients)

    def __call__(self):
        return self.clients.pop(0)


class Tracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.puts = []


class FakeResponse:
    def __init__(self, status, body=b"", headers=None):
        self.status = status
        self._body = body
        self._headers = headers or {}

    def read(self, amount=None):
        return self._body if amount is None else self._body[:amount]

    def getheaders(self):
        return list(self._headers.items())


class FakeConnection:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def request(self, method, path, body=None, headers=None):
        self.calls.append({"method": method, "path": path, "body": body, "headers": headers or {}})

    def getresponse(self):
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self):
        self.closed = True


class Factory:
    def __init__(self, *connections):
        self.pending = list(connections)
        self.created = []

    def __call__(self):
        connection = self.pending.pop(0)
        self.created.append(connection)
        return connection


def response(value, status=200, headers=None):
    return FakeResponse(status, json.dumps(value).encode(), headers)


def status_body(protocol=1):
    return {"protocol": protocol, "store_id": "usr-memories", "ready": True}


def hello_body(origin="origin-a"):
    return {
        "protocol": 1, "store_id": "usr-memories", "origin": origin, "revision": 0,
        "tombstone_watermark": 0, "learning": {"revision": 0, "digest": None, "records": 0},
    }


def config():
    return mirror.MirrorConfig(
        url="https://memories.example.test",
        service_token_file=Path("/nonexistent/token"),
        age_recipients_file=Path("/nonexistent/recipients"),
        age_identity_file=Path("/nonexistent/identity"),
        learning_projection=False,
    )


def client(factory, sleeps=None):
    delays = [] if sleeps is None else sleeps
    return mirror.MirrorClient(
        config(), token=("client-id.access", "client-secret"), factory=factory,
        sleep=lambda delay: delays.append(delay),
    ), delays


class FixtureParityTests(unittest.TestCase):
    def test_constants_match_the_shared_fixture(self):
        self.assertEqual(mirror.PROTOCOL, FIXTURE["protocol"])
        self.assertEqual(mirror.MAX_JSON_BYTES, FIXTURE["limits"]["json_bytes"])
        self.assertEqual(mirror.MAX_OBJECT_BYTES, FIXTURE["limits"]["object_bytes"])
        self.assertEqual(mirror.MAX_MISSING_OBJECTS, FIXTURE["limits"]["missing_objects"])
        self.assertEqual(mirror.MAX_CURSOR_CHARS, FIXTURE["limits"]["cursor_chars"])
        self.assertEqual(mirror.MAX_SNAPSHOT_BYTES, FIXTURE["limits"]["snapshot_bytes"])
        self.assertEqual(mirror.MAX_SNAPSHOT_CHUNKS, FIXTURE["limits"]["snapshot_chunks"])
        self.assertEqual(mirror.MAX_SNAPSHOT_OBJECTS, FIXTURE["limits"]["snapshot_objects"])
        self.assertEqual(mirror.MAX_SOURCE_BYTES, FIXTURE["limits"]["source_bytes"])
        self.assertEqual(mirror.GC_GRACE_SECONDS, FIXTURE["limits"]["gc_grace_seconds"])
        self.assertEqual(mirror.ERROR_CODES, frozenset(FIXTURE["error_codes"]))
    def test_digest_and_origin_validators_agree(self):
        for item in FIXTURE["digests"]:
            self.assertEqual(mirror.decode_digest(item["value"]) is None, not item["ok"], item["name"])
        for item in FIXTURE["origins"]:
            self.assertEqual(mirror.decode_origin(item["value"]) is None, not item["ok"], item["name"])

    def test_hello_and_missing_validators_agree(self):
        for item in FIXTURE["hello"]:
            decoded = mirror.decode_hello(item["value"])
            self.assertEqual(decoded is None, not item["ok"], item["name"])
            if decoded is not None:
                self.assertEqual(decoded["origin"], item["value"]["origin"])
        for item in FIXTURE["missing"]:
            decoded = mirror.decode_missing_request(item["value"])
            self.assertEqual(decoded is None, not item["ok"], item["name"])
            if decoded is not None:
                objects = decoded.get("objects")
                if not isinstance(objects, list):
                    self.fail(item["name"] + " objects is not a list")
                self.assertEqual(len(objects), len(item["value"]["objects"]))

    def test_cursor_codec_agrees(self):
        for item in FIXTURE["cursors"]:
            if "parts" in item:
                if item["ok"]:
                    encoded = mirror.encode_cursor(item["parts"])
                    if "encoded" in item:
                        self.assertEqual(encoded, item["encoded"], item["name"])
                    self.assertEqual(mirror.decode_cursor(encoded), item["parts"], item["name"])
                else:
                    with self.assertRaises(ValueError):
                        mirror.encode_cursor(item["parts"])
            else:
                self.assertEqual(mirror.decode_cursor(item["value"]) is None, not item["ok"], item["name"])

    def test_missing_count_limit(self):
        objects = [{"plaintext_digest": "%064x" % index, "size": 0}
                   for index in range(mirror.MAX_MISSING_OBJECTS + 1)]
        self.assertIsNone(mirror.decode_missing_request({
            "protocol": 1, "origin": "origin-a", "objects": objects,
        }))

    def test_manifest_validator_agrees_with_every_fixture(self):
        for item in FIXTURE["manifests"]:
            decoded = mirror.decode_generation_manifest(item["value"])
            self.assertEqual(decoded is None, not item["ok"], item["name"])
            if decoded is not None:
                self.assertEqual(decoded["source_digest"], item["value"]["source_digest"])
                self.assertEqual(len(cast(list[Any], decoded["chunks"])), len(cast(list[Any], item["value"]["chunks"])))
                self.assertEqual(decoded["manifest_object"], item["value"]["manifest_object"])

    def test_tombstone_validator_agrees_with_every_fixture(self):
        for item in FIXTURE["tombstone_pushes"]:
            decoded = mirror.decode_tombstone_request(item["value"])
            self.assertEqual(decoded is None, not item["ok"], item["name"])
            if decoded is not None:
                self.assertEqual(len(cast(list[Any], decoded["tombstones"])), len(cast(list[Any], item["value"]["tombstones"])))

    def test_harnesses_and_generation_limits_match_the_shared_fixture(self):
        self.assertEqual(list(types_module.HARNESSES), FIXTURE["harnesses"])
        self.assertEqual(mirror.MAX_GENERATION_OBJECTS, FIXTURE["limits"]["generation_objects"])
        self.assertEqual(mirror.MAX_GENERATION_ARTIFACTS, FIXTURE["limits"]["generation_artifacts"])
        self.assertEqual(mirror.MAX_TOMBSTONES, FIXTURE["limits"]["tombstones"])
        self.assertEqual(mirror.MAX_PAGE, FIXTURE["limits"]["page"])

    def test_snapshot_and_maintenance_validators_agree_with_every_fixture(self):
        for item in FIXTURE["snapshots"]:
            decoded = mirror.decode_snapshot_commit(item["value"])
            self.assertEqual(decoded is None, not item["ok"], item["name"])
            if decoded is not None:
                self.assertEqual(decoded["snapshot"]["id"], item["value"]["snapshot"]["db_digest"])
                self.assertEqual(len(decoded["snapshot"]["chunks"]), len(item["value"]["snapshot"]["chunks"]))
                self.assertEqual(len(decoded["snapshot"]["objects"]), len(item["value"]["snapshot"]["objects"]))
        for item in FIXTURE["gc_requests"]:
            decoded = mirror.decode_gc_request(item["value"])
            self.assertEqual(decoded is None, not item["ok"], item["name"])
            if decoded is not None:
                self.assertEqual(decoded["apply"], item["value"]["apply"])
        for item in FIXTURE["replace_requests"]:
            decoded = mirror.decode_object_replace_request(item["value"])
            self.assertEqual(decoded is None, not item["ok"], item["name"])
            if decoded is not None:
                self.assertEqual(decoded["ciphertext_digest"], item["value"]["ciphertext_digest"])


class ConfigTests(unittest.TestCase):
    def mapping(self, **overrides):
        value = {
            "transport": "cloudflare",
            "url": "https://memories.17166969.xyz",
            "service_token_file": "/tmp/token.json",
            "age_recipients_file": "/tmp/recipients.txt",
            "age_identity_file": "/tmp/identity.key",
            "learning_projection": False,
        }
        value.update(overrides)
        return value

    def test_valid_config_and_optional_projection(self):
        parsed = mirror.decode_config(self.mapping())
        self.assertEqual(parsed.url, "https://memories.17166969.xyz")
        self.assertFalse(parsed.learning_projection)
        self.assertTrue(mirror.decode_config(self.mapping(learning_projection=True)).learning_projection)
        without = self.mapping()
        del without["learning_projection"]
        self.assertFalse(mirror.decode_config(without).learning_projection)

    def test_config_is_closed_and_https_only(self):
        for value in [
            self.mapping(unknown="x"),
            self.mapping(transport="local"),
            self.mapping(url="http://memories.17166969.xyz"),
            self.mapping(url="https://memories.17166969.xyz/private"),
            self.mapping(url="https://memories.17166969.xyz?a=1"),
            self.mapping(url="https://memories.17166969.xyz#fragment"),
            self.mapping(url="https://user:pass@memories.17166969.xyz"),
            self.mapping(learning_projection="yes"),
            self.mapping(service_token_file=1),
            {"transport": "cloudflare"},
        ]:
            with self.assertRaises(mirror.MirrorError) as raised:
                mirror.decode_config(value)
            self.assertEqual(raised.exception.code, "invalid_config")

    def test_load_config_reads_the_central_block(self):
        with tempfile.TemporaryDirectory(dir=str(WORK_TMP)) as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(json.dumps({"central": self.mapping()}))
            self.assertEqual(mirror.load_config(path).url, "https://memories.17166969.xyz")
            path.write_text(json.dumps({"central": None}))
            with self.assertRaises(mirror.MirrorError):
                mirror.load_config(path)
            path.write_text("{")
            with self.assertRaises(mirror.MirrorError):
                mirror.load_config(path)
            with self.assertRaises(mirror.MirrorError):
                mirror.load_config(Path(temporary) / "missing.json")

    def test_service_token_file_must_be_private_and_closed(self):
        with tempfile.TemporaryDirectory(dir=str(WORK_TMP)) as temporary:
            path = Path(temporary) / "token.json"
            path.write_text(json.dumps({"client_id": "id.access", "client_secret": "secret"}))
            os.chmod(path, 0o600)
            self.assertEqual(mirror.load_service_token(path), ("id.access", "secret"))
            os.chmod(path, 0o644)
            for value in [path]:
                with self.assertRaises(mirror.MirrorError) as raised:
                    mirror.load_service_token(value)
                self.assertEqual(raised.exception.code, "invalid_config")
            os.chmod(path, 0o600)
            path.write_text(json.dumps({"client_id": "id.access", "client_secret": "secret", "extra": 1}))
            with self.assertRaises(mirror.MirrorError):
                mirror.load_service_token(path)
            path.write_text("{")
            with self.assertRaises(mirror.MirrorError):
                mirror.load_service_token(path)


class ClientTests(unittest.TestCase):
    def test_hello_sends_bounded_json_and_access_headers(self):
        connection = FakeConnection(response(hello_body()))
        runtime, _delays = client(Factory(connection))
        with runtime:
            result = runtime.hello("origin-a")
        self.assertEqual(result["store_id"], "usr-memories")
        call = connection.calls[0]
        self.assertEqual((call["method"], call["path"]), ("POST", "/api/v1/sync/hello"))
        self.assertEqual(json.loads(call["body"]), {"protocol": 1, "origin": "origin-a"})
        self.assertEqual(call["headers"]["CF-Access-Client-Id"], "client-id.access")
        self.assertEqual(call["headers"]["CF-Access-Client-Secret"], "client-secret")
        self.assertEqual(call["headers"]["Content-Type"], "application/json")
        self.assertEqual(call["headers"]["Accept"], "application/json")

    def test_connections_are_reused_between_requests(self):
        connection = FakeConnection(response(status_body()), response(status_body()))
        factory = Factory(connection)
        runtime, _delays = client(factory)
        with runtime:
            runtime.status()
            runtime.status()
            self.assertFalse(connection.closed)
        self.assertEqual(len(factory.created), 1)
        self.assertEqual(len(connection.calls), 2)
        self.assertTrue(connection.closed)

    def test_retryable_status_reconnects_with_exponential_backoff(self):
        first = FakeConnection(response({"error": {"code": "unavailable", "message": "busy"}}, status=503))
        second = FakeConnection(response(status_body()))
        factory = Factory(first, second)
        runtime, delays = client(factory)
        with runtime:
            self.assertEqual(runtime.status()["protocol"], 1)
        self.assertEqual(delays, [1])
        self.assertTrue(first.closed)
        self.assertEqual(len(factory.created), 2)

    def test_retry_after_is_honored_and_bounded(self):
        first = FakeConnection(response(
            {"error": {"code": "unavailable", "message": "busy"}}, status=503,
            headers={"Retry-After": "7"},
        ))
        second = FakeConnection(response(status_body()))
        runtime, delays = client(Factory(first, second))
        with runtime:
            runtime.status()
        self.assertEqual(delays, [7])

    def test_a_permanent_error_is_not_retried(self):
        connection = FakeConnection(response({"error": {"code": "forbidden", "message": "no"}}, status=403))
        factory = Factory(connection)
        runtime, delays = client(factory)
        with runtime:
            with self.assertRaises(mirror.MirrorError) as raised:
                runtime.hello("origin-a")
        self.assertEqual(raised.exception.code, "forbidden")
        self.assertEqual(raised.exception.status, 403)
        self.assertEqual(delays, [])
        self.assertEqual(len(factory.created), 1)

    def test_network_failure_reconnects_then_succeeds(self):
        first = FakeConnection(http.client.RemoteDisconnected("closed"))
        second = FakeConnection(response(status_body()))
        factory = Factory(first, second)
        runtime, delays = client(factory)
        with runtime:
            self.assertEqual(runtime.status()["protocol"], 1)
        self.assertEqual(delays, [1])
        self.assertTrue(first.closed)
        self.assertEqual(len(factory.created), 2)

    def test_retries_are_bounded(self):
        connections = [
            FakeConnection(response({"error": {"code": "unavailable", "message": "busy"}}, status=503))
            for _ in range(mirror.ATTEMPTS)
        ]
        runtime, delays = client(Factory(*connections))
        with runtime:
            with self.assertRaises(mirror.MirrorError) as raised:
                runtime.status()
        self.assertEqual(raised.exception.code, "unavailable")
        self.assertEqual(delays, [1, 2, 4, 8])
        self.assertTrue(all(connection.closed for connection in connections))

    def test_invalid_and_oversized_responses_are_refused(self):
        invalid = FakeConnection(FakeResponse(200, b"{"))
        runtime, _delays = client(Factory(invalid))
        with runtime:
            with self.assertRaises(mirror.MirrorError) as raised:
                runtime.status()
        self.assertEqual(raised.exception.code, "invalid_response")

        with mock.patch.object(mirror, "MAX_RESPONSE_BYTES", 10):
            oversized = FakeConnection(FakeResponse(200, b"x" * 11))
            runtime, _delays = client(Factory(oversized))
            with runtime:
                with self.assertRaises(mirror.MirrorError) as raised:
                    runtime.status()
        self.assertEqual(raised.exception.code, "invalid_response")

    def test_version_mismatch_is_reported(self):
        connection = FakeConnection(response(status_body(protocol=2)))
        runtime, _delays = client(Factory(connection))
        with runtime:
            with self.assertRaises(mirror.MirrorError) as raised:
                runtime.status()
        self.assertEqual(raised.exception.code, "unsupported_version")

    def test_put_object_sends_plaintext_metadata_and_ciphertext(self):
        prepared = prepared_for(b"synthetic", encoding="zlib", ciphertext=b"ciphertext bytes")
        body = {
            "stored": True,
            "object": {
                "plaintext_digest": prepared.plaintext_digest,
                "plaintext_size": prepared.plaintext_size,
                "encoding": prepared.encoding,
                "ciphertext_digest": prepared.ciphertext_digest,
                "ciphertext_size": prepared.ciphertext_size,
            },
        }
        connection = FakeConnection(response(body))
        runtime, _delays = client(Factory(connection))
        with runtime:
            result = runtime.put_object(prepared)
        self.assertTrue(result["stored"])
        call = connection.calls[0]
        self.assertEqual((call["method"], call["path"]),
                         ("PUT", "/api/v1/sync/objects/" + prepared.ciphertext_digest))
        self.assertEqual(call["body"], prepared.ciphertext)
        self.assertEqual(call["headers"]["X-Plaintext-Digest"], prepared.plaintext_digest)
        self.assertEqual(call["headers"]["X-Plaintext-Size"], str(prepared.plaintext_size))
        self.assertEqual(call["headers"]["X-Encoding"], "zlib")
        self.assertEqual(call["headers"]["Content-Type"], "application/octet-stream")

    def test_get_object_reads_raw_ciphertext(self):
        ciphertext = b"synthetic ciphertext"
        digest = hashlib.sha256(ciphertext).hexdigest()
        connection = FakeConnection(FakeResponse(200, ciphertext))
        runtime, _delays = client(Factory(connection))
        with runtime:
            self.assertEqual(runtime.get_object(digest), ciphertext)
        call = connection.calls[0]
        self.assertEqual((call["method"], call["path"]), ("GET", "/api/v1/sync/objects/" + digest))
        self.assertEqual(call["headers"]["Accept"], "application/octet-stream")
        with runtime:
            with self.assertRaises(mirror.MirrorError):
                runtime.get_object("not-a-digest")

    def test_missing_request_and_response_are_validated(self):
        body = {
            "protocol": 1, "origin": "origin-a",
            "missing": [{"plaintext_digest": OTHER, "size": 5}],
            "known": [{
                "plaintext_digest": DIGEST, "plaintext_size": 4, "encoding": "zlib",
                "ciphertext_digest": CIPHER, "ciphertext_size": 30,
            }],
        }
        connection = FakeConnection(response(body))
        runtime, _delays = client(Factory(connection))
        with runtime:
            result = runtime.missing("origin-a", [(DIGEST, 4), (OTHER, 5)])
            missing = cast(list[dict[str, object]], result["missing"])
            known = cast(list[dict[str, object]], result["known"])
            self.assertEqual(missing[0]["plaintext_digest"], OTHER)
            self.assertEqual(known[0]["ciphertext_digest"], CIPHER)
            sent = json.loads(connection.calls[0]["body"])
            self.assertEqual(sent["objects"], [
                {"plaintext_digest": DIGEST, "size": 4},
                {"plaintext_digest": OTHER, "size": 5},
            ])
            with self.assertRaises(mirror.MirrorError) as raised:
                runtime.missing("origin-a", [(DIGEST, 4), (DIGEST, 5)])
        self.assertEqual(raised.exception.code, "invalid_request")
        self.assertEqual(len(connection.calls), 1)


def generation_row(manifest, identifier=7, revision=3):
    return {
        "id": identifier,
        "origin_host": manifest["origin_host"],
        "harness": manifest["harness"],
        "native_id": manifest["native_id"],
        "manifest_digest": manifest["manifest_digest"],
        "source_digest": manifest["source_digest"],
        "source_size": manifest["source_size"],
        "captured_at": manifest["captured_at"],
        "committed_at": 1762000001.5,
        "revision": revision,
        "manifest_object": manifest["manifest_object"],
    }


class GenerationClientTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(json.dumps(FIXTURE["manifests"][0]["value"]))

    def test_commit_sends_the_validated_manifest(self):
        body = {
            "protocol": 1, "origin": "origin-a", "generation": 7,
            "manifest_digest": self.manifest["manifest_digest"], "revision": 4, "duplicate": False,
        }
        connection = FakeConnection(response(body))
        runtime, _delays = client(Factory(connection))
        with runtime:
            committed = runtime.commit_generation("origin-a", 3, self.manifest)
        self.assertEqual(committed["revision"], 4)
        self.assertFalse(committed["duplicate"])
        call = connection.calls[0]
        self.assertEqual((call["method"], call["path"]), ("POST", "/api/v1/sync/generations"))
        sent = json.loads(call["body"])
        self.assertEqual(sent["base_revision"], 3)
        self.assertEqual(sent["manifest"]["manifest_digest"], self.manifest["manifest_digest"])

    def test_commit_rejects_a_response_for_another_generation(self):
        body = {
            "protocol": 1, "origin": "origin-a", "generation": 7,
            "manifest_digest": "f" * 64, "revision": 4, "duplicate": False,
        }
        runtime, _delays = client(Factory(FakeConnection(response(body))))
        with runtime:
            with self.assertRaises(mirror.MirrorError) as raised:
                runtime.commit_generation("origin-a", 3, self.manifest)
        self.assertEqual(raised.exception.code, "invalid_response")

    def test_generation_lookup_and_page_carry_the_origin(self):
        row = generation_row(self.manifest)
        page = {"protocol": 1, "origin": "origin-a", "generations": [row], "next_cursor": None}
        connection = FakeConnection(response(page), response(page))
        runtime, _delays = client(Factory(connection))
        with runtime:
            found = runtime.generation_by_manifest("origin-a", self.manifest["manifest_digest"])
            listed = runtime.generations("origin-a", after=0, limit=10)
        self.assertIsNotNone(found)
        self.assertEqual(cast(dict[str, Any], found)["id"], 7)
        rows = cast(list[dict[str, Any]], listed["generations"])
        self.assertEqual(rows[0]["native_id"], "native-1")
        self.assertIn("manifest=" + self.manifest["manifest_digest"], connection.calls[0]["path"])
        self.assertEqual(connection.calls[1]["path"], "/api/v1/sync/generations?origin=origin-a&after=0&limit=10")

    def test_tombstone_page_and_push_round_trip(self):
        page = {
            "protocol": 1, "origin": "origin-a",
            "tombstones": [{
                "harness": "codex", "native_id": "native-1", "scope": "global",
                "forgotten_at": 100.0, "revision": 2,
            }],
            "next_cursor": "cursor", "watermark": 2,
        }
        pushed = {
            "protocol": 1, "origin": "origin-a", "revision": 4,
            "applied": [{"harness": "codex", "native_id": "native-1"}],
            "ignored": [],
        }
        connection = FakeConnection(response(page), response(pushed))
        runtime, _delays = client(Factory(connection))
        with runtime:
            fetched = runtime.tombstones("origin-a", after="cursor", limit=10)
            result = runtime.push_tombstones("origin-a", 3, [{
                "harness": "codex", "native_id": "native-1", "scope": "global", "forgotten_at": 100.0,
            }])
        self.assertEqual(fetched["watermark"], 2)
        self.assertEqual(fetched["next_cursor"], "cursor")
        self.assertEqual(result["applied"], [{"harness": "codex", "native_id": "native-1"}])
        self.assertIn("after=cursor", connection.calls[0]["path"])
        self.assertEqual(json.loads(connection.calls[1]["body"])["base_revision"], 3)

    def test_invalid_generation_requests_are_refused_before_the_network(self):
        connection = FakeConnection()
        runtime, _delays = client(Factory(connection))
        with runtime:
            for action in (
                lambda: runtime.generation_by_manifest("origin-a", "not-a-digest"),
                lambda: runtime.commit_generation("origin-a", -1, self.manifest),
                lambda: runtime.tombstones("origin-a", limit=0),
            ):
                with self.assertRaises(mirror.MirrorError):
                    action()
        self.assertEqual(connection.calls, [])


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temporary.name)
        self.archive = self.root / "archive"

    def tearDown(self):
        self.temporary.cleanup()

    def refs(self, payloads, kind="chunk"):
        return [(archive_object(self.archive, data)[0], len(data), kind) for data in payloads]

    def test_duplicate_references_collapse_before_the_request(self):
        refs = self.refs([b"same"])
        primary = FakeUploadClient(known=[{"plaintext_digest": refs[0][0]}])
        counters = mirror.upload_objects(
            config(), "origin-a", self.archive, [refs[0], refs[0]], recipients=["age1synthetic"],
            client_factory=SequenceFactory(primary), prepare=prepared_for,
        )
        self.assertEqual(counters["objects_requested"], 1)
        self.assertEqual(counters["objects_known"], 1)
        self.assertEqual(counters["objects_missing"], 0)

    def test_known_objects_are_not_reuploaded(self):
        refs = self.refs([b"one", b"two", b"three"])
        known = [{"plaintext_digest": digest} for digest, _size, _kind in refs]
        primary = FakeUploadClient(known=known)
        factory = SequenceFactory(primary)
        counters = mirror.upload_objects(
            config(), "origin-a", self.archive, refs, recipients=["age1synthetic"],
            client_factory=factory, prepare=prepared_for,
        )
        self.assertEqual(counters["objects_requested"], 3)
        self.assertEqual(counters["objects_known"], 3)
        self.assertEqual(counters["objects_missing"], 0)
        self.assertEqual(counters["objects_stored"], 0)
        self.assertEqual(primary.puts, [])
        self.assertTrue(primary.closed)

    def test_uploads_are_bounded_to_four_connections(self):
        refs = self.refs([("object-%d" % index).encode() * 64 for index in range(8)], kind="artifact")
        tracker = Tracker()
        primary = FakeUploadClient()
        workers = [FakeUploadClient(tracker=tracker) for _ in range(4)]
        factory = SequenceFactory(primary, *workers)
        counters = mirror.upload_objects(
            config(), "origin-a", self.archive, refs, recipients=["age1synthetic"],
            concurrency=4, client_factory=factory, prepare=prepared_for,
        )
        self.assertEqual(tracker.peak, 4)
        self.assertEqual(len(tracker.puts), 8)
        self.assertEqual(counters["objects_stored"], 8)
        self.assertEqual(counters["objects_missing"], 8)
        self.assertEqual(counters["bytes_plaintext"], sum(len(("object-%d" % index).encode() * 64) for index in range(8)))
        self.assertEqual(counters["bytes_ciphertext"], 8 * len(b"synthetic ciphertext"))
        classes = cast(dict[str, dict[str, float]], counters["classes"])
        self.assertEqual(classes["artifact"]["objects"], 8)
        self.assertEqual(classes["artifact"]["zlib_objects"], 0)
        self.assertEqual(counters["compress_cpu_ms"], 8.0)
        self.assertEqual(counters["encrypt_cpu_ms"], 16.0)
        self.assertTrue(primary.closed)
        self.assertTrue(all(worker.closed for worker in workers))

    def test_a_changed_prepared_digest_or_oversized_ciphertext_is_refused(self):
        refs = self.refs([b"synthetic payload"])
        cases = [
            lambda data, recipients: prepared_for(b"different data"),
            lambda data, recipients: prepared_for(data, ciphertext=b"x" * (mirror.MAX_OBJECT_BYTES + 1)),
        ]
        for prepare in cases:
            primary = FakeUploadClient()
            workers = [FakeUploadClient()]
            with self.assertRaises(mirror.MirrorError):
                mirror.upload_objects(
                    config(), "origin-a", self.archive, refs, recipients=["age1synthetic"],
                    concurrency=1, client_factory=SequenceFactory(primary, *workers), prepare=prepare,
                )
            self.assertEqual(workers[0].puts, [])

    def test_upload_arguments_are_closed(self):
        refs = self.refs([b"synthetic payload"])
        with self.assertRaises(mirror.MirrorError):
            mirror.upload_objects(config(), "origin-a", self.archive,
                                 [(refs[0][0], refs[0][1], "unknown")], recipients=["age1"],
                                 client_factory=SequenceFactory(FakeUploadClient()))
        with self.assertRaises(ValueError):
            mirror.upload_objects(config(), "origin-a", self.archive, refs, recipients=["age1"],
                                 concurrency=0, client_factory=SequenceFactory(FakeUploadClient()))


class DownloadTests(unittest.TestCase):
    def test_a_corrupted_object_is_named_by_digest(self):
        row = {
            "plaintext_digest": DIGEST,
            "plaintext_size": 8,
            "encoding": "identity",
            "ciphertext_digest": CIPHER,
            "ciphertext_size": 11,
        }
        client = mock.Mock()
        client.get_object.return_value = b"wrong bytes"
        with mock.patch.object(
                mirror.mirror_crypto, "decode_object",
                side_effect=mirror_crypto.CryptoError("object failed to decode")):
            with self.assertRaises(mirror.MirrorError) as raised:
                mirror._download_object(client, Path("identity.key"), row)
        self.assertEqual(raised.exception.code, "corrupt_object")
        self.assertIn(DIGEST, str(raised.exception))


class StoreMirrorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temporary.name)
        self.store = Store(self.root)

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def test_schema_v10_pins_a_remote_and_tracks_acks(self):
        self.assertEqual(self.store.db.execute("PRAGMA user_version").fetchone()[0], 10)
        self.assertEqual(self.store.mirror_remote_state("cloudflare"), None)
        self.store.write_mirror_remote("cloudflare", "usr-memories", 4, 2)
        state = self.store.mirror_remote_state("cloudflare")
        self.assertIsNotNone(state)
        state = cast(dict[str, Any], state)
        self.assertEqual((state["store_id"], state["revision"], state["tombstone_watermark"]),
                         ("usr-memories", 4, 2))
        self.assertIsNotNone(state["last_sync_at"])

        with self.store.db:
            self.store.db.execute(
                "INSERT INTO archive_generation(origin_host, harness, native_id, source_path, source_digest, "
                "source_size, captured_at, manifest_digest, session_metadata) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("origin-a", "codex", "native-1", "/synthetic", "a" * 64, 10, 1.0, "b" * 64, None))
            generation = self.store.db.execute("SELECT max(id) FROM archive_generation").fetchone()[0]
        self.assertEqual(len(self.store.pending_generations("usr-memories", "origin-a")), 1)
        self.store.mark_durable(generation, "usr-memories", 9)
        self.assertEqual(self.store.pending_generations("usr-memories", "origin-a"), [])
        self.assertEqual(self.store.remote_ack_count("usr-memories"), 1)

        with self.store.db:
            self.store.db.execute(
                "INSERT INTO tombstone(origin_host, harness, native_id, scope, forgotten_at) "
                "VALUES('origin-a', 'codex', 'native-1', 'global', 5.0)")
        self.assertEqual(len(self.store.pending_tombstones("usr-memories", "origin-a")), 1)
        self.store.mark_tombstone_durable("origin-a", "codex", "native-1", "usr-memories")
        self.assertEqual(self.store.pending_tombstones("usr-memories", "origin-a"), [])

        self.store.clear_remote_acks("usr-memories")
        self.assertEqual(self.store.remote_ack_count("usr-memories"), 0)
        self.assertIsNotNone(self.store.mirror_remote_state("cloudflare"))
        self.store.forget_mirror_remote("cloudflare")
        self.assertIsNone(self.store.mirror_remote_state("cloudflare"))

    def test_a_v9_schema_gains_mirror_remote_without_losing_tombstones(self):
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO tombstone(origin_host, harness, native_id, scope, forgotten_at) "
                "VALUES('origin-a', 'codex', 'native-1', 'global', 5.0)")
        self.store.close()
        with sqlite3.connect(self.store.path) as connection:
            connection.execute("DROP TABLE mirror_remote")
            connection.execute("PRAGMA user_version = 9")
        self.store = Store(self.root)
        self.assertEqual(self.store.db.execute("PRAGMA user_version").fetchone()[0], 10)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM tombstone").fetchone()[0], 1)
        self.store.write_mirror_remote("cloudflare", "usr-memories", 1, 0)
        state = self.store.mirror_remote_state("cloudflare")
        self.assertIsNotNone(state)
        self.assertEqual(cast(dict[str, Any], state)["revision"], 1)

    def test_applying_a_remote_tombstone_is_durable_for_that_remote(self):
        self.assertTrue(self.store.apply_remote_tombstone(
            "origin-a", "codex", "native-1", "global", 100.0, "usr-memories"))
        self.assertTrue(self.store.is_tombstoned("origin-a", "codex", "native-1"))
        self.assertEqual(self.store.pending_tombstones("usr-memories", "origin-a"), [])
        rows = self.store.tombstone_states("usr-memories")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["acked_remote"])

    def test_an_older_remote_tombstone_does_not_ack_a_newer_local_one(self):
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO tombstone(origin_host, harness, native_id, scope, forgotten_at) "
                "VALUES('origin-a', 'codex', 'native-1', 'global', 200.0)")
        self.assertFalse(self.store.apply_remote_tombstone(
            "origin-a", "codex", "native-1", "global", 100.0, "usr-memories"))
        self.assertEqual(len(self.store.pending_tombstones("usr-memories", "origin-a")), 1)
        self.assertTrue(self.store.apply_remote_tombstone(
            "origin-a", "codex", "native-1", "global", 300.0, "usr-memories"))
        self.assertEqual(self.store.pending_tombstones("usr-memories", "origin-a"), [])
        row = self.store.db.execute(
            "SELECT forgotten_at FROM tombstone WHERE origin_host = 'origin-a' AND harness = 'codex' "
            "AND native_id = 'native-1'").fetchone()
        self.assertEqual(row["forgotten_at"], 300.0)


class SyncStore:
    def __init__(self, origin="origin-a", pinned=None, pending_generations=None, pending_tombstones=None,
                 ack_count=0):
        self.db = object()
        self.archive_dir = Path("/nonexistent")
        self.origin = origin
        self.pinned = pinned
        self._pending_generations = list(pending_generations or [])
        self._pending_tombstones = list(pending_tombstones or [])
        self.ack_count = ack_count
        self.calls = []
        self.durable = []
        self.attempts = []
        self.writes = []
        self.applied = []
        self._pending = []
        self._tombstone_pending = list(self._pending_tombstones)

    def mirror_remote_state(self, remote):
        self.calls.append(("state", remote))
        return self.pinned

    def remote_ack_count(self, store_id):
        self.calls.append(("ack_count", store_id))
        return self.ack_count

    def pending_transfers(self, store_id):
        return 0

    def forget_mirror_remote(self, remote):
        self.calls.append(("forget", remote))
        self.pinned = None

    def apply_remote_tombstone(self, origin, harness, native, scope, forgotten_at, remote):
        self.calls.append(("apply", harness, native))
        self.applied.append((origin, harness, native, scope, forgotten_at, remote))

    def pending_tombstones(self, remote, origin):
        return list(self._tombstone_pending)

    def mark_tombstone_durable(self, origin, harness, native, remote):
        self.calls.append(("tomb_durable", harness, native))
        self._tombstone_pending = [row for row in self._tombstone_pending
                                   if (row["harness"], row["native_id"]) != (harness, native)]

    def pending_generations(self, remote, origin):
        return list(self._pending_generations)

    def mark_durable(self, generation, remote, remote_generation):
        self.calls.append(("durable", generation, remote, remote_generation))
        self.durable.append((generation, remote, remote_generation))
        self._pending_generations = [row for row in self._pending_generations if row["id"] != generation]

    def record_attempt(self, generation, remote, error):
        self.calls.append(("attempt", generation))
        self.attempts.append((generation, remote, error))

    def write_mirror_remote(self, remote, store_id, revision, watermark, error=None):
        self.calls.append(("write", remote, store_id, revision, watermark, error))
        self.writes.append((remote, store_id, revision, watermark, error))
        self.pinned = {"remote": remote, "store_id": store_id, "revision": revision,
                       "tombstone_watermark": watermark, "learning_seq": 0,
                       "learning_digest": None, "last_sync_at": 1.0, "last_error": error}


class SyncClient:
    def __init__(self, hello=None, tombstone_pages=None, duplicate=None, commit=None, error=None):
        self.hello_body = hello or {
            "protocol": 1, "store_id": "usr-memories", "origin": "origin-a", "revision": 2,
            "tombstone_watermark": 0, "learning": {"revision": 0, "digest": None, "records": 0},
        }
        self.hellos = 0
        self.pages = list(tombstone_pages or [])
        self.duplicate = duplicate
        self.commit = commit
        self.error = error
        self.calls = []
        self.puts = []

    def hello(self, origin):
        self.calls.append(("hello", origin))
        self.hellos += 1
        body = dict(self.hello_body)
        body["revision"] = self.hello_body["revision"] + max(0, self.hellos - 1) if False else self.hello_body["revision"]
        return body

    def tombstones(self, origin, after=None, limit=100):
        self.calls.append(("tombstones", after))
        return self.pages.pop(0)

    def push_tombstones(self, origin, base_revision, tombstones):
        self.calls.append(("push", base_revision, len(tombstones)))
        return {"protocol": 1, "origin": origin, "revision": base_revision + 1,
                "applied": [{"harness": row["harness"], "native_id": row["native_id"]} for row in tombstones],
                "ignored": []}

    def generation_by_manifest(self, origin, digest):
        self.calls.append(("lookup", digest))
        return self.duplicate

    def commit_generation(self, origin, base_revision, manifest):
        self.calls.append(("commit", base_revision, manifest))
        if self.error is not None:
            raise self.error
        assert self.commit is not None
        return self.commit

    def put_object(self, prepared):
        self.calls.append(("put", prepared.ciphertext_digest))
        self.puts.append(prepared)
        return {"stored": True, "object": {
            "plaintext_digest": prepared.plaintext_digest,
            "plaintext_size": prepared.plaintext_size,
            "encoding": prepared.encoding,
            "ciphertext_digest": prepared.ciphertext_digest,
            "ciphertext_size": prepared.ciphertext_size,
        }}

    def close(self):
        self.calls.append(("close",))


def upload_counters():
    return {"objects_requested": 1, "objects_known": 0, "objects_missing": 1, "objects_stored": 1,
            "bytes_plaintext": 10, "bytes_compressed": 10, "bytes_ciphertext": 20}


def snapshot_counters(revision):
    return {"id": "d" * 64, "revision": revision, "duplicate": False, "db_size": 4096,
            "chunks": 4, "chunks_uploaded": 0, "objects": 3, "objects_uploaded": 0,
            "object_bytes": 30, "bytes_plaintext": 0, "bytes_ciphertext": 0}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temporary.name)
        self.manifest = json.loads(json.dumps(FIXTURE["manifests"][0]["value"]))
        self.origin_patch = mock.patch.object(mirror.archive_module, "origin_for", return_value="origin-a")
        self.manifest_patch = mock.patch.object(
            mirror.archive_module, "generation_manifest", lambda db, identifier: dict(self.manifest))
        self.origin_patch.start()
        self.manifest_patch.start()

    def tearDown(self):
        self.manifest_patch.stop()
        self.origin_patch.stop()
        self.temporary.cleanup()

    def prepared(self, data, _recipients):
        return prepared_for(data, ciphertext=b"manifest ciphertext")

    def patch_snapshot(self):
        return mock.patch.object(
            mirror, "upload_snapshot",
            side_effect=lambda *args, **kwargs: snapshot_counters(kwargs["revision"]))

    def generation(self, identifier=5):
        return {"id": identifier, "manifest_digest": self.manifest["manifest_digest"],
                "harness": self.manifest["harness"], "native_id": self.manifest["native_id"]}

    def test_noop_sync_pins_once_and_then_writes_nothing(self):
        store = SyncStore()
        runtime = SyncClient()
        first = mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"])
        self.assertEqual(first["hello"], 1)
        self.assertFalse(first["unchanged"])
        self.assertEqual(len(store.writes), 1)
        self.assertEqual(store.writes[0][1:4], ("usr-memories", 2, 0))

        second_store = SyncStore(pinned=store.pinned)
        second_runtime = SyncClient()
        with mock.patch.object(mirror, "upload_snapshot") as snapshot:
            second = mirror.sync(second_store, config(), "cloudflare", client=second_runtime, recipients=["age1"])
        snapshot.assert_not_called()
        self.assertEqual(second["snapshots_created"], 0)
        self.assertEqual(second["snapshot_chunks_uploaded"], 0)
        self.assertEqual(second["hello"], 1)
        self.assertTrue(second["unchanged"])
        self.assertEqual(second_store.writes, [])
        self.assertEqual([call[0] for call in second_runtime.calls], ["hello"])

    def test_a_generation_uploads_objects_and_the_manifest_then_acks(self):
        commit = {"protocol": 1, "origin": "origin-a", "generation": 7,
                  "manifest_digest": self.manifest["manifest_digest"], "revision": 3, "duplicate": False}
        store = SyncStore(pending_generations=[self.generation()])
        runtime = SyncClient(commit=commit)
        with mock.patch.object(mirror, "upload_objects", return_value=upload_counters()) as upload, self.patch_snapshot():
            result = mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"],
                                 prepare=self.prepared)
        from_call = upload.call_args
        self.assertEqual(from_call.args[1], "origin-a")
        self.assertEqual([ref[2] for ref in from_call.args[3]], ["chunk", "chunk", "artifact"])
        self.assertEqual(len(runtime.puts), 1)
        commit_call = [call for call in runtime.calls if call[0] == "commit"][0]
        self.assertEqual(commit_call[1], 2)
        self.assertEqual(commit_call[2]["manifest_object"], runtime.puts[0].ciphertext_digest)
        self.assertIsNone(commit_call[2]["session_metadata"])
        self.assertEqual(commit_call[2]["manifest_digest"], self.manifest["manifest_digest"])
        self.assertEqual(store.durable, [(5, "usr-memories", 7)])
        self.assertEqual(result["generations_committed"], 1)
        self.assertEqual(result["objects_stored"], 1)
        self.assertEqual(store.writes[-1][1:4], ("usr-memories", 3, 0))

    def test_a_changed_sync_creates_a_snapshot_and_persists_its_revision(self):
        commit = {"protocol": 1, "origin": "origin-a", "generation": 7,
                  "manifest_digest": self.manifest["manifest_digest"], "revision": 3, "duplicate": False}
        store = SyncStore(pending_generations=[self.generation()])
        runtime = SyncClient(commit=commit)
        with mock.patch.object(mirror, "upload_objects", return_value=upload_counters()), mock.patch.object(
                mirror, "upload_snapshot",
                side_effect=lambda *args, **kwargs: snapshot_counters(kwargs["revision"] + 1)) as snapshot:
            result = mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"],
                                 prepare=self.prepared)
        self.assertEqual(snapshot.call_args.kwargs["revision"], 3)
        self.assertEqual(result["snapshots_created"], 1)
        self.assertEqual(store.writes[-1][1:4], ("usr-memories", 4, 0))

    def test_a_duplicate_generation_ack_skips_objects_and_refreshes_the_revision(self):
        duplicate = generation_row(self.manifest)
        runtime = SyncClient(duplicate=duplicate)
        runtime.hello_body = {"protocol": 1, "store_id": "usr-memories", "origin": "origin-a", "revision": 5,
                              "tombstone_watermark": 0, "learning": {"revision": 0, "digest": None, "records": 0}}
        calls = []

        def hello(origin):
            calls.append(origin)
            body = dict(runtime.hello_body)
            body["revision"] = 6 if len(calls) > 1 else 5
            return body

        cast(Any, runtime).hello = hello
        store = SyncStore(pending_generations=[self.generation()])
        with mock.patch.object(mirror, "upload_objects") as upload:
            result = mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"])
        upload.assert_not_called()
        self.assertEqual(runtime.puts, [])
        self.assertFalse([call for call in runtime.calls if call[0] == "commit"])
        self.assertEqual(store.durable, [(5, "usr-memories", 7)])
        self.assertEqual(result["generations_duplicate"], 1)
        self.assertEqual(result["revision"], 6)
        self.assertEqual(store.writes[-1][1:4], ("usr-memories", 6, 0))

    def test_a_changed_store_identity_refuses_inherited_acks(self):
        store = SyncStore(pinned={"store_id": "old-store", "revision": 1, "tombstone_watermark": 0},
                          ack_count=1)
        runtime = SyncClient()
        with self.assertRaises(mirror.MirrorError) as raised:
            mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"])
        self.assertEqual(raised.exception.code, "remote_identity_changed")
        self.assertFalse([call for call in store.calls if call[0] == "durable"])
        self.assertIsNotNone(store.writes[-1][4])

    def test_tombstones_are_pushed_before_any_generation(self):
        commit = {"protocol": 1, "origin": "origin-a", "generation": 7,
                  "manifest_digest": self.manifest["manifest_digest"], "revision": 4, "duplicate": False}
        tombstone = {"origin_host": "origin-a", "harness": "codex", "native_id": "gone",
                     "scope": "global", "forgotten_at": 1.0}
        store = SyncStore(pending_generations=[self.generation()], pending_tombstones=[tombstone])
        runtime = SyncClient(commit=commit)
        order = []
        original_push = runtime.push_tombstones
        original_commit = runtime.commit_generation

        def push(*args):
            order.append("push")
            return original_push(*args)

        def committed(*args):
            order.append("commit")
            return original_commit(*args)

        cast(Any, runtime).push_tombstones = push
        cast(Any, runtime).commit_generation = committed
        with mock.patch.object(mirror, "upload_objects", return_value=upload_counters()), self.patch_snapshot():
            result = mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"],
                                 prepare=self.prepared)
        self.assertEqual(order, ["push", "commit"])
        self.assertEqual(result["tombstones_pushed"], 1)
        self.assertEqual([call for call in runtime.calls if call[0] == "commit"][0][1], 3)

    def test_a_remote_newer_tombstone_is_acked_without_repushing(self):
        tombstone = {"origin_host": "origin-a", "harness": "codex", "native_id": "gone",
                     "scope": "global", "forgotten_at": 1.0}
        store = SyncStore(pending_tombstones=[tombstone])
        runtime = SyncClient()

        def push(origin, base_revision, tombstones):
            return {"protocol": 1, "origin": origin, "revision": base_revision + 1, "applied": [],
                    "ignored": [{"harness": row["harness"], "native_id": row["native_id"]} for row in tombstones]}

        cast(Any, runtime).push_tombstones = push
        result = mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"])
        self.assertEqual(result["tombstones_pushed"], 0)
        self.assertIn(("tomb_durable", "codex", "gone"), store.calls)
        self.assertEqual(store.pending_tombstones("usr-memories", "origin-a"), [])

    def test_remote_tombstones_apply_before_capture(self):
        page = {"protocol": 1, "origin": "origin-a", "watermark": 2, "next_cursor": None,
                "tombstones": [{"harness": "codex", "native_id": "gone", "scope": "global",
                                "forgotten_at": 100.0, "revision": 2}]}
        runtime = SyncClient(hello={"protocol": 1, "store_id": "usr-memories", "origin": "origin-a",
                                    "revision": 2, "tombstone_watermark": 2,
                                    "learning": {"revision": 0, "digest": None, "records": 0}},
                             tombstone_pages=[page])
        store = SyncStore(pinned={"store_id": "usr-memories", "revision": 2, "tombstone_watermark": 0})
        order = []
        store.calls = []

        def apply(*args):
            order.append("apply")

        def refresh():
            order.append("refresh")

        cast(Any, store).apply_remote_tombstone = apply
        with self.patch_snapshot():
            result = mirror.sync(store, config(), "cloudflare", client=runtime, refresh=refresh,
                                 recipients=["age1"])
        self.assertEqual(order, ["apply", "refresh"])
        self.assertEqual(result["tombstones_fetched"], 1)
        self.assertEqual(store.writes[-1][3], 2)

    def test_a_mismatched_generation_ack_is_refused(self):
        commit = {"protocol": 1, "origin": "origin-a", "generation": 7,
                  "manifest_digest": "f" * 64, "revision": 3, "duplicate": False}
        store = SyncStore(pending_generations=[self.generation()])
        runtime = SyncClient(commit=commit)
        with mock.patch.object(mirror, "upload_objects", return_value=upload_counters()):
            with self.assertRaises(mirror.MirrorError) as raised:
                mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"],
                            prepare=self.prepared)
        self.assertEqual(raised.exception.code, "invalid_response")
        self.assertEqual(store.durable, [])
        self.assertEqual(len(store.attempts), 1)

    def test_a_tombstoned_generation_is_acked_and_skipped(self):
        store = SyncStore(pending_generations=[self.generation()])
        runtime = SyncClient(error=mirror.MirrorError("tombstoned", "gone"))
        with mock.patch.object(mirror, "upload_objects", return_value=upload_counters()), self.patch_snapshot():
            result = mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"],
                                 prepare=self.prepared)
        self.assertEqual(store.durable, [(5, "usr-memories", 0)])
        self.assertEqual(result["generations_tombstoned"], 1)
        self.assertEqual(store.attempts, [])

    def test_a_stale_revision_records_the_attempt_and_stops(self):
        store = SyncStore(pending_generations=[self.generation()])
        runtime = SyncClient(error=mirror.MirrorError("stale_revision", "stale", status=409))
        with mock.patch.object(mirror, "upload_objects", return_value=upload_counters()):
            with self.assertRaises(mirror.MirrorError) as raised:
                mirror.sync(store, config(), "cloudflare", client=runtime, recipients=["age1"],
                            prepare=self.prepared)
        self.assertEqual(raised.exception.code, "stale_revision")
        self.assertEqual(len(store.attempts), 1)
        self.assertEqual(store.durable, [])


class MirrorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if node is None:
            raise AssertionError("node is required for mirror integration tests")
        cls.node: str = node
        cls.worker_dir = ROOT / "tools" / "agent-memory" / "cloudflare"
        cls.bundle = cls.worker_dir / ".cloudflare" / "output" / "v0" / "workers" / "default" / "bundle" / "index.js"
        if not cls.bundle.is_file():
            raise AssertionError("missing worker bundle; run `npm run build` in tools/agent-memory/cloudflare")
        try:
            mirror_crypto.binary()
        except mirror_crypto.CryptoError:
            result = subprocess.run(
                ["sh", str(cls.worker_dir / "dev-age.sh")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise AssertionError("cannot build rage: " + result.stderr.strip()) from None
            os.environ["AGE_BIN"] = result.stdout.strip()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temporary.name)
        self.identity = self.root / "identity.key"
        self.recipient = mirror_crypto.keygen(self.identity)
        self.recipients_file = self.root / "recipients.txt"
        self.recipients_file.write_text(self.recipient + "\n")
        self.token_file = self.root / "token.json"
        self.token_file.write_text('{"client_id":"collector-client.access","client_secret":"synthetic"}')
        os.chmod(self.token_file, 0o600)
        self.process: subprocess.Popen[str] | None = None
        self.port = self.start_server()
        self.config = mirror.MirrorConfig(
            url="http://127.0.0.1:%d" % self.port,
            service_token_file=self.token_file,
            age_recipients_file=self.recipients_file,
            age_identity_file=self.identity,
            learning_projection=False,
        )
        self.recipients = mirror_crypto.load_recipients(self.recipients_file)

    def tearDown(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
            if self.process.stdout is not None:
                self.process.stdout.close()
            if self.process.stderr is not None:
                self.process.stderr.close()
        self.temporary.cleanup()

    def start_server(self):
        env = dict(os.environ)
        env["COLLECTORS"] = json.dumps([{"client_id": "collector-client.access", "origin": "origin-a"}])
        self.process = subprocess.Popen(
            [self.node, "test/integration-server.mjs"], cwd=str(self.worker_dir),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        stdout = self.process.stdout
        assert stdout is not None
        ready, _, _ = select.select([stdout], [], [], 30)
        if not ready:
            self.process.kill()
            _, stderr = self.process.communicate(timeout=10)
            raise AssertionError("mirror integration server did not start: " + (stderr.strip() or "timeout"))
        line = stdout.readline()
        try:
            return int(json.loads(line)["port"])
        except (ValueError, KeyError, TypeError):
            self.process.kill()
            _, stderr = self.process.communicate(timeout=10)
            raise AssertionError("mirror integration server did not start: " + (stderr.strip() or line.strip())) from None

    def client(self, config=None):
        return mirror.MirrorClient(
            config or self.config,
            factory=lambda: http.client.HTTPConnection("127.0.0.1", self.port, timeout=30))

    def set_origin(self, store):
        with store.db:
            store.db.execute(
                "INSERT OR REPLACE INTO collector_identity(singleton, id, origin_host, display_label, created_at) "
                "VALUES(1, 'synthetic', 'origin-a', 'synthetic', 0)")

    def capture(self, store, native, text):
        source = self.root / (native + ".jsonl")
        source.write_text(json.dumps({
            "type": "message", "id": "m-" + native, "parentId": None,
            "timestamp": "2026-10-30T00:00:00Z",
            "message": {"role": "user", "content": [{"type": "text", "text": text}],
                        "meta": {"messageId": "m-" + native}},
        }, separators=(",", ":")) + "\n")
        return archive_module.capture(store.db, store.archive_dir, "codex", native, source)

    def sync(self, store):
        client = self.client()
        try:
            return mirror.sync(
                store, self.config, "cloudflare", client=client, upload_client_factory=self.client,
                recipients=self.recipients, concurrency=1)
        finally:
            client.close()

    def snapshots(self):
        client = self.client()
        try:
            return mirror.snapshots(self.config, client=client)
        finally:
            client.close()

    @staticmethod
    def skip_snapshot(*_args, **kwargs):
        return {"id": "d" * 64, "revision": kwargs["revision"], "duplicate": True, "db_size": 0,
                "chunks": 0, "chunks_uploaded": 0, "objects": 0, "objects_uploaded": 0,
                "object_bytes": 0, "bytes_plaintext": 0, "bytes_ciphertext": 0}

    def test_snapshot_restore_replays_a_generation_committed_after_the_snapshot(self):
        state = self.root / "source"
        store = Store(state)
        try:
            self.set_origin(store)
            self.capture(store, "native-1", "first")
            first = self.sync(store)
            self.assertEqual(first["generations_committed"], 1)
            self.assertEqual(first["snapshots_created"], 1)
            snapshots = self.snapshots()
            self.assertEqual(len(snapshots), 1)
            snapshot_id = snapshots[0]["id"]

            self.capture(store, "native-2", "second")
            with mock.patch.object(mirror, "upload_snapshot", side_effect=self.skip_snapshot):
                second = self.sync(store)
            self.assertEqual(second["generations_committed"], 1)
            self.assertEqual(len(self.snapshots()), 1)
        finally:
            store.close()

        client = self.client()
        try:
            verified = mirror.verify(self.config, client=client, objects=True)
            self.assertEqual(verified["generations"], 2)
            self.assertEqual(verified["snapshots"], 1)
            self.assertGreater(verified["sampled"], 0)
            collected = mirror.gc(self.config, client=client)
            self.assertEqual(collected["apply"], False)
            self.assertEqual(collected["snapshots_retained"], 1)
        finally:
            client.close()

        shutil.rmtree(state)
        client = self.client()
        try:
            report = mirror.restore(
                self.config, "cloudflare", snapshot_id, self.root / "restored",
                client=client, identity_path=self.identity)
        finally:
            client.close()
        self.assertEqual(report["replayed"], 1)

        restored = Store(self.root / "restored")
        try:
            generations = restored.db.execute("SELECT id FROM archive_generation ORDER BY id").fetchall()
            self.assertEqual(len(generations), 2)
            for row in generations:
                archive_module.verify_generation(restored.db, restored.archive_dir, row["id"])
            tables = {row[0] for row in restored.db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
            if "learning_projects" in tables:
                self.assertEqual(restored.db.execute(
                    "SELECT count(*) FROM learning_projects WHERE enabled = 1").fetchone()[0], 0)
            if "learning_global_grant" in tables:
                self.assertEqual(restored.db.execute(
                    "SELECT count(*) FROM learning_global_grant").fetchone()[0], 0)
            pinned = cast(dict[str, Any] | None, restored.mirror_remote_state("cloudflare"))
            self.assertIsNotNone(pinned)
            self.assertEqual(cast(dict[str, Any], pinned)["store_id"], "usr-memories")
        finally:
            restored.close()

    def test_a_restore_applies_tombstones_newer_than_the_snapshot(self):
        state = self.root / "source"
        store = Store(state)
        try:
            self.set_origin(store)
            self.capture(store, "native-1", "forget me")
            self.sync(store)
            snapshot_id = self.snapshots()[0]["id"]
            store.forget_session("codex:native-1", time.time())
            with mock.patch.object(mirror, "upload_snapshot", side_effect=self.skip_snapshot):
                self.sync(store)
        finally:
            store.close()

        shutil.rmtree(state)
        client = self.client()
        try:
            report = mirror.restore(
                self.config, "cloudflare", snapshot_id, self.root / "restored",
                client=client, identity_path=self.identity)
        finally:
            client.close()
        self.assertEqual(report["tombstones"], 1)
        restored = Store(self.root / "restored")
        try:
            self.assertEqual(restored.db.execute("SELECT count(*) FROM archive_generation").fetchone()[0], 0)
            self.assertEqual(restored.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)
            self.assertEqual(restored.db.execute("SELECT count(*) FROM tombstone").fetchone()[0], 1)
        finally:
            restored.close()

    def test_rotation_reencrypts_objects_and_only_the_new_identity_restores(self):
        state = self.root / "source"
        store = Store(state)
        try:
            self.set_origin(store)
            self.capture(store, "native-1", "rotate me")
            self.sync(store)
        finally:
            store.close()

        new_identity = self.root / "new.key"
        new_recipient = mirror_crypto.keygen(new_identity)
        new_recipients_file = self.root / "new-recipients.txt"
        new_recipients_file.write_text(new_recipient + "\n")
        client = self.client()
        try:
            rotated = mirror.rotate(
                self.config, recipients_file=new_recipients_file, identity_file=new_identity,
                old_identity_file=self.identity, client=client)
            self.assertGreaterEqual(rotated["rotated"], 1)
            new_config = replace(
                self.config, age_identity_file=new_identity, age_recipients_file=new_recipients_file)
            verified = mirror.verify(new_config, client=client, objects=True)
            self.assertGreater(verified["sampled"], 0)
            restored = mirror.restore(
                new_config, "cloudflare", self.snapshots()[0]["id"], self.root / "restored",
                client=client, identity_path=new_identity)
            self.assertEqual(restored["replayed"], 0)
            with self.assertRaises(mirror.MirrorError):
                mirror.restore(
                    self.config, "cloudflare", self.snapshots()[0]["id"], self.root / "old-restored",
                    client=client, identity_path=self.identity)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
