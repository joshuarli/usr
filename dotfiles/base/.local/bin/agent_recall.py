#!/usr/bin/env python3
"""Evidence-aware local retrieval over approved memories, project experiences, and indexed session events."""
import dataclasses
import json
import math
import re
import sqlite3
import subprocess
import time
from pathlib import Path

from agent_session_store import EvidenceChanged, EvidenceUnavailable, StoreError, redact
from agent_transcripts import split_id

DEFAULT_LIMIT = 3
MAX_LIMIT = 8
ACTIVE_SESSION_SECONDS = 120
EVENT_POOL = 60
RECORD_POOL = 30
EVENTS_PER_SESSION = 2
RRF_K = 20
MIN_COVERAGE = 0.4
MIN_MASS = 0.8
MIN_SCORE = 0.30
IDF_POWER = 1.0
IDENT_BOOST = 1.5
COVERAGE_TOP_K = 4
NEAR_DUPLICATE = 0.6
SUMMARY_CHARS = 280
CONTEXT_CHARS = 2400
AGED_PERFORMANCE_DAYS = 90
CONTENT_EVENT_KINDS = ("user", "assistant", "tool-call", "tool-output", "task_complete")
KIND_WEIGHT = {"tool-output": 1.0, "user": 0.9, "task_complete": 0.7, "assistant": 0.8, "tool-call": 0.6}
TIER_PRIOR = {"instruction": 0.12, "experience": 0.08, "lead": 0.0}
RECORD_BM25 = (3.0, 2.0, 2.0, 4.0)
SHORT_TECHNICAL = frozenset("ci cd gc vm io os db ui ux js ts py rs go cc ld tls ssl gpu cpu oom jit abi api cli tty pid".split())
STOP_WORDS = frozenset("""a an the to in of for and or is it this that these those i we you they he she me my our your its be been are was were
am do does did doing done have has had having not no nor so as at by on off up out into onto over under from with without about after before
then than too very can could should would will shall may might must please help need needs want wants like just also still only any all some
how what why when where which who whom whose there here again once ever never if else while because since until via per vs etc get gets got
make makes made use used using uses new old try trying tried let lets see look looks find found check checks thing things way ways work works
working issue issues problem problems task tasks code project repo repository file files""".split())
_RAW = re.compile(r"[^\s\"'`()\[\]{},;?!<>|]+")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")
_TRIM = " .:/\\-_=+*#@"
_TECH_SHAPES = (
    re.compile(r"[A-Za-z0-9]_[A-Za-z0-9]"),
    re.compile(r"[A-Za-z0-9][/\\][A-Za-z0-9]"),
    re.compile(r"[A-Za-z0-9]\.[A-Za-z0-9]"),
    re.compile(r"[A-Za-z0-9]::[A-Za-z0-9]"),
    re.compile(r"^--?[A-Za-z][A-Za-z0-9-]*"),
    re.compile(r"[a-z][A-Z]"),
    re.compile(r"[A-Za-z][0-9]|[0-9][A-Za-z]"),
    re.compile(r"[A-Za-z0-9]\(\)$"),
    re.compile(r"[A-Za-z0-9]-[A-Za-z0-9]"),
    re.compile(r"^[A-Z][A-Z0-9]{1,}$"),
)


class SourceError(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class Query:
    raw: str
    words: tuple
    idents: tuple

    @property
    def informative(self):
        return len(self.words) + len(self.idents) > 0


def stem(word):
    if len(word) <= 3:
        return word
    for suffix, replacement in (("ies", "y"), ("ingly", ""), ("edly", ""), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: len(word) - len(suffix)] + replacement
    return word


def subparts(token):
    parts = []
    for chunk in re.findall(r"[A-Za-z0-9]+", token):
        parts.extend(match.lower() for match in _CAMEL.findall(chunk))
    return parts


def is_technical(token):
    if len(token) > 120:
        return False
    return any(shape.search(token) for shape in _TECH_SHAPES)


def parse_query(text):
    text = str(text)[:2000]
    idents, words = [], []
    seen_idents, seen_words = set(), set()

    def add_ident(token):
        key = token.lower()
        if key not in seen_idents:
            seen_idents.add(key)
            idents.append(token)

    for match in _RAW.finditer(text):
        raw = match.group(0)
        if "=" in raw:
            key = raw.split("=", 1)[0].strip(_TRIM)
            if key and re.search(r"[A-Za-z]{2}", key):
                add_ident(key)
            continue
        flag = re.match(r"^--?([A-Za-z][A-Za-z0-9-]{2,})$", raw)
        if flag:
            add_ident(raw)
            continue
        token = raw.strip(_TRIM)
        if not token or not re.search(r"[A-Za-z0-9]", token) or not subparts(token):
            continue
        short_ok = token.lower() in SHORT_TECHNICAL or (token.isupper() and 2 <= len(token) <= 5 and token.isalpha())
        if is_technical(token) or short_ok:
            add_ident(token)
            continue
        word = token.lower()
        if word in STOP_WORDS or not word.isalnum():
            continue
        if len(word) < 3:
            continue
        if word not in seen_words:
            seen_words.add(word)
            words.append(word)
    return Query(text, tuple(words[:24]), tuple(idents[:12]))


def technical_tokens(text, limit=16):
    found, seen = [], set()
    for match in _RAW.finditer(str(text)[:6000]):
        token = match.group(0).strip(_TRIM)
        if token and is_technical(token) and len(token) >= 3 and token.lower() not in seen:
            seen.add(token.lower())
            found.append(token)
            if len(found) == limit:
                break
    return found


def _quote(parts):
    return '"' + " ".join(parts) + '"'


def ident_expression(ident):
    parts = subparts(ident)
    alternatives = {_quote(parts)}
    if len(parts) > 1:
        alternatives.add('"' + "".join(parts) + '"')
    return "(" + " OR ".join(sorted(alternatives)) + ")"


def word_expression(word, prefix):
    base = stem(word)
    if prefix and len(base) >= 4:
        return '"' + base + '"*'
    return '"' + word + '"'


def fts_expressions(query):
    expressions = []
    if query.idents:
        expressions.append(("identifiers", " OR ".join(ident_expression(ident) for ident in query.idents)))
    if query.words:
        expressions.append(("words", " OR ".join(word_expression(word, True) for word in query.words)))
    return expressions


def doc_tokens(text):
    tokens = set()
    for match in _RAW.finditer(text.lower()):
        token = match.group(0).strip(_TRIM)
        if token:
            tokens.add(token)
            tokens.add(stem(token))
    for chunk in re.findall(r"[A-Za-z0-9]+", text):
        for part in _CAMEL.findall(chunk):
            tokens.add(part.lower())
            tokens.add(stem(part.lower()))
        tokens.add(chunk.lower())
    return tokens


def normalized(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def ident_in(ident, doc_text, doc_norm, tokens):
    flat = normalized(ident)
    if len(flat) >= 5:
        return flat in doc_norm
    return ident.lower() in tokens or flat in tokens


def artifact_text(cwd, path):
    relative = Path(path)
    if relative.is_absolute() or not relative.parts or any(part in ("..", ".git", ".work") for part in relative.parts):
        raise SourceError("memory condition must name a tracked project file")
    try:
        top = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True, timeout=10, check=True)
        root = Path(top.stdout.decode().strip()).resolve(strict=True)
        candidate = root
        for part in relative.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise SourceError("memory condition may not traverse symlinks")
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", "--", str(relative)], capture_output=True, timeout=10)
        if tracked.returncode or not candidate.is_file() or candidate.stat().st_size > 262144:
            raise SourceError("memory condition source is unavailable or too large")
        return candidate.read_text()
    except (subprocess.SubprocessError, OSError, UnicodeError) as error:
        raise SourceError("memory condition source is unavailable: " + error.__class__.__name__) from error


def condition_states(conditions, cwd):
    states = []
    for condition in conditions:
        try:
            text = artifact_text(cwd, condition["path"])
        except SourceError:
            states.append((condition["path"], "source_unavailable"))
            continue
        states.append((condition["path"], "holds" if condition["contains"] in text else "excerpt_missing"))
    return states


def _git_changed_since(cwd, revision):
    try:
        result = subprocess.run(["git", "-C", str(cwd), "diff", "--name-only", revision, "HEAD"], capture_output=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode:
        return None
    return {line for line in result.stdout.decode(errors="replace").splitlines() if line}


@dataclasses.dataclass
class Candidate:
    kind: str
    ref: str
    project: str
    summary: str
    applies_when: str
    action: str
    text: str
    experience_kind: str
    tier: str
    observed_at: float
    ranks: dict = dataclasses.field(default_factory=dict)
    supports: list = dataclasses.field(default_factory=list)
    validity: list = dataclasses.field(default_factory=list)
    revision: str = ""
    tags: str = ""
    evidence_roots: int = 1
    event_kind: str = ""
    session_cwd: str = ""
    features: dict = dataclasses.field(default_factory=dict)
    status: str = "unverified"
    reasons: list = dataclasses.field(default_factory=list)
    conflicts: list = dataclasses.field(default_factory=list)
    score: float = 0.0


class Retriever:
    def __init__(self, store, project, cwd, now=None):
        self.store, self.db = store, store.db
        self.project, self.cwd = project, Path(cwd) if cwd is not None else None
        self.now = time.time() if now is None else float(now)
        self._df_cache = {}
        self._events_total = None

    def retrieve(self, text, limit=DEFAULT_LIMIT, explain=False, verify=True, include_events=True):
        limit = max(1, min(int(limit), MAX_LIMIT))
        query = parse_query(text)
        self._query = query
        trace = {"query": {"words": list(query.words), "identifiers": list(query.idents)}, "candidates": [], "excluded": []} if explain else None
        if not query.informative:
            return self._response([], True, "query has no searchable terms", trace)
        pool = {}
        for candidate in self._record_candidates(query):
            pool[candidate.ref] = candidate
        if include_events:
            for candidate in self._event_candidates(query):
                pool[candidate.ref] = candidate
        self._merge_source_events(pool, trace)
        scored = []
        for candidate in pool.values():
            self._score(candidate, query)
            scored.append(candidate)
        scored.sort(key=lambda item: (-item.score, item.ref))
        if trace is not None:
            trace["candidates"] = [self._trace(item) for item in scored[:25]]
        accepted = [item for item in scored if self._acceptable(item, trace)]
        window = accepted[: limit * 3]
        if verify:
            for item in window:
                self._assess(item)
        else:
            for item in window:
                item.reasons.append("not_rechecked")
        window = [item for item in window if item.status != "invalidated"]
        for item in window:
            self._finish(item)
        window.sort(key=lambda item: (-item.score, item.ref))
        selected = self._diversify(window, limit, trace)
        self._mark_conflicts(selected)
        selected = self._bound_context(selected, trace)
        if not selected:
            return self._response([], True, "no candidate cleared the relevance gate", trace)
        return self._response(selected, False, None, trace)

    def _response(self, selected, abstained, reason, trace):
        payload = {"results": [self._render(item) for item in selected], "abstained": abstained, "reason": reason}
        if trace is not None:
            payload["explain"] = trace
        return payload

    def _trace(self, item):
        return {"ref": item.ref, "tier": item.tier, "sessions": [support["session"] for support in item.supports], "score": round(item.score, 4), "features": {k: round(v, 3) for k, v in item.features.items()}}

    def _total_events(self):
        if self._events_total is None:
            self._events_total = self.db.execute("SELECT count(*) FROM events").fetchone()[0] or 1
        return self._events_total

    def _df(self, word):
        if word not in self._df_cache:
            try:
                self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.events_vocab USING fts5vocab(main, events_fts, 'row')")
                row = self.db.execute("SELECT doc FROM temp.events_vocab WHERE term = ?", (word,)).fetchone()
                self._df_cache[word] = row[0] if row else 0
            except sqlite3.DatabaseError:
                self._df_cache[word] = 0
        return self._df_cache[word]

    def _idf(self, word):
        total = self._total_events()
        frequency = self._df(word)
        if total >= 200 and frequency / total > 0.2:
            return 0.0
        return math.log(1 + total / (1 + frequency)) / math.log(1 + total)

    def _record_candidates(self, query):
        candidates = {}
        for label, expression in fts_expressions(query):
            try:
                rows = self.db.execute(
                    "SELECT d.kind AS kind, d.ref AS ref, bm25(learning_recall_fts, ?, ?, ?, ?) AS rank "
                    "FROM learning_recall_fts JOIN learning_recall_docs d ON d.doc = learning_recall_fts.rowid "
                    "WHERE learning_recall_fts MATCH ? AND d.project = ? ORDER BY rank LIMIT ?",
                    (*RECORD_BM25, expression, self.project, RECORD_POOL),
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for position, row in enumerate(rows):
                key = (row["kind"], row["ref"])
                entry = candidates.setdefault(key, {})
                entry[label] = position
        loaded = []
        for (kind, ref), ranks in candidates.items():
            candidate = self._load_record(kind, ref)
            if candidate is not None:
                candidate.ranks = ranks
                loaded.append(candidate)
        return loaded

    def _load_record(self, kind, ref):
        if kind == "memory":
            row = self.db.execute(
                "SELECT m.*, f.integrated_at, "
                "(SELECT count(DISTINCT root_session) FROM learning_incidents WHERE finding = m.finding) AS roots "
                "FROM learning_memories m JOIN learning_findings f ON f.id = m.finding WHERE m.finding = ? AND m.state = 'approved'",
                (ref,),
            ).fetchone()
            if row is None:
                return None
            supports = [dict(item) for item in self.db.execute(
                "SELECT session, position, digest FROM learning_incidents WHERE finding = ? ORDER BY observed_at DESC LIMIT 3", (ref,))]
            return Candidate(
                kind="memory", ref="memory:%d" % ref, project=row["project"], summary=row["action"], applies_when=row["applicability"],
                action=row["action"], text=row["action"] + " " + row["applicability"], experience_kind="method", tier="instruction",
                observed_at=row["integrated_at"] or row["created_at"], supports=supports, validity=json.loads(row["validity"] or "[]"),
                revision=row["revision"] or "", evidence_roots=max(1, row["roots"] or 1))
        row = self.db.execute("SELECT * FROM learning_experiences WHERE id = ? AND state = 'retained'", (ref,)).fetchone()
        if row is None:
            return None
        supports = [dict(item) for item in self.db.execute(
            "SELECT session, position, digest, role FROM learning_experience_sources WHERE experience = ? ORDER BY role, position LIMIT 4", (ref,))]
        roots = self.db.execute("SELECT count(DISTINCT session) FROM learning_experience_sources WHERE experience = ?", (ref,)).fetchone()[0]
        conflicts = [item[0] for item in self.db.execute(
            "SELECT l.older FROM learning_experience_links l JOIN learning_experiences o ON o.id = l.older "
            "WHERE l.newer = ? AND l.relation = 'contradicts' AND o.state = 'retained' "
            "UNION SELECT l.newer FROM learning_experience_links l JOIN learning_experiences o ON o.id = l.newer "
            "WHERE l.older = ? AND l.relation = 'contradicts' AND o.state = 'retained'", (ref, ref))]
        return Candidate(
            kind="experience", ref="experience:%d" % ref, project=row["project"], summary=row["claim"], applies_when=row["applies_when"],
            action="", text=row["claim"] + " " + row["applies_when"] + " " + row["identifiers"], experience_kind=row["kind"], tier="experience",
            observed_at=row["observed_at"], supports=supports, validity=json.loads(row["validity"]), revision=row["revision"] or "",
            tags=row["tags"], evidence_roots=max(1, roots), conflicts=["experience:%d" % item for item in conflicts])

    def _event_candidates(self, query):
        quoted = ",".join("'%s'" % kind for kind in CONTENT_EVENT_KINDS)
        candidates = {}
        for label, expression in fts_expressions(query):
            try:
                rows = self.db.execute(
                    "SELECT e.session AS session, e.position AS position, e.digest AS digest, e.kind AS kind, e.text AS text, "
                    "e.outcome AS outcome, s.cwd AS cwd, s.updated AS updated, bm25(events_fts) AS rank "
                    "FROM events_fts JOIN events e ON e.id = events_fts.rowid JOIN sessions s ON s.id = e.session "
                    "WHERE events_fts MATCH ? AND s.project = ? AND s.updated <= ? AND e.kind IN (" + quoted + ") "
                    "ORDER BY rank LIMIT ?",
                    (expression, self.project, self.now - ACTIVE_SESSION_SECONDS, EVENT_POOL),
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for position, row in enumerate(rows):
                key = (row["session"], row["position"])
                entry = candidates.get(key)
                if entry is None:
                    entry = candidates[key] = {"row": row, "ranks": {}}
                entry["ranks"][label] = position
        per_session = {}
        for key, entry in sorted(candidates.items(), key=lambda item: min(item[1]["ranks"].values())):
            if len(per_session.setdefault(key[0], [])) < EVENTS_PER_SESSION:
                per_session[key[0]].append(key)
        out = []
        for keys in per_session.values():
            for key in keys:
                row, ranks = candidates[key]["row"], candidates[key]["ranks"]
                out.append(Candidate(
                    kind="event", ref="event:%s@%d" % (row["session"], row["position"]), project=self.project, summary=row["text"],
                    applies_when="", action="", text=row["text"], experience_kind="", tier="lead", observed_at=row["updated"],
                    ranks=ranks, supports=[{"session": row["session"], "position": row["position"], "digest": row["digest"], "role": "match"}],
                    event_kind=row["kind"], session_cwd=row["cwd"]))
        return out

    def _merge_source_events(self, pool, trace):
        owners = {}
        for item in pool.values():
            if item.kind != "event":
                for support in item.supports:
                    owners.setdefault((support["session"], support["position"]), []).append(item)
        for ref in [ref for ref, item in pool.items() if item.kind == "event" and (item.supports[0]["session"], item.supports[0]["position"]) in owners]:
            event = pool.pop(ref)
            for owner in owners[(event.supports[0]["session"], event.supports[0]["position"])]:
                owner.text += " " + event.text[:800]
                for label, rank in event.ranks.items():
                    owner.ranks[label] = min(rank, owner.ranks.get(label, rank))
            if trace is not None:
                trace["excluded"].append({"ref": ref, "why": "merged into the record it supports"})

    def _ident_weight(self, ident):
        parts = subparts(ident)
        return IDENT_BOOST * max((self._idf(part) for part in parts), default=0.0) ** IDF_POWER

    def _score(self, candidate, query):
        tokens = doc_tokens(candidate.text)
        flat = normalized(candidate.text)
        terms = [(word, self._idf(word) ** IDF_POWER, word in tokens or stem(word) in tokens) for word in query.words]
        terms += [(ident, self._ident_weight(ident), ident_in(ident, candidate.text, flat, tokens)) for ident in query.idents]
        top = sorted(terms, key=lambda term: -term[1])[:COVERAGE_TOP_K]
        mass = sum(weight for _, weight, present in terms if present)
        total = sum(weight for _, weight, _ in top)
        coverage = (sum(weight for _, weight, present in top if present) / total) if total > 0 else 0.0
        hits = sum(1 for ident in query.idents if ident_in(ident, candidate.text, flat, tokens))
        lists = max(1, len(fts_expressions(query)))
        lexical = min(1.0, sum(1.0 / (RRF_K + rank + 1) for rank in candidate.ranks.values()) * (RRF_K + 1) / lists)
        kind_weight = KIND_WEIGHT.get(candidate.event_kind, 1.0)
        worktree = 0.0
        if candidate.session_cwd and self.cwd is not None:
            worktree = 0.05 if str(self.cwd) == candidate.session_cwd else 0.0
        evidence = min(0.06, 0.02 * (candidate.evidence_roots - 1))
        age_days = max(0.0, (self.now - candidate.observed_at) / 86400)
        recency = 0.03 * math.exp(-age_days / 180)
        score = (0.50 * coverage + 0.17 * lexical) * (0.6 + 0.4 * kind_weight) + TIER_PRIOR[candidate.tier] + evidence + recency + worktree
        candidate.features = {"mass": mass, "coverage": coverage, "identifier_hits": float(hits), "lexical": lexical, "kind_weight": kind_weight}
        candidate.score = score

    def _acceptable(self, candidate, trace):
        features = candidate.features
        ok = features["coverage"] >= MIN_COVERAGE and features["mass"] >= MIN_MASS and candidate.score >= MIN_SCORE
        if not ok and trace is not None:
            trace["excluded"].append({"ref": candidate.ref, "why": "below relevance gate", "score": round(candidate.score, 4)})
        return ok

    def _assess(self, candidate):
        reasons, status = candidate.reasons, "unverified"
        if candidate.validity:
            cwd = self.cwd
            if cwd is None:
                reasons.append("not_rechecked")
            else:
                states = condition_states(candidate.validity, cwd)
                failed = [(path, state) for path, state in states if state != "holds"]
                if failed:
                    status = "needs_revalidation"
                    reasons.extend("%s:%s" % (state, path) for path, state in failed)
                else:
                    status = "verified"
        elif candidate.kind != "event" and candidate.revision and candidate.revision != "fixture" and self.cwd is not None:
            changed = _git_changed_since(self.cwd, candidate.revision)
            if changed:
                named = {name for name in re.findall(r"[\w./-]+\.\w+", candidate.text)}
                if any(path in changed or Path(path).name in {Path(name).name for name in named} for path in changed if named):
                    status = "needs_revalidation"
                    reasons.append("files_changed_since_capture")
        for support in candidate.supports:
            try:
                self.store.resolve_evidence(support["session"], support["position"], support["digest"])
            except EvidenceUnavailable:
                reasons.append("evidence_unavailable")
                if status == "verified":
                    status = "needs_revalidation"
            except EvidenceChanged:
                reasons.append("evidence_changed")
                status = "needs_revalidation"
            except StoreError:
                reasons.append("evidence_unavailable")
        if "performance" in candidate.tags.split() and self.now - candidate.observed_at > AGED_PERFORMANCE_DAYS * 86400:
            status = "needs_revalidation"
            reasons.append("aged_performance_result")
        if candidate.conflicts:
            reasons.append("contradicted_by:" + ",".join(candidate.conflicts))
        if self._superseded(candidate):
            status = "invalidated"
            reasons.append("superseded")
        candidate.status = status
        candidate.reasons = sorted(set(reasons))

    def _superseded(self, candidate):
        if candidate.kind != "experience":
            return False
        ref = int(candidate.ref.split(":")[1])
        row = self.db.execute(
            "SELECT 1 FROM learning_experience_links l JOIN learning_experiences n ON n.id = l.newer "
            "WHERE l.older = ? AND l.relation = 'supersedes' AND n.state = 'retained'", (ref,)).fetchone()
        return row is not None

    def _finish(self, candidate):
        if candidate.kind == "memory":
            if candidate.status == "verified":
                candidate.tier = "instruction"
            elif candidate.status == "unverified":
                candidate.tier = "experience"
            else:
                candidate.tier = "lead"
        elif candidate.kind == "experience" and candidate.status == "needs_revalidation":
            candidate.tier = "lead"
        if candidate.status == "needs_revalidation":
            candidate.score *= 0.7
        elif candidate.status == "verified":
            candidate.score *= 1.08

    def _diversify(self, window, limit, trace):
        selected = []
        for candidate in window:
            tokens = doc_tokens(candidate.text)
            duplicate = None
            for chosen in selected:
                other = doc_tokens(chosen.text)
                if len(tokens & other) / max(1, len(tokens | other)) >= NEAR_DUPLICATE:
                    duplicate = chosen
                    break
                if {item["session"] for item in candidate.supports[:3]} & {item["session"] for item in chosen.supports[:3]}:
                    duplicate = chosen
                    break
            if duplicate is not None:
                if trace is not None:
                    trace["excluded"].append({"ref": candidate.ref, "why": "redundant with " + duplicate.ref})
                continue
            selected.append(candidate)
            if len(selected) == limit:
                break
        return selected

    def _mark_conflicts(self, selected):
        refs = {item.ref for item in selected}
        for item in selected:
            clash = [ref for ref in item.conflicts if ref in refs]
            if clash:
                item.tier = "lead"
                item.reasons.append("conflict_unresolved")

    def _bound_context(self, selected, trace):
        kept, used = [], 0
        for item in selected:
            size = len(self._render(item)["summary"]) + len(item.applies_when[:SUMMARY_CHARS])
            if kept and used + size > CONTEXT_CHARS:
                if trace is not None:
                    trace["excluded"].append({"ref": item.ref, "why": "context budget"})
                continue
            kept.append(item)
            used += size
        return kept

    def _render(self, item):
        if item.kind == "event":
            summary = _snippet(item.summary, [word for word in (*self._query.words, *(ident.lower() for ident in self._query.idents))])
        else:
            summary = item.summary
        summary = redact(" ".join(summary.split()))[:SUMMARY_CHARS]
        harness = split_id(item.supports[0]["session"])[0] if item.supports else ""
        support = []
        for entry in item.supports[:3]:
            support.append({
                "session": entry["session"], "position": entry["position"], "digest": entry["digest"],
                "harness": split_id(entry["session"])[0],
                "inspect": "agent-sessions show %s --position %d" % (entry["session"], entry["position"]),
            })
        authority = {
            "instruction": "Reviewed project advice; current source, tests, and instructions take precedence.",
            "experience": "Advisory historical experience; verify against the current worktree before relying on it.",
            "lead": "Search lead from past work; it is not an instruction and is not verified as current.",
        }[item.tier]
        return {
            "ref": item.ref, "tier": item.tier, "kind": item.experience_kind or item.event_kind, "summary": summary,
            "applies_when": redact(" ".join(item.applies_when.split()))[:SUMMARY_CHARS], "action": redact(item.action)[:600] if item.action else None,
            "status": item.status, "reasons": item.reasons, "support": support, "harness": harness,
            "score": round(item.score, 3), "authority": authority,
            "age_days": int(max(0, (self.now - item.observed_at) / 86400)),
        }


def _snippet(text, words):
    flat = " ".join(text.split())
    lowered = flat.lower()
    positions = [lowered.find(word) for word in words if lowered.find(word) >= 0]
    index = min(positions) if positions else 0
    start = max(0, index - 80)
    return ("…" if start else "") + flat[start:start + SUMMARY_CHARS]
