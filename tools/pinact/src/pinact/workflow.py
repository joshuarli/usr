"""Structural workflow/action checks sharing one node traversal."""

from __future__ import annotations

import re

from pinact._vendor.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from pinact.model import SourceDocument, mapping_get, mapping_pairs, scalar_text
from pinact import tables

JOB_ID = re.compile(r"[a-zA-Z_][a-zA-Z0-9_-]*\Z")
STEP_ID = re.compile(r"[a-zA-Z_][a-zA-Z0-9_-]*\Z")
CRON_FIELD = re.compile(
    r"^(\*|(\*|\d+)([-/]\d+)?(,(\*|\d+)([-/]\d+)?)*)$"
)


def _line_col(key_node) -> tuple[int, int]:
    return key_node.start_mark.line + 1, key_node.start_mark.column + 1


def _value_line_col(node) -> tuple[int, int]:
    return node.start_mark.line + 1, node.start_mark.column + 1


def check_top_level(doc: SourceDocument, root: MappingNode, profile: str) -> list[tuple]:
    out = []
    if doc.kind == "action":
        for key, _ in mapping_pairs(root):
            if not isinstance(key, ScalarNode):
                continue
            if key.value not in tables.ACTION_TOP_KEYS and profile in ("default", "strict"):
                line, col = _line_col(key)
                out.append((line, col, "unknown-key", "error",
                            f"unknown action key '{key.value}'", False))
        runs = mapping_get(root, "runs")
        if runs is None:
            key = root.value[0][0] if root.value else None
            line, col = _line_col(key) if key is not None else (1, 1)
            out.append((line, col, "missing-key", "error",
                        "action file is missing required key 'runs'", False))
        elif not isinstance(runs, MappingNode):
            line, col = _value_line_col(runs)
            out.append((line, col, "invalid-type", "error",
                        "'runs' must be a mapping", False))
        else:
            for key, _ in mapping_pairs(runs):
                if isinstance(key, ScalarNode) and key.value not in tables.RUNS_KEYS and profile in ("default", "strict"):
                    line, col = _line_col(key)
                    out.append((line, col, "unknown-key", "error",
                                f"unknown runs key '{key.value}'", False))
        return out
    for key, _ in mapping_pairs(root):
        if not isinstance(key, ScalarNode):
            continue
        if key.value not in tables.WORKFLOW_TOP_KEYS and profile in ("default", "strict"):
            line, col = _line_col(key)
            out.append((line, col, "unknown-key", "error",
                        f"unknown top-level key '{key.value}'", False))
    on = mapping_get(root, "on")
    jobs = mapping_get(root, "jobs")
    if jobs is None:
        line, col = (1, 1)
        out.append((line, col, "missing-key", "error",
                    "workflow is missing required key 'jobs'", False))
    elif not isinstance(jobs, MappingNode):
        line, col = _value_line_col(jobs)
        out.append((line, col, "invalid-type", "error",
                    "'jobs' must be a mapping", False))
    if on is None:
        out.append((1, 1, "missing-key", "error",
                    "workflow is missing required key 'on'", False))
    return out


def check_events(doc: SourceDocument, root: MappingNode) -> list[tuple]:
    out = []
    on = mapping_get(root, "on")
    if on is None or not isinstance(root, MappingNode):
        return out
    if isinstance(on, ScalarNode):
        events = [on.value]
        base_line, base_col = _value_line_col(on)
        for ev in events:
            if ev not in tables.EVENTS:
                out.append((base_line, base_col, "invalid-event", "error",
                            f"unknown trigger event '{ev}'", False))
        return out
    if isinstance(on, SequenceNode):
        for item in on.value:
            if isinstance(item, ScalarNode):
                if item.value not in tables.EVENTS:
                    line, col = _value_line_col(item)
                    out.append((line, col, "invalid-event", "error",
                                f"unknown trigger event '{item.value}'", False))
            else:
                line, col = _value_line_col(item)
                out.append((line, col, "invalid-type", "error",
                            "'on' list entries must be strings", False))
        return out
    if isinstance(on, MappingNode):
        for key, value in mapping_pairs(on):
            if not isinstance(key, ScalarNode):
                continue
            if key.value not in tables.EVENTS:
                line, col = _line_col(key)
                out.append((line, col, "invalid-event", "error",
                            f"unknown trigger event '{key.value}'", False))
                continue
            if key.value == "schedule":
                out.extend(check_schedule(key, value))
            elif key.value == "workflow_call":
                out.extend(check_workflow_call(key, value))
            elif key.value != "workflow_dispatch":
                out.extend(check_event_filters(key, value))
    else:
        line, col = _value_line_col(on)
        out.append((line, col, "invalid-type", "error",
                    "'on' must be a string, list, or mapping", False))
    return out


def check_event_filters(key_node, value) -> list[tuple]:
    out = []
    if not isinstance(value, MappingNode):
        return out
    allowed = tables.EVENT_FILTERS.get(key_node.value, frozenset())
    for fkey, fval in mapping_pairs(value):
        if not isinstance(fkey, ScalarNode):
            continue
        if fkey.value not in allowed:
            line, col = _line_col(fkey)
            out.append((line, col, "invalid-event-filter", "error",
                        f"unknown filter '{fkey.value}' for event '{key_node.value}'", False))
            continue
        if fkey.value in ("branches", "branches-ignore", "tags", "tags-ignore", "paths", "paths-ignore"):
            if not isinstance(fval, SequenceNode):
                line, col = _value_line_col(fval)
                out.append((line, col, "invalid-type", "error",
                            f"'{fkey.value}' must be a list of strings", False))
            else:
                for item in fval.value:
                    if not isinstance(item, ScalarNode):
                        line, col = _value_line_col(item)
                        out.append((line, col, "invalid-type", "error",
                                    f"'{fkey.value}' entries must be strings", False))
        elif fkey.value in ("types",):
            if not isinstance(fval, SequenceNode):
                line, col = _value_line_col(fval)
                out.append((line, col, "invalid-type", "error",
                            "'types' must be a list of strings", False))
    return out


def check_schedule(key_node, value) -> list[tuple]:
    out = []
    if not isinstance(value, SequenceNode):
        line, col = _value_line_col(value)
        out.append((line, col, "invalid-type", "error",
                    "'schedule' must be a list", False))
        return out
    for item in value.value:
        if not isinstance(item, MappingNode):
            line, col = _value_line_col(item)
            out.append((line, col, "invalid-type", "error",
                        "'schedule' entries must be mappings with 'cron'", False))
            continue
        cron = mapping_get(item, "cron")
        if cron is None:
            line, col = _value_line_col(item)
            out.append((line, col, "missing-key", "error",
                        "schedule entry is missing required key 'cron'", False))
            continue
        if not isinstance(cron, ScalarNode):
            line, col = _value_line_col(cron)
            out.append((line, col, "invalid-type", "error",
                        "'cron' must be a string", False))
            continue
        if not valid_cron(cron.value):
            line, col = _value_line_col(cron)
            out.append((line, col, "invalid-cron", "error",
                        f"invalid cron expression '{cron.value}'", False))
    return out


def valid_cron(expr: str) -> bool:
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    return all(bool(CRON_FIELD.fullmatch(p)) for p in parts)


def check_workflow_call(key_node, value) -> list[tuple]:
    out = []
    if not isinstance(value, MappingNode):
        return out
    for fkey, fval in mapping_pairs(value):
        if isinstance(fkey, ScalarNode) and fkey.value in ("inputs", "outputs", "secrets"):
            if not isinstance(fval, MappingNode):
                line, col = _value_line_col(fval)
                out.append((line, col, "invalid-type", "error",
                            f"'workflow_call.{fkey.value}' must be a mapping", False))
    return out


def check_permissions_node(node, where: str) -> list[tuple]:
    out = []
    if isinstance(node, ScalarNode):
        if node.value not in tables.PERMISSION_SHORTHANDS:
            line, col = _value_line_col(node)
            out.append((line, col, "invalid-permissions", "error",
                        f"invalid permissions value '{node.value}' at {where}", False))
        return out
    if not isinstance(node, MappingNode):
        line, col = _value_line_col(node)
        out.append((line, col, "invalid-permissions", "error",
                    f"'permissions' at {where} must be a mapping or shorthand", False))
        return out
    for key, value in mapping_pairs(node):
        if not isinstance(key, ScalarNode):
            continue
        if key.value not in tables.PERMISSION_SCOPES:
            line, col = _line_col(key)
            out.append((line, col, "invalid-permissions", "error",
                        f"unknown permission scope '{key.value}' at {where}", False))
            continue
        if not isinstance(value, ScalarNode) or value.value not in tables.PERMISSION_VALUES:
            line, col = _value_line_col(value)
            got = scalar_text(value) if isinstance(value, ScalarNode) else type(value).__name__
            out.append((line, col, "invalid-permissions", "error",
                        f"invalid permission value '{got}' for scope '{key.value}' at {where}", False))
    return out


def check_jobs(doc: SourceDocument, root: MappingNode, profile: str) -> list[tuple]:
    out = []
    jobs = mapping_get(root, "jobs")
    if not isinstance(jobs, MappingNode):
        return out
    seen_ids: dict[str, tuple[int, int]] = {}
    needs_map: dict[str, list[str]] = {}
    for job_key, job_val in mapping_pairs(jobs):
        if not isinstance(job_key, ScalarNode):
            continue
        jid = job_key.value
        if not JOB_ID.fullmatch(jid):
            line, col = _line_col(job_key)
            out.append((line, col, "invalid-job-id", "error",
                        f"invalid job id '{jid}'", False))
        if jid in seen_ids:
            line, col = _line_col(job_key)
            out.append((line, col, "duplicate-key", "error",
                        f"duplicate job id '{jid}'", False))
        else:
            seen_ids[jid] = _line_col(job_key)
        if not isinstance(job_val, MappingNode):
            line, col = _value_line_col(job_val)
            out.append((line, col, "invalid-type", "error",
                        f"job '{jid}' must be a mapping", False))
            continue
        for key, _ in mapping_pairs(job_val):
            if isinstance(key, ScalarNode) and key.value not in tables.JOB_KEYS and profile in ("default", "strict"):
                line, col = _line_col(key)
                out.append((line, col, "unknown-key", "error",
                            f"unknown job key '{key.value}' in job '{jid}'", False))
        out.extend(check_job_body(job_key, job_val, jid, profile))
        needs_node = mapping_get(job_val, "needs")
        if needs_node is not None:
            needs, nerrs = parse_needs(needs_node, jid)
            out.extend(nerrs)
            needs_map[jid] = needs
    out.extend(check_needs_edges(seen_ids, needs_map, jobs))
    return out


def parse_needs(node, jid: str) -> tuple[list[str], list[tuple]]:
    out: list[str] = []
    errs: list[tuple] = []
    if isinstance(node, ScalarNode):
        if not node.value:
            line, col = _value_line_col(node)
            errs.append((line, col, "invalid-needs", "error",
                         f"job '{jid}' has empty 'needs'", False))
        else:
            out = [node.value]
        return out, errs
    if isinstance(node, SequenceNode):
        for item in node.value:
            if not isinstance(item, ScalarNode) or not item.value:
                line, col = _value_line_col(item)
                errs.append((line, col, "invalid-needs", "error",
                             f"job '{jid}' has non-string 'needs' entry", False))
            else:
                out.append(item.value)
        if len(set(out)) != len(out):
            line, col = _value_line_col(node)
            errs.append((line, col, "invalid-needs", "error",
                         f"job '{jid}' has duplicate 'needs' entries", False))
        return out, errs
    line, col = _value_line_col(node)
    errs.append((line, col, "invalid-needs", "error",
                 f"job '{jid}' 'needs' must be a string or list", False))
    return out, errs


def check_needs_edges(seen: dict, needs_map: dict[str, list[str]], jobs_node) -> list[tuple]:
    out = []
    for jid, needs in needs_map.items():
        for need in needs:
            if need == jid:
                key = _find_job_key(jobs_node, jid)
                line, col = _line_col(key) if key is not None else (1, 1)
                out.append((line, col, "invalid-needs", "error",
                            f"job '{jid}' needs itself", False))
            elif need not in seen:
                key = _find_job_key(jobs_node, jid)
                line, col = _line_col(key) if key is not None else (1, 1)
                out.append((line, col, "invalid-needs", "error",
                            f"job '{jid}' needs unknown job '{need}'", False))
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {jid: WHITE for jid in seen}
    stack: list[str] = []

    def visit(node_id: str) -> bool:
        color[node_id] = GRAY
        stack.append(node_id)
        for dep in needs_map.get(node_id, []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                key = _find_job_key(jobs_node, stack[stack.index(dep)])
                line, col = _line_col(key) if key is not None else (1, 1)
                cycle = " -> ".join([*stack, dep])
                out.append((line, col, "needs-cycle", "error",
                            f"circular needs dependency: {cycle}", False))
                return True
            if color[dep] == WHITE and visit(dep):
                return True
        stack.pop()
        color[node_id] = BLACK
        return False

    for jid in seen:
        if color[jid] == WHITE:
            visit(jid)
    return out


def _find_job_key(jobs_node: MappingNode, jid: str):
    for key, _ in mapping_pairs(jobs_node):
        if isinstance(key, ScalarNode) and key.value == jid:
            return key
    return None


def check_job_body(job_key, job_val: MappingNode, jid: str, profile: str = "default") -> list[tuple]:
    out = []
    uses = mapping_get(job_val, "uses")
    steps = mapping_get(job_val, "steps")
    runs_on = mapping_get(job_val, "runs-on")
    if uses is not None:
        if not isinstance(uses, ScalarNode):
            line, col = _value_line_col(uses)
            out.append((line, col, "invalid-uses", "error",
                        f"job '{jid}' 'uses' must be a string", False))
        if steps is not None:
            line, col = _line_col(job_key)
            out.append((line, col, "invalid-type", "error",
                        f"job '{jid}' has both 'uses' and 'steps'", False))
    else:
        if steps is None:
            line, col = _line_col(job_key)
            out.append((line, col, "missing-key", "error",
                        f"job '{jid}' needs 'steps' or 'uses'", False))
        elif not isinstance(steps, SequenceNode):
            line, col = _value_line_col(steps)
            out.append((line, col, "invalid-type", "error",
                        f"job '{jid}' 'steps' must be a sequence", False))
        elif not steps.value:
            line, col = _value_line_col(steps)
            out.append((line, col, "missing-key", "error",
                        f"job '{jid}' has empty 'steps'", False))
        else:
            out.extend(check_steps(job_val, steps, jid, profile))
            if runs_on is None:
                line, col = _line_col(job_key)
                out.append((line, col, "missing-key", "error",
                            f"job '{jid}' is missing required key 'runs-on'", False))
    strategy = mapping_get(job_val, "strategy")
    if strategy is not None:
        out.extend(check_strategy(strategy, jid))
    perms = mapping_get(job_val, "permissions")
    if perms is not None:
        out.extend(check_permissions_node(perms, f"job '{jid}'"))
    return out


def check_steps(job_val: MappingNode, steps: SequenceNode, jid: str, profile: str = "default") -> list[tuple]:
    out = []
    seen: set[str] = set()
    for idx, item in enumerate(steps.value):
        if not isinstance(item, MappingNode):
            line, col = _value_line_col(item)
            out.append((line, col, "invalid-type", "error",
                        f"job '{jid}' step {idx + 1} must be a mapping", False))
            continue
        for key, _ in mapping_pairs(item):
            if isinstance(key, ScalarNode) and key.value not in tables.STEP_KEYS and profile in ("default", "strict"):
                line, col = _line_col(key)
                out.append((line, col, "unknown-key", "error",
                            f"unknown step key '{key.value}' in job '{jid}' step {idx + 1}", False))
        sid_node = mapping_get(item, "id")
        if sid_node is not None:
            if not isinstance(sid_node, ScalarNode) or not STEP_ID.fullmatch(sid_node.value or ""):
                line, col = _value_line_col(sid_node)
                out.append((line, col, "invalid-type", "error",
                            f"job '{jid}' step {idx + 1} has invalid id", False))
            else:
                if sid_node.value in seen:
                    line, col = _value_line_col(sid_node)
                    out.append((line, col, "duplicate-key", "error",
                                f"duplicate step id '{sid_node.value}' in job '{jid}'", False))
                seen.add(sid_node.value)
        uses = mapping_get(item, "uses")
        run = mapping_get(item, "run")
        if uses is None and run is None:
            line, col = _value_line_col(item)
            out.append((line, col, "missing-key", "error",
                        f"job '{jid}' step {idx + 1} needs 'uses' or 'run'", False))
        if uses is not None and run is not None:
            line, col = _value_line_col(item)
            out.append((line, col, "invalid-type", "error",
                        f"job '{jid}' step {idx + 1} has both 'uses' and 'run'", False))
        if uses is not None and not isinstance(uses, ScalarNode):
            line, col = _value_line_col(uses)
            out.append((line, col, "invalid-uses", "error",
                        f"job '{jid}' step {idx + 1} 'uses' must be a string", False))
    return out


def check_strategy(strategy, jid: str) -> list[tuple]:
    out = []
    if not isinstance(strategy, MappingNode):
        line, col = _value_line_col(strategy)
        out.append((line, col, "invalid-type", "error",
                    f"job '{jid}' 'strategy' must be a mapping", False))
        return out
    matrix = mapping_get(strategy, "matrix")
    if matrix is None:
        return out
    if not isinstance(matrix, MappingNode):
        line, col = _value_line_col(matrix)
        out.append((line, col, "invalid-matrix", "error",
                    f"job '{jid}' 'strategy.matrix' must be a mapping", False))
        return out
    for key, value in mapping_pairs(matrix):
        if not isinstance(key, ScalarNode):
            continue
        if key.value in ("include", "exclude"):
            if not isinstance(value, SequenceNode):
                line, col = _value_line_col(value)
                out.append((line, col, "invalid-matrix", "error",
                            f"job '{jid}' matrix '{key.value}' must be a list", False))
            else:
                for entry in value.value:
                    if not isinstance(entry, MappingNode):
                        line, col = _value_line_col(entry)
                        out.append((line, col, "invalid-matrix", "error",
                                    f"job '{jid}' matrix '{key.value}' entries must be mappings", False))
    return out


def check_composite_steps(doc: SourceDocument, root: MappingNode) -> list[tuple]:
    out = []
    runs = mapping_get(root, "runs")
    if not isinstance(runs, MappingNode):
        return out
    steps = mapping_get(runs, "steps")
    if steps is None:
        return out
    if not isinstance(steps, SequenceNode):
        line, col = _value_line_col(steps)
        out.append((line, col, "invalid-type", "error",
                    "composite 'runs.steps' must be a sequence", False))
        return out
    for idx, item in enumerate(steps.value):
        if not isinstance(item, MappingNode):
            line, col = _value_line_col(item)
            out.append((line, col, "invalid-type", "error",
                        f"composite step {idx + 1} must be a mapping", False))
            continue
        uses = mapping_get(item, "uses")
        run = mapping_get(item, "run")
        if uses is None and run is None:
            line, col = _value_line_col(item)
            out.append((line, col, "missing-key", "error",
                        f"composite step {idx + 1} needs 'uses' or 'run'", False))
        if uses is not None and run is not None:
            line, col = _value_line_col(item)
            out.append((line, col, "invalid-type", "error",
                        f"composite step {idx + 1} has both 'uses' and 'run'", False))
    return out
