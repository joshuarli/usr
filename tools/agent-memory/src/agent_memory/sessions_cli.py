#!/usr/bin/env python3
"""Search and inspect the local agent session index."""
import argparse
import datetime
import os
import shutil
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from agent_memory import archive as archive_module
from agent_memory import backup as backup_module
from agent_memory import transfer as transfer_module
from agent_memory.store import Store, StoreError, default_state_dir, project_identity, rebuild_index, redact
from agent_memory.transcripts import canonical_harness
from agent_memory.types import HARNESSES, Harness


def _state_dir(args):
    return Path(args.state_dir).expanduser() if args.state_dir else default_state_dir()


def _project(args):
    if args.all_projects:
        return None
    return project_identity(args.project if args.project else Path.cwd())


def _roots(args) -> dict[Harness, list[str]] | None:
    if not args.root:
        return None
    roots: dict[Harness, list[str]] = {}
    for value in args.root:
        name, separator, path = value.partition("=")
        if separator:
            try:
                roots.setdefault(canonical_harness(name), []).append(path)
            except ValueError:
                roots.setdefault("codex", []).append(value)
        else:
            roots.setdefault("codex", []).append(value)
    return roots


def _harnesses(args) -> tuple[Harness, ...]:
    selected = getattr(args, "harness", None)
    if selected:
        return tuple(canonical_harness(value) for value in selected)
    return HARNESSES


def _stats(stats):
    print(
        "sessions={sessions_indexed} events={events_added} malformed={malformed_lines} "
        "partial={partial_files} resets={resets} deleted={deleted} skipped_project={skipped_project} "
        "skipped_ephemeral={skipped_ephemeral} skipped_learning_workers={skipped_learning_workers} "
        "archived={archived} archive_errors={archive_errors}".format(**stats)
    )


def _since_value(value):
    if value is None:
        return None
    match = re.fullmatch(r"([0-9]+)([smhdw])", value, re.IGNORECASE)
    if match:
        seconds = int(match.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[match.group(2).lower()]
        return time.time() - seconds
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use an ISO date/time or a duration such as 30d") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.timestamp()


def _source_label(source, thread_source):
    if thread_source in ("user", "subagent"):
        return thread_source
    if not source:
        return "unknown"
    try:
        value = json.loads(source)
    except ValueError:
        return "unknown"
    if isinstance(value, dict) and "subagent" in value:
        return "subagent"
    return value if isinstance(value, str) and value in ("user", "cli", "child") else "unknown"


def _display_path(path):
    return json.dumps(str(path), ensure_ascii=False)


def _timestamp_epoch(value):
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.timestamp()


def _snippet(text, query, regex):
    flat = " ".join(text.split())
    if not flat:
        return ""
    if regex:
        match = re.search(query, flat, re.IGNORECASE)
        index = match.start() if match else 0
    else:
        terms = [term.strip('"') for term in re.findall(r"[\w-]+", query) if term.upper() not in ("AND", "OR", "NOT", "NEAR")]
        positions = [flat.lower().find(term.lower()) for term in terms if term and flat.lower().find(term.lower()) >= 0]
        index = min(positions) if positions else 0
    start = max(0, index - 72)
    end = min(len(flat), index + 160)
    snippet = ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")
    return redact(snippet)




def config_path():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config"))
    return base.expanduser() / "agent-sessions" / "config.json"


def load_config():
    path = config_path()
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text())
    except ValueError as exc:
        raise StoreError("agent-sessions config is not valid JSON: " + str(path)) from exc
    if not isinstance(value, dict):
        raise StoreError("agent-sessions config must be an object: " + str(path))
    return value


def central_settings(args):
    settings = dict(load_config().get("central") or {})
    if getattr(args, "central_state", None):
        settings.update({"transport": "local", "state_dir": args.central_state})
    if not settings:
        raise StoreError("no central store is configured; set ~/.config/agent-sessions/config.json or pass --central-state")
    return settings


def open_central(args):
    settings = central_settings(args)
    if settings.get("transport", "local") != "local":
        raise StoreError("central transport %r cannot be opened directly" % settings.get("transport"))
    return Store(Path(os.path.expanduser(str(settings["state_dir"]))))


def central_rows(args, op, payload) -> list[dict[str, Any]]:
    settings = central_settings(args)
    if settings.get("transport", "local") == "local":
        with Store(Path(os.path.expanduser(str(settings["state_dir"])))) as store:
            return transfer_module.query(store, op, payload)
    host = settings.get("host")
    command = settings.get("command")
    if not host or not command:
        raise StoreError("ssh central settings need host and command")
    return transfer_module.query_over_ssh(host, command, op, payload, "query", "agent-sessions")


def _print_central_row(row, query=None, regex=False):
    evidence = row["evidence"]
    timestamp = evidence.get("timestamp") or datetime.datetime.fromtimestamp(row["updated"], datetime.timezone.utc).isoformat(timespec="seconds")
    print(
        f"session={row['session']} byte={row['position']} kind={evidence['kind']} time={timestamp[:19]} "
        f"source={_source_label(row.get('source'), row.get('thread_source'))} project={_display_path(row.get('cwd') or '')} "
        f"harness={row['harness']} origin={row.get('origin_host') or 'unknown'} generation={row.get('archive_generation')}"
    )
    if row.get("parent"):
        print("parent=" + str(row["parent"]))
    text = _snippet(evidence["text"], query, regex) if query is not None else redact(evidence["text"])
    print("  " + text)


def _memory(args):
    try:
        rows = central_rows(args, "memory", {"limit": args.limit})
        for raw in rows:
            row = dict(raw)
            observed = datetime.datetime.fromtimestamp(float(row["observed_at"]), datetime.timezone.utc)
            print("record=%s origin=%s project=%s kind=%s observed=%s" % (
                row["record"], row.get("origin_host") or "central", row["project"], row["kind"],
                observed.isoformat(timespec="seconds")))
            print("  claim=" + redact(row["claim"]))
            if row.get("applies_when"):
                print("  applies_when=" + redact(row["applies_when"]))
            for item in row.get("sources") or []:
                source = dict(item)
                print("  evidence=%s byte=%s digest=%s role=%s" % (
                    source["session"], source["position"], str(source["digest"])[:16], source["role"]))
            print("  authority=" + str(row["authority"]))
        print("records=%d scope=central" % len(rows))
        return 0
    except (OSError, StoreError) as exc:
        print("agent-sessions memory: " + str(exc), file=sys.stderr)
        return 1


def _identity(args):
    try:
        with Store(_state_dir(args)) as store:
            regenerate = args.regenerate or args.action == "regenerate"
            origin, label = archive_module.ensure_identity(store.db, label=args.label, regenerate=regenerate)
            print("origin_host=" + origin)
            print("label=" + str(label or ""))
            for row in store.db.execute("SELECT id, display_label, created_at FROM origin_host ORDER BY created_at"):
                print("known_origin=%s label=%s created=%s" % (row[0], row[1], datetime.datetime.fromtimestamp(row[2], datetime.timezone.utc).isoformat(timespec="seconds")))
        return 0
    except (OSError, StoreError) as exc:
        print("agent-sessions identity: " + str(exc), file=sys.stderr)
        return 1


def _project_command(args):
    try:
        with Store(_state_dir(args)) as store:
            if args.action == "list":
                for row in store.db.execute("SELECT origin_host, name, checkout_path FROM project_map ORDER BY name"):
                    print("project=%s origin=%s checkout=%s" % (row[1], row[0], _display_path(row[2] or "")))
                return 0
            if not args.name or not args.checkout:
                raise StoreError("project map needs --name and --checkout")
            origin = args.origin or archive_module.origin_for(store.db)
            with store.db:
                store.db.execute(
                    "INSERT OR REPLACE INTO project_map (id, origin_host, name, checkout_path, created_at) VALUES (?, ?, ?, ?, ?)",
                    (origin + ":" + args.name, origin, args.name, argparse_checkout(args.checkout), time.time()))
            print("mapped=%s origin=%s" % (args.name, origin))
        return 0
    except (OSError, StoreError) as exc:
        print("agent-sessions project: " + str(exc), file=sys.stderr)
        return 1


def argparse_checkout(value):
    return str(Path(value).expanduser().resolve())


def _sync(args):
    import fcntl

    state = _state_dir(args)
    try:
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock = open(state / "sync.lock", "a+")
    except OSError as exc:
        print("agent-sessions sync: " + str(exc), file=sys.stderr)
        return 1
    try:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("overlapped=1 pending=skipped")
            return 0
        with Store(state) as store:
            settings = dict(load_config().get("central") or {})
            if args.central_state:
                settings.update({"transport": "local", "state_dir": args.central_state})
            if not settings:
                raise StoreError("no central store is configured; set ~/.config/agent-sessions/config.json or pass --central-state")
            store.refresh(roots=_roots(args), project=None, harnesses=_harnesses(args))
            origin = archive_module.origin_for(store.db)
            pending = store.pending_transfers(args.to)
            if args.dry_run:
                print("pending=%d origin=%s remote=%s" % (pending, origin, args.to))
                return 0
            if settings.get("transport", "local") == "local":
                delivered = transfer_module.local_sync(
                    store, Path(os.path.expanduser(str(settings["state_dir"]))), args.to, origin, args.label or "collector")
            else:
                host = settings.get("host")
                command = settings.get("command")
                if not host or not command:
                    raise StoreError("ssh central settings need host and command")
                delivered = transfer_module.ssh_sender(store, args.to, host, command, origin, args.label or "collector")
            print("delivered=%d pending=%d" % (len(delivered), store.pending_transfers(args.to)))
        return 0
    except (OSError, StoreError, transfer_module.TransferError) as exc:
        print("agent-sessions sync: " + str(exc), file=sys.stderr)
        return 1
    finally:
        lock.close()


def _archive(args):
    try:
        with Store(_state_dir(args)) as store:
            if args.action == "verify":
                bad = 0
                for row in store.db.execute("SELECT id FROM archive_generation ORDER BY id"):
                    try:
                        archive_module.verify_generation(store.db, store.archive_dir, row["id"])
                    except (archive_module.ArchiveError, OSError) as exc:
                        bad += 1
                        print("generation=%s error=%s" % (row["id"], exc))
                print("generations_checked=%d failures=%d" % (store.db.execute("SELECT count(*) FROM archive_generation").fetchone()[0], bad))
                return 1 if bad else 0
            if args.action == "reindex":
                count = store.reindex_generations()
                print("generations_reindexed=%d sessions=%d" % (count, store.db.execute("SELECT count(*) FROM sessions").fetchone()[0]))
                return 0
            report = archive_module.retention_report(store.db)
            print("generations=%d objects=%d bytes=%d tombstoned=%d" % (
                report["generations"], report["objects"], report["bytes"], report["tombstoned"]))
            print("pending_local_generations=%d" % store.db.execute(
                "SELECT count(*) FROM archive_generation WHERE indexed_at IS NULL AND harness NOT IN ('opencode')").fetchone()[0])
        return 0
    except (OSError, StoreError) as exc:
        print("agent-sessions archive: " + str(exc), file=sys.stderr)
        return 1


def _backup(args):
    try:
        if args.action == "restic":
            restic = shutil.which("restic")
            if restic is None:
                raise StoreError("restic is not installed; the built-in `backup create` still works without it")
            if not args.repo:
                raise StoreError("backup restic needs --repo, for example an r2:s3 endpoint")
            import subprocess

            completed = subprocess.run([restic, "-r", args.repo, "backup", args.destination], check=False)
            return 0 if completed.returncode == 0 else 1
        if args.action == "create":
            with Store(_state_dir(args)) as store:
                manifest = backup_module.create(store, args.destination)
            raw_objects = manifest.get("objects")
            count = len(raw_objects) if isinstance(raw_objects, list) else 0
            print("backup_objects=%d generations=%s destination=%s" % (
                count, manifest.get("generations"), args.destination))
            return 0
        if not args.to:
            raise StoreError("backup restore needs --to <new state directory>")
        tombstones = args.tombstones_from or (str(_state_dir(args)) if (_state_dir(args) / "sessions.sqlite3").is_file() else None)
        manifest = backup_module.restore(Path(args.destination), Path(args.to), tombstones)
        raw_objects = manifest.get("objects")
        count = len(raw_objects) if isinstance(raw_objects, list) else 0
        print("restored_generations=%s objects=%d destination=%s" % (
            manifest.get("generations"), count, args.to))
        return 0
    except (OSError, StoreError, backup_module.BackupError, ValueError) as exc:
        print("agent-sessions backup: " + str(exc), file=sys.stderr)
        return 1


def _search(args):
    state_dir = _state_dir(args)
    if args.central:
        try:
            rows = central_rows(args, "search", {
                "query": args.query, "project": args.central_project, "limit": args.limit,
                "regex": args.regex, "kinds": args.kind, "since": args.since})
            for row in rows:
                _print_central_row(row, args.query, args.regex)
            print("matches=%d scope=central" % len(rows))
            return 0
        except (OSError, StoreError) as exc:
            print("agent-sessions search: " + str(exc), file=sys.stderr)
            return 1
    try:
        with Store(state_dir) as store:
            project = _project(args)
            _stats(store.refresh(roots=_roots(args), project=project, harnesses=_harnesses(args)))
            rows = store.search(args.query, project, limit=args.limit, regex=args.regex, kinds=args.kind, since=args.since)
            for row in rows:
                evidence = store.resolve_evidence(row["session"], row["position"], row["digest"])
                timestamp = evidence.get("timestamp") or datetime.datetime.fromtimestamp(row["updated"], datetime.timezone.utc).isoformat(timespec="seconds")
                source = _source_label(row.get("source"), row.get("thread_source"))
                parent = row.get("parent")
                print(
                    f"session={row['session']} byte={row['position']} kind={evidence['kind']} "
                    f"time={timestamp[:19]} source={source} project={_display_path(row['cwd'])} file={_display_path(row['source_path'])} harness={row['harness']}"
                )
                if parent:
                    print("parent=" + parent)
                print("  " + _snippet(evidence["text"], args.query, args.regex))
            print("matches=" + str(len(rows)))
    except (OSError, StoreError) as exc:
        print("agent-sessions search: " + str(exc), file=sys.stderr)
        return 1
    return 0


def _print_event(store, row, max_chars, query=None, regex=False):
    evidence = store.resolve_evidence(row["session"], row["position"], row["digest"])
    timestamp = evidence.get("timestamp") or datetime.datetime.fromtimestamp(row["updated"], datetime.timezone.utc).isoformat(timespec="seconds")
    source = _source_label(row.get("source"), row.get("thread_source"))
    print(
        f"session={row['session']} byte={row['position']} kind={evidence['kind']} "
        f"time={timestamp[:19]} source={source} project={_display_path(row['cwd'])} file={_display_path(row['source_path'])} harness={row['harness']}"
    )
    if row.get("parent"):
        print("parent=" + row["parent"])
    text = _snippet(evidence["text"], query, regex) if query is not None else redact(evidence["text"])
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + "…"
    print("  " + text)


def _recent(args):
    if args.central:
        try:
            rows = central_rows(args, "recent", {"project": getattr(args, "central_project", None), "limit": args.limit,
                                                 "kinds": args.kind, "since": args.since})
            for row in rows:
                _print_central_row(row)
            print("sessions=%d scope=central" % len(rows))
            return 0
        except (OSError, StoreError) as exc:
            print("agent-sessions recent: " + str(exc), file=sys.stderr)
            return 1
    try:
        with Store(_state_dir(args)) as store:
            project = _project(args)
            _stats(store.refresh(roots=_roots(args), project=project, harnesses=_harnesses(args)))
            rows = store.recent(project, limit=args.limit, kinds=args.kind, since=args.since)
            for row in rows:
                _print_event(store, row, 240)
            print("sessions=" + str(len(rows)))
        return 0
    except (OSError, StoreError) as exc:
        print("agent-sessions recent: " + str(exc), file=sys.stderr)
        return 1


def _show(args):
    if args.before < 0 or args.after < 0:
        parser().error("--before and --after must not be negative")
    if args.central:
        try:
            rows = central_rows(args, "show", {"session": args.session, "project": getattr(args, "central_project", None),
                                               "position": args.position, "before": args.before, "after": args.after})
            if not rows:
                raise StoreError("no events in the requested window")
            for row in rows:
                _print_central_row(row)
            return 0
        except (OSError, StoreError) as exc:
            print("agent-sessions show: " + str(exc), file=sys.stderr)
            return 1
    try:
        with Store(_state_dir(args)) as store:
            project = _project(args)
            _stats(store.refresh(roots=_roots(args), project=project, harnesses=_harnesses(args)))
            rows = store.session_events(args.session, project, position=args.position, before=args.before, after=args.after)
            if args.kind:
                rows = [row for row in rows if row["kind"] in args.kind]
            if args.since is not None:
                rows = [row for row in rows if (_timestamp_epoch(row["timestamp"]) or row["updated"]) >= args.since]
            if not rows:
                raise StoreError("no events in the requested kind/time window")
            for row in rows:
                _print_event(store, row, args.max_chars)
        return 0
    except (OSError, StoreError, ValueError) as exc:
        print("agent-sessions show: " + str(exc), file=sys.stderr)
        return 1


def status_document(store):
    coverage = store.coverage()
    capture_failures = store.db.execute("SELECT count(*) FROM capture_failure").fetchone()[0]
    unindexed = store.db.execute(
        "SELECT count(*) FROM archive_generation WHERE indexed_at IS NULL AND harness NOT IN ('opencode')").fetchone()[0]
    pending = store.db.execute(
        "SELECT remote, count(*) AS pending, max(durable_at) AS last_ack FROM archive_generation g "
        "LEFT JOIN transfer_generation t ON t.generation = g.id "
        "WHERE t.durable_at IS NULL GROUP BY remote").fetchall()
    tombstones = store.db.execute("SELECT count(*) FROM tombstone").fetchone()[0]
    unmapped = store.db.execute(
        "SELECT count(DISTINCT cwd) FROM sessions WHERE project IS NULL AND cwd != ''").fetchone()[0]
    artifacts = store.db.execute("SELECT count(*), coalesce(sum(size), 0) FROM archive_artifact").fetchone()
    return {
        "harness": [dict(row) for row in coverage],
        "capture_failures": capture_failures,
        "unindexed_generations": unindexed,
        "pending_remote": [dict(row) for row in pending],
        "unmapped_workspaces": unmapped,
        "pending_deletions": tombstones,
        "deletions": store.tombstone_states(),
        "artifacts": {"count": artifacts[0], "bytes": artifacts[1]},
        "archive": archive_module.retention_report(store.db),
        "identity": archive_module.origin_for(store.db),
        "backup": {"restic": shutil.which("restic") is not None,
                   "builtin": True},
        "integrity": store.db.execute("PRAGMA quick_check").fetchone()[0],
    }


def _doctor(args):
    state_dir = _state_dir(args)
    try:
        if args.rebuild_index:
            rebuild_index(state_dir)
        with Store(state_dir) as store:
            if args.json:
                document = status_document(store)
                print(json.dumps(document, sort_keys=True))
                return 0 if document["integrity"] == "ok" else 1
            check = store.db.execute("PRAGMA quick_check").fetchone()[0]
            if check != "ok":
                raise StoreError("SQLite integrity check failed: " + str(check))
            try:
                store.db.execute("INSERT INTO events_fts(events_fts, rank) VALUES('integrity-check', 1)")
            except sqlite3.DatabaseError as exc:
                raise StoreError("FTS content is inconsistent; run `agent-sessions doctor --rebuild-index`: " + str(exc)) from exc
            sessions = store.db.execute("SELECT count(*) FROM sessions").fetchone()[0]
            events = store.db.execute("SELECT count(*) FROM events").fetchone()[0]
            malformed = store.db.execute("SELECT coalesce(sum(malformed_lines), 0) FROM sessions").fetchone()[0]
            partial = store.db.execute("SELECT count(*) FROM sessions WHERE partial_bytes > 0").fetchone()[0]
            print("ok sqlite=" + store.db.execute("SELECT sqlite_version()").fetchone()[0])
            print("database=" + str(store.path))
            print("sessions=" + str(sessions) + " events=" + str(events) + " malformed=" + str(malformed) + " partial=" + str(partial))
            for row in store.coverage():
                print("harness=%(harness)s sessions=%(sessions)d events=%(events)d complete=%(complete)d degraded=%(degraded)d unsupported=%(unsupported)d unrecognized_events=%(unrecognized)d unknown_ancestry=%(unknown_ancestry)d" % row)
            for row in store.unrecognized_kinds():
                print("unrecognized harness=%(harness)s kind=%(kind)s events=%(events)d" % row)
            return 0
    except (OSError, StoreError) as exc:
        print("agent-sessions doctor: " + str(exc), file=sys.stderr)
        print("For a valid but stale index, run `agent-sessions doctor --rebuild-index`; this preserves learning tables.", file=sys.stderr)
        return 1


def _refresh(args):
    try:
        with Store(_state_dir(args)) as store:
            _stats(store.refresh(roots=_roots(args), project=_project(args), harnesses=_harnesses(args)))
        return 0
    except (OSError, StoreError) as exc:
        print("agent-sessions refresh: " + str(exc), file=sys.stderr)
        return 1


def _readme_path():
    return Path(__file__).resolve().parents[2] / "README.md"


def parser():
    result = argparse.ArgumentParser(
        prog="agent-sessions",
        description="Search and inspect the local agent session index: every Codex, Claude, Muse, Grok, OpenCode, and Pi transcript on this machine.",
        epilog="Examples:\n"
        "  agent-sessions search 'codegen-units' --all-projects --kind user\n"
        "  agent-sessions search 'thin lto / codegen-units' --all-projects --kind user --since 1d\n"
        "  agent-sessions recent --kind user --since 2026-10-25\n"
        "  agent-sessions show opencode:ses_abc123 --position 3553000\n"
        "\n"
        "Hyphenated identifiers and slashes are autoquoted, so codegen-units works\n"
        "unquoted; quoting still forces an exact phrase and AND/OR still combine terms.\n"
        "Use --kind user to find your own prompts, --all-projects to leave the current\n"
        "repository, and --regex only for pattern matching.\n"
        f"Full docs: {_readme_path()}.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = result.add_subparsers(dest="command", metavar="command")

    refresh = commands.add_parser("refresh", help="incrementally index transcripts")
    refresh.add_argument("--state-dir")
    refresh.add_argument("--root", action="append", metavar="[HARNESS=]PATH", help="transcript root, repeatable; HARNESS is codex, claude, muse, grok, opencode, pi, cmd or agy (default codex)")
    _add_scope(refresh)
    refresh.set_defaults(run=_refresh)

    search = commands.add_parser("search", help="search indexed transcript text")
    search.add_argument("query", help="words, hyphenated identifiers, or quoted phrases; AND/OR combine terms")
    search.add_argument("--state-dir", help="session index state directory")
    search.add_argument("--root", action="append", metavar="[HARNESS=]PATH", help="transcript root, repeatable; HARNESS is codex, claude, muse, grok, opencode, pi, cmd or agy (default codex)")
    _add_scope(search)
    search.add_argument("--regex", action="store_true", help="scan indexed text using a Python regular expression")
    search.add_argument("--kind", action="append", help="only return this event kind, e.g. user, assistant, tool-call, tool-output; repeatable")
    search.add_argument("--since", type=_since_value, help="only include event time on or after an ISO date/time or duration such as 30d")
    search.add_argument("--limit", type=int, default=20, help="max matches (default %(default)s)")
    search.set_defaults(run=_search)

    recent = commands.add_parser("recent", help="show the latest indexed event for each recent session")
    recent.add_argument("--state-dir")
    recent.add_argument("--root", action="append", metavar="[HARNESS=]PATH", help="transcript root, repeatable; HARNESS is codex, claude, muse, grok, opencode, pi, cmd or agy (default codex)")
    _add_scope(recent)
    recent.add_argument("--kind", action="append", help="only include sessions whose latest matching event has this kind")
    recent.add_argument("--since", type=_since_value, help="only include events on or after an ISO date/time or duration such as 30d")
    recent.add_argument("--limit", type=int, default=20)
    recent.set_defaults(run=_recent)

    show = commands.add_parser("show", help="show source-verified events around a session byte offset")
    show.add_argument("session", help="session id as printed by search, e.g. opencode:ses_abc123")
    show.add_argument("--state-dir", help="session index state directory")
    show.add_argument("--root", action="append", metavar="[HARNESS=]PATH", help="transcript root, repeatable; HARNESS is codex, claude, muse, grok, opencode, pi, cmd or agy (default codex)")
    _add_scope(show)
    show.add_argument("--position", type=int, help="anchor the window at this byte offset; default is latest event")
    show.add_argument("--before", type=int, default=3, help="events before the anchor (default %(default)s)")
    show.add_argument("--after", type=int, default=3, help="events after the anchor (default %(default)s)")
    show.add_argument("--kind", action="append", help="only display this event kind; repeatable")
    show.add_argument("--since", type=_since_value, help="only display events on or after an ISO date/time or duration such as 30d")
    show.add_argument("--max-chars", type=int, default=2000, help="max event text chars (default %(default)s)")
    show.set_defaults(run=_show)

    doctor = commands.add_parser("doctor", help="check the local index and SQLite FTS5")
    doctor.add_argument("--state-dir")
    doctor.add_argument("--json", action="store_true", help="print a machine-readable status document")
    doctor.add_argument("--rebuild-index", action="store_true", help="rebuild derived transcript tables while preserving learning tables")
    doctor.set_defaults(run=_doctor)

    memory = commands.add_parser("memory", help="list retained experience records exposed by the central store")
    memory.add_argument("--state-dir")
    memory.add_argument("--central-state")
    memory.add_argument("--limit", type=int, default=20)
    memory.set_defaults(run=_memory)

    identity = commands.add_parser("identity", help="show or regenerate this collector identity")
    identity.add_argument("action", nargs="?", choices=("show", "regenerate"), default="show")
    identity.add_argument("--state-dir")
    identity.add_argument("--label")
    identity.add_argument("--regenerate", action="store_true", help="mint a new collector id; recorded origins are unchanged")
    identity.set_defaults(run=_identity)

    project = commands.add_parser("project", help="map a logical project to a checkout on an origin host")
    project.add_argument("action", choices=("map", "list"))
    project.add_argument("--state-dir")
    project.add_argument("--origin", help="origin host id; defaults to this collector")
    project.add_argument("--name")
    project.add_argument("--checkout")
    project.set_defaults(run=_project_command)

    sync = commands.add_parser("sync", help="capture and deliver pending generations to the central store")
    sync.add_argument("--state-dir")
    sync.add_argument("--central-state", help="local central store directory (offline/local transport)")
    sync.add_argument("--to", default="central", help="configured remote name (default %(default)s)")
    sync.add_argument("--label", help="display label recorded with this collector")
    sync.add_argument("--dry-run", action="store_true", help="report pending work without transferring")
    sync.add_argument("--root", action="append", metavar="[HARNESS=]PATH")
    sync.set_defaults(run=_sync)

    archive = commands.add_parser("archive", help="verify, reindex, or report the local archive")
    archive.add_argument("action", choices=("status", "verify", "reindex"))
    archive.add_argument("--state-dir")
    archive.set_defaults(run=_archive)

    backup = commands.add_parser("backup", help="create or restore a consistent backup")
    backup.add_argument("action", choices=("create", "restore", "restic"))
    backup.add_argument("--state-dir")
    backup.add_argument("destination", help="backup directory to create, or an existing backup to restore")
    backup.add_argument("--to", help="restore destination for `backup restore`")
    backup.add_argument("--tombstones-from", help="merge newer tombstones from this state directory (defaults to --state-dir)")
    backup.add_argument("--repo", help="restic repository URL for the optional external backup")
    backup.set_defaults(run=_backup)
    return result


def _add_scope(command):
    command.add_argument("--harness", action="append", metavar="NAME", help="only index and search this harness; repeatable")
    command.add_argument("--project", metavar="PATH", help="scope to this project path; defaults to the current repository")
    command.add_argument("--all-projects", action="store_true", help="search every indexed project")
    command.add_argument("--central", action="store_true", help="query the configured central store instead of this machine")
    command.add_argument("--central-state", help="central store directory for the local transport")
    command.add_argument("--central-project", help="limit a central query to this mapped project name")


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.command is None:
        cli.print_help()
        return 2
    if hasattr(args, "limit") and args.limit < 1:
        cli.error("--limit must be positive")
    if hasattr(args, "max_chars") and args.max_chars < 1:
        cli.error("--max-chars must be positive")
    if getattr(args, "all_projects", False) and getattr(args, "project", None):
        cli.error("--project and --all-projects cannot be used together")
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
