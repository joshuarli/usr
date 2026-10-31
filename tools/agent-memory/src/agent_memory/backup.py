#!/usr/bin/env python3
"""Consistent snapshots and restore into a new destination.

A backup is a SQLite-API copy of the catalog plus a verified copy of every
immutable object the catalog references, pinned by digest in a manifest. Restore
verifies the manifest, restores the catalog, rebuilds derived indexes from
the captured bytes, and never activates a service or a review grant.
"""
import contextlib
import json
import os
import secrets
import shutil
import sqlite3
import time
from pathlib import Path

from agent_memory import archive as archive_module
from agent_memory.learning import apply_remote_forget

MANIFEST = "manifest.json"


class BackupError(RuntimeError):
    pass


def _fsync(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create(store, destination, protocol=1):
    """Write a complete backup to a staging directory, then publish it with one rename.

    The shared object lock is held from before the catalog snapshot until every
    referenced object is copied, so a concurrent forget can delete catalog rows
    but cannot unlink an object this backup still needs. A destination either
    does not exist or holds a complete backup whose manifest was written last.
    """
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise BackupError("backup destination must be new or empty: " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(destination.name + ".partial-" + secrets.token_hex(4))
    staging.mkdir(mode=0o700)
    try:
        manifest = _populate(store, staging, protocol)
        if destination.exists():
            destination.rmdir()
        os.rename(staging, destination)
        _fsync(destination.parent)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest


def _populate(store, staging, protocol):
    database = staging / "sessions.sqlite3"
    pinned = []
    with archive_module.object_lock(store.archive_dir):
        with contextlib.closing(sqlite3.connect(str(database))) as target:
            store.db.backup(target)
        os.chmod(database, 0o600)
        with contextlib.closing(sqlite3.connect("file:%s?mode=ro" % database.as_posix(), uri=True)) as snapshot:
            counts = {name: snapshot.execute("SELECT count(*) FROM " + name).fetchone()[0]
                      for name in ("archive_generation", "tombstone")}
            schema_version = snapshot.execute("PRAGMA user_version").fetchone()[0]
            for digest, size in snapshot.execute("SELECT digest, size FROM archive_object ORDER BY digest"):
                try:
                    data = archive_module.read_object(store.archive_dir, digest)
                except (OSError, archive_module.ArchiveError) as exc:
                    raise BackupError("snapshot references an unreadable object: %s (%s)" % (digest, exc)) from exc
                if len(data) != int(size):
                    raise BackupError("snapshot object has the wrong size: " + digest)
                archive_module._write_object(staging, data)
                pinned.append({"digest": digest, "size": int(size)})
    manifest = {
        "protocol": protocol,
        "created_at": time.time(),
        "schema_version": schema_version,
        "objects": pinned,
        "generations": counts["archive_generation"],
        "tombstones": counts["tombstone"],
    }
    pending = staging / (MANIFEST + ".tmp")
    pending.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    _fsync(pending)
    os.replace(pending, staging / MANIFEST)
    _fsync(staging)
    return manifest


def verify(destination):
    destination = Path(destination)
    manifest_path = destination / MANIFEST
    if not manifest_path.is_file():
        raise BackupError("backup manifest is missing")
    manifest = json.loads(manifest_path.read_text())
    for item in manifest.get("objects") or []:
        path = archive_module.object_path(destination, item["digest"])
        if not path.is_file():
            raise BackupError("backup object is missing: " + item["digest"])
        if path.stat().st_size != int(item["size"]):
            raise BackupError("backup object has the wrong size: " + item["digest"])
        if archive_module.sha256(path.read_bytes()) != item["digest"]:
            raise BackupError("backup object failed verification: " + item["digest"])
    database = destination / "sessions.sqlite3"
    if not database.is_file():
        raise BackupError("backup database is missing")
    with sqlite3.connect("file:%s?mode=ro" % database.as_posix(), uri=True) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BackupError("backup database failed integrity_check")
    return manifest


def restore(backup_dir, new_state_dir, tombstones_from=None):
    backup_dir = Path(backup_dir)
    manifest = verify(backup_dir)
    from agent_memory.store import SCHEMA_VERSION, Store, StoreError, _prepare_state_dir

    if int(manifest.get("schema_version") or 0) > SCHEMA_VERSION:
        raise BackupError("backup schema is newer than this tool")
    state = _prepare_state_dir(new_state_dir)
    if (state / "sessions.sqlite3").exists():
        raise BackupError("restore destination already holds a session store; choose a new directory")
    archive_dir = state / "archive"
    archive_dir.mkdir(mode=0o700, exist_ok=True)
    for item in manifest.get("objects") or []:
        target = archive_module.object_path(archive_dir, item["digest"])
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(archive_module.object_path(backup_dir, item["digest"]), target)
    database = state / "sessions.sqlite3"
    with sqlite3.connect("file:%s?mode=ro" % (backup_dir / "sessions.sqlite3").as_posix(), uri=True) as source:
        with sqlite3.connect(str(database)) as target:
            source.backup(target)
    os.chmod(database, 0o600)
    try:
        store = Store(state)
    except StoreError as exc:
        raise BackupError(str(exc)) from exc
    with store:
        tables = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        with store.db:
            if "learning_projects" in tables:
                store.db.execute("UPDATE learning_projects SET enabled = 0, grant_source = 'project'")
            if "learning_global_grant" in tables:
                store.db.execute("DELETE FROM learning_global_grant")
        store.reindex_generations()
        if tombstones_from is not None:
            with sqlite3.connect("file:%s?mode=ro" % (Path(tombstones_from) / "sessions.sqlite3").as_posix(), uri=True) as current:
                current.row_factory = sqlite3.Row
                for row in current.execute("SELECT origin_host, harness, native_id, scope, forgotten_at FROM tombstone"):
                    apply_remote_forget(store, row["origin_host"], row["harness"], row["native_id"],
                                        row["scope"], row["forgotten_at"])
    return manifest
