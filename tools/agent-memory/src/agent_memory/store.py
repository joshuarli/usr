#!/usr/bin/env python3
"""Normalize and index local agent transcripts."""
import contextlib
import functools
import hashlib
import hmac
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import urllib.parse
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from agent_memory.transcripts import opencode_database, opencode_events, opencode_record, clean_native_id, coerce_roots, is_source_name, normalize, prefers_sibling, qualified_id, read_header
from agent_memory.types import DATABASE_HARNESSES, HARNESSES, OPENCODE_DB, OPENCODE_SUBPOSITIONS, SUBSTANTIVE_KINDS, Harness

DB_FILENAME = "sessions.sqlite3"
SCHEMA_VERSION = 7
ARCHIVE_DIRNAME = "archive"
ARCHIVE_OBJECTS = "objects"
ARCHIVE_COMPANIONS = {"grok": ("summary.json", "events.jsonl")}
_REDACTIONS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|sk_live_[A-Za-z0-9]{16,}|rk_live_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]{12,}|glpat-[A-Za-z0-9_-]{12,}|xox[baprs]-[A-Za-z0-9-]{12,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"),
    re.compile(r"(?i)\b(api[_-]?key|api[_-]?token|access[_-]?(?:token|key)|refresh[_-]?token|auth(?:orization)?|password|passwd|(?:client[_-]?)?secret(?:[_-]access[_-]?key)?|private[_-]?key|credential)\b\s*[:=]\s*(?:Bearer\s+)?([\"']?)([^\s,;\"']+)"),
)


class StoreError(RuntimeError):
    pass


class EvidenceUnavailable(StoreError):
    pass


class EvidenceChanged(StoreError):
    pass


def default_state_dir():
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base).expanduser() / "agent-sessions"


def redact(text):
    value = str(text)
    value = _REDACTIONS[2].sub(lambda match: match.group(1) + "=[REDACTED]", value)
    value = _REDACTIONS[0].sub("Bearer [REDACTED]", value)
    value = _REDACTIONS[1].sub("[REDACTED]", value)
    return value


_FTS_TERM = re.compile(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+|[A-Za-z0-9]{2,}")


def fts_fallback(query):
    seen = set()
    terms = []
    for match in _FTS_TERM.findall(str(query)):
        key = match.lower()
        if key not in seen:
            seen.add(key)
            terms.append(match)
    if not terms:
        return None
    return " OR ".join('"' + term.replace('"', "") + '"' for term in terms)


def _run_git(path, *args, stats=None):
    if stats is not None:
        stats["git_processes"] += 1
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def project_identity(path, stats=None):
    candidate = Path(path).expanduser().resolve()
    common_dir = _run_git(candidate, "rev-parse", "--path-format=absolute", "--git-common-dir", stats=stats)
    if not common_dir:
        common_dir = _run_git(candidate, "rev-parse", "--git-common-dir", stats=stats)
        if common_dir and not Path(common_dir).is_absolute():
            common_dir = str(candidate / common_dir)
    if common_dir:
        return "git:" + str(Path(common_dir).resolve())
    return "path:" + str(candidate)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _json_line(raw):
    return json.loads(raw.decode("utf-8-sig"))


def _open_source(path, stats=None):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    if stats is not None:
        stats["content_opens"] += 1
    return os.fdopen(fd, "rb")


def _stat_source(path, stats):
    stats["stat_operations"] += 1
    return os.stat(path, follow_symlinks=False)


def _fstat_source(stream, stats):
    if stats is not None:
        stats["stat_operations"] += 1
    return os.fstat(stream.fileno())


def _readline(stream, stats):
    data = stream.readline()
    if stats is not None:
        stats["bytes_read"] += len(data)
    return data


def _open_database(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise OSError("session database is not a regular file")
    connection = sqlite3.connect("file:%s?mode=ro" % urllib.parse.quote(str(path)), uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _prepare_state_dir(state_dir):
    path = Path(os.path.abspath(str(Path(state_dir).expanduser())))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise StoreError("session state path contains a symlink: " + str(current))
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise StoreError("session state path must be a real directory: " + str(path))
    os.chmod(path, 0o700)
    return path


def _prepare_database(path):
    if path.is_symlink():
        raise StoreError("session database may not be a symlink: " + str(path))
    if path.exists():
        mode = path.lstat()
        if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
            raise StoreError("session database must be a regular, unlinked file: " + str(path))
    else:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
        except FileExistsError:
            mode = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
                raise StoreError("session database must be a regular, unlinked file: " + str(path)) from None
    os.chmod(path, 0o600)


def _metadata(path, harness, project_cache, stats=None):
    try:
        header = read_header(harness, path, _open_source, stats)
    except OSError as exc:
        return None, "source_unreadable:" + exc.__class__.__name__
    cwd = header["cwd"]
    project = None
    if cwd:
        if cwd not in project_cache:
            project_cache[cwd] = project_identity(cwd, stats=stats)
        project = project_cache[cwd]
    file_stat = header["file_stat"]
    assert isinstance(file_stat, os.stat_result)
    first = header["first"]
    parent = header["parent_native"]
    return {
        "id": qualified_id(harness, clean_native_id(header["native_id"], path)),
        "native_id": clean_native_id(header["native_id"], path),
        "cwd": cwd,
        "project": project,
        "parent": qualified_id(harness, clean_native_id(parent, path)) if parent is not None else None,
        "source": header["source"],
        "thread_source": header["thread_source"],
        "ancestry": header["ancestry"],
        "harness": harness,
        "source_path": str(path.absolute()),
        "file_size": file_stat.st_size,
        "file_mtime_ns": file_stat.st_mtime_ns,
        "file_ctime_ns": file_stat.st_ctime_ns,
        "file_dev": file_stat.st_dev,
        "file_ino": file_stat.st_ino,
        "header_digest": _sha256(first) if first else "",
        "updated": file_stat.st_mtime,
        "branch_tip": header.get("branch_tip"),
        "workspaces": json.dumps(header["workspaces"], separators=(",", ":")) if header.get("workspaces") else None,
        "step_count": header.get("step_count"),
    }, None


def _is_learning_worker(meta):
    if not meta.get("source"):
        return False
    try:
        source = json.loads(meta["source"])
    except (TypeError, ValueError):
        return False
    if not isinstance(source, (dict, list)):
        return False
    markers = {"learning_worker", "learning-worker", "agent_session_learning"}

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in markers and child not in (None, False, "", 0):
                    return True
                if key in ("agent_role", "purpose", "worker_kind") and isinstance(child, str) and child.lower() in markers:
                    return True
                if visit(child):
                    return True
        elif isinstance(value, list):
            return any(visit(child) for child in value)
        return False

    return visit(source)


def _ephemeral(meta):
    paths = (meta.get("source_path", ""), meta.get("cwd", ""))
    return any(".ephemeral" in Path(value).parts for value in paths if value)


def _archive_path(archive_dir, harness, source):
    return Path(archive_dir) / harness / os.path.abspath(source).lstrip(os.sep)


def _live_source_for_archive(path, archive_dir, harness):
    try:
        prefix = os.path.abspath(str(Path(archive_dir) / harness))
        absolute = os.path.abspath(str(path))
    except (OSError, ValueError):
        return None
    if absolute == prefix or not absolute.startswith(prefix + os.sep):
        return None
    return absolute[len(prefix):] or None


def _copy_file_data(source, staging):
    if sys.platform == "darwin":
        try:
            import ctypes

            libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            clonefile = libc.clonefile
            clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
            clonefile.restype = ctypes.c_int
            if clonefile(os.fsencode(str(source)), os.fsencode(str(staging)), 0) == 0:
                return
        except (OSError, AttributeError):
            pass
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass
    shutil.copyfile(source, staging)


def _archive_copy(source, destination):
    source_stat = os.lstat(source)
    if not stat.S_ISREG(source_stat.st_mode):
        raise OSError("refusing to archive a non-regular file: " + str(source))
    try:
        destination_stat = os.lstat(destination)
    except FileNotFoundError:
        pass
    else:
        try:
            same = os.path.samestat(source_stat, destination_stat)
        except OSError:
            same = False
        if not same and destination_stat.st_size == source_stat.st_size and destination_stat.st_mtime_ns >= source_stat.st_mtime_ns:
            return False
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = destination.with_name(destination.name + ".copying")
    try:
        staging.unlink(missing_ok=True)
    except OSError:
        pass
    _copy_file_data(source, staging)
    os.chmod(staging, 0o600)
    os.replace(staging, destination)
    return True


def active_branch(events, tip=None):
    parents = {event["entry"]: event["parent_entry"] for event in events if event["entry"] is not None}
    if not parents:
        return list(events)
    path = set()
    if tip is not None and tip in parents:
        current = tip
    else:
        current = max((event for event in events if event["entry"] is not None), key=lambda event: event["position"])["entry"]
    while current in parents and current not in path:
        path.add(current)
        current = parents[current]
    return [event for event in events if event["entry"] is None or event["entry"] in path]


def _under(path, root):
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
        return True
    except (OSError, ValueError):
        return False


def _guarded(method: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(method)
    def guarded(*args: Any, **kwargs: Any) -> Any:
        try:
            return method(*args, **kwargs)
        except sqlite3.DatabaseError as exc:
            if isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower():
                raise
            raise StoreError("session index database is unreadable; preserve learning data and run `agent-sessions doctor`: " + str(exc)) from exc
    return guarded


class Store:
    def __init__(self, state_dir):
        self.state_dir = _prepare_state_dir(state_dir)
        self.archive_dir = self.state_dir / ARCHIVE_DIRNAME
        if self.archive_dir.is_symlink():
            raise StoreError("session archive may not be a symlink: " + str(self.archive_dir))
        self.archive_dir.mkdir(mode=0o700, exist_ok=True)
        os.chmod(self.archive_dir, 0o700)
        self.path = self.database_path(self.state_dir)
        try:
            _prepare_database(self.path)
            self.db = sqlite3.connect(str(self.path), timeout=10)
        except StoreError:
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            raise StoreError("cannot open session index; run `agent-sessions doctor` for recovery guidance: " + str(exc)) from exc
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA busy_timeout = 10000")
        try:
            self._initialize()
        except Exception:
            self.db.close()
            raise

    @staticmethod
    def database_path(state_dir):
        return Path(state_dir).expanduser() / DB_FILENAME

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _initialize(self):
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise StoreError("session index schema is newer than this tool; upgrade agent-sessions before opening it")
            owned = {"sessions", "events", "events_fts", "index_issues", "unindexed_sources"}
            existing = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if version == 0 and existing & owned:
                raise StoreError("session index has an unversioned schema; run `agent-sessions doctor --rebuild-index` to rebuild only index tables")
            if version not in (0, 1, 2, 3, 4, 5, 6, SCHEMA_VERSION):
                raise StoreError("unsupported session index schema version " + str(version))
            if version == 1:
                if not self._schema_ready(1):
                    raise StoreError("session index schema is incomplete; run `agent-sessions doctor --rebuild-index` to rebuild only index tables")
                self._migrate_v1()
                version = 2
            if version == 2:
                if not self._schema_ready(2):
                    raise StoreError("session index schema is incomplete; run `agent-sessions doctor --rebuild-index` to rebuild only index tables")
                self._migrate_v2()
                version = 3
            if version == 3:
                if not self._schema_ready(3):
                    raise StoreError("session index schema is incomplete; run `agent-sessions doctor --rebuild-index` to rebuild only index tables")
                self._migrate_v3()
                version = 4
            if version == 4:
                if not self._schema_ready(4):
                    raise StoreError("session index schema is incomplete; run `agent-sessions doctor --rebuild-index` to rebuild only index tables")
                self._migrate_v4()
                version = 5
            if version == 5:
                if not self._schema_ready(5):
                    raise StoreError("session index schema is incomplete; run `agent-sessions doctor --rebuild-index` to rebuild only index tables")
                self._migrate_v5()
                version = 6
            if version == 6:
                if not self._schema_ready(6):
                    raise StoreError("session index schema is incomplete; run `agent-sessions doctor --rebuild-index` to rebuild only index tables")
                self._migrate_v6()
                return
            if version == SCHEMA_VERSION:
                if not self._schema_ready(SCHEMA_VERSION):
                    raise StoreError("session index schema is incomplete; run `agent-sessions doctor --rebuild-index` to rebuild only index tables")
                return
            self._create_schema()
        except sqlite3.OperationalError as exc:
            self.db.rollback()
            if self._schema_ready():
                return
            if "fts5" in str(exc).lower() or "no such module" in str(exc).lower():
                raise StoreError("this Python SQLite build lacks FTS5; use a Python build with SQLite FTS5 enabled") from exc
            raise StoreError("cannot initialize session index: " + str(exc)) from exc
        except sqlite3.DatabaseError as exc:
            self.db.rollback()
            raise StoreError("session index database is unreadable; preserve learning data and run `agent-sessions doctor`: " + str(exc)) from exc

    def _schema_ready(self, expected_version=SCHEMA_VERSION):
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            existing = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            triggers = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
            session_columns = {row[1] for row in self.db.execute("PRAGMA table_info(sessions)")}
            event_columns = {row[1] for row in self.db.execute("PRAGMA table_info(events)")}
        except sqlite3.DatabaseError:
            return False
        return (
            version == expected_version
            and {"sessions", "events", "events_fts", "index_issues"} <= existing
            and {"events_ai", "events_ad", "events_au"} <= triggers
            and {"id", "project", "cwd", "parent", "source", "thread_source", "harness", "source_path", "updated", "indexed_bytes"} <= session_columns
            and {"id", "session", "position", "kind", "text", "timestamp", "call_id", "digest"} <= event_columns
            and (expected_version < 2 or "file_ctime_ns" in session_columns)
            and (expected_version < 3 or "unindexed_sources" in existing)
            and (expected_version < 4 or ({"native_id", "ancestry", "recognized_events", "unrecognized_events"} <= session_columns and "outcome" in event_columns))
            and (expected_version < 5 or "forgotten_sessions" in existing)
            and (expected_version < 6 or {"entry", "parent_entry"} <= event_columns)
            and (expected_version < 7 or ({"branch_tip", "workspaces", "step_count"} <= session_columns
                 and "synthetic_id" in event_columns
                 and {"archive_generation", "archive_object", "tombstone", "collector_identity", "project_map"} <= existing))
        )

    def _migrate_v1(self):
        try:
            self.db.executescript(
                "BEGIN IMMEDIATE;"
                "ALTER TABLE sessions ADD COLUMN file_ctime_ns INTEGER;"
                "PRAGMA user_version = 2;COMMIT;"
            )
        except sqlite3.DatabaseError:
            self.db.rollback()
            raise

    def _migrate_v2(self):
        try:
            self.db.executescript(
                "BEGIN IMMEDIATE;"
                "CREATE TABLE unindexed_sources ("
                "id TEXT NOT NULL, project TEXT, cwd TEXT NOT NULL, parent TEXT, source TEXT, thread_source TEXT, "
                "harness TEXT NOT NULL, source_path TEXT PRIMARY KEY, updated REAL NOT NULL, file_size INTEGER NOT NULL, "
                "file_mtime_ns INTEGER NOT NULL, file_ctime_ns INTEGER NOT NULL, file_dev INTEGER NOT NULL, "
                "file_ino INTEGER NOT NULL, header_digest TEXT NOT NULL);"
                "PRAGMA user_version = 3;COMMIT;"
            )
        except sqlite3.DatabaseError:
            self.db.rollback()
            raise

    def _migrate_v3(self):
        try:
            self.db.executescript(
                "BEGIN IMMEDIATE;"
                "ALTER TABLE sessions ADD COLUMN native_id TEXT;"
                "ALTER TABLE sessions ADD COLUMN ancestry TEXT NOT NULL DEFAULT 'known' CHECK(ancestry IN ('known','unknown'));"
                "ALTER TABLE sessions ADD COLUMN recognized_events INTEGER NOT NULL DEFAULT 0;"
                "ALTER TABLE sessions ADD COLUMN unrecognized_events INTEGER NOT NULL DEFAULT 0;"
                "ALTER TABLE events ADD COLUMN outcome TEXT CHECK(outcome IN ('ok','error'));"
                "ALTER TABLE unindexed_sources ADD COLUMN native_id TEXT;"
                "ALTER TABLE unindexed_sources ADD COLUMN ancestry TEXT NOT NULL DEFAULT 'known';"
                "UPDATE sessions SET native_id = id WHERE native_id IS NULL;"
                "UPDATE unindexed_sources SET native_id = id WHERE native_id IS NULL;"
                "UPDATE sessions SET recognized_events = (SELECT count(*) FROM events WHERE events.session = sessions.id AND events.kind IN (" + ",".join("'" + kind + "'" for kind in SUBSTANTIVE_KINDS) + ")),"
                " unrecognized_events = (SELECT count(*) FROM events WHERE events.session = sessions.id AND events.kind LIKE 'unknown:%');"
                "PRAGMA user_version = 4;COMMIT;"
            )
        except sqlite3.DatabaseError:
            self.db.rollback()
            raise

    def _migrate_v4(self):
        try:
            self.db.executescript(
                "BEGIN IMMEDIATE;"
                "CREATE TABLE IF NOT EXISTS forgotten_sessions (id TEXT PRIMARY KEY, forgotten_at REAL NOT NULL);"
                "PRAGMA user_version = 5;COMMIT;"
            )
        except sqlite3.DatabaseError:
            self.db.rollback()
            raise

    def _migrate_v5(self):
        try:
            self.db.executescript(
                "BEGIN IMMEDIATE;"
                "ALTER TABLE events ADD COLUMN entry TEXT;"
                "ALTER TABLE events ADD COLUMN parent_entry TEXT;"
                "DELETE FROM sessions WHERE harness = 'pi';"
                "PRAGMA user_version = 6;COMMIT;"
            )
        except sqlite3.DatabaseError:
            self.db.rollback()
            raise

    def _migrate_v6(self):
        try:
            self.db.executescript(
                "BEGIN IMMEDIATE;"
                "ALTER TABLE sessions ADD COLUMN branch_tip TEXT;"
                "ALTER TABLE sessions ADD COLUMN workspaces TEXT;"
                "ALTER TABLE sessions ADD COLUMN step_count INTEGER;"
                "ALTER TABLE events ADD COLUMN synthetic_id INTEGER NOT NULL DEFAULT 0;"
                "CREATE TABLE IF NOT EXISTS collector_identity ("
                "id TEXT PRIMARY KEY, origin_host TEXT NOT NULL, display_label TEXT NOT NULL, created_at REAL NOT NULL);"
                "CREATE TABLE IF NOT EXISTS origin_host ("
                "id TEXT PRIMARY KEY, display_label TEXT NOT NULL, created_at REAL NOT NULL);"
                "CREATE TABLE IF NOT EXISTS project_map ("
                "id TEXT PRIMARY KEY, origin_host TEXT NOT NULL, name TEXT NOT NULL, checkout_path TEXT, "
                "created_at REAL NOT NULL, UNIQUE(origin_host, name));"
                "CREATE TABLE IF NOT EXISTS archive_object ("
                "digest TEXT PRIMARY KEY, size INTEGER NOT NULL, created_at REAL NOT NULL);"
                "CREATE TABLE IF NOT EXISTS archive_generation ("
                "id INTEGER PRIMARY KEY, origin_host TEXT NOT NULL, harness TEXT NOT NULL, native_id TEXT NOT NULL, "
                "source_path TEXT NOT NULL, source_digest TEXT NOT NULL, source_size INTEGER NOT NULL, "
                "captured_at REAL NOT NULL, protocol INTEGER NOT NULL DEFAULT 1, stored_at REAL, indexed_at REAL, "
                "tombstoned INTEGER NOT NULL DEFAULT 0, "
                "UNIQUE(origin_host, harness, native_id, source_digest));"
                "CREATE TABLE IF NOT EXISTS archive_generation_object ("
                "generation INTEGER NOT NULL REFERENCES archive_generation(id) ON DELETE CASCADE, "
                "ordinal INTEGER NOT NULL, digest TEXT NOT NULL, size INTEGER NOT NULL, offset INTEGER NOT NULL, "
                "PRIMARY KEY(generation, ordinal));"
                "CREATE TABLE IF NOT EXISTS archive_artifact ("
                "generation INTEGER NOT NULL REFERENCES archive_generation(id) ON DELETE CASCADE, "
                "name TEXT NOT NULL, digest TEXT NOT NULL, size INTEGER NOT NULL, PRIMARY KEY(generation, name));"
                "CREATE TABLE IF NOT EXISTS transfer_generation ("
                "id INTEGER PRIMARY KEY, generation INTEGER NOT NULL REFERENCES archive_generation(id) ON DELETE CASCADE, "
                "remote TEXT NOT NULL, durable_at REAL, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, "
                "UNIQUE(generation, remote));"
                "CREATE TABLE IF NOT EXISTS tombstone ("
                "origin_host TEXT NOT NULL, harness TEXT NOT NULL, native_id TEXT NOT NULL, "
                "scope TEXT NOT NULL CHECK(scope IN ('local','global')), forgotten_at REAL NOT NULL, "
                "PRIMARY KEY(origin_host, harness, native_id));"
                "PRAGMA user_version = 7;COMMIT;"
            )
        except sqlite3.DatabaseError:
            self.db.rollback()
            raise

    def _create_schema(self):
        self.db.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE sessions ("
            "id TEXT PRIMARY KEY, project TEXT, cwd TEXT NOT NULL, parent TEXT, source TEXT, "
            "thread_source TEXT, harness TEXT NOT NULL, source_path TEXT NOT NULL, updated REAL NOT NULL, "
            "file_size INTEGER NOT NULL, file_mtime_ns INTEGER NOT NULL, file_ctime_ns INTEGER, file_dev INTEGER NOT NULL, "
            "file_ino INTEGER NOT NULL, indexed_bytes INTEGER NOT NULL DEFAULT 0, header_digest TEXT NOT NULL, "
            "checkpoint_position INTEGER, checkpoint_digest TEXT, malformed_lines INTEGER NOT NULL DEFAULT 0, "
            "partial_bytes INTEGER NOT NULL DEFAULT 0, coverage TEXT NOT NULL DEFAULT 'complete', native_id TEXT, "
            "ancestry TEXT NOT NULL DEFAULT 'known' CHECK(ancestry IN ('known','unknown')), "
            "recognized_events INTEGER NOT NULL DEFAULT 0, unrecognized_events INTEGER NOT NULL DEFAULT 0, "
            "branch_tip TEXT, workspaces TEXT, step_count INTEGER);"
            "CREATE TABLE unindexed_sources ("
            "id TEXT NOT NULL, project TEXT, cwd TEXT NOT NULL, parent TEXT, source TEXT, thread_source TEXT, "
            "harness TEXT NOT NULL, source_path TEXT PRIMARY KEY, updated REAL NOT NULL, file_size INTEGER NOT NULL, "
            "file_mtime_ns INTEGER NOT NULL, file_ctime_ns INTEGER NOT NULL, file_dev INTEGER NOT NULL, "
            "file_ino INTEGER NOT NULL, header_digest TEXT NOT NULL, native_id TEXT, ancestry TEXT NOT NULL DEFAULT 'known');"
            "CREATE INDEX sessions_project_updated ON sessions(project, updated DESC);"
            "CREATE INDEX sessions_parent ON sessions(parent);"
            "CREATE TABLE events ("
            "id INTEGER PRIMARY KEY, session TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, "
            "position INTEGER NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, timestamp TEXT, call_id TEXT, "
            "raw_type TEXT, digest TEXT NOT NULL, outcome TEXT CHECK(outcome IN ('ok','error')), entry TEXT, parent_entry TEXT, "
            "synthetic_id INTEGER NOT NULL DEFAULT 0, UNIQUE(session, position));"
            "CREATE INDEX events_session_position ON events(session, position);"
            "CREATE VIRTUAL TABLE events_fts USING fts5(text, content='events', content_rowid='id');"
            "CREATE TRIGGER events_ai AFTER INSERT ON events BEGIN "
            "INSERT INTO events_fts(rowid, text) VALUES (new.id, new.text); END;"
            "CREATE TRIGGER events_ad AFTER DELETE ON events BEGIN "
            "INSERT INTO events_fts(events_fts, rowid, text) VALUES ('delete', old.id, old.text); END;"
            "CREATE TRIGGER events_au AFTER UPDATE ON events BEGIN "
            "INSERT INTO events_fts(events_fts, rowid, text) VALUES ('delete', old.id, old.text); "
            "INSERT INTO events_fts(rowid, text) VALUES (new.id, new.text); END;"
            "CREATE TABLE IF NOT EXISTS forgotten_sessions (id TEXT PRIMARY KEY, forgotten_at REAL NOT NULL);"
            "CREATE TABLE index_issues ("
            "session TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, position INTEGER NOT NULL, "
            "kind TEXT NOT NULL, PRIMARY KEY(session, position));"
            "CREATE TABLE IF NOT EXISTS collector_identity ("
            "id TEXT PRIMARY KEY, origin_host TEXT NOT NULL, display_label TEXT NOT NULL, created_at REAL NOT NULL);"
            "CREATE TABLE IF NOT EXISTS origin_host ("
            "id TEXT PRIMARY KEY, display_label TEXT NOT NULL, created_at REAL NOT NULL);"
            "CREATE TABLE IF NOT EXISTS project_map ("
            "id TEXT PRIMARY KEY, origin_host TEXT NOT NULL, name TEXT NOT NULL, checkout_path TEXT, "
            "created_at REAL NOT NULL, UNIQUE(origin_host, name));"
            "CREATE TABLE IF NOT EXISTS archive_object ("
            "digest TEXT PRIMARY KEY, size INTEGER NOT NULL, created_at REAL NOT NULL);"
            "CREATE TABLE IF NOT EXISTS archive_generation ("
            "id INTEGER PRIMARY KEY, origin_host TEXT NOT NULL, harness TEXT NOT NULL, native_id TEXT NOT NULL, "
            "source_path TEXT NOT NULL, source_digest TEXT NOT NULL, source_size INTEGER NOT NULL, "
            "captured_at REAL NOT NULL, protocol INTEGER NOT NULL DEFAULT 1, stored_at REAL, indexed_at REAL, "
            "tombstoned INTEGER NOT NULL DEFAULT 0, "
            "UNIQUE(origin_host, harness, native_id, source_digest));"
            "CREATE TABLE IF NOT EXISTS archive_generation_object ("
            "generation INTEGER NOT NULL REFERENCES archive_generation(id) ON DELETE CASCADE, "
            "ordinal INTEGER NOT NULL, digest TEXT NOT NULL, size INTEGER NOT NULL, offset INTEGER NOT NULL, "
            "PRIMARY KEY(generation, ordinal));"
            "CREATE TABLE IF NOT EXISTS archive_artifact ("
            "generation INTEGER NOT NULL REFERENCES archive_generation(id) ON DELETE CASCADE, "
            "name TEXT NOT NULL, digest TEXT NOT NULL, size INTEGER NOT NULL, PRIMARY KEY(generation, name));"
            "CREATE TABLE IF NOT EXISTS transfer_generation ("
            "id INTEGER PRIMARY KEY, generation INTEGER NOT NULL REFERENCES archive_generation(id) ON DELETE CASCADE, "
            "remote TEXT NOT NULL, durable_at REAL, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, "
            "UNIQUE(generation, remote));"
            "CREATE TABLE IF NOT EXISTS tombstone ("
            "origin_host TEXT NOT NULL, harness TEXT NOT NULL, native_id TEXT NOT NULL, "
            "scope TEXT NOT NULL CHECK(scope IN ('local','global')), forgotten_at REAL NOT NULL, "
            "PRIMARY KEY(origin_host, harness, native_id));"
            "PRAGMA user_version = " + str(SCHEMA_VERSION) + ";COMMIT;"
        )

    @_guarded
    def refresh(self, roots=None, project=None, projects=None, *, updated_after=None, harnesses: tuple[Harness, ...] = HARNESSES):
        return self._refresh(roots, project, projects, updated_after=updated_after, harnesses=tuple(harnesses))

    @_guarded
    def refresh_headers(self, roots=None):
        return self._refresh(roots, None, set(), headers_only=True, harnesses=("codex",))

    def _refresh(self, roots=None, project=None, projects=None, *, updated_after=None, headers_only=False, harnesses: tuple[Harness, ...] = HARNESSES):
        if project is not None and projects is not None:
            raise ValueError("choose either project or projects")
        root_map = coerce_roots(roots)
        live_roots = [(harness, root) for harness in HARNESSES if harness in harnesses for root in root_map.get(harness, [])]
        roots = live_roots + [(harness, self._archive_root(harness, root)) for harness, root in live_roots]
        live_count = len(live_roots)
        live_identities = set()
        live_files: dict[str, tuple[int, int]] = {}
        live_database_sessions = set()
        project = str(project) if project is not None else None
        projects = frozenset(str(value) for value in projects) if projects is not None else None
        if updated_after is not None:
            updated_after = {str(project): float(timestamp) for project, timestamp in updated_after.items()}
            if projects is None or not set(updated_after) <= projects:
                raise ValueError("updated_after requires selected project identifiers")
        else:
            updated_after = {}
        cache = {}
        grouped = {}
        unreadable_paths = set()
        sqlite_changes = self.db.total_changes
        stats = {
            "sessions_seen": 0, "sessions_indexed": 0, "events_added": 0,
            "malformed_lines": 0, "partial_files": 0, "resets": 0,
            "deleted": 0, "skipped_project": 0, "skipped_ephemeral": 0,
            "skipped_learning_workers": 0, "unreadable": 0,
            "stat_operations": 0, "content_opens": 0, "bytes_read": 0,
            "git_processes": 0, "sqlite_changes": 0, "skipped_forgotten": 0,
            "archived": 0, "archive_errors": 0,
        }
        forgotten = {row[0] for row in self.db.execute("SELECT id FROM forgotten_sessions")}
        indexed_by_path = {
            row["source_path"]: dict(row)
            for row in self.db.execute("SELECT * FROM sessions")
        }
        unindexed_by_path = {
            row["source_path"]: dict(row)
            for row in self.db.execute("SELECT * FROM unindexed_sources")
        }
        present_paths = set()
        fresh_archives: set[str] = set()

        def admit(meta, existing, unchanged, source_path, root_order, path):
            if _ephemeral(meta):
                stats["skipped_ephemeral"] += 1
                return
            if meta["id"] in forgotten:
                stats["skipped_forgotten"] += 1
                return
            selected = (project is None or meta["project"] == project) and (
                projects is None or meta["project"] in projects
            )
            cutoff = updated_after.get(meta["project"])
            if cutoff is not None and meta["updated"] < cutoff:
                selected = False
            learning_worker = _is_learning_worker(meta)
            if existing is None and (learning_worker or not selected):
                self._cache_unindexed_metadata(meta, unindexed_by_path)
            if learning_worker:
                if headers_only:
                    with self.db:
                        self.db.execute("DELETE FROM unindexed_sources WHERE source_path = ?", (source_path,))
                stats["skipped_learning_workers"] += 1
                return
            for archived in self._archive_source(meta, path, stats):
                fresh_archives.add(archived)
            if headers_only:
                if not unchanged:
                    self._cache_unindexed_metadata(meta, unindexed_by_path)
                return
            grouped.setdefault(meta["id"], []).append((root_order, path, meta))

        for root_order, (harness, root) in enumerate(roots):
            if harness in DATABASE_HARNESSES:
                archive = self._archive_root(harness, root) if root_order < live_count else None
                self._discover_database(root_order, harness, root, admit, indexed_by_path, unindexed_by_path, cache, present_paths, unreadable_paths, stats, archive, live_database_sessions, forgotten)
                continue
            if not root.is_dir():
                continue
            walk_errors = []
            paths = []
            for directory, directories, filenames in os.walk(str(root.resolve()), onerror=walk_errors.append, followlinks=False):
                if ".ephemeral" in Path(directory).parts:
                    directories[:] = []
                    stats["skipped_ephemeral"] += 1
                    continue
                for filename in filenames:
                    if is_source_name(harness, filename):
                        candidate = Path(directory) / filename
                        if prefers_sibling(harness, candidate):
                            continue
                        paths.append(candidate)
            for error_path in walk_errors:
                stats["unreadable"] += 1
                unreadable_paths.add(str(Path(error_path.filename or root).absolute()))
            for path in sorted(paths):
                if any(part == ".ephemeral" for part in path.parts):
                    stats["skipped_ephemeral"] += 1
                    continue
                source_path = str(path.absolute())
                try:
                    source_stat = _stat_source(path, stats)
                except OSError:
                    stats["unreadable"] += 1
                    unreadable_paths.add(source_path)
                    continue
                if not stat.S_ISREG(source_stat.st_mode):
                    stats["unreadable"] += 1
                    unreadable_paths.add(source_path)
                    continue
                present_paths.add(source_path)
                identity = (source_stat.st_dev, source_stat.st_ino)
                if root_order >= live_count and identity in live_identities:
                    continue
                if root_order < live_count:
                    live_identities.add(identity)
                    live_files[os.path.abspath(source_path)] = (source_stat.st_size, source_stat.st_mtime_ns)
                else:
                    if os.path.abspath(source_path) in fresh_archives:
                        continue
                    live_source = _live_source_for_archive(path, self.archive_dir, harness)
                    if live_source is not None and live_source in live_files:
                        live_size, live_mtime_ns = live_files[live_source]
                        if source_stat.st_size == live_size and source_stat.st_mtime_ns >= live_mtime_ns:
                            continue
                existing = indexed_by_path.get(source_path)
                unindexed = unindexed_by_path.get(source_path)
                if self._cached_metadata_matches(existing, source_stat):
                    meta = existing
                elif self._cached_metadata_matches(unindexed, source_stat):
                    meta = unindexed
                else:
                    meta, error = _metadata(path, harness, cache, stats)
                    if error:
                        stats["unreadable"] += 1
                        unreadable_paths.add(source_path)
                        continue
                admit(meta, existing, self._cached_metadata_matches(existing, source_stat), source_path, root_order, path)
        candidates = {}
        for session_id, paths in grouped.items():
            ordered = sorted(paths, key=lambda item: (item[0], str(item[1])))
            selected = ordered[0]
            candidates[session_id] = selected[2]
        stats["sessions_seen"] = len(candidates)
        for meta in candidates.values():
            if project is not None and meta["project"] != project or projects is not None and meta["project"] not in projects:
                stats["skipped_project"] += 1
                continue
            cutoff = updated_after.get(meta["project"])
            if cutoff is not None and meta["updated"] < cutoff:
                stats["skipped_project"] += 1
                continue
            changed, added, malformed, partial = self._refresh_file(meta, stats)
            if meta["source_path"] in unindexed_by_path:
                with self.db:
                    self.db.execute("DELETE FROM unindexed_sources WHERE source_path = ?", (meta["source_path"],))
            stats["sessions_indexed"] += 1
            stats["events_added"] += added
            stats["malformed_lines"] += malformed
            stats["partial_files"] += int(partial > 0)
            stats["resets"] += int(changed)
        target_project = project
        scanned_roots = [root.resolve() for _, root in roots if root.is_dir()]
        rows = self.db.execute("SELECT id, project, source_path FROM sessions").fetchall()
        remove = []
        degraded = []
        for row in rows:
            if target_project is not None and row["project"] != target_project:
                continue
            if projects is not None and row["project"] not in projects:
                continue
            if not any(_under(row["source_path"], root) for root in scanned_roots):
                continue
            if any(row["source_path"] == path or _under(row["source_path"], path) for path in unreadable_paths):
                degraded.append(row["id"])
                continue
            if row["id"] not in candidates or (
                target_project is not None and candidates[row["id"]]["project"] != target_project
            ) or (
                projects is not None and candidates[row["id"]]["project"] not in projects
            ):
                remove.append(row["id"])
        if remove:
            with self.db:
                self.db.executemany("DELETE FROM sessions WHERE id = ?", ((value,) for value in remove))
            stats["deleted"] = len(remove)
        if degraded:
            with self.db:
                self.db.executemany("UPDATE sessions SET coverage = 'degraded' WHERE id = ?", ((value,) for value in degraded))
        stale_headers = [
            row["source_path"]
            for row in self.db.execute("SELECT source_path FROM unindexed_sources")
            if any(_under(row["source_path"], root) for root in scanned_roots)
            and row["source_path"] not in present_paths
            and not any(row["source_path"] == path or _under(row["source_path"], path) for path in unreadable_paths)
        ]
        if stale_headers:
            with self.db:
                self.db.executemany("DELETE FROM unindexed_sources WHERE source_path = ?", ((value,) for value in stale_headers))
        stats["sqlite_changes"] = self.db.total_changes - sqlite_changes
        return stats

    def _cache_unindexed_metadata(self, meta, cached):
        if self._file_metadata_matches(cached.get(meta["source_path"]), meta):
            return
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO unindexed_sources (id, project, cwd, parent, source, thread_source, harness, "
                "source_path, updated, file_size, file_mtime_ns, file_ctime_ns, file_dev, file_ino, header_digest, native_id, ancestry) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (meta["id"], meta["project"], meta["cwd"], meta["parent"], meta["source"], meta["thread_source"],
                 meta["harness"], meta["source_path"], meta["updated"], meta["file_size"], meta["file_mtime_ns"],
                 meta["file_ctime_ns"], meta["file_dev"], meta["file_ino"], meta["header_digest"], meta["native_id"], meta["ancestry"]),
            )
        cached[meta["source_path"]] = meta

    @staticmethod
    def _cached_metadata_matches(existing, source_stat):
        return Store._file_metadata_matches(existing, {
            "file_size": source_stat.st_size,
            "file_mtime_ns": source_stat.st_mtime_ns,
            "file_ctime_ns": source_stat.st_ctime_ns,
            "file_dev": source_stat.st_dev,
            "file_ino": source_stat.st_ino,
        })

    @staticmethod
    def _file_metadata_matches(existing, meta):
        return existing is not None and existing["file_ctime_ns"] is not None and all(
            existing[key] == meta[key]
            for key in ("file_size", "file_mtime_ns", "file_ctime_ns", "file_dev", "file_ino")
        )

    def _discover_database(self, root_order, harness: Harness, root, admit, indexed_by_path, unindexed_by_path, cache, present_paths, unreadable_paths, stats, archive, known_sessions, forgotten):
        database = opencode_database(root)
        if database is None:
            return
        try:
            with contextlib.closing(_open_database(database)) as connection:
                sessions = connection.execute(
                    "SELECT id, parent_id, fork_session_id, directory, time_created, time_updated FROM session_v2").fetchall()
                counts = {row[0]: (row[1], row[2]) for row in connection.execute(
                    "SELECT session_id, count(*), max(time_updated) FROM session_message GROUP BY session_id")}
                if archive is not None:
                    try:
                        self._archive_database(connection, sessions, counts, archive, forgotten)
                    except (OSError, sqlite3.DatabaseError):
                        stats["archive_errors"] += 1
        except (OSError, sqlite3.DatabaseError):
            stats["unreadable"] += 1
            unreadable_paths.add(str(Path(root).absolute()))
            return
        stats["stat_operations"] += 1
        for row in sessions:
            native = clean_native_id(row["id"], database)
            if archive is not None:
                known_sessions.add(native)
            elif native in known_sessions:
                present_paths.add("%s#%s" % (database.absolute(), native))
                continue
            source_path = "%s#%s" % (database.absolute(), native)
            present_paths.add(source_path)
            count, latest = counts.get(row["id"], (0, 0))
            signature = {"file_size": count, "file_mtime_ns": latest or 0, "file_ctime_ns": row["time_updated"], "file_dev": 0, "file_ino": 0}
            existing = indexed_by_path.get(source_path)
            unindexed = unindexed_by_path.get(source_path)
            if self._file_metadata_matches(existing, signature):
                meta, unchanged = existing, True
            elif self._file_metadata_matches(unindexed, signature):
                meta, unchanged = unindexed, False
            else:
                cwd = row["directory"] if isinstance(row["directory"], str) else ""
                if cwd and cwd not in cache:
                    cache[cwd] = project_identity(cwd, stats=stats)
                lineage = row["parent_id"] or row["fork_session_id"]
                meta = dict(signature, **{
                    "id": qualified_id(harness, native), "native_id": native, "cwd": cwd, "project": cache.get(cwd) if cwd else None,
                    "parent": qualified_id(harness, clean_native_id(lineage, database)) if lineage else None,
                    "source": json.dumps({"subagent": {"parent": lineage}} if row["parent_id"] else "user"),
                    "thread_source": "subagent" if row["parent_id"] else "user", "ancestry": "known", "harness": harness,
                    "source_path": source_path, "header_digest": _sha256(("%s:%s" % (native, row["time_created"])).encode()),
                    "updated": max(row["time_updated"], latest or 0) / 1000.0,
                })
                unchanged = False
            admit(meta, existing, unchanged, source_path, root_order, database)

    def _archive_root(self, harness, root):
        root = Path(root)
        if harness in DATABASE_HARNESSES:
            return _archive_path(self.archive_dir, harness, root if root.name.endswith(".db") else root / OPENCODE_DB)
        return _archive_path(self.archive_dir, harness, root.resolve())

    def _archive_source(self, meta, path, stats):
        if meta["harness"] in DATABASE_HARNESSES or _under(path, self.archive_dir):
            return []
        archived: list[str] = []
        for name in (path.name, *ARCHIVE_COMPANIONS.get(meta["harness"], ())):
            source = path.parent / name
            destination = _archive_path(self.archive_dir, meta["harness"], source)
            try:
                if _archive_copy(source, destination):
                    stats["archived"] += 1
                    archived.append(os.path.abspath(str(destination)))
            except FileNotFoundError:
                continue
            except OSError:
                stats["archive_errors"] += 1
        return archived

    def _archive_database(self, source, sessions, counts, destination, forgotten):
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with contextlib.closing(sqlite3.connect(str(destination), timeout=10)) as target:
            target.executescript(
                "CREATE TABLE IF NOT EXISTS session_v2 (id TEXT PRIMARY KEY, parent_id TEXT, fork_session_id TEXT, directory TEXT NOT NULL, "
                "time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL);"
                "CREATE TABLE IF NOT EXISTS session_message (session_id TEXT NOT NULL, seq INTEGER NOT NULL, type TEXT NOT NULL, "
                "time_updated INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY (session_id, seq));"
            )
            os.chmod(destination, 0o600)
            archived = {row[0]: row[1:] for row in target.execute(
                "SELECT s.id, s.time_updated, count(m.seq), coalesce(max(m.time_updated), 0) FROM session_v2 s "
                "LEFT JOIN session_message m ON m.session_id = s.id GROUP BY s.id")}
            changed = []
            for row in sessions:
                if qualified_id("opencode", clean_native_id(row["id"], destination)) in forgotten:
                    continue
                count, latest = counts.get(row["id"], (0, 0))
                have = archived.get(row["id"])
                if have is None or have[0] != row["time_updated"] or have[1] < count or have[2] < (latest or 0):
                    changed.append(row)
            with target:
                for row in changed:
                    target.execute("INSERT OR REPLACE INTO session_v2 VALUES (?, ?, ?, ?, ?, ?)", tuple(row))
                    for message in source.execute("SELECT type, seq, time_updated, data FROM session_message WHERE session_id = ? ORDER BY seq", (row["id"],)):
                        target.execute("INSERT OR REPLACE INTO session_message VALUES (?, ?, ?, ?, ?)", (row["id"], message["seq"], message["type"], message["time_updated"], message["data"]))

    def _archived_copy(self, harness, path):
        path = Path(path)
        return path if _under(path, self.archive_dir) else _archive_path(self.archive_dir, harness, path)

    def _purge_archive(self, harness, source_path):
        if harness in DATABASE_HARNESSES:
            database, _, native = source_path.rpartition("#")
            archive = self._archived_copy(harness, database)
            if archive.is_file():
                with contextlib.closing(sqlite3.connect(str(archive), timeout=10)) as target, target:
                    target.execute("PRAGMA secure_delete = ON")
                    target.execute("DELETE FROM session_message WHERE session_id = ?", (native,))
                    target.execute("DELETE FROM session_v2 WHERE id = ?", (native,))
            return
        archive = self._archived_copy(harness, source_path)
        for name in (archive.name, *ARCHIVE_COMPANIONS.get(harness, ())):
            (archive.parent / name).unlink(missing_ok=True)

    def _refresh_database_session(self, meta, stats):
        existing = self.db.execute("SELECT * FROM sessions WHERE id = ?", (meta["id"],)).fetchone()
        if existing is not None and existing["project"] == meta["project"] and existing["source_path"] == meta["source_path"] and self._file_metadata_matches(existing, meta):
            return False, 0, 0, 0
        database, _, native = meta["source_path"].rpartition("#")
        try:
            with contextlib.closing(_open_database(database)) as connection:
                messages = connection.execute("SELECT seq, type, data FROM session_message WHERE session_id = ? ORDER BY seq", (native,)).fetchall()
        except (OSError, sqlite3.DatabaseError) as exc:
            raise StoreError("cannot read OpenCode database " + database + ": " + str(exc)) from exc
        stats["content_opens"] += 1
        added = malformed = recognized = unrecognized = 0
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE id = ?", (meta["id"],))
            self.db.execute(
                "INSERT OR IGNORE INTO sessions (id, project, cwd, parent, source, thread_source, harness, source_path, updated, "
                "file_size, file_mtime_ns, file_ctime_ns, file_dev, file_ino, indexed_bytes, header_digest, coverage, native_id, ancestry) "
                "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'degraded', ?, ? "
                "WHERE NOT EXISTS (SELECT 1 FROM forgotten_sessions WHERE id = ?)",
                (meta["id"], meta["project"], meta["cwd"], meta["parent"], meta["source"], meta["thread_source"], meta["harness"], meta["source_path"],
                 meta["updated"], meta["file_size"], meta["file_mtime_ns"], meta["file_ctime_ns"], meta["file_dev"], meta["file_ino"], meta["file_size"],
                 meta["header_digest"], meta["native_id"], meta["ancestry"], meta["id"]))
            if self.db.execute("SELECT 1 FROM sessions WHERE id = ?", (meta["id"],)).fetchone() is None:
                return False, 0, 0, 0
            for message in messages:
                text = message["data"]
                stats["bytes_read"] += len(text)
                digest = _sha256(text.encode("utf-8"))
                try:
                    data = json.loads(text)
                except ValueError:
                    self.db.execute("INSERT OR REPLACE INTO index_issues(session, position, kind) VALUES (?, ?, 'malformed_json')", (meta["id"], message["seq"] * OPENCODE_SUBPOSITIONS))
                    malformed += 1
                    continue
                for sub, record in opencode_events(message["type"], data):
                    self.db.execute(
                        "INSERT OR REPLACE INTO events(session, position, kind, text, timestamp, call_id, raw_type, digest, outcome) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (meta["id"], message["seq"] * OPENCODE_SUBPOSITIONS + sub, record["kind"], record["text"], record["timestamp"], record["call_id"],
                         record["raw_type"], digest, record["outcome"]))
                    added += 1
                    if record["kind"].startswith("unknown:"):
                        unrecognized += 1
                    elif record["kind"] in SUBSTANTIVE_KINDS:
                        recognized += 1
            coverage = "unsupported" if recognized == 0 and (unrecognized or malformed) else "degraded" if unrecognized or malformed else "complete"
            self.db.execute("UPDATE sessions SET coverage = ?, malformed_lines = ?, recognized_events = ?, unrecognized_events = ? WHERE id = ?",
                            (coverage, malformed, recognized, unrecognized, meta["id"]))
        return existing is not None, added, malformed, 0

    def _refresh_file(self, meta, stats):
        if meta["harness"] in DATABASE_HARNESSES:
            return self._refresh_database_session(meta, stats)
        existing = self.db.execute("SELECT * FROM sessions WHERE id = ?", (meta["id"],)).fetchone()
        reset = existing is not None and (
            existing["source_path"] != meta["source_path"]
            or existing["file_dev"] != meta["file_dev"]
            or existing["file_ino"] != meta["file_ino"]
            or meta["file_size"] < existing["indexed_bytes"]
            or existing["header_digest"] != meta["header_digest"]
            or (meta["file_size"] == existing["file_size"] and (
                meta["file_mtime_ns"] != existing["file_mtime_ns"]
                or existing["file_ctime_ns"] is not None and meta["file_ctime_ns"] != existing["file_ctime_ns"]
            ))
        )
        if (
            existing is not None
            and not reset
            and existing["project"] == meta["project"]
            and self._file_metadata_matches(existing, meta)
            and existing["indexed_bytes"] + existing["partial_bytes"] == meta["file_size"]
        ):
            return False, 0, 0, existing["partial_bytes"]
        if existing is not None and not reset and not self._checkpoint_valid(meta, existing, stats):
            reset = True
        if existing is not None and (reset or existing["project"] != meta["project"]):
            with self.db:
                self.db.execute("DELETE FROM sessions WHERE id = ?", (meta["id"],))
            existing = None
        if (
            existing is not None
            and existing["indexed_bytes"] + existing["partial_bytes"] == meta["file_size"]
            and self._file_metadata_matches(existing, meta)
        ):
            return False, 0, 0, existing["partial_bytes"]
        if existing is None:
            with self.db:
                self.db.execute(
                    "INSERT OR IGNORE INTO sessions (id, project, cwd, parent, source, thread_source, harness, source_path, updated, "
                    "file_size, file_mtime_ns, file_ctime_ns, file_dev, file_ino, indexed_bytes, header_digest, coverage, native_id, ancestry, "
                    "branch_tip, workspaces, step_count) "
                    "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'degraded', ?, ?, ?, ?, ? "
                    "WHERE NOT EXISTS (SELECT 1 FROM forgotten_sessions WHERE id = ?)",
                    (meta["id"], meta["project"], meta["cwd"], meta["parent"], meta["source"], meta["thread_source"],
                     meta["harness"], meta["source_path"], meta["updated"], meta["file_size"], meta["file_mtime_ns"],
                     meta["file_ctime_ns"], meta["file_dev"], meta["file_ino"], meta["header_digest"], meta["native_id"], meta["ancestry"],
                     meta.get("branch_tip"), meta.get("workspaces"), meta.get("step_count"), meta["id"]),
                )
                self.db.execute("DELETE FROM unindexed_sources WHERE source_path = ?", (meta["source_path"],))
            existing = self.db.execute("SELECT * FROM sessions WHERE id = ?", (meta["id"],)).fetchone()
            if existing is None:
                return False, 0, 0, 0
        offset = existing["indexed_bytes"]
        added = 0
        malformed = 0
        recognized = unrecognized = 0
        checkpoint_position = existing["checkpoint_position"]
        checkpoint_digest = existing["checkpoint_digest"]
        partial = 0
        try:
            with _open_source(meta["source_path"], stats) as stream:
                opened = _fstat_source(stream, stats)
                if (opened.st_dev, opened.st_ino) != (meta["file_dev"], meta["file_ino"]) or opened.st_size < meta["file_size"]:
                    raise StoreError("transcript was replaced while refresh was starting; retry refresh")
                stream.seek(offset)
                with self.db:
                    while True:
                        position = stream.tell()
                        raw = _readline(stream, stats)
                        if not raw:
                            break
                        if not raw.endswith(b"\n"):
                            partial = len(raw)
                            break
                        digest = _sha256(raw)
                        try:
                            obj = _json_line(raw)
                            records = normalize(obj, meta["harness"])
                        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
                            self.db.execute(
                                "INSERT OR REPLACE INTO index_issues(session, position, kind) VALUES (?, ?, 'malformed_json')",
                                (meta["id"], position),
                            )
                            malformed += 1
                        else:
                            for record in records:
                                self.db.execute(
                                    "INSERT OR REPLACE INTO events(session, position, kind, text, timestamp, call_id, raw_type, digest, outcome, entry, parent_entry, synthetic_id) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                    (meta["id"], position, record["kind"], record["text"], record["timestamp"],
                                     record["call_id"], record["raw_type"], digest, record["outcome"], record.get("entry"),
                                     record.get("parent_entry"), 1 if record.get("synthetic_id") else 0),
                                )
                                if record.get("truncated"):
                                    self.db.execute(
                                        "INSERT OR REPLACE INTO index_issues(session, position, kind) VALUES (?, ?, 'truncated_content')",
                                        (meta["id"], position),
                                    )
                                added += 1
                                if record["kind"].startswith("unknown:"):
                                    unrecognized += 1
                                elif record["kind"] in SUBSTANTIVE_KINDS:
                                    recognized += 1
                        offset = stream.tell()
                        checkpoint_position = position
                        checkpoint_digest = digest
                    malformed_total = self.db.execute(
                        "SELECT count(*) FROM index_issues WHERE session = ?", (meta["id"],)
                    ).fetchone()[0]
                    final_stat = _fstat_source(stream, stats)
                    size = final_stat.st_size
                    mtime_ns = final_stat.st_mtime_ns
                    ctime_ns = final_stat.st_ctime_ns
                    updated = final_stat.st_mtime
                    totals = self.db.execute(
                        "SELECT recognized_events + ?, unrecognized_events + ? FROM sessions WHERE id = ?",
                        (recognized, unrecognized, meta["id"]),
                    ).fetchone()
                    if totals[0] == 0 and (totals[1] or malformed_total):
                        coverage = "unsupported"
                    elif malformed_total or partial or totals[1]:
                        coverage = "degraded"
                    else:
                        coverage = "complete"
                    if coverage == "complete" and meta.get("step_count") and totals[0] + totals[1] < meta["step_count"]:
                        coverage = "degraded"
                        self.db.execute(
                            "INSERT OR REPLACE INTO index_issues(session, position, kind) VALUES (?, ?, 'truncated_session')",
                            (meta["id"], 0),
                        )
                    self.db.execute(
                        "UPDATE sessions SET updated = ?, file_size = ?, file_mtime_ns = ?, file_ctime_ns = ?, indexed_bytes = ?, "
                        "checkpoint_position = ?, checkpoint_digest = ?, malformed_lines = ?, partial_bytes = ?, coverage = ?, "
                        "recognized_events = ?, unrecognized_events = ? WHERE id = ?",
                        (updated, size, mtime_ns, ctime_ns, offset, checkpoint_position, checkpoint_digest, malformed_total, partial, coverage,
                         totals[0], totals[1], meta["id"]),
                    )
        except OSError as exc:
            raise StoreError("cannot read transcript " + meta["source_path"] + ": " + str(exc)) from exc
        return reset, added, malformed, partial

    def _checkpoint_valid(self, meta, existing, stats):
        position = existing["checkpoint_position"]
        digest = existing["checkpoint_digest"]
        if position is None or digest is None:
            return True
        try:
            with _open_source(meta["source_path"], stats) as stream:
                opened = _fstat_source(stream, stats)
                if (opened.st_dev, opened.st_ino) != (meta["file_dev"], meta["file_ino"]) or opened.st_size < meta["file_size"]:
                    return False
                stream.seek(position)
                raw = _readline(stream, stats)
        except OSError:
            return False
        return bool(raw and hmac.compare_digest(_sha256(raw), digest))

    @_guarded
    def resolve_evidence(self, session, position, digest):
        row = self.db.execute("SELECT source_path, harness, native_id FROM sessions WHERE id = ?", (str(session),)).fetchone()
        if row is None:
            raise EvidenceUnavailable("session is no longer indexed")
        if row["harness"] in DATABASE_HARNESSES:
            return self._resolve_database_evidence(row, session, position, digest)
        try:
            with _open_source(Path(row["source_path"])) as stream:
                stream.seek(int(position))
                raw = stream.readline()
        except FileNotFoundError:
            try:
                with _open_source(self._archived_copy(row["harness"], row["source_path"])) as stream:
                    stream.seek(int(position))
                    raw = stream.readline()
            except FileNotFoundError as exc:
                raise EvidenceUnavailable("indexed transcript source is unavailable: " + str(exc)) from exc
            except OSError as exc:
                raise EvidenceUnavailable("indexed transcript source is unavailable: " + str(exc)) from exc
        except OSError as exc:
            raise EvidenceUnavailable("indexed transcript source is unavailable: " + str(exc)) from exc
        if not raw or not hmac.compare_digest(_sha256(raw), str(digest)):
            raise EvidenceChanged("transcript evidence changed since indexing; refresh the session index")
        try:
            obj = _json_line(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise StoreError("transcript evidence is no longer valid JSON") from exc
        records = normalize(obj, row["harness"])
        if len(records) != 1:
            raise StoreError("transcript evidence does not normalize to one event")
        record = dict(records[0])
        record.update({"session": str(session), "position": int(position), "digest": str(digest)})
        return record

    @_guarded
    def forget_session(self, session, now):
        row = self.db.execute("SELECT harness, source_path FROM sessions WHERE id = ?", (str(session),)).fetchone()
        if row is not None:
            self._purge_archive(row["harness"], row["source_path"])
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE id = ?", (str(session),))
            self.db.execute("INSERT OR REPLACE INTO forgotten_sessions(id, forgotten_at) VALUES (?, ?)", (str(session), float(now)))

    @_guarded
    def coverage(self):
        rows = self.db.execute(
            "SELECT harness, count(*) AS sessions, coalesce(sum(recognized_events + unrecognized_events), 0) AS events, "
            "coalesce(sum(coverage = 'complete'), 0) AS complete, coalesce(sum(coverage = 'degraded'), 0) AS degraded, "
            "coalesce(sum(coverage = 'unsupported'), 0) AS unsupported, coalesce(sum(unrecognized_events), 0) AS unrecognized, "
            "coalesce(sum(ancestry = 'unknown'), 0) AS unknown_ancestry FROM sessions GROUP BY harness ORDER BY harness"
        )
        return [dict(row) for row in rows]

    @_guarded
    def unrecognized_kinds(self, limit=20):
        rows = self.db.execute(
            "SELECT s.harness AS harness, e.kind AS kind, count(*) AS events FROM events e JOIN sessions s ON s.id = e.session "
            "WHERE e.kind LIKE 'unknown:%' GROUP BY s.harness, e.kind ORDER BY events DESC LIMIT ?",
            (int(limit),),
        )
        return [dict(row) for row in rows]

    def _resolve_database_evidence(self, row, session, position, digest):
        database = row["source_path"].rpartition("#")[0]
        seq, sub = divmod(int(position), OPENCODE_SUBPOSITIONS)
        try:
            with contextlib.closing(_open_database(database)) as connection:
                found = connection.execute("SELECT type, data FROM session_message WHERE session_id = ? AND seq = ?", (row["native_id"], seq)).fetchone()
        except (OSError, sqlite3.DatabaseError):
            found = None
            live_unavailable = True
        else:
            live_unavailable = False
        if live_unavailable or found is None:
            try:
                with contextlib.closing(_open_database(str(self._archived_copy(row["harness"], database)))) as connection:
                    message = connection.execute("SELECT type, data FROM session_message WHERE session_id = ? AND seq = ?", (row["native_id"], seq)).fetchone()
            except (OSError, sqlite3.DatabaseError) as exc:
                raise EvidenceUnavailable("indexed OpenCode database is unavailable: " + str(exc)) from exc
            if message is None:
                if live_unavailable:
                    raise EvidenceUnavailable("indexed OpenCode database is unavailable")
                raise EvidenceChanged("transcript evidence changed since indexing; refresh the session index")
            if not hmac.compare_digest(_sha256(message["data"].encode("utf-8")), str(digest)):
                raise EvidenceChanged("transcript evidence changed since indexing; refresh the session index")
        else:
            message = found
            if not hmac.compare_digest(_sha256(message["data"].encode("utf-8")), str(digest)):
                raise EvidenceChanged("transcript evidence changed since indexing; refresh the session index")
        record = opencode_record(message["type"], message["data"], sub)
        if record is None:
            raise EvidenceChanged("transcript evidence no longer contains that event")
        record = dict(record)
        record.update({"session": str(session), "position": int(position), "digest": str(digest)})
        return record

    def _filters(self, kinds, since):
        clauses = []
        params = []
        if kinds:
            values = tuple(str(kind) for kind in kinds)
            clauses.append("e.kind IN (" + ",".join("?" for _ in values) + ")")
            params.extend(values)
        if since is not None:
            clauses.append("COALESCE(CAST(strftime('%s', e.timestamp) AS REAL), s.updated) >= ?")
            params.append(float(since))
        return (" AND " + " AND ".join(clauses)) if clauses else "", params

    @_guarded
    def search(self, query, project=None, *, limit=20, regex=False, kinds: Sequence[str] | None = None, since=None):
        if int(limit) < 1:
            raise ValueError("limit must be positive")
        project = str(project) if project is not None else None
        if regex:
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error as exc:
                raise StoreError("invalid regular expression: " + str(exc)) from exc
            sql = "SELECT e.session, e.position, e.digest, e.kind, e.text, e.timestamp, e.call_id, s.project, s.cwd, s.parent, s.source, s.thread_source, s.source_path, s.updated, s.harness "
            sql += "FROM events e JOIN sessions s ON s.id=e.session WHERE e.text != ''"
            params = []
            if project is not None:
                sql += " AND s.project = ?"
                params.append(project)
            filter_sql, filter_params = self._filters(kinds, since)
            sql += filter_sql
            params.extend(filter_params)
            sql += " ORDER BY s.updated DESC, e.position"
            matches = []
            for row in self.db.execute(sql, params):
                if pattern.search(row["text"]):
                    matches.append(dict(row))
                    if len(matches) >= limit:
                        break
            return matches
        sql = "SELECT e.session, e.position, e.digest, e.kind, e.text, e.timestamp, e.call_id, s.project, s.cwd, s.parent, s.source, s.thread_source, s.source_path, s.updated, s.harness "
        sql += "FROM events_fts JOIN events e ON e.id=events_fts.rowid JOIN sessions s ON s.id=e.session "
        sql += "WHERE events_fts MATCH ?"
        params = [query]
        if project is not None:
            sql += " AND s.project = ?"
            params.append(project)
        filter_sql, filter_params = self._filters(kinds, since)
        sql += filter_sql
        params.extend(filter_params)
        sql += " ORDER BY bm25(events_fts), s.updated DESC LIMIT ?"
        params.append(max(1, int(limit)))
        try:
            return [dict(row) for row in self.db.execute(sql, params)]
        except sqlite3.OperationalError as exc:
            fallback = fts_fallback(query)
            if fallback is not None and fallback != query:
                retry_params = [fallback, *params[1:]]
                try:
                    return [dict(row) for row in self.db.execute(sql, retry_params)]
                except sqlite3.OperationalError:
                    pass
            raise StoreError("FTS5 search failed; quote phrases and use AND/OR between terms: " + str(exc)) from exc

    @_guarded
    def recent(self, project=None, *, limit=20, kinds: Sequence[str] | None = None, since=None):
        if int(limit) < 1:
            raise ValueError("limit must be positive")
        project = str(project) if project is not None else None
        filter_sql, params = self._filters(kinds, since)
        project_sql = " AND s.project = ?" if project is not None else ""
        if project is not None:
            params.insert(0, project)
        sql = (
            "WITH ranked AS (SELECT e.session, e.position, e.digest, e.kind, e.text, e.timestamp, e.call_id, "
            "s.project, s.cwd, s.parent, s.source, s.thread_source, s.source_path, s.updated, s.harness, "
            "row_number() OVER (PARTITION BY e.session ORDER BY e.position DESC) AS rank "
            "FROM events e JOIN sessions s ON s.id=e.session WHERE 1=1" + project_sql + filter_sql + ") "
            "SELECT session, position, digest, kind, text, timestamp, call_id, project, cwd, parent, source, thread_source, source_path, updated, harness "
            "FROM ranked WHERE rank=1 ORDER BY updated DESC, position DESC LIMIT ?"
        )
        params.append(max(1, int(limit)))
        return [dict(row) for row in self.db.execute(sql, params)]

    @_guarded
    def session_events(self, session, project=None, *, position=None, before=3, after=3):
        if before < 0 or after < 0:
            raise ValueError("event window sizes cannot be negative")
        session = str(session)
        project = str(project) if project is not None else None
        session_row = self.db.execute("SELECT project FROM sessions WHERE id = ?", (session,)).fetchone()
        if session_row is None or (project is not None and session_row["project"] != project):
            raise StoreError("session is not indexed in this project scope")
        if position is None:
            target = self.db.execute("SELECT max(position) FROM events WHERE session = ?", (session,)).fetchone()[0]
            if target is None:
                raise StoreError("session has no complete indexed events")
        else:
            target = int(position)
            if self.db.execute("SELECT 1 FROM events WHERE session = ? AND position = ?", (session, target)).fetchone() is None:
                raise StoreError("event byte offset is not indexed for this session")
        columns = (
            "e.session, e.position, e.digest, e.kind, e.text, e.timestamp, e.call_id, "
            "s.project, s.cwd, s.parent, s.source, s.thread_source, s.source_path, s.updated, s.harness"
        )
        before_rows = self.db.execute(
            "SELECT " + columns + " FROM events e JOIN sessions s ON s.id=e.session "
            "WHERE e.session = ? AND e.position < ? ORDER BY e.position DESC LIMIT ?",
            (session, target, before),
        ).fetchall()
        target_row = self.db.execute(
            "SELECT " + columns + " FROM events e JOIN sessions s ON s.id=e.session "
            "WHERE e.session = ? AND e.position = ?",
            (session, target),
        ).fetchone()
        after_rows = self.db.execute(
            "SELECT " + columns + " FROM events e JOIN sessions s ON s.id=e.session "
            "WHERE e.session = ? AND e.position > ? ORDER BY e.position LIMIT ?",
            (session, target, after),
        ).fetchall()
        return [dict(row) for row in reversed(before_rows)] + [dict(target_row)] + [dict(row) for row in after_rows]


def rebuild_index(state_dir):
    state_dir = _prepare_state_dir(state_dir)
    path = Store.database_path(state_dir)
    if not path.exists():
        Store(state_dir).close()
        return
    try:
        _prepare_database(path)
        db = sqlite3.connect(str(path), timeout=10)
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise StoreError("refusing to rebuild an index from a newer schema version")
        result = db.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise StoreError("SQLite integrity check failed; preserve the database and recover it with SQLite before rebuilding")
        db.execute("PRAGMA foreign_keys = OFF")
        with db:
            for name in ("events_ai", "events_ad", "events_au"):
                db.execute("DROP TRIGGER IF EXISTS " + name)
            for name in ("events_fts", "index_issues", "events", "sessions", "unindexed_sources"):
                db.execute("DROP TABLE IF EXISTS " + name)
            db.execute("PRAGMA user_version = 0")
        db.close()
    except sqlite3.DatabaseError as exc:
        raise StoreError("cannot rebuild a corrupt session index without risking learning data: " + str(exc)) from exc
    Store(state_dir).close()
