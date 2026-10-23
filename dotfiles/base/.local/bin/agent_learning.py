import argparse
import collections
import contextlib
import dataclasses
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from agent_learning_ops import SchedulerError
from agent_session_store import Store, StoreError, default_state_dir, project_identity, redact


SCHEMA_VERSION = 1
MAX_EVENTS = 2000
MAX_REVIEWS = 2
STABLE_SECONDS = 120
CORRECTION = re.compile(r"\b(actually|i meant|you (?:should|must|already)|do not|don't|stop|wrong|instead|again|ignored|forgot|why did you)\b", re.I)
ERROR = re.compile(r"(?:exit(?:ed)? (?:code|with code|status)[: ]+[1-9]|(?:command |test |build )?failed|permission denied|not found|no such file|error:)", re.I)
SKILL_PATH = re.compile(r"/skills/([a-z0-9-]+)/SKILL\.md")
STOP_WORDS = frozenset("a an the to in of for and or is it this that you i we please should must do not don't again instead actually was have has with from be on then agent use using".split())


class LearningError(Exception):
    pass


def initialize(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS learning_schema(version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS learning_projects(
            project TEXT PRIMARY KEY, cwd TEXT NOT NULL, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
            enabled_at REAL NOT NULL, repository TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS learning_processed(
            session TEXT PRIMARY KEY, signature TEXT NOT NULL, processed_at REAL NOT NULL,
            truncated INTEGER NOT NULL CHECK(truncated IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS learning_hints(
            project TEXT PRIMARY KEY REFERENCES learning_projects(project) ON DELETE CASCADE,
            observed_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS learning_findings(
            id INTEGER PRIMARY KEY, project TEXT NOT NULL, signal TEXT NOT NULL, fingerprint TEXT NOT NULL,
            terms TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN
                ('pending','reviewing','deferred','rejected','held','promoted','memory','superseded','reversed')),
            created_at REAL NOT NULL, updated_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            retry_at REAL NOT NULL DEFAULT 0, proposal TEXT, reason TEXT, commit_id TEXT,
            integrated_at REAL, reviewed_incidents INTEGER NOT NULL DEFAULT 0,
            UNIQUE(project,fingerprint)
        );
        CREATE TABLE IF NOT EXISTS learning_incidents(
            id INTEGER PRIMARY KEY, finding INTEGER NOT NULL REFERENCES learning_findings(id),
            session TEXT NOT NULL, root_session TEXT NOT NULL, position INTEGER NOT NULL, digest TEXT NOT NULL,
            signal TEXT NOT NULL, observed_at REAL NOT NULL,
            UNIQUE(session,position,digest,signal)
        );
        CREATE TABLE IF NOT EXISTS learning_memories(
            finding INTEGER PRIMARY KEY REFERENCES learning_findings(id), project TEXT NOT NULL,
            action TEXT NOT NULL, applicability TEXT NOT NULL, revision TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('approved','superseded')), created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS learning_evaluations(
            finding INTEGER NOT NULL REFERENCES learning_findings(id), session TEXT NOT NULL,
            phase TEXT NOT NULL CHECK(phase IN ('before','after')), relevant INTEGER NOT NULL,
            loaded INTEGER NOT NULL, repeated INTEGER NOT NULL, assessment TEXT NOT NULL,
            PRIMARY KEY(finding,session)
        );
        CREATE TABLE IF NOT EXISTS learning_reviews(
            id INTEGER PRIMARY KEY, finding INTEGER NOT NULL REFERENCES learning_findings(id),
            started_at REAL NOT NULL, finished_at REAL, outcome TEXT, usage TEXT
        );
    """)
    row = db.execute("SELECT version FROM learning_schema").fetchone()
    if row is None:
        db.execute("INSERT INTO learning_schema VALUES(?)", (SCHEMA_VERSION,))
    elif row[0] != SCHEMA_VERSION:
        raise LearningError("incompatible learning schema; preserve database and upgrade the tool")
    db.commit()


def words(text):
    return frozenset(w for w in re.findall(r"[a-z][a-z0-9_-]{2,}", text.lower()) if w not in STOP_WORDS)


def similarity(left, right):
    return len(left & right) / max(1, min(len(left), len(right)))


def canonical_command(text):
    return re.sub(r"\s+", " ", re.sub(r"\b[0-9a-f]{12,}\b", "REV", text)).strip()[:600]


def signals(events):
    calls = {}
    failed = collections.defaultdict(list)
    for index, event in enumerate(events):
        kind, text = event["kind"], event["text"]
        if kind == "user" and len(text) <= 6000 and CORRECTION.search(text):
            yield index, "correction", text
        if kind in ("tool-call", "tool_call", "tool"):
            calls[event.get("call_id") or str(index)] = (index, canonical_command(text))
        if kind in ("tool-output", "tool_output", "error") and ERROR.search(text):
            call = calls.get(event.get("call_id"))
            if call:
                failed[call[1]].append(index)
                if len(failed[call[1]]) == 2:
                    yield index, "repeated-command", call[1]
        if kind == "assistant" and re.search(r"\b(?:correct command|prerequisite|should have (?:used|read|run)|ignored (?:the )?(?:skill|procedure)|abandon(?:ed|ing)|assumption was wrong)\b", text, re.I):
            if any(ERROR.search(e["text"]) for e in events[max(0, index-8):index]) or "should have" in text.lower() or "ignored" in text.lower():
                yield index, "discovery", text


def git_revision(path):
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, timeout=10)
    if result.returncode:
        raise LearningError("project is not a readable Git repository")
    return result.stdout.decode().strip()


def repository_state(path):
    status = subprocess.run(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"], capture_output=True, timeout=10, check=True)
    return hashlib.sha256(git_revision(path).encode() + status.stdout).hexdigest()


@contextlib.contextmanager
def run_lock(directory):
    path = Path(directory) / "learning.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class Learner:
    def __init__(self, store, reviewer=None):
        self.store, self.db, self.reviewer = store, store.db, reviewer
        initialize(self.db)

    def enable(self, cwd, repository, now):
        cwd, repository = Path(cwd).resolve(strict=True), Path(repository).resolve(strict=True)
        git_revision(cwd)
        git_revision(repository)
        if not (repository / "dotfiles/base/.agents/skills/do/SKILL.md").is_file():
            raise LearningError("--usr-root must name the tracked usr source")
        identity = project_identity(cwd)
        with self.db:
            self.db.execute("""INSERT INTO learning_projects VALUES(?,?,1,?,?)
                ON CONFLICT(project) DO UPDATE SET cwd=excluded.cwd,enabled=1,repository=excluded.repository""",
                            (identity, str(cwd), now, str(repository)))
        return identity

    def disable(self, cwd):
        with self.db:
            self.db.execute("UPDATE learning_projects SET enabled=0 WHERE project=?", (project_identity(cwd),))

    def _events(self, session):
        rows = list(self.db.execute("SELECT * FROM events WHERE session=? ORDER BY position DESC,id DESC LIMIT ?", (session, MAX_EVENTS + 1)))
        truncated = len(rows) > MAX_EVENTS
        return [dict(row) for row in reversed(rows[:MAX_EVENTS])], truncated

    def _cluster(self, project, signal, text, now):
        terms = words(text)
        fingerprint = hashlib.sha256((signal + " " + " ".join(sorted(terms))).encode()).hexdigest()
        for row in self.db.execute("SELECT * FROM learning_findings WHERE project=? AND signal=? ORDER BY id DESC LIMIT 300", (project, signal)):
            if row["fingerprint"] == fingerprint or (len(terms) >= 3 and similarity(terms, words(row["terms"])) >= .72):
                return row["id"]
        cursor = self.db.execute("""INSERT INTO learning_findings(project,signal,fingerprint,terms,state,created_at,updated_at)
            VALUES(?,?,?,?,'pending',?,?)""", (project, signal, fingerprint, " ".join(sorted(terms)), now, now))
        return cursor.lastrowid

    def _root_session(self, session):
        seen = set()
        current = session
        while current not in seen:
            seen.add(current)
            row = self.db.execute("SELECT parent,source,thread_source FROM sessions WHERE id=?", (current,)).fetchone()
            if row is None:
                return "unresolved-ancestry"
            if not row[0]:
                if "subagent" in str(row[1]) or "subagent" in str(row[2]):
                    return "unresolved-ancestry"
                return current
            current = row[0]
        return "unresolved-ancestry"

    def discover(self, project, now, stable_seconds=STABLE_SECONDS):
        rows = self.db.execute("""SELECT s.* FROM sessions s
            JOIN learning_projects p ON p.project=s.project
            LEFT JOIN learning_processed lp ON lp.session=s.id
            WHERE s.project=? AND p.enabled=1 AND s.updated<=? AND s.updated>=p.enabled_at
            AND (lp.signature IS NULL OR lp.signature !=
                 (SELECT cast(e.position AS TEXT)||':'||e.digest FROM events e WHERE e.session=s.id ORDER BY e.position DESC,e.id DESC LIMIT 1))
            ORDER BY s.updated DESC LIMIT 100""", (project, now-stable_seconds)).fetchall()
        processed = found = 0
        for session in rows:
            session = dict(session)
            provenance = str(session.get("thread_source", "")) + str(session.get("source", ""))
            if "agent-learn" in provenance or "agent_learning" in provenance:
                continue
            last = self.db.execute("SELECT position,digest FROM events WHERE session=? ORDER BY position DESC,id DESC LIMIT 1", (session["id"],)).fetchone()
            if last is None:
                continue
            signature = str(last["position"]) + ":" + last["digest"]
            old = self.db.execute("SELECT signature FROM learning_processed WHERE session=?", (session["id"],)).fetchone()
            if old and old[0] == signature:
                continue
            events, truncated = self._events(session["id"])
            with self.db:
                for index, signal, text in signals(events):
                    event = events[index]
                    finding = self._cluster(project, signal, text, now)
                    cursor = self.db.execute("""INSERT OR IGNORE INTO learning_incidents
                        (finding,session,root_session,position,digest,signal,observed_at) VALUES(?,?,?,?,?,?,?)""",
                        (finding, session["id"], self._root_session(session["id"]), event["position"], event["digest"], signal, now))
                    if cursor.rowcount:
                        found += 1
                        self.db.execute("""UPDATE learning_findings SET updated_at=?,
                            state=CASE WHEN state IN ('deferred','rejected') THEN 'pending' ELSE state END
                            WHERE id=?""", (now, finding))
                self.db.execute("INSERT OR REPLACE INTO learning_processed VALUES(?,?,?,?)", (session["id"], signature, now, int(truncated)))
                self.evaluate(session, events)
            processed += 1
        return {"processed": processed, "signals": found}

    def _evidence(self, finding):
        evidence = []
        for row in self.db.execute("SELECT * FROM learning_incidents WHERE finding=? ORDER BY id DESC LIMIT 6", (finding,)):
            row = dict(row)
            self.store.resolve_evidence(row["session"], row["position"], row["digest"])
            window = self.db.execute("""SELECT * FROM events WHERE session=? AND position>=
                COALESCE((SELECT position FROM events WHERE session=? AND position<? ORDER BY position DESC LIMIT 1 OFFSET 3),0)
                ORDER BY position LIMIT 9""", (row["session"], row["session"], row["position"]))
            row["window"] = [{"kind": e["kind"], "text": redact(e["text"])[:650], "position": e["position"]} for e in list(window)[:5]]
            evidence.append(row)
        return evidence

    def _context(self, finding, repository, evidence):
        related = []
        for row in self.db.execute("SELECT id,state,proposal FROM learning_findings WHERE project=? AND id!=? AND proposal IS NOT NULL ORDER BY updated_at DESC LIMIT 8", (finding["project"], finding["id"])):
            proposal = json.loads(row["proposal"])
            related.append({"id": row["id"], "state": row["state"], "action": proposal.get("future_action", "")[:400]})
        descriptions, guidance = [], []
        from agent_learning_promote import KNOWN_LEAF_SKILLS
        for name in sorted(KNOWN_LEAF_SKILLS):
            path = repository / "dotfiles/base/.agents/skills" / name / "SKILL.md"
            if not path.is_symlink() and path.is_file():
                text = path.read_text()
                description = re.search(r"^description: (.+)$", text, re.M)
                descriptions.append({"owner": name, "description": description[1][:140] if description else ""})
                guidance.append((len(words(text) & words(finding["terms"])), name, text))
        owning_guidance = {}
        budget = 8000
        for _, name, text in sorted(guidance, reverse=True)[:3]:
            if len(text) <= budget:
                owning_guidance[name] = text
                budget -= len(text)
        existing_guidance = []
        contract = repository / "dotfiles/base/.codex/AGENTS.md"
        if contract.is_file():
            paragraphs = contract.read_text().split("\n\n")
            for paragraph in sorted(paragraphs, key=lambda text: len(words(text) & words(finding["terms"])), reverse=True):
                if sum(map(len, existing_guidance)) + len(paragraph) <= 2500:
                    existing_guidance.append(redact(paragraph))
        context = {"signal": finding["signal"], "evidence": evidence[:2], "existing_owners": descriptions,
                "owning_guidance": owning_guidance,
                "existing_instructions": existing_guidance,
                "related_findings": related, "existing_memories": self.recall(finding["project"], finding["terms"], check_revision=False),
                "policy": "Structural fixes before prose. Hold unrelated code changes. Inspect owning guidance before edits. Never change permissions, security, authorization, model routing or verification requirements. Existing rule ignored means improve execution or discovery, not duplicate rules."}
        while len(json.dumps(context)) > 22000 and context["related_findings"]:
            context["related_findings"].pop()
        return context

    def _verify(self, refs, evidence):
        if not refs or not isinstance(refs, list):
            return False
        allowed = {(e["session"], e["position"], e["digest"]) for e in evidence}
        try:
            for ref in refs:
                if (ref["session"], ref["position"], ref["digest"]) not in allowed:
                    return False
                self.store.resolve_evidence(ref["session"], ref["position"], ref["digest"])
        except (KeyError, OSError, ValueError, StoreError, sqlite3.Error):
            return False
        return True

    def review(self, finding, project, now):
        from agent_learning_promote import promote
        repository = Path(project["repository"])
        expected_head = git_revision(repository)
        try:
            evidence = self._evidence(finding["id"])
        except (StoreError, ValueError, OSError) as error:
            with self.db:
                self.db.execute("UPDATE learning_findings SET state='rejected',reason=? WHERE id=?", (redact(str(error))[:600], finding["id"]))
            return
        context = self._context(finding, repository, evidence)
        with self.db:
            self.db.execute("UPDATE learning_findings SET state='reviewing',attempts=attempts+1,reviewed_incidents=? WHERE id=?",
                            (len(evidence), finding["id"]))
            review_id = self.db.execute("INSERT INTO learning_reviews(finding,started_at) VALUES(?,?)", (finding["id"], now)).lastrowid
        reviewer = self.reviewer
        try:
            if reviewer is None:
                from agent_learning_review import CodexReviewer
                reviewer = CodexReviewer(repository, self.store.state_dir)
            proposal = reviewer.review(context)
            if not self._verify(proposal.get("evidence_refs"), evidence):
                raise LearningError("proposal evidence does not resolve to the selected original records")
            state, reason, commit = "deferred", "insufficient independent evidence", None
            proposal["proposal_id"] = finding["fingerprint"]
            proposal["target_skill"] = proposal["owner"]
            proposal["blocked_state"] = repository_state(repository)
            proposal["base_head"] = expected_head
            ref_keys = {(ref["session"], ref["position"], ref["digest"]) for ref in proposal["evidence_refs"]}
            independent = len({e["root_session"] for e in evidence if e["root_session"] != "unresolved-ancestry" and (e["session"], e["position"], e["digest"]) in ref_keys}) >= 2
            represented = False
            for previous in self.db.execute("SELECT project,proposal FROM learning_findings WHERE id!=? AND state IN ('promoted','memory') AND proposal IS NOT NULL", (finding["id"],)):
                prior = json.loads(previous["proposal"])
                if prior["owner"] == proposal["owner"] and prior["target"] == proposal["target"] and (proposal["target"] == "skill" or finding["project"] == previous["project"]):
                    represented = similarity(words(prior["future_action"]), words(proposal["future_action"])) >= .9
                    if represented:
                        break
            if proposal["action"] == "improve" and represented:
                state, reason = "superseded", "an approved finding already represents this action"
            elif proposal["action"] == "reject":
                state, reason = "rejected", proposal["uncertainty"]
            elif proposal["action"] == "supersede":
                older = proposal.get("supersedes", 0)
                with self.db:
                    self.db.execute("UPDATE learning_memories SET state='superseded' WHERE finding=? AND project=?", (older, finding["project"]))
                state, reason = "superseded", "new evidence supersedes project memory; skill reversal needs attributable regression"
            elif proposal["action"] == "improve" and independent:
                if proposal["target"] == "memory":
                    state, reason = self._approve_memory(finding, project, proposal, evidence, now)
                elif proposal["target"] == "skill":
                    owner = proposal["owner"]
                    from agent_learning_promote import KNOWN_LEAF_SKILLS
                    if owner not in KNOWN_LEAF_SKILLS:
                        raise LearningError("proposal has no allowed existing leaf owner")
                    if owner not in context["owning_guidance"]:
                        context["owning_guidance"] = {owner: (repository / "dotfiles/base/.agents/skills" / owner / "SKILL.md").read_text()}
                        context["routing_proposal"] = proposal
                        proposal = reviewer.review(context)
                        if proposal["owner"] != owner or proposal["target"] != "skill" or proposal["action"] != "improve" or not self._verify(proposal["evidence_refs"], evidence):
                            raise LearningError("proposal changed owner or evidence after inspecting guidance")
                        proposal["proposal_id"] = finding["fingerprint"]
                        proposal["target_skill"] = owner
                        proposal["blocked_state"] = repository_state(repository)
                        proposal["base_head"] = expected_head
                    skill = repository / "dotfiles/base/.agents/skills" / owner / "SKILL.md"
                    context["owning_guidance"] = {owner: skill.read_text()}
                    reviewer_proposal = {key: value for key, value in proposal.items() if key not in ("blocked_state", "base_head")}
                    proposal["independent_review"] = reviewer.adversarial(context, reviewer_proposal)
                    with self.db:
                        self.db.execute("UPDATE learning_findings SET proposal=?,reason='promotion prepared' WHERE id=?", (json.dumps(proposal), finding["id"]))
                    promotion_proposal = {key: value for key, value in proposal.items() if key not in ("blocked_state", "base_head", "confidence", "supersedes")}
                    refs = {(ref["session"], ref["position"], ref["digest"]) for ref in proposal["evidence_refs"]}
                    selected_evidence = [item for item in evidence if (item["session"], item["position"], item["digest"]) in refs]
                    result = promote(repository, promotion_proposal, selected_evidence, expected_head, verify_evidence=self._verify)
                    state = "promoted" if result["status"] == "promoted" else "held"
                    reason, commit = result.get("reason"), result.get("commit")
            with self.db:
                self.db.execute("""UPDATE learning_findings SET state=?,proposal=?,reason=?,commit_id=?,integrated_at=?,updated_at=? WHERE id=?""",
                                (state, json.dumps(proposal), reason, commit, now if state in ("promoted", "memory") else None, now, finding["id"]))
                self.db.execute("UPDATE learning_reviews SET finished_at=?,outcome=?,usage=? WHERE id=?",
                                (now, state, json.dumps(getattr(reviewer, "usage", None)), review_id))
                if state in ("promoted", "memory"):
                    for session_id in {item["session"] for item in evidence}:
                        session = self.db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
                        if session:
                            self.evaluate(dict(session), self._events(session_id)[0])
        except (LearningError, StoreError, OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
            with self.db:
                self.db.execute("UPDATE learning_findings SET state='deferred',reason=?,retry_at=?,updated_at=? WHERE id=?",
                                (redact(str(error))[:600], now + 3600, now, finding["id"]))
                self.db.execute("UPDATE learning_reviews SET finished_at=?,outcome='error' WHERE id=?", (now, review_id))

    def _approve_memory(self, finding, project, proposal, evidence, now):
        from agent_learning_promote import protected_text, safe_action
        if not safe_action(proposal["future_action"]) or protected_text(proposal["applicability"]):
            return "held", "project memory may not change protected policies"
        if not proposal["future_action"].strip() or not proposal["applicability"].strip():
            return "rejected", "memory needs an action and applicability"
        context = {"owning_guidance": "Project-specific memory. Never overrides repository rules.", "evidence": evidence[:2]}
        reviewer = self.reviewer
        if reviewer is None:
            from agent_learning_review import CodexReviewer
            reviewer = CodexReviewer(Path(project["repository"]), self.store.state_dir)
        verdict = reviewer.adversarial(context, {key: value for key, value in proposal.items() if key not in ("blocked_state", "base_head")})
        if not verdict.get("approves") or verdict.get("risks") or not verdict.get("does_not_weaken"):
            return "held", "independent review did not approve project memory"
        action = proposal["future_action"][:600]
        for memory in self.db.execute("SELECT action FROM learning_memories WHERE project=? AND state='approved'", (finding["project"],)):
            if similarity(words(action), words(memory[0])) > .8:
                return "superseded", "existing memory already represents this action"
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO learning_memories VALUES(?,?,?,?,?,'approved',?)",
                            (finding["id"], finding["project"], action, proposal["applicability"][:400], git_revision(project["cwd"]), now))
        return "memory", "approved project-scoped action"

    def monitor(self, finding, project, now):
        proposal = json.loads(finding["proposal"])
        incident_count = self.db.execute("SELECT count(*) FROM learning_incidents WHERE finding=?", (finding["id"],)).fetchone()[0]
        if incident_count <= finding["reviewed_incidents"]:
            return False
        try:
            evidence = [row for row in self._evidence(finding["id"]) if row["observed_at"] > finding["integrated_at"]]
        except (StoreError, ValueError, OSError) as error:
            with self.db:
                self.db.execute("UPDATE learning_findings SET reason=? WHERE id=?", (redact(str(error))[:600], finding["id"]))
            return False
        if len({row["root_session"] for row in evidence}) < 2:
            return False
        repository = Path(project["repository"])
        if self.reviewer is None:
            from agent_learning_review import CodexReviewer
            reviewer = CodexReviewer(repository, self.store.state_dir)
        else:
            reviewer = self.reviewer
        context = {"evidence": evidence[:2], "prior_promotion": proposal,
                   "policy": "Investigate attribution, alternatives and procedure adherence. Repeated corrections alone do not establish harm. Return supersede only for a clearly attributable regression, with the exact inverse edit and supersedes finding ID.",
                   "finding_id": finding["id"]}
        with self.db:
            self.db.execute("UPDATE learning_findings SET reviewed_incidents=? WHERE id=?", (incident_count, finding["id"]))
            review_id = self.db.execute("INSERT INTO learning_reviews(finding,started_at) VALUES(?,?)", (finding["id"], now)).lastrowid
        try:
            review = reviewer.review(context)
            with self.db:
                for item in evidence:
                    self.db.execute("UPDATE learning_evaluations SET assessment=? WHERE finding=? AND session=?",
                                    (json.dumps(review), finding["id"], item["session"]))
            if review["action"] != "supersede" or review.get("supersedes") != finding["id"] or not self._verify(review["evidence_refs"], evidence):
                return True
            if finding["state"] == "memory":
                with self.db:
                    self.db.execute("UPDATE learning_memories SET state='superseded' WHERE finding=?", (finding["id"],))
                    self.db.execute("UPDATE learning_findings SET state='superseded',reason='new evidence contradicts memory' WHERE id=?", (finding["id"],))
                return True
            added_action = proposal["future_action"]
            attributed = all(any(added_action in e["text"] and re.search(r"\b(caused|regression|contradicts)\b", e["text"], re.I)
                                 for e in row["window"] if e["kind"] == "user") for row in evidence[:2])
            if not attributed or review["edit"] != {"old": proposal["edit"]["new"], "new": proposal["edit"]["old"]}:
                return True
            verdict = reviewer.adversarial(context, review)
            if not verdict.get("approves") or verdict.get("risks") or not verdict.get("does_not_weaken"):
                return True
            from agent_learning_promote import rollback
            result = rollback(repository, finding["commit_id"], git_revision(repository))
            if result["status"] == "reverted":
                with self.db:
                    self.db.execute("UPDATE learning_findings SET state='reversed',reason=?,updated_at=? WHERE id=?",
                                    ("attributed regression reversed: " + str(result.get("commit")), now, finding["id"]))
            return True
        except (StoreError, ValueError, OSError, subprocess.SubprocessError) as error:
            with self.db:
                self.db.execute("UPDATE learning_findings SET reason=? WHERE id=?", (redact(str(error))[:600], finding["id"]))
            return True
        finally:
            with self.db:
                self.db.execute("UPDATE learning_reviews SET finished_at=?,outcome='monitor',usage=? WHERE id=?",
                                (now, json.dumps(getattr(reviewer, "usage", None)), review_id))

    def reconcile(self, now, roots=None, stable_seconds=STABLE_SECONDS, max_reviews=MAX_REVIEWS):
        totals = {"processed": 0, "signals": 0, "reviews": 0}
        projects = list(self.db.execute("""SELECT p.* FROM learning_projects p LEFT JOIN learning_hints h ON h.project=p.project
            WHERE p.enabled=1 ORDER BY coalesce(h.observed_at,0) DESC,p.project"""))
        if not projects:
            return totals
        self.resume_promotions(now)
        self.recover_rollbacks()
        with self.db:
            self.db.execute("UPDATE learning_findings SET state='deferred',reason='interrupted review',retry_at=? WHERE state='reviewing'", (now + 3600,))
        for project in projects:
            self.store.refresh(roots=roots, project=project["project"])
            stats = self.discover(project["project"], now, stable_seconds)
            with self.db:
                self.db.execute("DELETE FROM learning_hints WHERE project=? AND observed_at<=?", (project["project"], now))
            for key in stats:
                totals[key] += stats[key]
            with self.db:
                for row in self.db.execute("SELECT * FROM learning_findings WHERE project=? AND state='held' AND proposal IS NOT NULL AND attempts<3", (project["project"],)).fetchall():
                    if json.loads(row["proposal"]).get("blocked_state") != repository_state(project["repository"]):
                        self.db.execute("UPDATE learning_findings SET state='pending' WHERE id=?", (row["id"],))
            for row in self.db.execute("SELECT * FROM learning_findings WHERE project=? AND state IN ('promoted','memory')", (project["project"],)).fetchall():
                if totals["reviews"] < max_reviews and self.monitor(row, project, now):
                    totals["reviews"] += 1
            pending = list(self.db.execute("""SELECT f.* FROM learning_findings f WHERE project=?
                AND state IN ('pending','deferred') AND attempts<3 AND retry_at<=?
                AND (state='pending' OR reason='interrupted review' OR reason LIKE '%unavailable%' OR retry_at>0)
                ORDER BY (SELECT count(DISTINCT root_session) FROM learning_incidents WHERE finding=f.id) DESC,created_at
                LIMIT ?""", (project["project"], now, max(0, max_reviews-totals["reviews"]))))
            for finding in pending:
                self.review(finding, project, now)
                totals["reviews"] += 1
        return totals

    def resume_promotions(self, now):
        from agent_learning_promote import promote
        rows = self.db.execute("""SELECT f.*,p.repository FROM learning_findings f
            JOIN learning_projects p ON p.project=f.project WHERE p.enabled=1
            AND f.state='reviewing' AND f.reason='promotion prepared' AND f.proposal IS NOT NULL LIMIT 2""").fetchall()
        for row in rows:
            proposal = json.loads(row["proposal"])
            try:
                evidence = self._evidence(row["id"])
                refs = {(ref["session"], ref["position"], ref["digest"]) for ref in proposal["evidence_refs"]}
                evidence = [item for item in evidence if (item["session"], item["position"], item["digest"]) in refs]
                payload = {key: value for key, value in proposal.items() if key not in ("blocked_state", "base_head", "confidence", "supersedes")}
                result = promote(Path(row["repository"]), payload, evidence, proposal["base_head"], verify_evidence=self._verify)
                state = "promoted" if result["status"] == "promoted" else "held"
                with self.db:
                    self.db.execute("UPDATE learning_findings SET state=?,commit_id=?,integrated_at=?,reason=?,updated_at=? WHERE id=?",
                                    (state, result.get("commit"), now if state == "promoted" else None, result.get("reason"), now, row["id"]))
                    self.db.execute("UPDATE learning_reviews SET finished_at=?,outcome=? WHERE finding=? AND finished_at IS NULL", (now, state, row["id"]))
            except (StoreError, ValueError, OSError) as error:
                with self.db:
                    self.db.execute("UPDATE learning_findings SET state='held',reason=? WHERE id=?", (redact(str(error))[:600], row["id"]))

    def recover_rollbacks(self):
        for row in self.db.execute("""SELECT f.id,f.commit_id,p.repository FROM learning_findings f
            JOIN learning_projects p ON p.project=f.project
            WHERE p.enabled=1 AND f.state='promoted' AND f.commit_id IS NOT NULL""").fetchall():
            marker = "Reverts-Learning-Promotion: " + row["commit_id"]
            result = subprocess.run(["git", "-C", row["repository"], "log", "--format=%B", "--fixed-strings", "--grep="+marker], capture_output=True, timeout=10, check=True)
            if marker in result.stdout.decode().splitlines():
                with self.db:
                    self.db.execute("UPDATE learning_findings SET state='reversed',reason='recovered committed rollback' WHERE id=?", (row["id"],))

    def recall(self, project, query, check_revision=True):
        row = self.db.execute("SELECT cwd FROM learning_projects WHERE project=? AND enabled=1", (project,)).fetchone()
        if row is None:
            return []
        revision = git_revision(row[0]) if check_revision else None
        terms, matches = words(query), []
        for memory in self.db.execute("SELECT * FROM learning_memories WHERE project=? AND state='approved'", (project,)):
            if revision and memory["revision"] != revision:
                continue
            score = len(terms & words(memory["action"] + " " + memory["applicability"]))
            if score:
                matches.append((score, {"id": memory["finding"], "action": redact(memory["action"]), "when": redact(memory["applicability"])}))
        return [value for _, value in sorted(matches, key=lambda entry: -entry[0])[:3]]

    def evaluate(self, session, events):
        loaded = set()
        for event in events:
            if event["kind"] in ("tool-call", "tool_call"):
                loaded.update(SKILL_PATH.findall(event["text"]))
        repeated = {kind for _, kind, _ in signals(events)}
        task_words = words(" ".join(e["text"] for e in events if e["kind"] == "user")[:12000])
        for finding in self.db.execute("SELECT * FROM learning_findings WHERE project=? AND state IN ('promoted','memory','reversed') AND proposal IS NOT NULL", (session["project"],)).fetchall():
            proposal = json.loads(finding["proposal"])
            relevant = len(task_words & words(proposal["applicability"])) >= 2
            phase = "after" if session["updated"] > (finding["integrated_at"] or 0) else "before"
            self.db.execute("INSERT OR REPLACE INTO learning_evaluations VALUES(?,?,?,?,?,?,?)", (
                finding["id"], session["id"], phase, int(relevant), int(proposal["owner"] in loaded),
                int(relevant and finding["signal"] in repeated), "observational; procedure adherence and causality unestablished"))

    def status(self):
        return {
            "projects": [dict(row) for row in self.db.execute("SELECT * FROM learning_projects")],
            "eligible_sessions_processed": self.db.execute("SELECT count(*) FROM learning_processed").fetchone()[0],
            "candidate_signals": self.db.execute("SELECT count(*) FROM learning_incidents").fetchone()[0],
            "pending_hook_hints": self.db.execute("SELECT count(*) FROM learning_hints").fetchone()[0],
            "findings": {row[0]: row[1] for row in self.db.execute("SELECT state,count(*) FROM learning_findings GROUP BY state")},
            "deduplicated_incidents": self.db.execute("SELECT count(*)-count(DISTINCT finding) FROM learning_incidents").fetchone()[0],
            "model_reviews": self.db.execute("SELECT count(*) FROM learning_reviews").fetchone()[0],
            "promotions_rejected_by_validation": self.db.execute("SELECT count(*) FROM learning_findings WHERE state='held'").fetchone()[0],
            "recurring_mistakes": self.db.execute("SELECT COALESCE(sum(repeated),0) FROM learning_evaluations WHERE phase='after'").fetchone()[0],
            "model_usage": [json.loads(row[0]) for row in self.db.execute("SELECT usage FROM learning_reviews WHERE usage IS NOT NULL AND usage!='null' ORDER BY id DESC LIMIT 10")],
            "bounded_session_coverage": self.db.execute("SELECT count(*) FROM learning_processed WHERE truncated=1").fetchone()[0],
            "effectiveness": [dict(row) for row in self.db.execute("SELECT finding,phase,count(*) AS sessions,sum(relevant) AS relevant,sum(loaded*relevant) AS invoked,sum(repeated) AS recurring FROM learning_evaluations GROUP BY finding,phase")],
            "causal_improvement": "not established; invocation and recurrence are observational",
        }


def parser():
    cli = argparse.ArgumentParser(description="Bounded, opt-in local agent learning")
    cli.add_argument("--state-dir", type=Path, default=default_state_dir())
    commands = cli.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--scheduled", action="store_true")
    for command in ("status", "doctor", "findings"):
        commands.add_parser(command)
    commands.add_parser("show").add_argument("finding", type=int)
    for command in ("enable", "disable"):
        operation = commands.add_parser(command)
        operation.add_argument("--project", type=Path, default=Path.cwd())
        operation.add_argument("--schedule", action="store_true")
        if command == "enable":
            operation.add_argument("--usr-root", type=Path, default=Path(__file__).resolve().parents[4])
    recall = commands.add_parser("recall")
    recall.add_argument("query")
    recall.add_argument("--project", type=Path, default=Path.cwd())
    commands.add_parser("hook", help=argparse.SUPPRESS)
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "hook":
        from agent_learning_ops import hook
        try:
            raw = sys.stdin.buffer.read(16385)
            if len(raw) <= 16384:
                hook(args.state_dir, json.loads(raw))
        except (OSError, ValueError, sqlite3.Error) as error:
            print("agent-learn hook: " + redact(str(error))[:200], file=sys.stderr)
        print("{}")
        return 0
    try:
        store = Store(args.state_dir)
        learner = Learner(store)
        if args.command == "run":
            if os.environ.get("AGENT_LEARN_WORKER"):
                return 0
            with run_lock(args.state_dir) as acquired:
                if not acquired:
                    return 0
                result = learner.reconcile(time.time())
            if not args.scheduled:
                print(json.dumps(result))
        elif args.command == "enable":
            learner.enable(args.project, args.usr_root, time.time())
            if args.schedule:
                from agent_learning_ops import install_scheduler
                install_scheduler(args.usr_root, args.state_dir, Path.home())
            print("Enabled model review for this project. Hooks require separate Codex trust; timer reconciliation recovers missed hooks.")
        elif args.command == "disable":
            learner.disable(args.project)
            if args.schedule:
                from agent_learning_ops import remove_scheduler
                remove_scheduler(Path.home())
            print("Project model review disabled.")
        elif args.command in ("status", "doctor"):
            from agent_learning_ops import scheduler_status
            result = learner.status()
            result["scheduler"] = dataclasses.asdict(scheduler_status(Path.home()))
            if args.command == "doctor":
                from agent_learning_review import CodexReviewer
                result["database"] = store.db.execute("PRAGMA quick_check").fetchone()[0]
                repository = Path(__file__).resolve().parents[4]
                result["reviewer"] = CodexReviewer(repository, args.state_dir).capabilities()
                result["redaction"] = "heuristic, cannot guarantee removal of all secrets"
                result["hook_trust"] = "inspect /hooks in Codex; never inferred from configured commands"
            print(redact(json.dumps(result, indent=2)))
        elif args.command == "recall":
            print(json.dumps(learner.recall(project_identity(args.project), args.query), indent=2))
        elif args.command == "findings":
            print(redact(json.dumps([dict(row) for row in learner.db.execute("SELECT id,signal,state,reason,commit_id FROM learning_findings ORDER BY id DESC LIMIT 50")], indent=2)))
        elif args.command == "show":
            row = learner.db.execute("SELECT * FROM learning_findings WHERE id=?", (args.finding,)).fetchone()
            if row is None:
                raise LearningError("finding does not exist")
            evaluations = [dict(item) for item in learner.db.execute("SELECT * FROM learning_evaluations WHERE finding=? ORDER BY session LIMIT 20", (args.finding,))]
            print(redact(json.dumps({"finding": dict(row), "evidence": learner._evidence(args.finding), "evaluations": evaluations}, indent=2)))
        store.db.close()
        return 0
    except (LearningError, StoreError, SchedulerError, OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
        print("agent-learn: " + redact(str(error))[:600], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
