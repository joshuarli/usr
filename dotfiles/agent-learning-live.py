#!/usr/bin/env python3

import argparse
import importlib.machinery
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "dotfiles/base/.local/bin/agent_learning_review.py"
LOADER = importlib.machinery.SourceFileLoader("agent_learning_review", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("agent_learning_review", LOADER)
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
REPOSITORY = SCRIPT.parents[4]
TMP_ROOT = REPOSITORY / ".work" / "tmp"
GUIDANCE = (
    "---\n"
    "name: technical-writing\n"
    "description: Write clear project procedures. Skip broad style feedback.\n\n"
    "## Procedures\n\n"
    "Document commands with their prerequisites and verification steps."
)


def _evidence(project, session, text):
    return {
        "session": session,
        "position": 12,
        "digest": (session[0] * 64),
        "root_session": session,
        "project": project,
        "window": [{"kind": "user", "text": text, "position": 12}],
    }


def _context(signal, evidence, **extra):
    context = {
        "signal": signal,
        "evidence": evidence,
        "existing_owners": [{"owner": "technical-writing", "description": "Write clear project procedures."}],
        "owning_guidance": {"technical-writing": GUIDANCE},
        "tracked_project_files": [],
        "policy": "Existing instructions ignored require better discovery or execution, not another copy.",
    }
    context.update(extra)
    return context


def _has_improvement_for_both_projects(proposal, context):
    if proposal["action"] != "improve" or proposal["target"] != "skill" or proposal["scope"] != "global":
        return False
    if proposal["owner"] != "technical-writing" or proposal["validity"]:
        return False
    selected = {
        (row["session"], row["position"], row["digest"]): row
        for row in context["evidence"]
    }
    cited = [
        selected.get((ref["session"], ref["position"], ref["digest"]))
        for ref in proposal["evidence_refs"]
    ]
    cited = [row for row in cited if row is not None]
    return len({row["project"] for row in cited}) >= 2 and len({row["root_session"] for row in cited}) >= 2


def _cases():
    discovery = _context(
        "repeated-command",
        [
            _evidence("synthetic-project-a", "synthetic-session-a", "The task matched technical-writing, but the skill index did not make it discoverable. The agent wrote a runbook without reading that skill; the user asked why it was missed."),
            _evidence("synthetic-project-b", "synthetic-session-b", "The same documentation task appeared in a second synthetic project. The agent again missed technical-writing in the skill index and the user asked why."),
        ],
        corroborating_projects=["synthetic-project-a", "synthetic-project-b"],
    )
    read = _context(
        "repeated-correction",
        [
            _evidence("synthetic-project-a", "synthetic-session-c", "The agent listed and read technical-writing before editing a runbook. The documentation had no recovery step, and the user asked for it."),
            _evidence("synthetic-project-b", "synthetic-session-d", "The agent listed and read the same skill before a second runbook task. The same missing recovery step prompted another user correction."),
        ],
        corroborating_projects=["synthetic-project-a", "synthetic-project-b"],
    )
    followthrough = _context(
        "repeated-command",
        [
            _evidence("synthetic-project-a", "synthetic-session-e", "The agent read the documented backup prerequisite, then ran a migration without checking the backup. The user corrected it."),
            _evidence("synthetic-project-b", "synthetic-session-f", "A second project showed the same sequence: the agent read the backup prerequisite, skipped the check, and the user corrected it."),
        ],
        corroborating_projects=["synthetic-project-a", "synthetic-project-b"],
    )
    history = _context(
        "repeated-command",
        [
            _evidence("synthetic-project-a", "synthetic-session-g", "A command failed twice because its prerequisite was not checked."),
            _evidence("synthetic-project-b", "synthetic-session-h", "The same prerequisite mistake occurred in a second synthetic project."),
        ],
        corroborating_projects=["synthetic-project-a", "synthetic-project-b"],
        related_findings=[
            {
                "state": "promoted",
                "action": "When a documented command fails twice, verify its prerequisites before changing the procedure.",
            }
        ],
    )
    negative = _context(
        "repeated-tool-failure",
        [
            _evidence("synthetic-project-a", "synthetic-session-i", "A service request failed twice during an outage, then succeeded when the service recovered. No user correction or procedure change followed.")
        ],
    )
    return (
        ("discoverability", discovery, _has_improvement_for_both_projects),
        ("skill-read", read, _has_improvement_for_both_projects),
        ("followthrough", followthrough, _has_improvement_for_both_projects),
        ("historical-mistake", history, lambda proposal, context: proposal["action"] in {"defer", "reject"}),
        ("negative-control", negative, lambda proposal, context: proposal["action"] in {"defer", "reject"}),
    )


def _live(api_key):
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    call_count = 0
    with tempfile.TemporaryDirectory(prefix="agent-learning-live-", dir=str(TMP_ROOT)) as temp:
        scratch = Path(temp)
        home = scratch / "home"
        codex_home = scratch / "codex-home"
        home.mkdir(mode=0o700)
        codex_home.mkdir(mode=0o700)
        environment = {
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "TMPDIR": str(TMP_ROOT),
            "OPENAI_API_KEY": api_key,
        }
        reviewer = REVIEW.CodexReviewer(REPOSITORY, scratch / "state")
        with mock.patch.dict(os.environ, environment, clear=False):
            capabilities = reviewer.capabilities()
            if capabilities.get("status") != "ok":
                return {"status": "unavailable", "capabilities": capabilities}
            for name, context, grade in _cases():
                proposal = reviewer.review(context)
                call_count += 1
                passed = grade(proposal, context)
                results.append({"case": name, "passed": passed})
                if name == "discoverability" and passed:
                    proposal.update({"proposal_id": "synthetic-discovery", "target_skill": proposal["owner"]})
                    verdict = reviewer.adversarial(context, proposal)
                    call_count += 1
                    results.append(
                        {
                            "case": "independent-scope-review",
                            "passed": verdict["approves"]
                            and verdict["globally_applicable"]
                            and not verdict["risks"]
                            and verdict["does_not_weaken"],
                        }
                    )
    status = "ok" if all(result["passed"] for result in results) else "failed"
    return {
        "status": status,
        "static_cli": "verified",
        "live_model": "verified",
        "results": results,
        "calls": call_count,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the bounded synthetic Codex reviewer evaluation.")
    parser.add_argument("--live", action="store_true", help="make explicit model calls using OPENAI_API_KEY")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("pass --live to opt in to model calls")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        result = {"status": "unverified", "reason": "OPENAI_API_KEY is not set"}
    else:
        result = _live(api_key)
    print(json.dumps(result, separators=(",", ":")))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
