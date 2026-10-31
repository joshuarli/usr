#!/usr/bin/env python3
"""Versioned transfer of captured generations over a byte stream.

The same receiver serves the in-process local transport and an SSH pipe, so a
quoting or framing bug cannot hide behind an untested local path. Every frame
is length-prefixed; no transcript content, path, or identifier is ever
interpolated into a shell command.
"""
import hashlib
import json
import socket
import struct
import time
import zlib
from typing import Any

from agent_memory import archive as archive_module

PROTOCOL = 1
MAX_FRAME = 4 * 1024 * 1024
MAX_BLOB = 64 * 1024 * 1024
COMPRESSION = "zlib"
LOCAL_SOCKET_TIMEOUT = 900


def compress(data):
    return zlib.compress(data, 6)


def decompress(data, expected):
    """Inflate to at most the declared size; a larger object is refused."""
    if expected < 0 or expected > MAX_BLOB:
        raise TransferError("declared object size is out of bounds")
    engine = zlib.decompressobj()
    try:
        out = engine.decompress(data, expected + 1)
        if len(out) > expected or engine.unconsumed_tail:
            raise TransferError("compressed object exceeds its declared size")
        out += engine.flush()
    except zlib.error as exc:
        raise TransferError("object failed to decompress: " + str(exc)) from exc
    if len(out) != expected:
        raise TransferError("decompressed object does not match its declared size")
    return out


class TransferError(RuntimeError):
    pass


def _read_exactly(stream, size):
    chunks = []
    remaining = size
    while remaining:
        data = stream.read(remaining)
        if not data:
            raise TransferError("connection closed mid-frame")
        chunks.append(data)
        remaining -= len(data)
    return b"".join(chunks)


def write_message(stream, value):
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(payload) > MAX_FRAME:
        raise TransferError("frame exceeds the protocol limit")
    stream.write(struct.pack(">Q", len(payload)))
    stream.write(payload)
    stream.flush()


def read_message(stream):
    header = _read_exactly(stream, 8)
    size = struct.unpack(">Q", header)[0]
    if size > MAX_FRAME:
        raise TransferError("frame exceeds the protocol limit")
    payload = _read_exactly(stream, size)
    try:
        value = json.loads(payload)
    except ValueError as exc:
        raise TransferError("frame is not valid JSON") from exc
    if not isinstance(value, dict):
        raise TransferError("frame is not an object")
    return value


def write_blob(stream, data):
    if len(data) > MAX_BLOB:
        raise TransferError("object exceeds the protocol limit")
    stream.write(struct.pack(">Q", len(data)))
    stream.write(data)
    stream.flush()


def read_blob(stream, size=None):
    declared = struct.unpack(">Q", _read_exactly(stream, 8))[0]
    if declared > MAX_BLOB:
        raise TransferError("object exceeds the protocol limit")
    if size is not None and declared != size:
        raise TransferError("object length does not match the manifest")
    return _read_exactly(stream, declared)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


class Sender:
    def __init__(self, store, remote, instream, outstream, origin, label):
        self.store, self.remote = store, remote
        self.instream, self.outstream = instream, outstream
        self.origin, self.label = origin, label
        self.compression = None
        self.endpoint = str(remote)
        self.raw_bytes = 0
        self.sent_bytes = 0
        self.stats: dict[str, Any] = {"delivered": [], "raw_bytes": 0, "sent_bytes": 0,
                                      "compression": None, "endpoint": str(remote)}

    def _expect(self, kind):
        message = read_message(self.instream)
        if message.get("type") == "error":
            raise TransferError(str(message.get("message")))
        if message.get("type") != kind:
            raise TransferError("expected %s frame, received %s" % (kind, message.get("type")))
        return message

    def handshake(self):
        write_message(self.outstream, {"type": "hello", "protocol": PROTOCOL, "origin": self.origin,
                                       "label": self.label, "compression": [COMPRESSION]})
        ready = self._expect("ready")
        if ready.get("protocol") != PROTOCOL:
            raise TransferError("central store speaks protocol %r" % ready.get("protocol"))
        self.compression = ready.get("compression")
        store_origin = ready.get("store")
        if isinstance(store_origin, str) and store_origin:
            self.endpoint = store_origin

    def send_tombstones(self):
        rows = self.store.db.execute(
            "SELECT origin_host, harness, native_id, scope, forgotten_at FROM tombstone").fetchall()
        for row in rows:
            payload = {"type": "tombstone", "origin_host": row["origin_host"], "harness": row["harness"],
                       "native_id": row["native_id"], "scope": row["scope"], "forgotten_at": row["forgotten_at"]}
            write_message(self.outstream, payload)
            self._expect("tombstone_ack")
            self.store.mark_tombstone_durable(row["origin_host"], row["harness"], row["native_id"], self.remote)

    def record_attempt(self, generation, remote, error):
        self.store.record_attempt(generation, remote, error)

    def pending(self):
        return self.store.db.execute(
            "SELECT g.* FROM archive_generation g LEFT JOIN transfer_generation t "
            "ON t.generation = g.id AND t.remote = ? WHERE t.durable_at IS NULL ORDER BY g.id",
            (self.endpoint,)).fetchall()

    def send_generation(self, generation):
        if str(generation["origin_host"]) != self.origin:
            raise TransferError("refusing to send a generation from another origin")
        chunks = [
            {"digest": row["digest"], "size": int(row["size"]), "offset": int(row["offset"])}
            for row in self.store.db.execute(
                "SELECT digest, size, offset FROM archive_generation_object WHERE generation = ? ORDER BY ordinal",
                (int(generation["id"]),))
        ]
        artifacts = [
            {"name": row["name"], "digest": row["digest"], "size": int(row["size"])}
            for row in self.store.db.execute(
                "SELECT name, digest, size FROM archive_artifact WHERE generation = ? ORDER BY name",
                (int(generation["id"]),))
        ]
        manifest = {
            "type": "generation",
            "origin_host": generation["origin_host"],
            "harness": generation["harness"],
            "native_id": generation["native_id"],
            "source_path": generation["source_path"],
            "workspace_path": generation["workspace_path"],
            "source_digest": generation["source_digest"],
            "source_size": int(generation["source_size"]),
            "captured_at": float(generation["captured_at"]),
            "chunks": chunks,
            "artifacts": artifacts,
        }
        write_message(self.outstream, manifest)
        needed = self._expect("need")
        wanted = set(needed.get("digests") or [])
        for chunk in chunks:
            if chunk["digest"] not in wanted:
                continue
            self._send_object(chunk["digest"])
            wanted.discard(chunk["digest"])
        for artifact in artifacts:
            if artifact["digest"] not in wanted:
                continue
            self._send_object(artifact["digest"])
            wanted.discard(artifact["digest"])
        if wanted:
            raise TransferError("central store requested an unknown object")
        write_message(self.outstream, {"type": "commit"})
        ack = self._expect("ack")
        if ack.get("origin_host") != manifest["origin_host"] or ack.get("source_digest") != manifest["source_digest"]:
            raise TransferError("acknowledgement does not match the delivered generation")
        return int(ack["generation"])

    def _send_object(self, digest):
        data = self.store.read_object_bytes(digest)
        encoding = "identity"
        payload = data
        if self.compression == COMPRESSION:
            packed = compress(data)
            if len(packed) < len(data):
                encoding, payload = COMPRESSION, packed
        self.raw_bytes += len(data)
        self.sent_bytes += len(payload)
        write_message(self.outstream, {"type": "object", "digest": digest, "encoding": encoding})
        write_blob(self.outstream, payload)

    def run(self, attempts=5, progress=None):
        try:
            self.handshake()
            self.send_tombstones()
        except (OSError, TransferError) as exc:
            for generation in self.pending():
                self.record_attempt(generation["id"], self.endpoint, str(exc))
            raise TransferError("cannot reach the central store: %s" % exc) from exc
        delivered = []
        for generation in self.pending():
            last = None
            for attempt in range(attempts):
                try:
                    local_id = self.send_generation(generation)
                    self.store.mark_durable(generation["id"], self.endpoint, local_id)
                    delivered.append(int(generation["id"]))
                    if progress is not None:
                        progress(len(delivered))
                    break
                except (OSError, TransferError) as exc:
                    last = exc
                    self.record_attempt(generation["id"], self.endpoint, str(exc))
                    if attempt + 1 >= attempts:
                        raise TransferError("delivery failed after %d attempts: %s" % (attempts, last)) from last
                    time.sleep(min(60, 2 ** attempt))
        write_message(self.outstream, {"type": "bye"})
        self._expect("done")
        self.stats.update({"delivered": delivered, "raw_bytes": self.raw_bytes, "sent_bytes": self.sent_bytes,
                           "compression": self.compression, "endpoint": self.endpoint})
        return delivered


def receiver(store, instream, outstream, allowed_origins=None):
    """Serve one connection. Bound to a fixed command; content is never code."""
    hello = read_message(instream)
    if hello.get("type") != "hello" or hello.get("protocol") != PROTOCOL:
        write_message(outstream, {"type": "error", "message": "unsupported protocol"})
        return
    origin = str(hello.get("origin") or "")
    if allowed_origins is not None and origin not in allowed_origins:
        write_message(outstream, {"type": "error", "message": "origin is not allowed: " + origin})
        return
    if not origin:
        write_message(outstream, {"type": "error", "message": "origin is required"})
        return
    offered = hello.get("compression")
    compression = COMPRESSION if isinstance(offered, list) and COMPRESSION in offered else None
    write_message(outstream, {"type": "ready", "protocol": PROTOCOL, "compression": compression,
                              "store": archive_module.origin_for(store.db)})
    while True:
        try:
            message = read_message(instream)
        except TransferError:
            raise
        kind = message.get("type")
        if kind == "bye":
            write_message(outstream, {"type": "done"})
            return
        if kind == "tombstone":
            store.apply_tombstone(origin, str(message["harness"]), str(message["native_id"]),
                                  str(message["scope"]), float(message["forgotten_at"]))
            write_message(outstream, {"type": "tombstone_ack"})
            continue
        if kind == "generation":
            _receive_generation(store, instream, outstream, message, origin)
            continue
        if kind == "query":
            try:
                rows = handle_query(store, str(message.get("op")), message.get("args") or {})
            except (KeyError, ValueError, TypeError, OSError) as exc:
                write_message(outstream, {"type": "error", "message": str(exc)})
                continue
            write_message(outstream, {"type": "result", "rows": rows})
            continue
        write_message(outstream, {"type": "error", "message": "unsupported frame: " + str(kind)})
        return


def _receive_generation(store, instream, outstream, manifest, connection_origin):
    origin = str(manifest["origin_host"])
    if origin != connection_origin:
        write_message(outstream, {"type": "error", "message": "generation origin does not match the connection"})
        raise TransferError("generation origin does not match the authenticated peer")
    harness = str(manifest["harness"])
    native = str(manifest["native_id"])
    source_digest = str(manifest["source_digest"])
    if store.is_tombstoned(origin, harness, native):
        write_message(outstream, {"type": "error", "message": "session is tombstoned"})
        raise TransferError("receiver refused a tombstoned session")
    existing = store.find_generation(origin, harness, native, source_digest)
    if existing is not None and store.generation_complete(existing):
        write_message(outstream, {"type": "need", "digests": []})
        _expect_object_or_commit(instream, outstream, store, [])
        write_message(outstream, {"type": "ack", "generation": int(existing), "origin_host": origin,
                                  "source_digest": source_digest, "durable": True})
        return
    chunks = manifest.get("chunks") or []
    artifacts = manifest.get("artifacts") or []
    if not isinstance(chunks, list) or not isinstance(artifacts, list):
        write_message(outstream, {"type": "error", "message": "malformed manifest"})
        raise TransferError("malformed manifest")
    wanted = []
    declared = {}
    for item in [*chunks, *artifacts]:
        digest = str(item.get("digest") or "")
        size = int(item.get("size") or -1)
        if not digest or size < 0:
            write_message(outstream, {"type": "error", "message": "malformed manifest entry"})
            raise TransferError("malformed manifest entry")
        if digest in declared and declared[digest] != size:
            write_message(outstream, {"type": "error", "message": "conflicting sizes for one digest"})
            raise TransferError("conflicting sizes for one digest")
        declared[digest] = size
        if not store.has_object(digest):
            wanted.append(digest)
    write_message(outstream, {"type": "need", "digests": wanted})
    received = {}
    while True:
        message = read_message(instream)
        if message.get("type") == "commit":
            break
        if message.get("type") != "object":
            write_message(outstream, {"type": "error", "message": "expected an object or commit"})
            raise TransferError("unexpected frame during object transfer")
        digest = str(message.get("digest") or "")
        expected = next((int(item["size"]) for item in [*chunks, *artifacts] if item["digest"] == digest), None)
        if expected is None:
            write_message(outstream, {"type": "error", "message": "object was not requested"})
            raise TransferError("unexpected object")
        encoding = message.get("encoding") or "identity"
        try:
            payload = read_blob(instream)
            if encoding == COMPRESSION:
                data = decompress(payload, expected)
            elif encoding == "identity":
                data = payload
            else:
                raise TransferError("unsupported object encoding: " + str(encoding))
            if len(data) != expected or _digest(data) != digest:
                raise TransferError("object failed verification: " + digest)
        except TransferError as exc:
            write_message(outstream, {"type": "error", "message": str(exc)})
            raise
        received[digest] = data
    generation = store.commit_generation(manifest, received)
    write_message(outstream, {"type": "ack", "generation": int(generation), "origin_host": origin,
                              "source_digest": source_digest, "durable": True})


def _expect_object_or_commit(instream, outstream, store, wanted):
    while True:
        message = read_message(instream)
        if message.get("type") == "commit":
            return
        if message.get("type") != "object":
            write_message(outstream, {"type": "error", "message": "unexpected frame"})
            raise TransferError("unexpected frame")
        data = read_blob(instream)
        store.store_object(data)


def local_pair(store, remote, origin, label):
    """Run sender and receiver in one process over an in-memory pipe."""
    return store, remote, origin, label


class _ActivityStream:
    """Record activity so the transport timeout measures idleness, not duration."""

    def __init__(self, stream, activity):
        self._stream = stream
        self._activity = activity

    def read(self, size=-1):
        data = self._stream.read(size)
        self._activity["t"] = time.monotonic()
        return data

    def write(self, data):
        written = self._stream.write(data)
        self._activity["t"] = time.monotonic()
        return written

    def flush(self):
        self._stream.flush()
        self._activity["t"] = time.monotonic()

    def close(self):
        self._stream.close()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _drain(stream, sink, limit=65536):
    try:
        while True:
            data = stream.read(4096)
            if not data:
                return
            if len(sink[0]) < limit:
                sink[0] += data
    except (OSError, ValueError):
        return


def ssh_sender(store, remote, host, command, origin, label, timeout=120, progress=None) -> dict[str, Any]:
    import subprocess
    import threading

    process = subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", host, "--", command],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    sink = [b""]
    assert process.stderr is not None
    drain = threading.Thread(target=_drain, args=(process.stderr, sink), daemon=True)
    drain.start()
    activity = {"t": time.monotonic()}
    finished = threading.Event()

    def expire():
        while not finished.wait(2.0):
            if time.monotonic() - activity["t"] <= timeout:
                continue
            for stream in (process.stdin, process.stdout):
                if stream is None:
                    continue
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
            return

    watchdog = threading.Thread(target=expire, daemon=True)
    watchdog.start()
    try:
        assert process.stdout is not None and process.stdin is not None
        sender = Sender(store, remote, _ActivityStream(process.stdout, activity),
                        _ActivityStream(process.stdin, activity), origin, label)
        sender.run(progress=progress)
        return sender.stats
    except (OSError, ValueError, TransferError) as exc:
        detail = sink[0].decode("utf-8", "replace").strip()[-600:]
        raise TransferError("ssh transport failed: %s%s" % (exc, ("; remote stderr: " + detail) if detail else "")) from exc
    finally:
        finished.set()
        stdin = process.stdin
        if stdin is not None:
            try:
                stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            raise TransferError("ssh transport timed out") from exc


def socket_timeout(stream, seconds):
    try:
        stream.settimeout(seconds)
    except (AttributeError, socket.error):
        pass


def local_sync(source_store, central_state_dir, remote, origin, label, attempts=3, progress=None) -> dict[str, Any]:
    """Run the sender and receiver over a real socketpair in one process.

    The receiver opens its own store: a SQLite connection belongs to the thread
    that created it, and reusing the caller's handle here is a real defect.
    """
    import threading

    from agent_memory.store import Store

    left, right = socket.socketpair()
    left.settimeout(LOCAL_SOCKET_TIMEOUT)
    right.settimeout(LOCAL_SOCKET_TIMEOUT)
    failure = {}

    def serve():
        try:
            with Store(central_state_dir) as central:
                with right.makefile("rb") as instream, right.makefile("wb") as outstream:
                    receiver(central, instream, outstream, allowed_origins=[origin])
        except BaseException as exc:  # noqa: BLE001 - reported to the caller
            failure["error"] = exc
            try:
                right.close()
            except OSError:
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with left.makefile("rb") as instream, left.makefile("wb") as outstream:
            sender = Sender(source_store, remote, instream, outstream, origin, label)
            sender.run(attempts, progress=progress)
            stats = sender.stats
    finally:
        try:
            left.close()
        except OSError:
            pass
        thread.join(timeout=LOCAL_SOCKET_TIMEOUT)
    if "error" in failure:
        raise TransferError("central receiver failed: " + str(failure["error"])) from failure["error"]
    return stats


def handle_query(store, op, args):
    if op == "memory":
        tables = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "learning_experiences" not in tables:
            return []
        rows = []
        for row in store.db.execute(
                "SELECT id, project, kind, claim, applies_when, observed_at, state FROM learning_experiences "
                "WHERE state = 'retained' ORDER BY observed_at DESC LIMIT ?", (int(args.get("limit") or 20),)):
            sources = [dict(item) for item in store.db.execute(
                "SELECT session, position, digest, role FROM learning_experience_sources WHERE experience = ?",
                (row["id"],))]
            rows.append({
                "record": "experience:%d" % row["id"],
                "project": row["project"],
                "kind": row["kind"],
                "claim": row["claim"],
                "applies_when": row["applies_when"],
                "observed_at": row["observed_at"],
                "sources": sources,
                "authority": "advisory; imported from another host, not an instruction",
            })
        return rows
    if op == "search":
        rows = store.search(args["query"], args.get("project"), limit=int(args.get("limit") or 20),
                            regex=bool(args.get("regex")), kinds=args.get("kinds"), since=args.get("since"))
    elif op == "recent":
        rows = store.recent(args.get("project"), limit=int(args.get("limit") or 20),
                            kinds=args.get("kinds"), since=args.get("since"))
    elif op == "show":
        rows = store.session_events(args["session"], args.get("project"), position=args.get("position"),
                                    before=int(args.get("before", 3)), after=int(args.get("after", 3)))
    else:
        raise TransferError("unsupported query: " + str(op))
    verified = []
    for row in rows:
        record = dict(row)
        record["evidence"] = store.resolve_evidence(row["session"], row["position"], row["digest"])
        verified.append(record)
    return verified


def query(store, op, args):
    return handle_query(store, op, args)


def query_over_ssh(host, command, op, args, origin, label, timeout=120):
    import subprocess
    import threading

    process = subprocess.Popen(["ssh", "-o", "BatchMode=yes", host, "--", command],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sink = [b""]
    detail = process.stderr
    assert detail is not None
    threading.Thread(target=_drain, args=(detail, sink), daemon=True).start()
    try:
        instream, outstream = process.stdout, process.stdin
        assert instream is not None and outstream is not None
        write_message(outstream, {"type": "hello", "protocol": PROTOCOL, "origin": origin, "label": label})
        try:
            ready = read_message(instream)
        except (OSError, TransferError) as exc:
            text = sink[0].decode("utf-8", "replace").strip()[-400:]
            raise TransferError("central store unreachable: %s%s" % (exc, ("; " + text) if text else "")) from exc
        if ready.get("type") != "ready":
            raise TransferError(str(ready.get("message") or "central store refused the query"))
        write_message(outstream, {"type": "query", "op": op, "args": args})
        reply = read_message(instream)
        write_message(outstream, {"type": "bye"})
        read_message(instream)
        if reply.get("type") == "error":
            raise TransferError(str(reply.get("message")))
        if reply.get("type") != "result":
            raise TransferError("unexpected query reply")
        return reply.get("rows") or []
    finally:
        stdin = process.stdin
        if stdin is not None:
            try:
                stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            raise TransferError("central query timed out") from exc
