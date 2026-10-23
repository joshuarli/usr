#!/usr/bin/env python3
import argparse
import importlib.machinery
import importlib.util
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK_TMP = ROOT / ".work" / "tmp"
WORK_TMP.mkdir(parents=True, exist_ok=True)
BIN_DIR = ROOT / "dotfiles" / "base" / ".local" / "bin"
STORE_SPEC = importlib.util.spec_from_file_location("agent_session_store", BIN_DIR / "agent_session_store.py")
STORE_MODULE = importlib.util.module_from_spec(STORE_SPEC)
sys.modules[STORE_SPEC.name] = STORE_MODULE
STORE_SPEC.loader.exec_module(STORE_MODULE)
Store = STORE_MODULE.Store
normalize = STORE_MODULE.normalize
project_identity = STORE_MODULE.project_identity
SKILL_USAGE_PATH = BIN_DIR / "skill-usage"
SKILL_USAGE_LOADER = importlib.machinery.SourceFileLoader("skill_usage_bench", str(SKILL_USAGE_PATH))
SPEC = importlib.util.spec_from_loader("skill_usage_bench", SKILL_USAGE_LOADER)
SKILL_USAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SKILL_USAGE
SPEC.loader.exec_module(SKILL_USAGE)
PERF_GATE = ROOT / "dotfiles" / "base" / ".local" / "bin" / "perf-gate-ready"
QUERY = "retentionmarker"


def _line(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def _make_corpus(root, session_count, message_count):
    project = root / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    transcripts = root / "sessions"
    transcripts.mkdir()
    event_count = 0
    for session_number in range(session_count):
        session = "bench-%05d" % session_number
        path = transcripts / ("rollout-%s.jsonl" % session)
        with path.open("wb") as stream:
            stream.write(_line({"type": "session_meta", "payload": {
                "id": session, "cwd": str(project), "source": "cli", "thread_source": "user",
            }}))
            stream.write(_line({"type": "response_item", "payload": {
                "type": "message", "role": "developer", "content": [{
                    "type": "input_text", "text": "Available skills\n- benchmark: synthetic\n",
                }],
            }}))
            event_count += 2
            for message_number in range(message_count):
                marker = " retentionmarker" if message_number % 10 == 0 else ""
                stream.write(_line({"type": "response_item", "timestamp": "2026-10-23T00:00:00Z", "payload": {
                    "type": "message", "role": "user", "content": [{
                        "type": "input_text", "text": "synthetic prompt session %d message %d%s" % (session_number, message_number, marker),
                    }],
                }}))
                event_count += 1
            stream.write(_line({"type": "response_item", "payload": {
                "type": "function_call", "name": "read_file", "call_id": "call-%d" % session_number,
                "arguments": json.dumps({"path": "/synthetic/.agents/skills/benchmark/SKILL.md"}),
            }}))
            event_count += 1
    return project, transcripts, event_count


def _direct_search(root, query):
    matches = []
    bytes_read = 0
    for path in sorted(Path(root).rglob("rollout-*.jsonl")):
        session = path.stem.removeprefix("rollout-")
        with path.open("rb") as stream:
            position = 0
            for raw in stream:
                bytes_read += len(raw)
                try:
                    obj = json.loads(raw)
                except ValueError:
                    position += len(raw)
                    continue
                for record in normalize(obj, "codex"):
                    if query.casefold() in record["text"].casefold():
                        matches.append((session, position))
                position += len(raw)
    return matches, bytes_read


def _source_read_baseline(store):
    total = 0
    sessions = store.db.execute("SELECT source_path, indexed_bytes, checkpoint_position FROM sessions").fetchall()
    for session in sessions:
        path = Path(session["source_path"])
        with path.open("rb") as stream:
            total += len(stream.readline())
        if session["checkpoint_position"] is not None:
            total += session["indexed_bytes"] - session["checkpoint_position"]
    return total


def _first_line_bytes(root):
    total = 0
    for path in Path(root).rglob("rollout-*.jsonl"):
        with path.open("rb") as stream:
            total += len(stream.readline())
    return total


def _skill_usage(root):
    usage = SKILL_USAGE.Usage(False)
    SKILL_USAGE.scan_codex(root, 0, usage)
    return len(usage.sessions["codex"]), len(usage.loaded["benchmark"])


def _gate(after=False):
    args = ["sh", str(PERF_GATE)] + (["-1"] if after else [])
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode == 0


def _timed(operation, action, timings, deferred):
    if not _gate():
        deferred[0] = True
        return None
    started = time.perf_counter()
    cpu_started = time.process_time()
    result = action()
    elapsed = time.perf_counter() - started
    cpu_elapsed = time.process_time() - cpu_started
    if not _gate(after=True):
        deferred[0] = True
        return None
    timings.setdefault(operation, []).append({"wall": elapsed, "cpu": cpu_elapsed})
    return result


def _summary(values):
    if not values:
        return None
    output = {"runs": len(values)}
    for key, suffix in (("wall", "wall"), ("cpu", "cpu")):
        samples = [value[key] for value in values]
        output[suffix + "_median_ms"] = round(statistics.median(samples) * 1000, 3)
        output[suffix + "_range_ms"] = [round(min(samples) * 1000, 3), round(max(samples) * 1000, 3)]
    return output


def run(args):
    if args.sessions < 1 or args.messages < 1:
        raise ValueError("sessions and messages must be positive")
    with tempfile.TemporaryDirectory(dir=str(WORK_TMP), prefix="agent-sessions-bench-") as temporary:
        root = Path(temporary)
        project, transcripts, generated_events = _make_corpus(root, args.sessions, args.messages)
        project_id = project_identity(project)
        source_bytes = sum(path.stat().st_size for path in transcripts.rglob("rollout-*.jsonl"))
        direct, direct_bytes = _direct_search(transcripts, QUERY)
        usage_sessions, usage_loads = _skill_usage(transcripts)
        state = root / "state"
        with Store(state) as store:
            build = store.refresh([transcripts], project=project_id)
            indexed = store.search(QUERY, project_id, limit=args.sessions * args.messages)
            indexed_keys = {(row["session"], row["position"]) for row in indexed}
            if set(direct) != indexed_keys:
                raise RuntimeError("direct scan and FTS search returned different source events")
            database_path = store.path
            database_bytes = database_path.stat().st_size
            hit = indexed[0]
            evidence = store.resolve_evidence(hit["session"], hit["position"], hit["digest"])
            if QUERY not in evidence["text"].casefold():
                raise RuntimeError("resolved evidence does not contain the indexed query")
        target = transcripts / "rollout-bench-00000.jsonl"
        with Store(state) as store:
            increment_read_baseline = _source_read_baseline(store)
        appended = _line({"type": "response_item", "timestamp": "2026-10-23T00:00:01Z", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": "incrementmarker"}],
        }})
        with target.open("ab") as stream:
            stream.write(appended)
        with Store(state) as store:
            increment = store.refresh([transcripts], project=project_id)
            noop = store.refresh([transcripts], project=project_id)
            if increment["events_added"] != 1 or noop["events_added"] != 0:
                raise RuntimeError("incremental or no-op refresh processed the wrong number of events")
            fts_after = len(store.search(QUERY, project_id, limit=args.sessions * args.messages))
            if fts_after != len(direct):
                raise RuntimeError("FTS result count changed after unrelated append")
            final_database_bytes = store.path.stat().st_size
            noop_read_estimate = _source_read_baseline(store)
        results = {
            "corpus": {"sessions": args.sessions, "messages_per_session": args.messages, "events": generated_events, "source_bytes": source_bytes},
            "correctness": {"direct_hits": len(direct), "fts_hits": len(indexed), "skill_usage_sessions": usage_sessions, "skill_usage_loads": usage_loads},
            "source_reads_bytes": {
                "direct_scan": direct_bytes,
                "skill_usage_scan": source_bytes,
            "initial_build_estimate": source_bytes + _first_line_bytes(transcripts),
            "increment_estimate": increment_read_baseline + len(appended),
            "no_op_estimate": noop_read_estimate,
                "fts_search": 0,
            },
            "index": {"build_sessions": build["sessions_indexed"], "build_events_added": build["events_added"], "increment_events_added": increment["events_added"], "no_op_events_added": noop["events_added"], "database_bytes": database_bytes, "database_bytes_after_increment": final_database_bytes},
        }
        if args.timings:
            timings = {}
            deferred = [False]
            expected = set(direct)
            for _ in range(5):
                direct_result = _timed("direct_search", lambda: _direct_search(transcripts, QUERY)[0], timings, deferred)
                if direct_result is not None and set(direct_result) != expected:
                    raise RuntimeError("timed direct search returned different source events")
                with Store(state) as store:
                    fts_result = _timed("fts_search", lambda: store.search(QUERY, project_id, limit=args.sessions * args.messages), timings, deferred)
                    if fts_result is not None and {(row["session"], row["position"]) for row in fts_result} != expected:
                        raise RuntimeError("timed FTS search returned different source events")
            for index in range(5):
                build_state = root / ("timed-build-%d" % index)

                def build_once(path=build_state):
                    with Store(path) as store:
                        stats = store.refresh([transcripts], project=project_id)
                        return stats["events_added"]

                built_events = _timed("build", build_once, timings, deferred)
                if built_events is not None and built_events != generated_events + 1 + index:
                    raise RuntimeError("timed build indexed an unexpected number of events")
                appended_line = _line({"type": "response_item", "timestamp": "2026-10-23T00:00:02Z", "payload": {
                    "type": "message", "role": "user", "content": [{"type": "input_text", "text": "timedincrement%d" % index}],
                }})
                with target.open("ab") as stream:
                    stream.write(appended_line)
                with Store(state) as store:
                    incremented_events = _timed("increment", lambda: store.refresh([transcripts], project=project_id)["events_added"], timings, deferred)
                    if incremented_events is not None and incremented_events != 1:
                        raise RuntimeError("timed append processed an unexpected number of events")
                    noop_events = _timed("no_op", lambda: store.refresh([transcripts], project=project_id)["events_added"], timings, deferred)
                    if noop_events is not None and noop_events != 0:
                        raise RuntimeError("timed no-op refresh processed events")
                skill_counts = _timed("skill_usage", lambda: _skill_usage(transcripts), timings, deferred)
                if skill_counts is not None and skill_counts != (args.sessions, args.sessions):
                    raise RuntimeError("timed skill-usage scan returned different counts")
                shutil.rmtree(build_state, ignore_errors=True)
            results["timings"] = {name: _summary(values) for name, values in timings.items()}
            results["timing_status"] = "perf gate deferred: host busy" if deferred[0] else "gate passed"
        else:
            results["timing_status"] = "not requested"
        print(json.dumps(results, sort_keys=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare synthetic direct transcript scans with the incremental FTS index.")
    parser.add_argument("--sessions", type=int, default=100)
    parser.add_argument("--messages", type=int, default=50)
    parser.add_argument("--timings", action="store_true", help="run gated, interleaved timing samples")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print("agent-sessions-bench: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
