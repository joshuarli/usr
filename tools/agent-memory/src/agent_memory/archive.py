#!/usr/bin/env python3
"""Content-addressed capture of agent transcripts.

Captured bytes are immutable objects named by digest. A generation records
what one capture of one native source observed: the chunk objects in order,
their offsets, and the source identity. Rewrites and truncations create a new
generation instead of destroying the previous one, and an unchanged source
reads no content bytes.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import stat
import time
from pathlib import Path

CHUNK_BYTES = 65536
PROTOCOL = 1
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_ARTIFACTS = 200


class ArchiveError(RuntimeError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_identity(db, label=None, regenerate=False):
    row = db.execute("SELECT id, origin_host, display_label FROM collector_identity WHERE singleton = 1").fetchone()
    if row is not None and not regenerate:
        return row["origin_host"], row["display_label"]
    origin = secrets.token_hex(16)
    display = str(label or "collector")
    now = time.time()
    with db:
        db.execute("INSERT OR IGNORE INTO origin_host (id, display_label, created_at) VALUES (?, ?, ?)", (origin, display, now))
        db.execute("INSERT OR REPLACE INTO collector_identity (singleton, id, origin_host, display_label, created_at) "
                   "VALUES (1, ?, ?, ?, ?)", (secrets.token_hex(16), origin, display, now))
    return origin, display


def origin_for(db):
    row = db.execute("SELECT origin_host FROM collector_identity WHERE singleton = 1").fetchone()
    if row is None:
        return ensure_identity(db)[0]
    return row["origin_host"]


def object_path(archive_dir, digest):
    return Path(archive_dir) / "objects" / digest[:2] / digest


def _write_object(archive_dir, data):
    digest = sha256(data)
    target = object_path(archive_dir, digest)
    if target.is_file() and not target.is_symlink():
        if target.stat().st_size == len(data):
            return digest, len(data), False
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = target.with_name(".tmp." + secrets.token_hex(8))
    try:
        descriptor = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(staging, target)
        _fsync_directory(target.parent)
    except BaseException:
        try:
            staging.unlink()
        except OSError:
            pass
        raise
    return digest, len(data), True


def read_object(archive_dir, digest):
    path = object_path(archive_dir, digest)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        data = stream.read()
    if sha256(data) != digest:
        raise ArchiveError("archived object is corrupt: " + digest)
    return data


def generation_chunks(db, generation):
    return [
        (int(row["offset"]), int(row["size"]), row["digest"])
        for row in db.execute(
            "SELECT offset, size, digest FROM archive_generation_object WHERE generation = ? ORDER BY ordinal",
            (int(generation),),
        )
    ]


def read_generation(db, archive_dir, generation, offset=0, length=None):
    chunks = generation_chunks(db, generation)
    if not chunks:
        raise ArchiveError("generation has no captured objects")
    wanted_from = int(offset)
    wanted_to = None if length is None else wanted_from + int(length)
    parts = []
    for start, size, chunk_digest in chunks:
        end = start + size
        if end <= wanted_from or (wanted_to is not None and start >= wanted_to):
            continue
        data = read_object(archive_dir, chunk_digest)
        lo = max(0, wanted_from - start)
        hi = len(data) if wanted_to is None else min(len(data), wanted_to - start)
        parts.append(data[lo:hi])
    return b"".join(parts)


def read_line_at(db, archive_dir, generation, position, limit=8 * 1024 * 1024):
    """Read one newline-terminated record starting at position, across chunks."""
    chunks = generation_chunks(db, generation)
    if not chunks:
        raise ArchiveError("generation has no captured objects")
    position = int(position)
    collected = bytearray()
    for start, size, chunk_digest in chunks:
        end = start + size
        if end <= position:
            continue
        data = read_object(archive_dir, chunk_digest)
        lo = max(0, position - start)
        collected.extend(data[lo:])
        if b"\n" in collected:
            break
        if len(collected) > limit:
            raise ArchiveError("archived record exceeds the read limit")
    line, separator, _ = bytes(collected).partition(b"\n")
    if not separator:
        raise ArchiveError("archived record is not newline terminated")
    return line + b"\n"


def verify_generation(db, archive_dir, generation):
    chunks = generation_chunks(db, generation)
    for _start, size, chunk_digest in chunks:
        data = read_object(archive_dir, chunk_digest)
        if len(data) != size:
            raise ArchiveError("archived object size mismatch: " + chunk_digest)
    return len(chunks)


def last_generation(db, origin_host, harness, native_id):
    return db.execute(
        "SELECT * FROM archive_generation WHERE origin_host = ? AND harness = ? AND native_id = ? "
        "ORDER BY captured_at DESC, id DESC LIMIT 1",
        (origin_host, harness, native_id),
    ).fetchone()


def _same_source(generation, info):
    if generation is None:
        return False
    return (
        int(generation["source_size"]) == info.st_size
        and int(generation["source_dev"]) == info.st_dev
        and int(generation["source_ino"]) == info.st_ino
        and int(generation["source_mtime_ns"]) == info.st_mtime_ns
        and int(generation["source_ctime_ns"]) == info.st_ctime_ns
    )


def _prefix_to_carry(db, archive_dir, previous, previous_size, stream, stats):
    """Reuse every captured chunk of a growing source after verifying its tail.

    The tail chunk is re-read and hashed, so an append costs one bounded tail
    verification plus the delta rather than a copy of the whole log.
    """
    if previous is None or not previous_size:
        return [], 0
    chunks = generation_chunks(db, previous["id"])
    if not chunks:
        return [], 0
    start, size, digest = chunks[-1]
    stream.seek(start)
    data = stream.read(size)
    stats["bytes_read"] = stats.get("bytes_read", 0) + len(data)
    if sha256(data) != digest:
        raise ArchiveError("source was rewritten beneath the captured prefix; retry capture")
    return chunks, previous_size


def capture(db, archive_dir, harness, native_id, source_path, *, workspace=None, artifacts=(), allow_artifacts=False, stats=None):
    """Capture the current bytes of source_path as a verified generation.

    Returns (generation_id, created). Raises OSError when the source cannot be
    read as a regular file.
    """
    stats = stats if stats is not None else {}
    archive_dir = Path(archive_dir)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(source_path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError("refusing to capture a non-regular file: " + str(source_path))
        origin_host = origin_for(db)
        previous = last_generation(db, origin_host, harness, native_id)
        if _same_source(previous, info):
            stats["archive_unchanged"] = stats.get("archive_unchanged", 0) + 1
            return int(previous["id"]), False
        previous_size = int(previous["source_size"]) if previous is not None else 0
        if previous is not None and info.st_size > previous_size:
            carried, start = _prefix_to_carry(db, archive_dir, previous, previous_size, stream, stats)
        else:
            carried, start = [], 0
        stream.seek(start)
        new_chunks = []
        digest = hashlib.sha256()
        for _offset, _size, chunk_digest in carried:
            digest.update(chunk_digest.encode("ascii"))
        while True:
            data = stream.read(CHUNK_BYTES)
            if not data:
                break
            stats["bytes_read"] = stats.get("bytes_read", 0) + len(data)
            chunk_digest, size, written = _write_object(archive_dir, data)
            if written:
                stats["archive_objects"] = stats.get("archive_objects", 0) + 1
                stats["archive_bytes"] = stats.get("archive_bytes", 0) + size
            new_chunks.append((start, size, chunk_digest))
            digest.update(chunk_digest.encode("ascii"))
            start += size
        final = os.fstat(stream.fileno())
        if (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns) != (
                info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns):
            raise ArchiveError("source changed during capture; retry capture")
        all_chunks = carried + new_chunks
    source_digest = digest.hexdigest()
    now = time.time()
    try:
        cursor = db.execute(
            "INSERT INTO archive_generation (origin_host, harness, native_id, source_path, source_digest, source_size, "
            "captured_at, protocol, stored_at, source_dev, source_ino, source_mtime_ns, source_ctime_ns, workspace_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (origin_host, harness, native_id, str(source_path), source_digest, final.st_size, now, PROTOCOL, now,
             final.st_dev, final.st_ino, final.st_mtime_ns, final.st_ctime_ns, workspace),
        )
    except sqlite3.IntegrityError:
        existing = db.execute(
            "SELECT id FROM archive_generation WHERE origin_host = ? AND harness = ? AND native_id = ? AND source_digest = ?",
            (origin_host, harness, native_id, source_digest),
        ).fetchone()
        stats["archive_unchanged"] = stats.get("archive_unchanged", 0) + 1
        return int(existing["id"]), False
    generation = int(cursor.lastrowid)
    with db:
        for index, (offset, size, chunk_digest) in enumerate(all_chunks):
            db.execute(
                "INSERT OR IGNORE INTO archive_object (digest, size, created_at) VALUES (?, ?, ?)",
                (chunk_digest, size, now),
            )
            db.execute(
                "INSERT INTO archive_generation_object (generation, ordinal, digest, size, offset) VALUES (?, ?, ?, ?, ?)",
                (generation, index, chunk_digest, size, offset),
            )
        if allow_artifacts:
            for name, data in artifacts:
                if len(data) > MAX_ARTIFACT_BYTES:
                    continue
                artifact_digest, size, _ = _write_object(archive_dir, data)
                db.execute(
                    "INSERT OR REPLACE INTO archive_artifact (generation, name, digest, size) VALUES (?, ?, ?, ?)",
                    (generation, str(name), artifact_digest, size),
                )
        db.execute("UPDATE archive_generation SET stored_at = ? WHERE id = ?", (now, generation))
    stats["archived"] = stats.get("archived", 0) + 1
    return generation, True


def capture_artifacts(paths, limit=MAX_ARTIFACTS):
    """Read bounded, session-owned artifact files without following symlinks.

    Returns (artifacts, refused). A companion that exists but is not a regular
    file is refused and counted instead of being followed.
    """
    collected = []
    refused = 0
    for name, path in paths:
        if len(collected) >= limit:
            break
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError:
            refused += 1
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT_BYTES:
            refused += 1
            continue
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            collected.append((str(name), stream.read(MAX_ARTIFACT_BYTES + 1)))
    return collected, refused


def retention_report(db):
    return {
        "generations": db.execute("SELECT count(*) FROM archive_generation").fetchone()[0],
        "objects": db.execute("SELECT count(*) FROM archive_object").fetchone()[0],
        "bytes": db.execute("SELECT coalesce(sum(size), 0) FROM archive_object").fetchone()[0],
        "tombstoned": db.execute("SELECT count(*) FROM archive_generation WHERE tombstoned = 1").fetchone()[0],
    }


def pin_manifest(db, destination):
    generations = [dict(row) for row in db.execute(
        "SELECT id, origin_host, harness, native_id, source_digest, source_size, captured_at FROM archive_generation ORDER BY id")]
    objects = [dict(row) for row in db.execute("SELECT digest, size FROM archive_object ORDER BY digest")]
    manifest = {"protocol": PROTOCOL, "generations": generations, "objects": objects}
    Path(destination).write_text(json.dumps(manifest, sort_keys=True, indent=1))
    return manifest
