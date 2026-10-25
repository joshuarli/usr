"""High-confidence security rules for GitHub Actions workflows.

Trust model: every finding names why it is high confidence and what is
deliberately left out to avoid false positives. All rules are offline,
AST-backed, and reuse the U3 expression tree for sources and sinks.

Rules (all default-profile except missing-permissions which is strict-only
to preserve the R0 13/13 correctness probe):

- ``checkout-credentials`` (warning, default): explicit
  ``with: persist-credentials: true`` on ``actions/checkout``. Missing keys
  are NOT flagged: the upstream default is true, and flagging every
  checkout without the key would punish valid repos. Autofix only under
  explicit policy (see fixes).
- ``excessive-permissions`` (error, default): provably broad
  ``permissions: write-all`` at workflow or job level. Per-scope ``write``
  alone is NOT flagged: many legitimate releases need ``contents: write``.
  ``permissions: {}`` (empty mapping), ``read-all``, and ``read``/``none``
  values are explicit-safe, never flagged.
- ``missing-permissions`` (warning, strict only): neither workflow nor job
  sets ``permissions``. Strict-only so default stays near-zero-FP on repos
  that rely on org defaults. ``permissions: {}`` counts as set.
- ``dangerous-trigger`` (error, default): high-risk trigger
  (``pull_request_target``, ``workflow_run``, ``issue_comment``,
  ``workflow_dispatch``) PLUS untrusted-execution context: a checkout step
  AND (write-ish permissions OR a ``run:`` interpolation). A bare trigger
  with read-only permissions and no checkout/interpolation is safe and
  never flagged.
- ``template-injection`` (error, default, report only): known-untrusted
  contexts (PR title/body, issue title/body, comment/review bodies,
  ``github.head_ref``/``github.ref`` attacker refs, head-commit messages)
  interpolated into a ``run:`` sink. Shell quoting does NOT sanitize:
  interpolation happens before the shell runs, so quoted sinks are still
  flagged. ``env:``-mediated indirection (``env: BODY: ${{ ... }}`` plus
  ``run: echo "$BODY"``) is lookalike-safe and never flagged. Dynamic
  ``fromJSON``/unknown roots are unknown, never flagged. No autofix.
- ``credential-exposure`` (error, default, report only): direct ``secrets.*``
  dumps (``toJSON(secrets)``), ``echo``/``printf`` of a secret in ``run:``,
  secret interpolation written to ``$GITHUB_OUTPUT``/``$GITHUB_ENV`` etc.,
  and hard-coded credential literals under ``with:`` (``password``,
  ``token``, ``secret`` and hyphen/underscore variants) with a plain
  literal value. ``token: ${{ secrets.X }}`` and empty values are safe.
  No naive ``token`` substring matching: the key name must be an exact
  credential name and the value a literal.

Second-priority items deliberately left out (no proven FP-free context):
cache-poisoning/artipacked audits, OIDC/``id-token`` hardening beyond
``write-all``, branch-protection/CODEOWNERS checks, Dependabot/container
provenance, ``workflow_call`` secret inheritance, runner-label trust,
full shell-taint beyond ``run:`` interpolation. See README limits.
"""

from __future__ import annotations

import re

from pinact._vendor.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from pinact.model import SourceDocument, mapping_get
from pinact import expressions as expr
from pinact import pinning

CHECKOUT_CREDENTIALS = "checkout-credentials"
EXCESSIVE_PERMISSIONS = "excessive-permissions"
MISSING_PERMISSIONS = "missing-permissions"
DANGEROUS_TRIGGER = "dangerous-trigger"
TEMPLATE_INJECTION = "template-injection"
CREDENTIAL_EXPOSURE = "credential-exposure"
DEPRECATED_COMMAND = "deprecated-command"

HIGH_RISK_TRIGGERS = frozenset({
    "pull_request_target", "workflow_run", "issue_comment", "workflow_dispatch",
})

UNTRUSTED_PREFIXES = (
    "github.event.pull_request.title",
    "github.event.pull_request.body",
    "github.event.issue.title",
    "github.event.issue.body",
    "github.event.comment.body",
    "github.event.review.body",
    "github.event.review_comment.body",
    "github.event.discussion.body",
    "github.event.head_commit.message",
    "github.event.head_commit.author.name",
    "github.event.head_commit.author.email",
    "github.event.commits",
    "github.event.pull_request.head.ref",
    "github.event.pull_request.head.label",
    "github.head_ref",
    "github.ref",
    "github.event.pull_request.head.sha",
)

SAFE_UNTRUSTED_EXACT = frozenset({
    "github.event.pull_request.number",
    "github.event.issue.number",
    "github.event.pull_request.base.sha",
    "github.sha",
    "github.run_id",
    "github.run_number",
})

CREDENTIAL_KEYS = frozenset({
    "password", "passwd", "token", "secret", "api-key", "api_key",
    "client-secret", "client_secret",
})

PLACEHOLDER_VALUES = frozenset({
    "", "***", "xxx", "placeholder", "example", "changeme", "redacted",
})

WRITE_ALL = "write-all"


def _line_col(node) -> tuple[int, int]:
    return node.start_mark.line + 1, node.start_mark.column + 1


def _scalar_str(node: object) -> str | None:
    if isinstance(node, ScalarNode):
        return node.value
    return None


def _is_truthy_str(value: str | None) -> bool:
    return value is not None and value.strip().lower() == "true"


def _is_falsy_str(value: str | None) -> bool:
    return value is not None and value.strip().lower() == "false"


def workflow_triggers(root: MappingNode) -> set[str]:
    on = mapping_get(root, "on")
    if on is None:
        return set()
    if isinstance(on, ScalarNode):
        return {on.value.strip()} if on.value.strip() else set()
    if isinstance(on, SequenceNode):
        out = set()
        for item in on.value:
            if isinstance(item, ScalarNode) and item.value.strip():
                out.add(item.value.strip())
        return out
    if isinstance(on, MappingNode):
        out = set()
        for key, _ in on.value:
            if isinstance(key, ScalarNode):
                out.add(key.value)
        return out
    return set()


def iter_jobs(root: MappingNode):
    jobs = mapping_get(root, "jobs")
    if not isinstance(jobs, MappingNode):
        return
    for key, val in jobs.value:
        if isinstance(key, ScalarNode) and isinstance(val, MappingNode):
            yield key.value, key, val


def iter_steps(job: MappingNode):
    steps = mapping_get(job, "steps")
    if not isinstance(steps, SequenceNode):
        return
    for item in steps.value:
        if isinstance(item, MappingNode):
            yield item


def step_uses_repo(step: MappingNode) -> str | None:
    uses = mapping_get(step, "uses")
    if not isinstance(uses, ScalarNode) or not uses.value:
        return None
    text = uses.value.strip()
    if "${{" in text:
        return None
    try:
        parsed = pinning.parse_action(text)
    except Exception:
        return None
    if parsed is None:
        return None
    return parsed[0]


def has_checkout(doc_steps: list) -> bool:
    for step in doc_steps:
        if step_uses_repo(step) == "actions/checkout":
            return True
    return False


def all_steps(doc: SourceDocument, root: MappingNode) -> list:
    out: list = []
    if doc.kind == "action":
        runs = mapping_get(root, "runs")
        if isinstance(runs, MappingNode):
            steps = mapping_get(runs, "steps")
            if isinstance(steps, SequenceNode):
                for item in steps.value:
                    if isinstance(item, MappingNode):
                        out.append(item)
        return out
    for _, _, job in iter_jobs(root):
        out.extend(list(iter_steps(job)))
    return out


def _perm_is_write_all(node: object) -> bool:
    return isinstance(node, ScalarNode) and node.value.strip() == WRITE_ALL


def _perm_is_set(node: object | None) -> bool:
    if node is None:
        return False
    if isinstance(node, MappingNode):
        return True
    if isinstance(node, ScalarNode):
        text = node.value.strip()
        if text == "{}":
            return True
        if "${{" in text:
            return True
        return text != ""
    return True


def _perm_has_write(node: object | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ScalarNode):
        text = node.value.strip()
        if text == WRITE_ALL:
            return True
        if "${{" in text:
            return False
        return False
    if isinstance(node, MappingNode):
        for _, value in node.value:
            if isinstance(value, ScalarNode) and value.value.strip() == "write":
                return True
        return False
    return False


def check_checkout_credentials(doc: SourceDocument, root: MappingNode) -> list[tuple]:
    out = []
    for step in all_steps(doc, root):
        if step_uses_repo(step) != "actions/checkout":
            continue
        with_node = mapping_get(step, "with")
        if not isinstance(with_node, MappingNode):
            continue
        persist = mapping_get(with_node, "persist-credentials")
        if persist is None:
            continue
        text = _scalar_str(persist)
        if text is None:
            continue
        if _is_truthy_str(text):
            line, col = _line_col(persist)
            out.append((line, col, CHECKOUT_CREDENTIALS, "warning",
                        "actions/checkout keeps GITHUB_TOKEN available to later job commands; "
                        "set 'persist-credentials: false' unless later steps need git access "
                        "(fix only under explicit policy)", False))
    return out


def check_permissions_security(doc: SourceDocument, root: MappingNode) -> list[tuple]:
    out = []
    if doc.kind == "action":
        return out
    top = mapping_get(root, "permissions")
    if _perm_is_write_all(top):
        line, col = _line_col(top)
        out.append((line, col, EXCESSIVE_PERMISSIONS, "error",
                    "workflow 'permissions: write-all' is provably excessive; "
                    "scope each job to the minimum (e.g. 'contents: read')", False))
    for jid, _, job in iter_jobs(root):
        node = mapping_get(job, "permissions")
        if _perm_is_write_all(node):
            line, col = _line_col(node)
            out.append((line, col, EXCESSIVE_PERMISSIONS, "error",
                        f"job '{jid}' has 'permissions: write-all', provably excessive; "
                        "scope to the minimum needed", False))
    if top is None or (isinstance(top, ScalarNode) and top.value.strip() == ""):
        line, col = (1, 1)
        out.append((line, col, MISSING_PERMISSIONS, "warning",
                    "workflow sets no 'permissions'; pin an explicit minimum "
                    "(e.g. 'permissions: {}' or 'contents: read')", False))
        for jid, jkey, job in iter_jobs(root):
            node = mapping_get(job, "permissions")
            if not _perm_is_set(node):
                line, col = _line_col(jkey)
                out.append((line, col, MISSING_PERMISSIONS, "warning",
                            f"job '{jid}' sets no 'permissions' and the workflow sets none; "
                            "pin an explicit minimum", False))
    return out


def _run_interpolations(run_text: str) -> list[str]:
    found, _ = expr.scan_interpolations(run_text)
    return [item.inner for item in found]


def _shell_commands(run_text: str) -> list[str]:
    commands: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(run_text):
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote is not None:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char in ";&|\n":
            commands.append(run_text[start:index])
            start = index + 1
    commands.append(run_text[start:])
    return commands


def _chains_in_node(node: expr.Node) -> list[str]:
    out: list[str] = []

    def visit(current: expr.Node) -> None:
        if current.kind in ("prop", "index", "deref"):
            chain = expr._prop_chain(current)
            dotted = ".".join(part for part in chain if part not in ("<index>", "*"))
            out.append(dotted)
        for child in current.children:
            visit(child)

    visit(node)
    return out


def _inner_is_untrusted(inner: str) -> str | None:
    node, err = expr.parse_expression(inner)
    if err is not None or node is None:
        return None
    if _expression_returns_boolean(node):
        return None
    for chain in _chains_in_node(node):
        low = chain.lower()
        if low in SAFE_UNTRUSTED_EXACT:
            continue
        for prefix in UNTRUSTED_PREFIXES:
            if low == prefix or low.startswith(prefix + ".") or low.startswith(prefix + "["):
                return chain
            if prefix == "github.event.commits" and low.startswith("github.event.commits"):
                return chain
    return None


def _expression_returns_boolean(node: expr.Node) -> bool:
    return node.kind in {"cmp", "not"} or (
        node.kind == "call" and node.value.lower() in {
            "contains", "startswith", "endswith", "success", "failure",
            "cancelled", "always"}
    )


def _inner_uses_secrets(inner: str) -> bool:
    node, err = expr.parse_expression(inner)
    if err is not None or node is None:
        return False
    if _expression_returns_boolean(node):
        return False
    for chain in _chains_in_node(node):
        low = chain.lower()
        if low == "secrets" or low.startswith("secrets."):
            return True
    return False


def _inner_dumps_secrets(inner: str) -> bool:
    node, err = expr.parse_expression(inner)
    if err is not None or node is None:
        return False
    if _expression_returns_boolean(node):
        return False

    def visit(current: expr.Node) -> bool:
        if current.kind == "call" and current.value.lower() == "tojson":
            for child in current.children:
                for chain in _expression_chains(child):
                    low = chain.lower()
                    if low == "secrets" or low.startswith("secrets."):
                        return True
        return any(visit(child) for child in current.children)

    return visit(node)


def _expression_chains(node: expr.Node) -> list[str]:
    chains = []
    if node.kind in ("prop", "index", "deref"):
        chains.append(".".join(
            part for part in expr._prop_chain(node) if part not in ("<index>", "*")))
    elif node.kind == "ident":
        chains.append(node.value)
    for child in node.children:
        chains.extend(_expression_chains(child))
    return chains


def check_template_injection(doc: SourceDocument, root: MappingNode) -> list[tuple]:
    out = []
    for step in all_steps(doc, root):
        run = mapping_get(step, "run")
        if not isinstance(run, ScalarNode) or not run.value:
            continue
        inners = _run_interpolations(run.value)
        if not inners:
            continue
        for inner in inners:
            hit = _inner_is_untrusted(inner)
            if hit is None:
                continue
            line, col = _line_col(run)
            out.append((line, col, TEMPLATE_INJECTION, "error",
                        f"untrusted context '{hit}' flows into 'run:'; interpolation runs "
                        "before the shell so quoting does not sanitize (report only; "
                        "reroute through 'env:' instead)", False))
            break
    return out


def check_credential_exposure(doc: SourceDocument, root: MappingNode) -> list[tuple]:
    out = []
    for step in all_steps(doc, root):
        run = mapping_get(step, "run")
        if isinstance(run, ScalarNode) and run.value and "${{" in run.value:
            inners = _run_interpolations(run.value)
            dumps = any(_inner_dumps_secrets(i) for i in inners)
            if dumps:
                line, col = _line_col(run)
                out.append((line, col, CREDENTIAL_EXPOSURE, "error",
                            "run: dumps secrets via toJSON(secrets); never serialize the "
                            "whole secrets context (report only)", False))
                continue
            exposes = False
            writes_output = False
            for command in _shell_commands(run.value):
                if not any(_inner_uses_secrets(inner)
                           for inner in _run_interpolations(command)):
                    continue
                lowered_command = command.lower()
                stdout_command = re.match(r"\s*(?:command\s+)?(?:echo|printf|print)\b",
                                          lowered_command) is not None
                output_file = re.search(
                    r">+\s*[\"']?\$github_(?:output|env|state|path)\b",
                    lowered_command) is not None
                legacy_output = "::set-output" in lowered_command or "::set-env" in lowered_command
                exposes |= stdout_command or legacy_output
                writes_output |= output_file or legacy_output
            if exposes or writes_output:
                line, col = _line_col(run)
                why = ("writes a secret to a workflow command file"
                       if writes_output else "echoes a secret to logs")
                out.append((line, col, CREDENTIAL_EXPOSURE, "error",
                            f"run: {why}; pass secrets via 'env:' without printing "
                            "them (report only)", False))
        with_node = mapping_get(step, "with")
        if isinstance(with_node, MappingNode):
            for key, value in with_node.value:
                if not isinstance(key, ScalarNode):
                    continue
                norm = key.value.strip().lower().replace("_", "-")
                if norm not in CREDENTIAL_KEYS:
                    continue
                if not isinstance(value, ScalarNode):
                    continue
                text = value.value
                if "${{" in text:
                    continue
                if text.strip().lower() in PLACEHOLDER_VALUES:
                    continue
                if len(text.strip()) < 4:
                    continue
                line, col = _line_col(value)
                out.append((line, col, CREDENTIAL_EXPOSURE, "error",
                            f"'with: {key.value}:' looks like a hard-coded credential; "
                            "read it from '${{ secrets.* }}' instead (report only)", False))
    return out


def check_dangerous_triggers(doc: SourceDocument, root: MappingNode) -> list[tuple]:
    out = []
    if doc.kind == "action":
        return out
    triggers = workflow_triggers(root)
    risky = triggers & HIGH_RISK_TRIGGERS
    if not risky:
        return out
    top = mapping_get(root, "permissions")
    exposed_jobs: list[tuple[str, bool, bool]] = []
    for jid, _, job in iter_jobs(root):
        steps = list(iter_steps(job))
        checkout = has_checkout(steps)
        permissions = mapping_get(job, "permissions")
        write = _perm_has_write(top if permissions is None else permissions)
        untrusted_run = any(
            isinstance(run, ScalarNode)
            and any(_inner_is_untrusted(inner) for inner in _run_interpolations(run.value))
            for step in steps
            for run in [mapping_get(step, "run")]
        )
        if checkout and (write or untrusted_run):
            exposed_jobs.append((jid, write, untrusted_run))
    if not exposed_jobs:
        return out
    on_node = None
    for key, _ in root.value:
        if isinstance(key, ScalarNode) and key.value == "on":
            on_node = key
            break
    line, col = _line_col(on_node) if on_node is not None else (1, 1)
    names = ", ".join(sorted(risky))
    contexts = sorted({
        "+".join(value for value, enabled in (
            ("write permissions", write), ("untrusted run interpolation", untrusted_run)
        ) if enabled)
        for _, write, untrusted_run in exposed_jobs
    })
    jobs = ", ".join(jid for jid, _, _ in exposed_jobs)
    out.append((line, col, DANGEROUS_TRIGGER, "error",
                f"high-risk trigger ({names}) exposes job(s) {jobs} with "
                f"{'; '.join(contexts)} and checkout; review trust and permissions "
                "(report only)", False))
    return out


def check_deprecated_commands(doc: SourceDocument, root: MappingNode) -> list[tuple]:
    out = []
    markers = ("::set-output", "::save-state", "::set-env", "::add-path")
    for step in all_steps(doc, root):
        run = mapping_get(step, "run")
        if not isinstance(run, ScalarNode) or not run.value:
            continue
        if any(marker in run.value for marker in markers):
            line, col = _line_col(run)
            out.append((line, col, DEPRECATED_COMMAND, "error",
                        "run: uses a removed workflow command (::set-output/::save-state/"
                        "::set-env/::add-path); use $GITHUB_OUTPUT/$GITHUB_ENV/"
                        "$GITHUB_PATH instead (single-line rewrites are fixable)", True))
    return out
