from __future__ import annotations

import argparse
import difflib
import os
import re
import stat
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pinact import pinning
from pinact.model import SourceDocument, mapping_get
from pinact._vendor.yaml.nodes import MappingNode, ScalarNode


class FixError(Exception):
    pass


class EditRejected(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Edit:
    start: int
    end: int
    expected: bytes
    replacement: bytes
    rule: str


def apply_edits(source: bytes, edits: list[Edit]) -> bytes:
    ordered = sorted(edits, key=lambda e: (e.start, e.end))
    for item in ordered:
        if item.start < 0 or item.end > len(source) or item.start > item.end:
            raise EditRejected(f"out-of-span edit for {item.rule}")
    for prev, cur in zip(ordered, ordered[1:]):
        if cur.start < prev.end:
            raise EditRejected(f"overlapping edits for {cur.rule}")
    for item in ordered:
        if source[item.start:item.end] != item.expected:
            raise EditRejected(f"expected bytes mismatch for {item.rule}")
    parts: list[bytes] = []
    cursor = 0
    for item in ordered:
        parts.append(source[cursor:item.start])
        parts.append(item.replacement)
        cursor = item.end
    parts.append(source[cursor:])
    return b"".join(parts)


def _line_byte_offsets(source: bytes) -> list[int]:
    offsets = [0]
    for match in re.finditer(rb"\n", source):
        offsets.append(match.end())
    return offsets


OBSOLETE_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"""echo\s+(['"]?)::set-output\s+name=([^:]+)::(.*)\1\s*$"""),
     "output"),
    (re.compile(r"""echo\s+(['"]?)::save-state\s+name=([^:]+)::(.*)\1\s*$"""),
     "state"),
    (re.compile(r"""echo\s+(['"]?)::set-env\s+name=([^:]+)::(.*)\1\s*$"""),
     "env"),
    (re.compile(r"""echo\s+(['"]?)::add-path::(.*)\1\s*$"""), "path"),
)


def _obsolete_replacement(kind: str, match: re.Match[str]) -> str | None:
    def literal(value: str) -> bool:
        return not value or bool(re.fullmatch(r"[A-Za-z0-9_.:/@+-]+(?: [A-Za-z0-9_.:/@+-]+)*", value))

    if kind == "output":
        name, value = match.group(2), match.group(3)
        if (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", name)
                or value != value.strip() or not literal(value)):
            return None
        return f'echo "{name}={value}" >> "$GITHUB_OUTPUT"'
    if kind == "state":
        name, value = match.group(2), match.group(3)
        if (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", name)
                or value != value.strip() or not literal(value)):
            return None
        return f'echo "{name}={value}" >> "$GITHUB_STATE"'
    if kind == "env":
        name, value = match.group(2), match.group(3)
        if (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", name)
                or value != value.strip() or not literal(value)):
            return None
        return f'echo "{name}={value}" >> "$GITHUB_ENV"'
    if kind == "path":
        value = match.group(2)
        if value != value.strip() or not literal(value):
            return None
        return f'echo "{value}" >> "$GITHUB_PATH"'
    return None


def _parse_policy(items: list[str]) -> dict[str, str]:
    policy: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise FixError(f"invalid --policy {item!r}; want KEY=VALUE")
        key, _, value = item.partition("=")
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise FixError(f"invalid --policy {item!r}; want KEY=VALUE")
        if key in policy:
            raise FixError(f"duplicate --policy key {key!r}")
        policy[key] = value
    return policy


def _check_writable(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    component = absolute
    while component != component.parent:
        if component.is_symlink():
            raise FixError(f"pinact: {path}: refusing a symlink path")
        component = component.parent
    if not path.is_file():
        raise FixError(f"pinact: {path}: cannot read file")
    mode = path.stat().st_mode
    if not (mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)):
        raise FixError(f"pinact: {path}: file is read-only; refusing to fix")


def _has_alias(doc: SourceDocument) -> bool:
    text = doc.text
    return bool(re.search(r"(?m)^\s*\w.*&[\w-]+\s*$|<<\s*:\s*\*", text))


def plan_pin_edits(doc: SourceDocument, source: bytes,
                    entries: dict | None,
                    resolved: dict[tuple[str, str], str] | None) -> tuple[list[Edit], list[str]]:
    from pinact.pinning import SHA
    edits: list[Edit] = []
    notes: list[str] = []
    lines = source.splitlines(keepends=True)
    try:
        scanned, uses = pinning.scan(doc.path, refresh=False,
                                     include_pinned=entries is not None)
        if scanned.encode("utf-8") != source:
            raise EditRejected("workflow changed while planning pin edits")
    except pinning.PinError as exc:
        notes.append(str(exc))
        return [], notes
    line_starts = _line_byte_offsets(source)
    for use in uses:
        if entries is not None:
            from pinact.catalog import catalog_approves_use, catalog_pin_for_spec
            if pinning.SHA.fullmatch(use.ref):
                approved, note = catalog_approves_use(use, entries)
                if not approved:
                    notes.append(f"{doc.display}:{use.index + 1}: cannot approve "
                                 f"{use.spec}: {note}")
                continue
            name = use.spec.rsplit("@", 1)[0]
            parts = name.split("/")
            base = "/".join(parts[:2]) if len(parts) >= 2 else name
            sha, subpath, note = catalog_pin_for_spec(use.spec, entries)
            if sha is None:
                notes.append(f"{doc.display}:{use.index + 1}: cannot pin "
                             f"{use.repo}@{use.ref}: {note}")
                continue
            full_name = base + subpath
            annotation_ref = entries[use.repo.lower()].version
        elif resolved is not None and (use.repo, use.ref) in resolved:
            sha = resolved[use.repo, use.ref]
            full_name = use.spec.rsplit("@", 1)[0]
            note = "resolved via network"
            annotation_ref = use.ref
        else:
            notes.append(f"{doc.display}:{use.index + 1}: {use.repo}@{use.ref} "
                         "needs --pin (network) or --catalog; leaving unchanged")
            continue
        if SHA.fullmatch(use.ref):
            continue
        body = lines[use.index]
        from pinact.pinning import pin_comment
        annotation = pin_comment(use.comment, annotation_ref)
        separator = use.gap or (" " if annotation else "")
        start = line_starts[use.index]
        end = start + len(body.rstrip(b"\r\n"))
        expected = source[start:end]
        expect_text = expected.decode("utf-8")
        bom_prefix = ""
        if expect_text.startswith("\ufeff"):
            bom_prefix = "\ufeff"
            expect_text = expect_text[1:]
        new_line_text = (bom_prefix + use.prefix + use.quote + full_name + "@" + sha
                         + use.quote + separator + annotation)
        replacement = new_line_text.encode("utf-8")
        edits.append(Edit(start, end, expected, replacement, "unpinned-uses"))
    return edits, notes


def _run_shell(root: MappingNode, job: MappingNode | None,
               step: MappingNode) -> str | None:
    step_shell = mapping_get(step, "shell")
    if isinstance(step_shell, ScalarNode):
        return step_shell.value.strip().lower()
    for owner in (job, root):
        if owner is None:
            continue
        defaults = mapping_get(owner, "defaults")
        run_defaults = mapping_get(defaults, "run") if isinstance(defaults, MappingNode) else None
        shell = mapping_get(run_defaults, "shell") if isinstance(run_defaults, MappingNode) else None
        if isinstance(shell, ScalarNode):
            return shell.value.strip().lower()
    if job is not None:
        runner = mapping_get(job, "runs-on")
        if isinstance(runner, ScalarNode):
            name = runner.value.strip().lower()
            if name.startswith(("ubuntu-", "macos-")):
                return "bash"
            if name.startswith("windows-"):
                return "pwsh"
    return None


def plan_obsolete_edits(doc: SourceDocument, source: bytes) -> tuple[list[Edit], list[str]]:
    edits: list[Edit] = []
    notes: list[str] = []
    for root in doc.documents:
        if not isinstance(root, MappingNode):
            continue
        from pinact import security as sec
        scoped_steps: list[tuple[MappingNode | None, MappingNode]] = []
        if doc.kind == "action":
            scoped_steps.extend((None, step) for step in sec.all_steps(doc, root))
        else:
            for _, _, job in sec.iter_jobs(root):
                scoped_steps.extend((job, step) for step in sec.iter_steps(job))
        for job, step in scoped_steps:
            run = mapping_get(step, "run")
            if not isinstance(run, ScalarNode) or not run.value:
                continue
            markers = ("::set-output", "::save-state", "::set-env", "::add-path")
            if not any(marker in run.value for marker in markers):
                continue
            shell = _run_shell(root, job, step)
            if shell not in {"bash", "sh"}:
                notes.append(f"{doc.display}:{run.start_mark.line + 1}: obsolete-command "
                             f"rewrite refused for unknown or unsupported shell {shell!r}")
                continue
            if "\n" in run.value:
                notes.append(f"{doc.display}:{run.start_mark.line + 1}: multiline obsolete-command "
                             "rewrite refused; split into one command per line")
                continue
            for pattern, kind in OBSOLETE_REWRITES:
                match = pattern.search(run.value.strip())
                if not match:
                    continue
                new_cmd = _obsolete_replacement(kind, match)
                if new_cmd is None:
                    notes.append(f"{doc.display}:{run.start_mark.line + 1}: "
                                 "obsolete command has no known semantics here")
                    break
                line_no = run.start_mark.line + 1
                line_starts = _line_byte_offsets(source)
                start_line = line_starts[line_no - 1]
                end_line = source.find(b"\n", start_line)
                if end_line < 0:
                    end_line = len(source)
                line_bytes = source[start_line:end_line].rstrip(b"\r")
                old_bytes = match.group(0).encode("utf-8")
                at = line_bytes.find(old_bytes)
                if at < 0:
                    notes.append(f"{doc.display}:{line_no}: cannot anchor "
                                 "obsolete-command span; leaving unchanged")
                    break
                estart, eend = start_line + at, start_line + at + len(old_bytes)
                edits.append(Edit(estart, eend, old_bytes,
                                  new_cmd.encode("utf-8"), "deprecated-command"))
                break
    return edits, notes


def _job_indent(doc: SourceDocument, job: MappingNode) -> int | None:
    indents = set()
    for key, _ in job.value:
        if hasattr(key, "start_mark"):
            indents.add(key.start_mark.column)
    if len(indents) != 1:
        return None
    first = next(iter(job.value))[0]
    body_indent = first.start_mark.column
    return body_indent


def plan_policy_edits(doc: SourceDocument, source: bytes,
                       policy: dict[str, str]) -> tuple[list[Edit], list[str]]:
    edits: list[Edit] = []
    notes: list[str] = []
    if not policy:
        return edits, notes
    if _has_alias(doc):
        notes.append(f"{doc.display}: alias/anchor document; structural "
                     "insertions refused")
        return edits, notes
    perm_value = policy.get("permissions")
    timeout_value = policy.get("timeout-minutes", policy.get("timeout"))
    if perm_value is not None:
        low = perm_value.strip().lower()
        if "write" in low and low not in ("{}"):
            notes.append(f"{doc.display}: refusing privilege-adding "
                         f"permissions policy {perm_value!r}")
            perm_value = None
        elif low not in ("read-all", "{}"):
            match = re.fullmatch(
                r"([a-z][a-z0-9-]*)\s*:\s*(read|none)", perm_value.strip(), re.I)
            scopes = {
                "actions", "attestations", "checks", "contents", "deployments",
                "discussions", "id-token", "issues", "packages", "pages",
                "pull-requests", "repository-projects", "security-events", "statuses",
            }
            if match is None or match.group(1).lower() not in scopes:
                notes.append(f"{doc.display}: invalid permissions policy "
                             f"{perm_value!r}; want read-all, {{}}, or a known scope "
                             "with read/none")
                perm_value = None
    if timeout_value is not None:
        if not re.fullmatch(r"\d+", timeout_value.strip()) or not (
                1 <= int(timeout_value.strip()) <= 1440):
            notes.append(f"{doc.display}: invalid timeout policy "
                         f"{timeout_value!r}; want minutes 1..1440")
            timeout_value = None
    if perm_value is None and timeout_value is None:
        return edits, notes
    line_starts = _line_byte_offsets(source)
    newline = "\r\n" if b"\r\n" in source else "\n"
    for root in doc.documents:
        if not isinstance(root, MappingNode):
            continue
        if doc.kind == "action":
            continue
        top_perms = mapping_get(root, "permissions")
        if perm_value is not None and top_perms is None:
            jobs_line = None
            for key, _ in root.value:
                if isinstance(key, ScalarNode) and key.value == "jobs":
                    jobs_line = key.start_mark.line + 1
                    break
            if jobs_line is None:
                notes.append(f"{doc.display}: cannot anchor permissions insert")
            else:
                start = line_starts[jobs_line - 1]
                if ":" in perm_value:
                    scope, _, level = perm_value.partition(":")
                    block = (f"permissions:{newline}  {scope.strip()}: "
                             f"{level.strip()}{newline}")
                elif perm_value.strip() == "{}":
                    block = "permissions: {}" + newline
                else:
                    block = f"permissions: {perm_value.strip()}{newline}"
                edits.append(Edit(start, start, b"", block.encode(), "missing-permissions"))
        jobs = mapping_get(root, "jobs")
        if not isinstance(jobs, MappingNode):
            continue
        for key, job in jobs.value:
            if not isinstance(key, ScalarNode) or not isinstance(job, MappingNode):
                continue
            jid = key.value
            if timeout_value is not None:
                if mapping_get(job, "uses") is not None:
                    continue
                if mapping_get(job, "timeout-minutes") is None:
                    if not job.value:
                        continue
                    indent = _job_indent(doc, job)
                    if indent is None:
                        notes.append(f"{doc.display}: ambiguous indent in job "
                                     f"'{jid}'; skipping timeout insert")
                    else:
                        block = (" " * indent
                                 + f"timeout-minutes: {timeout_value.strip()}{newline}")
                        first_child_line = job.value[0][0].start_mark.line + 1
                        start = line_starts[first_child_line - 1]
                        edits.append(Edit(start, start, b"", block.encode(),
                                          "suggest-timeout"))
    return edits, notes


def fix_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Apply safe pinact fixes.")
    parser.add_argument("--diff", action="store_true",
                        help="print a diff without writing")
    parser.add_argument("--pin", action="store_true",
                        help="allow network (git ls-remote) for pin resolution")
    parser.add_argument("--catalog", default=None,
                        help="approved-pin catalog (TOML)")
    parser.add_argument("--policy", action="append", default=[],
                        help="explicit policy KEY=VALUE (permissions, timeout-minutes)")
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args(argv)
    try:
        policy = _parse_policy(list(args.policy))
    except FixError as exc:
        print(f"pinact: {exc}", file=sys.stderr)
        return 2
    entries: dict | None = None
    if args.catalog is not None:
        from pinact.catalog import CatalogError, load_catalog
        try:
            entries = load_catalog(Path(args.catalog))
        except CatalogError as exc:
            print(f"pinact: {exc}", file=sys.stderr)
            return 2
    try:
        files = list(args.files) if args.files else pinning.discover()
    except pinning.PinError as exc:
        print(f"pinact: {exc}", file=sys.stderr)
        return 2
    resolved: dict[tuple[str, str], str] | None = None
    if args.pin and entries is None:
        requested: dict[str, set[str]] = {}
        file_uses: dict[Path, tuple[bytes, list]] = {}
        for path in files:
            try:
                _check_writable(path)
                raw = path.read_bytes()
            except (OSError, FixError) as exc:
                print(f"pinact: {exc}", file=sys.stderr)
                return 2
            try:
                _, uses = pinning.scan(path, refresh=False)
            except pinning.PinError as exc:
                print(f"pinact: {exc}", file=sys.stderr)
                return 2
            file_uses[path] = (raw, uses)
            for use in uses:
                requested.setdefault(use.repo, set()).add(use.ref)
        if requested:
            try:
                resolved = pinning.resolve(requested, False)
            except pinning.PinError as exc:
                print(f"pinact: {exc}", file=sys.stderr)
                return 2
    pending_notes: list[str] = []
    total_edits = 0
    dirty = False
    for path in files:
        try:
            _check_writable(path)
        except FixError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        try:
            original = path.read_bytes()
        except OSError as exc:
            print(f"pinact: {path}: {exc}", file=sys.stderr)
            return 2
        try:
            text = original.decode("utf-8")
        except UnicodeError:
            print(f"pinact: {path}: not utf-8; refusing to fix", file=sys.stderr)
            return 2
        from pinact.model import parse_document
        from pinact.lint import _display
        doc, _ = parse_document(path, _display(path))
        if doc.text.encode("utf-8") != original:
            print(f"pinact: {path}: changed while planning; retry", file=sys.stderr)
            return 2
        if doc.syntax_error is not None:
            pending_notes.append(f"{doc.display}: syntax error; leaving unchanged")
            dirty = True
            continue
        try:
            pin_edits, pin_notes = plan_pin_edits(doc, original, entries, resolved)
            obs_edits, obs_notes = plan_obsolete_edits(doc, original)
            pol_edits, pol_notes = plan_policy_edits(doc, original, policy)
        except EditRejected as exc:
            print(f"pinact: {path}: {exc}", file=sys.stderr)
            return 2
        pending_notes.extend(pin_notes + obs_notes + pol_notes)
        edits = pin_edits + obs_edits + pol_edits
        if not edits:
            continue
        try:
            updated = apply_edits(original, edits)
        except EditRejected as exc:
            print(f"pinact: {path}: {exc}", file=sys.stderr)
            return 2
        if updated == original:
            continue
        tmpdir = Path(os.environ.get("TMPDIR", tempfile.gettempdir()))
        try:
            tmpdir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix=".pinact-fix-", suffix=".yml",
                                             dir=str(tmpdir), delete=False) as tmp:
                tmp.write(updated)
                tmppath = Path(tmp.name)
        except OSError as exc:
            print(f"pinact: {exc}", file=sys.stderr)
            return 2
        try:
            from pinact.lint import lint_one_file
            before_default, _ = lint_one_file(path, "default")
            after_default, _ = lint_one_file(tmppath, "default")
            targeted = {e.rule for e in edits}
            for rule in targeted:
                profile = "strict" if rule in {"missing-permissions", "suggest-timeout"} else "default"
                before, _ = lint_one_file(path, profile)
                after, _ = lint_one_file(tmppath, profile)
                n_before = sum(1 for f in before if f.id == rule or
                               (rule == "unpinned-uses" and f.id == rule) or
                               (rule == "missing-permissions" and f.id in (
                                   "missing-permissions", "suggest-permissions")) or
                               (rule == "suggest-timeout" and f.id in (
                                   "suggest-timeout",)))
                n_after = sum(1 for f in after if f.id == rule or
                              (rule == "missing-permissions" and f.id in (
                                  "missing-permissions", "suggest-permissions")) or
                              (rule == "suggest-timeout" and f.id in ("suggest-timeout",)))
                if n_after >= n_before:
                    print(f"pinact: {path}: fix for {rule} did not resolve; "
                          "leaving unchanged", file=sys.stderr)
                    dirty = True
                    break
            else:
                from pinact.lint import CORRECTNESS_IDS
                correct_before = Counter(
                    (f.id, f.severity, f.message) for f in before_default
                    if f.id in CORRECTNESS_IDS)
                correct_after = Counter(
                    (f.id, f.severity, f.message) for f in after_default
                    if f.id in CORRECTNESS_IDS)
                if any(count > correct_before[finding]
                       for finding, count in correct_after.items()):
                    print(f"pinact: {path}: fix introduces new correctness "
                          "errors; leaving unchanged", file=sys.stderr)
                    dirty = True
                    continue
                from pinact.model import parse_document as _parse
                redoc, _ = _parse(tmppath, str(tmppath))
                re_pin, _n1 = plan_pin_edits(redoc, updated, entries, resolved)
                re_obs, _n2 = plan_obsolete_edits(redoc, updated)
                re_pol, _n3 = plan_policy_edits(redoc, updated, policy)
                if re_pin or re_obs or re_pol:
                    print(f"pinact: {path}: fix is not idempotent; "
                          "leaving unchanged", file=sys.stderr)
                    dirty = True
                    continue
                total_edits += len(edits)
                if args.diff:
                    old_lines = original.decode("utf-8", "replace").splitlines()
                    new_lines = updated.decode("utf-8", "replace").splitlines()
                    for line in difflib.unified_diff(
                            old_lines, new_lines,
                            fromfile=f"a/{path}", tofile=f"b/{path}",
                            lineterm=""):
                        print(line)
                    dirty = True
                    continue
                try:
                    _check_writable(path)
                    if path.read_bytes() != original:
                        print(f"pinact: {path}: changed while fixing; retry",
                              file=sys.stderr)
                        dirty = True
                        continue
                    pinning.write_file(path, text, updated.decode("utf-8"))
                except (OSError, pinning.PinError) as exc:
                    print(f"pinact: {exc}", file=sys.stderr)
                    return 2
                continue
        finally:
            try:
                tmppath.unlink()
            except OSError:
                pass
    for note in pending_notes:
        print(f"pinact: {note}", file=sys.stderr)
    if args.diff:
        return 1 if (total_edits or dirty or pending_notes) else 0
    if pending_notes or dirty:
        return 1
    return 0 if total_edits else 0
