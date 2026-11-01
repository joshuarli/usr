#!/usr/bin/env python3
"""Measure the mirror's local hot paths and the Worker over real HTTP."""
import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "tools" / "agent-memory" / "src"
WORK_TMP = ROOT / ".work" / "tmp"
PERF_GATE = ROOT / "dotfiles" / "base" / ".local" / "bin" / "perf-gate-ready"
SCHEMA_VERSION = 1
QUERY = "retentionmarker"
sys.path.insert(0, str(SRC_DIR))

from agent_memory import learning, learning_sync  # noqa: E402
from agent_memory.store import Store, project_identity  # noqa: E402

DEFERRED = {
    "recall": "P5.3",
    "search": "P3.3",
    "inspect": "P3.3",
    "learning-delta": "P3.1",
    "mirror-initial": "P2.2",
    "mirror-noop": "P2.3",
    "mirror-append": "P2.3",
    "recovery": "P2.4",
    "html": "P4.1",
    "mirror-concurrent": "P5.2",
    "worker-status": "P1.4",
}
LOCAL_SCENARIOS = ("capture", "learning-import")


def _line(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def _now():
    return datetime.now(timezone.utc)


def _stamp(moment):
    return moment.strftime("%Y%m%dT%H%M%SZ")


def _iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _percentile(values, fraction):
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _summary(samples):
    walls = [sample["wall_ms"] for sample in samples if sample["wall_ms"] is not None]
    cpus = [sample["cpu_ms"] for sample in samples if sample["cpu_ms"] is not None]
    entry = {"runs": len(walls)}
    if not walls:
        return entry
    median = statistics.median(walls)
    entry.update({
        "median": round(median, 3),
        "p50": round(_percentile(walls, 0.50), 3),
        "p95": round(_percentile(walls, 0.95), 3),
        "p99": round(_percentile(walls, 0.99), 3),
        "min": round(min(walls), 3),
        "max": round(max(walls), 3),
        "spread": round(_percentile(walls, 0.95) - _percentile(walls, 0.50), 3),
        "mad": round(statistics.median([abs(value - median) for value in walls]), 3),
    })
    if cpus:
        entry.update({
            "cpu_median": round(statistics.median(cpus), 3),
            "cpu_p95": round(_percentile(cpus, 0.95), 3),
            "cpu_min": round(min(cpus), 3),
            "cpu_max": round(max(cpus), 3),
        })
    return entry


def _peak_rss_kib():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak // 1024 if sys.platform == "darwin" else peak


def _version(argv):
    executable = shutil.which(argv[0])
    if executable is None:
        return None
    try:
        result = subprocess.run([executable, *argv[1:]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else None


def _git(*args):
    try:
        result = subprocess.run(["git", "-C", str(ROOT), *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _runtime():
    return {
        "python": platform.python_version(),
        "node": _version(["node", "--version"]),
        "workerd": None,
        "rage": _version([os.environ.get("AGE_BIN", "rage"), "--version"]) or _version(["age", "--version"]),
    }


def _cores():
    try:
        return os.cpu_count() or 1
    except OSError:
        return 1


def _load1():
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):
        return None


def _gate():
    try:
        result = subprocess.run(["sh", str(PERF_GATE), "-1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _timed(action, repeat, gate):
    load_before = _load1()
    before = gate()
    started = time.perf_counter()
    cpu_started = time.process_time()
    counters = action()
    timings = counters.pop("_timings", {}) if isinstance(counters, dict) else {}
    wall_ms = round((time.perf_counter() - started) * 1000, 3)
    cpu_ms = round((time.process_time() - cpu_started) * 1000, 3)
    after = gate()
    load_after = _load1()
    passed = before and after
    return {
        "repeat": repeat,
        "wall_ms": wall_ms if passed else None,
        "cpu_ms": cpu_ms if passed else None,
        "counters": counters,
        "timings": timings,
        "gate": {
            "before": before,
            "after": after,
            "load1": [None if load_before is None else round(load_before, 2),
                      None if load_after is None else round(load_after, 2)],
        },
    }


def _make_sessions(root, session_count, message_count, project_count):
    projects = []
    for project_number in range(project_count):
        project = root / ("project-%03d" % project_number)
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        projects.append(project)
    transcripts = root / "sessions"
    transcripts.mkdir()
    event_count = 0
    for session_number in range(session_count):
        session = "bench-%05d" % session_number
        project = projects[session_number % len(projects)]
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
    return projects, transcripts, event_count


def _work(stats):
    return {key: stats[key] for key in ("bytes_read", "content_opens", "git_processes", "sqlite_changes", "stat_operations")}


def _capture(scenario, args, root):
    samples = []
    dataset = None
    for repeat in range(args.repeats):
        repeat_root = root / ("repeat-%d" % repeat)
        repeat_root.mkdir()
        projects, transcripts, events = _make_sessions(repeat_root, args.sessions, args.messages, min(args.projects, args.sessions))
        project_ids = [project_identity(project) for project in projects]
        source_bytes = sum(path.stat().st_size for path in transcripts.rglob("rollout-*.jsonl"))
        if dataset is None:
            dataset = {
                "sessions": args.sessions, "messages_per_session": args.messages, "projects": len(projects),
                "events": events, "source_bytes": source_bytes,
            }
        store = Store(repeat_root / "state")
        try:
            fresh = _timed(lambda store=store, transcripts=transcripts, project_ids=project_ids: _work(store.refresh([transcripts], projects=project_ids)), repeat, _gate)
            target = transcripts / "rollout-bench-00000.jsonl"
            with target.open("ab") as stream:
                stream.write(_line({"type": "response_item", "timestamp": "2026-10-23T00:00:01Z", "payload": {
                    "type": "message", "role": "user", "content": [{"type": "input_text", "text": "incrementmarker"}],
                }}))
            append = _timed(lambda store=store, transcripts=transcripts, project_ids=project_ids: _work(store.refresh([transcripts], projects=project_ids)), repeat, _gate)
            unchanged = _timed(lambda store=store, transcripts=transcripts, project_ids=project_ids: _work(store.refresh([transcripts], projects=project_ids)), repeat, _gate)
        finally:
            store.close()
        for operation, sample in (("fresh", fresh), ("append", append), ("unchanged", unchanged)):
            sample["operation"] = operation
            samples.append(sample)
    return dataset, samples, ("fresh", "append", "unchanged")


def _seed_learning(store, records):
    experiences = []
    memories = []
    sources = []
    incidents = []
    links = []
    now = 1_767_225_600.0
    for index in range(records):
        project = "git:/synthetic/project-%02d" % (index % 10)
        digest = hashlib.sha256(("source-%d" % index).encode()).hexdigest()
        session = "bench-%05d" % (index % 200)
        if index % 10 == 0:
            memories.append((index, project, "synthetic action %d retentionmarker" % index,
                             "when synthetic condition %d holds" % index, "synthetic-revision",
                             "approved", now + index))
            incidents.append((index, session, session, index, digest, "synthetic", now + index))
        else:
            experiences.append((
                index, project, "gotcha", "synthetic observation %d retentionmarker" % index,
                "synthetic condition %d" % index, "synthetic-identifier-%d" % index,
                hashlib.sha256(("fingerprint-%d" % index).encode()).hexdigest(),
                "deterministic", "synthetic-detector", "synthetic-revision", None,
                now + index, now + index, "[]", "", "retained", None, None,
            ))
            sources.append((index, session, index, digest, "trigger"))
            if index % 50 == 3:
                links.append((index, index - 2, "supersedes", now + index))
    learning.initialize(store.db)
    db = store.db
    with db:
        db.executemany(
            "INSERT INTO learning_findings(id, project, signal, fingerprint, terms, state, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
            ((finding, project, "synthetic", "fingerprint-%d" % finding, "synthetic", "memory", now, now)
             for finding, project, *_rest in memories))
        db.executemany(
            "INSERT INTO learning_experiences(id, project, kind, claim, applies_when, identifiers, fingerprint, basis, detector, revision, worktree, observed_at, captured_at, validity, tags, state, state_reason, state_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", experiences)
        db.executemany(
            "INSERT INTO learning_memories(finding, project, action, applicability, revision, state, created_at) VALUES(?,?,?,?,?,?,?)",
            memories)
        db.executemany(
            "INSERT INTO learning_experience_sources(experience, session, position, digest, role) VALUES(?,?,?,?,?)", sources)
        db.executemany(
            "INSERT INTO learning_experience_links(newer, older, relation, created_at) VALUES(?,?,?,?)", links)
        db.executemany(
            "INSERT INTO learning_incidents(finding, session, root_session, position, digest, signal, observed_at) VALUES(?,?,?,?,?,?,?)",
            incidents)
    return {"records": records, "experiences": len(experiences), "memories": len(memories),
            "sources": len(sources) + len(incidents), "links": len(links)}


def _learning_import(scenario, args, root):
    state = root / "state"
    store = Store(state)
    try:
        dataset = _seed_learning(store, args.records)
        samples = []
        for repeat in range(args.repeats):
            def export():
                started = time.perf_counter()
                records = learning_sync.export_snapshot(store.db)
                exported_ms = (time.perf_counter() - started) * 1000
                started = time.perf_counter()
                body = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
                return {
                    "records": len(records), "bytes": len(body.encode("utf-8")), "digest": digest,
                    "_timings": {
                        "export_ms": round(exported_ms, 3),
                        "serialization_ms": round((time.perf_counter() - started) * 1000, 3),
                        "records_per_second": round(len(records) / (exported_ms / 1000), 1) if exported_ms else None,
                    },
                }
            sample = _timed(export, repeat, _gate)
            sample["operation"] = "export"
            samples.append(sample)
    finally:
        store.close()
    return dataset, samples, ("export",)


def _document(environment, scenario, dataset, samples, operations):
    moment = _now()
    counters = {}
    variance = []
    for operation in operations:
        seen = [sample["counters"] for sample in samples if sample["operation"] == operation]
        counters[operation] = seen[0] if seen else {}
        if any(item != seen[0] for item in seen):
            variance.append(operation)
    timed = [sample for sample in samples if sample["wall_ms"] is not None]
    return {
        "schema_version": SCHEMA_VERSION,
        "commit": _git("rev-parse", "HEAD"),
        "generated_at": _iso(moment),
        "environment": environment,
        "scenario": scenario,
        "runtime": {**_runtime(), "dirty": bool(_git("status", "--porcelain", "--untracked-files=no"))},
        "dataset": dataset,
        "perf_gate": "passed" if len(timed) == len(samples) else "deferred",
        "load": {"source": "perf-gate-ready", "cores": _cores(), "max_load1": max(
            (sample["gate"]["load1"][0] or 0) for sample in samples) if samples else 0},
        "samples": samples,
        "summary": {operation: _summary([sample for sample in samples if sample["operation"] == operation])
                    for operation in operations},
        "counters": counters,
        "peak_rss_kib": _peak_rss_kib(),
        "counter_variance": variance,
    }


def _write(document, out):
    out.mkdir(parents=True, exist_ok=True)
    path = out / ("%s-%s-%s.json" % (document["environment"], document["scenario"], _stamp(_now())))
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return path


def _load(path):
    document = json.loads(Path(path).read_text())
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported benchmark schema in " + str(path))
    return document


def _threshold(baseline):
    return max(baseline["median"] * 0.05, baseline["mad"] * 2)


def _compare(baseline, candidate):
    if baseline["scenario"] != candidate["scenario"]:
        raise ValueError("benchmark scenarios differ: %s and %s" % (baseline["scenario"], candidate["scenario"]))
    verdict = {"scenario": baseline["scenario"], "environment": baseline["environment"], "passed": True,
               "deferred": baseline["perf_gate"] != "passed" or candidate["perf_gate"] != "passed", "violations": []}
    for operation, base_counters in baseline["counters"].items():
        candidate_counters = candidate["counters"].get(operation)
        if candidate_counters != base_counters:
            verdict["passed"] = False
            verdict["violations"].append({"operation": operation, "kind": "counters", "baseline": base_counters,
                                          "candidate": candidate_counters})
    for operation, base in baseline["summary"].items():
        candidate_summary = candidate["summary"].get(operation)
        if not base.get("runs") or not candidate_summary or not candidate_summary.get("runs"):
            verdict["deferred"] = True
            continue
        allowed = base["median"] + _threshold(base)
        if candidate_summary["median"] > allowed:
            verdict["passed"] = False
            verdict["violations"].append({
                "operation": operation, "kind": "wall", "baseline_median": base["median"],
                "candidate_median": candidate_summary["median"], "allowed": round(allowed, 3),
                "baseline_mad": base["mad"],
            })
    if verdict["deferred"]:
        verdict["passed"] = False
    return verdict


def _print_compare(verdict):
    print("scenario %s (%s): %s" % (verdict["scenario"], verdict["environment"],
                                    "deferred" if verdict["deferred"] else ("pass" if verdict["passed"] else "fail")))
    for violation in verdict["violations"]:
        if violation["kind"] == "wall":
            print("  %s: %.3f ms -> %.3f ms (allowed <= %.3f)" % (
                violation["operation"], violation["baseline_median"], violation["candidate_median"], violation["allowed"]))
        else:
            print("  %s: deterministic counters changed" % violation["operation"])


def _report(directory):
    documents = []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            documents.append((path, _load(path)))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("skipping %s: %s" % (path, exc), file=sys.stderr)
    groups = {}
    for path, document in documents:
        groups.setdefault((document["environment"], document["scenario"]), []).append((document["generated_at"], path, document))
    if not groups:
        print("no benchmark results under %s" % directory)
        return 1
    for (environment, scenario), runs in sorted(groups.items()):
        runs.sort()
        print("## %s %s" % (environment, scenario))
        print("| operation | runs | median ms | p95 ms | counters |")
        print("| --- | ---: | ---: | ---: | --- |")
        latest = runs[-1][2]
        for operation, summary in latest["summary"].items():
            counters = json.dumps(latest["counters"].get(operation, {}), sort_keys=True)
            print("| %s | %s | %s | %s | %s |" % (operation, summary.get("runs", 0), summary.get("median", "-"),
                                                 summary.get("p95", "-"), counters))
        if len(runs) > 1:
            verdict = _compare(runs[0][2], latest)
            print("")
            _print_compare(verdict)
        print("")
    return 0


def _dispatch(environment, args):
    if environment == "worker":
        print("bench_mirror: worker benchmarks land in P1.4 with the Miniflare harness", file=sys.stderr)
        return 2
    if environment == "deployed":
        print("bench_mirror: deployed benchmarks land in P1.6 after the first deploy", file=sys.stderr)
        return 2
    scenario = args.scenario or "capture"
    if scenario not in LOCAL_SCENARIOS:
        owner = DEFERRED.get(scenario, "a later slice")
        print("bench_mirror: local scenario %s lands in %s" % (scenario, owner), file=sys.stderr)
        return 2
    if args.repeats < 1:
        raise ValueError("repeats must be positive")
    if args.records < 1 or args.sessions < 1 or args.messages < 1 or args.projects < 1:
        raise ValueError("records, sessions, messages, and projects must be positive")
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    with tempfile.TemporaryDirectory(dir=str(WORK_TMP), prefix="mirror-bench-") as temporary:
        root = Path(temporary)
        if scenario == "capture":
            dataset, samples, operations = _capture(scenario, args, root)
        else:
            dataset, samples, operations = _learning_import(scenario, args, root)
    document = _document("local", scenario, dataset, samples, operations)
    _write(document, out)
    print(json.dumps(document, indent=2, sort_keys=True))
    variance = document.get("counter_variance")
    if isinstance(variance, list) and variance:
        print("bench_mirror: deterministic counters varied across repeats: " + ", ".join(str(item) for item in variance),
              file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark the mirror's local paths and the deployed Worker.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for environment in ("local", "worker", "deployed"):
        command = subparsers.add_parser(environment)
        command.add_argument("--scenario")
        command.add_argument("--repeats", type=int, default=5)
        command.add_argument("--records", type=int, default=1000)
        command.add_argument("--sessions", type=int, default=200)
        command.add_argument("--messages", type=int, default=10)
        command.add_argument("--projects", type=int, default=10)
        command.add_argument("--out", default=".work/perf")
    compare = subparsers.add_parser("compare")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--json", action="store_true")
    report = subparsers.add_parser("report")
    report.add_argument("--dir", default=".work/perf")
    args = parser.parse_args(argv)
    try:
        if args.command in ("local", "worker", "deployed"):
            return _dispatch(args.command, args)
        if args.command == "compare":
            verdict = _compare(_load(args.baseline), _load(args.candidate))
            if args.json:
                print(json.dumps(verdict, indent=2, sort_keys=True))
            else:
                _print_compare(verdict)
            return 0 if verdict["passed"] else 1
        return _report(args.dir)
    except (OSError, ValueError, RuntimeError) as exc:
        print("bench_mirror: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
