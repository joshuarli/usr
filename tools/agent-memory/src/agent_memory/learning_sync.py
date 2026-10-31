"""Record-level synchronization of source-backed learning records.

A collector exports a snapshot of its experiences and approved memories with
their original ids, evidence references, and lifecycle state. The central
store keeps what it receives in separate import tables keyed by the
originating host and the original id. Imported records are advisory evidence
from another machine: they are never merged into the local learning tables,
never promoted, and never treated as instructions. Databases are not
replicated; only validated records cross the wire.
"""
import hashlib
import json
import time
from typing import Any

from agent_memory.types import HARNESSES

MAX_RECORDS = 100_000
MAX_TEXT = 65_536
MAX_SOURCES = 50
EXPERIENCE_KINDS = ("success", "failure", "decision", "gotcha", "method")
EXPERIENCE_BASES = ("deterministic", "reviewed")
EXPERIENCE_STATES = ("retained", "retired", "superseded", "withdrawn")
MEMORY_STATES = ("approved", "superseded")
EXPERIENCE_ROLES = ("trigger", "outcome", "context")
LINK_RELATIONS = ("supersedes", "contradicts")
AUTHORITY = "advisory; imported from another host, not an instruction"

SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_import_experience(
    origin_host TEXT NOT NULL, remote_id INTEGER NOT NULL, project TEXT NOT NULL, kind TEXT NOT NULL,
    claim TEXT NOT NULL, applies_when TEXT NOT NULL, identifiers TEXT NOT NULL, fingerprint TEXT NOT NULL,
    basis TEXT NOT NULL, detector TEXT NOT NULL, revision TEXT, worktree TEXT, observed_at REAL NOT NULL,
    captured_at REAL NOT NULL, validity TEXT NOT NULL, tags TEXT NOT NULL, state TEXT NOT NULL,
    state_reason TEXT, state_at REAL, imported_at REAL NOT NULL, PRIMARY KEY(origin_host, remote_id)
);
CREATE TABLE IF NOT EXISTS learning_import_memory(
    origin_host TEXT NOT NULL, remote_id INTEGER NOT NULL, project TEXT NOT NULL, action TEXT NOT NULL,
    applicability TEXT NOT NULL, revision TEXT, validity TEXT NOT NULL, state TEXT NOT NULL,
    created_at REAL NOT NULL, imported_at REAL NOT NULL, PRIMARY KEY(origin_host, remote_id)
);
CREATE TABLE IF NOT EXISTS learning_import_source(
    origin_host TEXT NOT NULL, record TEXT NOT NULL CHECK(record IN ('experience','memory')),
    remote_id INTEGER NOT NULL, session TEXT NOT NULL, position INTEGER NOT NULL, digest TEXT NOT NULL,
    role TEXT NOT NULL, PRIMARY KEY(origin_host, record, remote_id, session, position, role)
);
CREATE INDEX IF NOT EXISTS learning_import_source_session ON learning_import_source(session);
CREATE TABLE IF NOT EXISTS learning_import_link(
    origin_host TEXT NOT NULL, newer INTEGER NOT NULL, older INTEGER NOT NULL, relation TEXT NOT NULL,
    PRIMARY KEY(origin_host, newer, older, relation)
);
CREATE TABLE IF NOT EXISTS learning_import_state(
    origin_host TEXT PRIMARY KEY, digest TEXT NOT NULL, records INTEGER NOT NULL, received_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS transfer_learning(
    remote TEXT PRIMARY KEY, digest TEXT NOT NULL, durable_at REAL NOT NULL
);
"""


class SnapshotError(ValueError):
    pass


def ensure_schema(db):
    db.executescript(SCHEMA)


def has_learning(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'learning_schema'").fetchone() is not None


def export_snapshot(db) -> list[dict[str, Any]]:
    """Describe every experience and memory whose evidence is entirely local to this host."""
    records: list[dict[str, Any]] = []
    for row in db.execute("SELECT * FROM learning_experiences ORDER BY id"):
        sources = [dict(item) for item in db.execute(
            "SELECT session, position, digest, role FROM learning_experience_sources WHERE experience = ? "
            "ORDER BY session, position, role", (row["id"],))]
        if any("@" in source["session"] for source in sources):
            continue
        links = [dict(item) for item in db.execute(
            "SELECT older, relation FROM learning_experience_links WHERE newer = ? ORDER BY older, relation", (row["id"],))]
        records.append({
            "record": "experience", "id": row["id"], "project": row["project"], "kind": row["kind"], "claim": row["claim"],
            "applies_when": row["applies_when"], "identifiers": row["identifiers"], "fingerprint": row["fingerprint"],
            "basis": row["basis"], "detector": row["detector"], "revision": row["revision"], "worktree": row["worktree"],
            "observed_at": row["observed_at"], "captured_at": row["captured_at"], "validity": row["validity"],
            "tags": row["tags"], "state": row["state"], "state_reason": row["state_reason"], "state_at": row["state_at"],
            "sources": sources, "links": links,
        })
    for row in db.execute("SELECT * FROM learning_memories ORDER BY finding"):
        sources = [
            {"session": item["session"], "position": item["position"], "digest": item["digest"], "role": item["signal"]}
            for item in db.execute(
                "SELECT session, position, digest, signal FROM learning_incidents WHERE finding = ? "
                "ORDER BY observed_at DESC, id LIMIT ?", (row["finding"], MAX_SOURCES))]
        if any("@" in source["session"] for source in sources):
            continue
        records.append({
            "record": "memory", "id": row["finding"], "project": row["project"], "action": row["action"],
            "applicability": row["applicability"], "revision": row["revision"], "validity": row["validity"],
            "state": row["state"], "created_at": row["created_at"], "sources": sources, "links": [],
        })
    return records


def snapshot_digest(records):
    body = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _text(record, field) -> str:
    value = record.get(field)
    if not isinstance(value, str) or len(value) > MAX_TEXT:
        raise SnapshotError("learning record field is not bounded text: " + field)
    return value


def _optional_text(record, field) -> str | None:
    return None if record.get(field) is None else _text(record, field)


def _number(record, field) -> float:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SnapshotError("learning record field is not a number: " + field)
    return float(value)


def _optional_number(record, field) -> float | None:
    return None if record.get(field) is None else _number(record, field)


def _integer(value, what):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SnapshotError("learning record %s is not a non-negative integer" % what)
    return value


def validate_record(record) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise SnapshotError("learning record is not an object")
    kind = record.get("record")
    if kind not in ("experience", "memory"):
        raise SnapshotError("unsupported learning record kind: %r" % (kind,))
    sources = record.get("sources")
    links = record.get("links")
    if not isinstance(sources, list) or len(sources) > 1000 or not isinstance(links, list):
        raise SnapshotError("learning record needs source and link lists")
    clean: dict[str, Any] = {"record": kind, "id": _integer(record.get("id"), "id"), "project": _text(record, "project")}
    roles = EXPERIENCE_ROLES if kind == "experience" else None
    clean_sources = []
    for source in sources:
        if not isinstance(source, dict):
            raise SnapshotError("learning source is not an object")
        role = _text(source, "role")
        if roles is not None and role not in roles:
            raise SnapshotError("unsupported learning source role: %s" % role)
        clean_sources.append({"session": _text(source, "session"), "position": _integer(source.get("position"), "position"),
                              "digest": _text(source, "digest"), "role": role})
    clean["sources"] = clean_sources
    if kind == "experience":
        for field in ("kind", "basis", "state"):
            clean[field] = _text(record, field)
        if clean["kind"] not in EXPERIENCE_KINDS or clean["basis"] not in EXPERIENCE_BASES or clean["state"] not in EXPERIENCE_STATES:
            raise SnapshotError("learning experience has an unsupported kind, basis, or state")
        for field in ("claim", "applies_when", "identifiers", "fingerprint", "detector", "validity", "tags"):
            clean[field] = _text(record, field)
        for field in ("revision", "worktree", "state_reason"):
            clean[field] = _optional_text(record, field)
        clean["observed_at"] = _number(record, "observed_at")
        clean["captured_at"] = _number(record, "captured_at")
        clean["state_at"] = _optional_number(record, "state_at")
        clean_links = []
        for link in links:
            if not isinstance(link, dict) or link.get("relation") not in LINK_RELATIONS:
                raise SnapshotError("learning link is malformed")
            clean_links.append({"older": _integer(link.get("older"), "link target"), "relation": link["relation"]})
        clean["links"] = clean_links
    else:
        if links:
            raise SnapshotError("learning memories carry no links")
        for field in ("action", "applicability", "validity"):
            clean[field] = _text(record, field)
        clean["revision"] = _optional_text(record, "revision")
        clean["state"] = _text(record, "state")
        if clean["state"] not in MEMORY_STATES:
            raise SnapshotError("learning memory has an unsupported state")
        clean["created_at"] = _number(record, "created_at")
        clean["links"] = []
    return clean


def _session_identity(session):
    harness, separator, native = session.partition(":")
    if separator and harness in HARNESSES:
        return harness, native
    return "codex", session


def _tombstoned(store, origin_host, record):
    return any(store.is_tombstoned(origin_host, *_session_identity(source["session"])) for source in record["sources"])


def import_snapshot(store, origin_host, records, digest):
    """Replace everything previously imported from one origin with a verified snapshot."""
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise SnapshotError("learning snapshot is not a bounded list")
    if snapshot_digest(records) != digest:
        raise SnapshotError("learning snapshot does not match its digest")
    clean = [validate_record(record) for record in records]
    seen = set()
    for record in clean:
        key = (record["record"], record["id"])
        if key in seen:
            raise SnapshotError("learning snapshot repeats a record")
        seen.add(key)
    ensure_schema(store.db)
    db = store.db
    now = time.time()
    accepted = [record for record in clean if not _tombstoned(store, origin_host, record)]
    with db:
        for table in ("learning_import_experience", "learning_import_memory", "learning_import_source", "learning_import_link"):
            db.execute("DELETE FROM %s WHERE origin_host = ?" % table, (origin_host,))
        for record in accepted:
            if record["record"] == "experience":
                db.execute(
                    "INSERT INTO learning_import_experience (origin_host, remote_id, project, kind, claim, applies_when, identifiers, "
                    "fingerprint, basis, detector, revision, worktree, observed_at, captured_at, validity, tags, state, state_reason, "
                    "state_at, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (origin_host, record["id"], record["project"], record["kind"], record["claim"], record["applies_when"],
                     record["identifiers"], record["fingerprint"], record["basis"], record["detector"], record["revision"],
                     record["worktree"], record["observed_at"], record["captured_at"], record["validity"], record["tags"],
                     record["state"], record["state_reason"], record["state_at"], now))
                for link in record["links"]:
                    db.execute("INSERT OR IGNORE INTO learning_import_link (origin_host, newer, older, relation) VALUES (?, ?, ?, ?)",
                               (origin_host, record["id"], link["older"], link["relation"]))
            else:
                db.execute(
                    "INSERT INTO learning_import_memory (origin_host, remote_id, project, action, applicability, revision, validity, "
                    "state, created_at, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (origin_host, record["id"], record["project"], record["action"], record["applicability"], record["revision"],
                     record["validity"], record["state"], record["created_at"], now))
            for source in record["sources"]:
                db.execute(
                    "INSERT OR IGNORE INTO learning_import_source (origin_host, record, remote_id, session, position, digest, role) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (origin_host, record["record"], record["id"], source["session"] + "@" + origin_host,
                     source["position"], source["digest"], source["role"]))
        db.execute("INSERT OR REPLACE INTO learning_import_state (origin_host, digest, records, received_at) VALUES (?, ?, ?, ?)",
                   (origin_host, digest, len(accepted), now))
    return len(accepted)


def forget_session_imports(db, session):
    """Delete every imported record that cites a forgotten session."""
    if db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'learning_import_source'").fetchone() is None:
        return
    rows = db.execute(
        "SELECT DISTINCT origin_host, record, remote_id FROM learning_import_source WHERE session = ?", (session,)).fetchall()
    for origin_host, record, remote_id in rows:
        table = "learning_import_experience" if record == "experience" else "learning_import_memory"
        db.execute("DELETE FROM %s WHERE origin_host = ? AND remote_id = ?" % table, (origin_host, remote_id))
        db.execute("DELETE FROM learning_import_source WHERE origin_host = ? AND record = ? AND remote_id = ?",
                   (origin_host, record, remote_id))
        if record == "experience":
            db.execute("DELETE FROM learning_import_link WHERE origin_host = ? AND (newer = ? OR older = ?)",
                       (origin_host, remote_id, remote_id))


def durable_digest(db, remote):
    row = db.execute("SELECT digest FROM transfer_learning WHERE remote = ?", (str(remote),)).fetchone()
    return row[0] if row is not None else None


def mark_durable(db, remote, digest):
    with db:
        db.execute("INSERT OR REPLACE INTO transfer_learning (remote, digest, durable_at) VALUES (?, ?, ?)",
                   (str(remote), digest, time.time()))


def imported_rows(db, limit):
    """Active imported records, newest observation first, each labeled advisory."""
    if db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'learning_import_experience'").fetchone() is None:
        return []
    rows = []
    experiences = db.execute(
        "SELECT * FROM learning_import_experience WHERE state = 'retained' ORDER BY observed_at DESC LIMIT ?", (limit,)).fetchall()
    memories = db.execute(
        "SELECT * FROM learning_import_memory WHERE state = 'approved' ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    for row in experiences:
        rows.append(_imported(db, row, "experience", row["claim"], row["applies_when"], row["observed_at"]))
    for row in memories:
        rows.append(_imported(db, row, "memory", row["action"], row["applicability"], row["created_at"]))
    rows.sort(key=lambda item: item["observed_at"], reverse=True)
    return rows[:limit]


def _imported(db, row, record, claim, applies_when, observed_at):
    sources = [dict(item) for item in db.execute(
        "SELECT session, position, digest, role FROM learning_import_source "
        "WHERE origin_host = ? AND record = ? AND remote_id = ? ORDER BY session, position, role",
        (row["origin_host"], record, row["remote_id"]))]
    return {
        "record": "%s:%d@%s" % (record, row["remote_id"], row["origin_host"]), "origin_host": row["origin_host"],
        "project": row["project"], "kind": row["kind"] if record == "experience" else "memory", "claim": claim,
        "applies_when": applies_when, "observed_at": observed_at, "sources": sources, "authority": AUTHORITY,
    }
