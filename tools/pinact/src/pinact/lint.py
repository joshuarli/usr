"""Findings model and ``pinact lint`` entry point.

Record shape, stable IDs, deterministic order, and exit codes are the
repomod contract. Rule coverage grows by campaign item; the shape must not
change without a coordinated update.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from pinact import pinning
from pinact.model import SourceDocument, mapping_get, parse_document
from pinact._vendor.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from pinact import workflow as wf
from pinact import expressions as expr
from pinact import security as sec

UNPINNED_USES = "unpinned-uses"
INVALID_USES = "invalid-uses"

KEY_COLUMN = re.compile(r"(?P<prefix>[ \t]*(?:-[ \t]+)?['\"]?)uses")
FINDING_LINE = re.compile(r":(\d+):")

CORRECTNESS_IDS = frozenset({
    "yaml-syntax", "duplicate-key", "invalid-type", "missing-key",
    "invalid-job-id", "invalid-needs", "needs-cycle",
    "invalid-uses", "unpinned-uses", "expression-syntax",
})

DEFAULT_IDS = CORRECTNESS_IDS | frozenset({
    "unknown-key", "invalid-event", "invalid-cron", "invalid-matrix",
    "invalid-permissions", "invalid-expression",
    "checkout-credentials", "excessive-permissions", "dangerous-trigger",
    "template-injection", "credential-exposure", "deprecated-command",
    "unapproved-pin",
})

STRICT_IDS = DEFAULT_IDS | frozenset({
    "suggest-permissions", "suggest-timeout", "missing-permissions",
})


@dataclass(frozen=True, slots=True)
class Finding:
    filepath: str
    line: int
    column: int
    id: str
    severity: str
    message: str
    fixable: bool


def _display(path: Path) -> str:
    text = str(path)
    if not os.path.isabs(text):
        return text
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            text=True, capture_output=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return text
    top = proc.stdout.strip()
    if not top:
        return text
    try:
        return os.path.relpath(text, top)
    except ValueError:
        return text


def _column(source: str, index: int) -> int:
    body, _ = pinning.split_line(source.splitlines(keepends=True)[index])
    body = body.removeprefix("\ufeff") if index == 0 else body
    match = KEY_COLUMN.match(body)
    if not match:
        return 1
    return len(match["prefix"]) + 1


def _profile_ids(profile: str) -> frozenset:
    if profile == "correctness":
        return CORRECTNESS_IDS
    if profile == "strict":
        return STRICT_IDS
    return DEFAULT_IDS


def _build_context(doc: SourceDocument) -> expr.Context:
    ctx = expr.Context()
    for root in doc.documents:
        if not isinstance(root, MappingNode):
            continue
        jobs = mapping_get(root, "jobs")
        if isinstance(jobs, MappingNode):
            for key, _ in jobs.value:
                if isinstance(key, ScalarNode):
                    ctx.job_ids.add(key.value)
            for key, val in jobs.value:
                if not isinstance(key, ScalarNode) or not isinstance(val, MappingNode):
                    continue
                jid = key.value
                needs = mapping_get(val, "needs")
                if isinstance(needs, ScalarNode) and needs.value:
                    ctx.needs_by_job[jid] = {needs.value}
                elif isinstance(needs, SequenceNode):
                    got = set()
                    for item in needs.value:
                        if isinstance(item, ScalarNode) and item.value:
                            got.add(item.value)
                    ctx.needs_by_job[jid] = got
                strategy = mapping_get(val, "strategy")
                if isinstance(strategy, MappingNode):
                    matrix = mapping_get(strategy, "matrix")
                    if isinstance(matrix, MappingNode):
                        keys = set()
                        for mkey, _ in matrix.value:
                            if isinstance(mkey, ScalarNode) and mkey.value not in ("include", "exclude"):
                                keys.add(mkey.value)
                        ctx.matrix_keys[jid] = keys
                steps = mapping_get(val, "steps")
                if isinstance(steps, SequenceNode):
                    ids = set()
                    for item in steps.value:
                        if isinstance(item, MappingNode):
                            sid = mapping_get(item, "id")
                            if isinstance(sid, ScalarNode) and sid.value:
                                ids.add(sid.value)
                    ctx.step_ids_by_job[jid] = ids
        on = mapping_get(root, "on")
        if isinstance(on, MappingNode):
            for ekey, eval_ in on.value:
                if isinstance(ekey, ScalarNode) and ekey.value in ("workflow_call", "workflow_dispatch"):
                    if isinstance(eval_, MappingNode):
                        inputs = mapping_get(eval_, "inputs")
                        if isinstance(inputs, MappingNode):
                            for ikey, _ in inputs.value:
                                if isinstance(ikey, ScalarNode):
                                    ctx.inputs.add(ikey.value)
    return ctx


def _collect_scalars(node: object, seen: set[int], out: list) -> None:
    if isinstance(node, MappingNode):
        if id(node) in seen:
            return
        seen.add(id(node))
        for _, value in node.value:
            _collect_scalars(value, seen, out)
    elif isinstance(node, SequenceNode):
        if id(node) in seen:
            return
        seen.add(id(node))
        for item in node.value:
            _collect_scalars(item, seen, out)
    elif isinstance(node, ScalarNode):
        out.append(node)


def _collect_scalars_with_location(node: object, seen: set[int], out: list, location: str = "") -> None:
    if isinstance(node, MappingNode):
        if id(node) in seen:
            return
        seen.add(id(node))
        for _, value in node.value:
            _collect_scalars_with_location(value, seen, out, location)
    elif isinstance(node, SequenceNode):
        if id(node) in seen:
            return
        seen.add(id(node))
        for item in node.value:
            _collect_scalars_with_location(item, seen, out, location)
    elif isinstance(node, ScalarNode):
        out.append((node, location))


def _expression_findings(doc: SourceDocument, ctx: expr.Context, profile: str) -> list[Finding]:
    out: list[Finding] = []
    located: list = []
    for root in doc.documents:
        if root is None or not isinstance(root, MappingNode):
            if root is not None:
                _collect_scalars_with_location(root, set(), located, "")
            continue
        jobs = mapping_get(root, "jobs")
        if isinstance(jobs, MappingNode):
            for key, val in jobs.value:
                if isinstance(key, ScalarNode) and isinstance(val, MappingNode):
                    _collect_scalars_with_location(val, set(), located, key.value)
            top_scalars: list = []
            for key, value in root.value:
                if isinstance(key, ScalarNode) and key.value == "jobs":
                    continue
                _collect_scalars_with_location(value, set(), top_scalars, "")
            located.extend(top_scalars)
        else:
            _collect_scalars_with_location(root, set(), located, "")
    for node, location in located:
        text = node.value
        if "${{" not in text:
            continue
        line = node.start_mark.line + 1
        col = node.start_mark.column + 1
        import dataclasses as _dc
        local_ctx = _dc.replace(ctx, location=location)
        found, scan_errors = expr.scan_interpolations(text, base_line=line)
        for err_line, err_col, msg in scan_errors:
            if "expression-syntax" not in _profile_ids(profile):
                continue
            out.append(Finding(doc.display, err_line, err_col,
                               "expression-syntax", "error", msg, False))
        for interp in found:
            status, msg = expr.analyze_expression(interp.inner, local_ctx)
            if status == "syntax-error":
                if "expression-syntax" not in _profile_ids(profile):
                    continue
                out.append(Finding(doc.display, line, col, "expression-syntax", "error",
                                   f"invalid expression ${{{{ {interp.inner.strip()} }}}}: {msg}", False))
            elif status == "semantic-error":
                if "invalid-expression" not in _profile_ids(profile):
                    continue
                out.append(Finding(doc.display, line, col, "invalid-expression", "error",
                                   f"invalid expression ${{{{ {interp.inner.strip()} }}}}: {msg}", False))
    return out


def _strict_suggestions(doc: SourceDocument, profile: str) -> list[Finding]:
    if profile != "strict":
        return []
    out: list[Finding] = []
    for root in doc.documents:
        if not isinstance(root, MappingNode):
            continue
        if doc.kind != "workflow":
            continue
        perms = mapping_get(root, "permissions")
        if perms is None:
            out.append(Finding(doc.display, 1, 1, "suggest-permissions", "warning",
                               "consider setting explicit 'permissions' for the workflow", False))
        jobs = mapping_get(root, "jobs")
        if isinstance(jobs, MappingNode):
            for key, val in jobs.value:
                if not isinstance(key, ScalarNode) or not isinstance(val, MappingNode):
                    continue
                line = key.start_mark.line + 1
                col = key.start_mark.column + 1
                if mapping_get(val, "permissions") is None and perms is None:
                    out.append(Finding(doc.display, line, col, "suggest-permissions", "warning",
                                       f"consider setting 'permissions' for job '{key.value}'", False))
                if mapping_get(val, "timeout-minutes") is None and mapping_get(val, "uses") is None:
                    out.append(Finding(doc.display, line, col, "suggest-timeout", "warning",
                                       f"consider setting 'timeout-minutes' for job '{key.value}'", False))
    return out


def _model_invalid_uses(doc: SourceDocument, profile: str) -> list[tuple[int, int, str]]:
    from pinact.pinning import NON_ACTION, parse_action
    out: list[tuple[int, int, str]] = []

    def walk(node: object, scoped: bool, flowing: bool, seen: set[int]) -> None:
        if isinstance(node, MappingNode):
            if id(node) in seen:
                return
            seen.add(id(node))
            nested = flowing or node.flow_style is True
            for key, value in node.value:
                name = key.value if isinstance(key, ScalarNode) else None
                if name == "uses" and isinstance(key, ScalarNode) and not scoped and not nested:
                    value_flow = getattr(value, "flow_style", None) is True
                    if value_flow:
                        out.append((key.start_mark.line + 1, key.start_mark.column + 1,
                                    "unsupported inline uses syntax"))
                    elif isinstance(value, ScalarNode) and value.style in ("|", ">"):
                        out.append((key.start_mark.line + 1, key.start_mark.column + 1,
                                    "unsupported block-scalar uses value"))
                    elif isinstance(value, ScalarNode):
                        try:
                            parse_action(value.value)
                        except Exception as exc:
                            out.append((key.start_mark.line + 1, key.start_mark.column + 1, str(exc)))
                    elif not isinstance(value, ScalarNode):
                        out.append((key.start_mark.line + 1, key.start_mark.column + 1,
                                    "unsupported uses value"))
                walk(value, scoped or name in NON_ACTION, nested, seen)
        elif isinstance(node, SequenceNode):
            if id(node) in seen:
                return
            seen.add(id(node))
            nested = flowing or node.flow_style is True
            for item in node.value:
                walk(item, scoped, nested, seen)

    for root in doc.documents:
        if root is not None:
            walk(root, False, False, set())
    return out


def lint_one_file(path: Path, profile: str, catalog: str | None = None) -> tuple[list[Finding], str | None]:
    display = _display(path)
    if path.is_symlink():
        return [], f"pinact: {path}: refusing to read a symlink"
    if not path.is_file():
        return [], f"pinact: {path}: cannot read file"
    doc, _ = parse_document(path, display)
    findings: list[Finding] = []
    if doc.syntax_error is not None:
        if "yaml-syntax" in _profile_ids(profile):
            findings.append(Finding(display, doc.syntax_error.line, doc.syntax_error.column,
                                    "yaml-syntax", "error",
                                    f"invalid YAML: {doc.syntax_error.message}", False))
        findings.sort(key=lambda item: (item.filepath, item.line, item.column, item.id, item.message))
        return findings, None
    for line, col, key in doc.duplicate_keys:
        if "duplicate-key" in _profile_ids(profile):
            findings.append(Finding(display, line, col, "duplicate-key", "error",
                                    f"duplicate key '{key}'", False))
    for root in doc.documents:
        if not isinstance(root, MappingNode):
            if root is not None and "invalid-type" in _profile_ids(profile):
                findings.append(Finding(display, 1, 1, "invalid-type", "error",
                                        "document root must be a mapping", False))
            continue
        if doc.kind == "action":
            for item in wf.check_top_level(doc, root, profile):
                if item[2] in _profile_ids(profile):
                    findings.append(Finding(display, *item))
            for item in wf.check_composite_steps(doc, root):
                if item[2] in _profile_ids(profile):
                    findings.append(Finding(display, *item))
        else:
            for item in wf.check_top_level(doc, root, profile):
                if item[2] in _profile_ids(profile):
                    findings.append(Finding(display, *item))
            for item in wf.check_events(doc, root):
                if item[2] in _profile_ids(profile):
                    findings.append(Finding(display, *item))
            top_perms = mapping_get(root, "permissions")
            if top_perms is not None:
                for item in wf.check_permissions_node(top_perms, "workflow"):
                    if item[2] in _profile_ids(profile):
                        findings.append(Finding(display, *item))
            for item in wf.check_jobs(doc, root, profile):
                if item[2] in _profile_ids(profile):
                    findings.append(Finding(display, *item))
    ctx = _build_context(doc)
    for item in _expression_findings(doc, ctx, profile):
        findings.append(item)
    for item in _strict_suggestions(doc, profile):
        findings.append(item)
    for root in doc.documents:
        if not isinstance(root, MappingNode):
            continue
        for check in (sec.check_checkout_credentials,
                      sec.check_permissions_security,
                      sec.check_dangerous_triggers,
                      sec.check_template_injection,
                      sec.check_credential_exposure,
                      sec.check_deprecated_commands):
            for item in check(doc, root):
                if item[2] in _profile_ids(profile):
                    findings.append(Finding(display, *item))
    uses: list = []
    source_text = doc.text
    try:
        _, uses = pinning.scan(path, refresh=False, include_pinned=catalog is not None)
        for use in uses:
            if UNPINNED_USES in _profile_ids(profile) and not pinning.SHA.fullmatch(use.ref):
                findings.append(Finding(display, use.index + 1, _column(source_text, use.index),
                                        UNPINNED_USES, "error",
                                        f"{use.repo}@{use.ref} is not pinned to an immutable commit SHA",
                                        True))
    except pinning.PinError as exc:
        detail = str(exc)
        match = FINDING_LINE.search(detail)
        if not match:
            model_invalid = _model_invalid_uses(doc, profile)
            if model_invalid:
                for line_no, col_no, msg in model_invalid:
                    if INVALID_USES in _profile_ids(profile):
                        findings.append(Finding(display, line_no, col_no, INVALID_USES, "error", msg, False))
            else:
                if INVALID_USES in _profile_ids(profile):
                    findings.append(Finding(display, 1, 1, INVALID_USES, "error", detail, False))
        elif INVALID_USES in _profile_ids(profile):
            findings.append(Finding(display, int(match[1]), 1, INVALID_USES, "error", detail, False))
    if catalog is not None:
        from pinact.catalog import CatalogError, catalog_approves_use, load_catalog
        try:
            entries = load_catalog(Path(catalog))
        except CatalogError as exc:
            return [], f"pinact: {exc}"
        if "unapproved-pin" in _profile_ids(profile):
            for use in uses:
                approved, note = catalog_approves_use(use, entries)
                if not approved:
                    findings.append(Finding(
                        display, use.index + 1, _column(source_text, use.index),
                        "unapproved-pin", "error",
                        f"{use.repo}@{use.ref} is not approved by the catalog: "
                        f"{note}", False))
    findings.sort(key=lambda item: (item.filepath, item.line, item.column, item.id, item.message))
    return findings, None


def lint_files(files: list[Path], profile: str = "default",
               select: list[str] | None = None,
               catalog: str | None = None) -> tuple[list[Finding], str | None]:
    try:
        targets = files or pinning.discover()
    except pinning.PinError as exc:
        return [], f"pinact: {exc}"
    findings: list[Finding] = []
    for path in targets:
        file_findings, error = lint_one_file(path, profile, catalog)
        if error is not None:
            if error.startswith("pinact: catalog"):
                return [], error
            match = FINDING_LINE.search(error)
            if not match:
                return [], error
            findings.extend(file_findings)
            continue
        findings.extend(file_findings)
    if select:
        wanted = set(select)
        findings = [f for f in findings if f.id in wanted]
    findings.sort(key=lambda item: (item.filepath, item.line, item.column, item.id, item.message))
    return findings, None


def render_json(findings: list[Finding]) -> str:
    return json.dumps([asdict(item) for item in findings], indent=2, sort_keys=True) + "\n"


def render_text(findings: list[Finding]) -> str:
    lines = [
        f"{item.filepath}:{item.line}:{item.column}: {item.id} [{item.severity}] {item.message}"
        for item in findings
    ]
    return "".join(line + "\n" for line in lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint GitHub Actions workflow files.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--profile", choices=("correctness", "default", "strict"), default="default")
    parser.add_argument("--select", default=None,
                        help="comma-separated rule IDs to report")
    parser.add_argument("--catalog", default=None, help="approved-pin catalog path (validation minimal in U2)")
    parser.add_argument("files", nargs="*", type=Path, help="YAML files (default: discover workflows and actions)")
    args = parser.parse_args(argv)
    select = [s.strip() for s in args.select.split(",") if s.strip()] if args.select else None
    findings, error = lint_files(args.files, profile=args.profile, select=select, catalog=args.catalog)
    if error is not None:
        print(error, file=sys.stderr)
        return 2
    if args.format == "json":
        sys.stdout.write(render_json(findings))
    else:
        sys.stdout.write(render_text(findings))
    return 1 if findings else 0
