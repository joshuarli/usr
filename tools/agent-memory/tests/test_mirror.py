#!/usr/bin/env python3
"""Mirror protocol parity, configuration, and pooled-client behavior."""
import hashlib
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import cast
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
WORK_TMP = ROOT / ".work" / "tmp"
WORK_TMP.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools" / "agent-memory" / "src"))

from agent_memory import archive as archive_module  # noqa: E402
from agent_memory import mirror  # noqa: E402
from agent_memory import mirror_crypto  # noqa: E402

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
