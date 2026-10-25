"""Security rule regression tests (U4 first priority only).

Run with an isolated interpreter::

    python3 -I tools/pinact/tests/test_security.py

Each rule has vulnerable / safe / lookalike-safe / unknown-dynamic /
multi-job / privilege-scoped cases plus explicit negatives. Second-priority
items (cache-poisoning, OIDC hardening, branch protection, runner trust,
full shell taint) ship no rules; see README limits.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SRC = HERE.parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinact import lint as L  # noqa: E402


def lint_text(content: str, profile: str = "default", filename: str = "w.yml",
              select: list[str] | None = None):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / filename
        path.write_text(content, encoding="utf-8", newline="")
        findings, error = L.lint_files([path], profile=profile, select=select)
        by_id: dict[str, list] = {}
        for item in findings:
            by_id.setdefault(item.id, []).append(item)
        return findings, error, by_id


JOB = """on: push
permissions: {top}
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
{steps}
"""


def jobbody(top: str, steps: str) -> str:
    indented = "\n".join("      " + line if line.strip() else line
                         for line in steps.splitlines())
    return JOB.format(top=top, steps=indented)


class CheckoutCredentialsTests(unittest.TestCase):
    VULN = jobbody("{}", "      - uses: actions/checkout@v4\n"
                         "        with:\n          persist-credentials: true\n")

    def test_explicit_true_reported(self) -> None:
        _, _, by_id = lint_text(self.VULN)
        self.assertIn("checkout-credentials", by_id)

    def test_missing_key_is_safe(self) -> None:
        content = jobbody("{}", "      - uses: actions/checkout@v4\n")
        _, _, by_id = lint_text(content)
        self.assertNotIn("checkout-credentials", by_id)

    def test_explicit_false_is_safe(self) -> None:
        content = jobbody("{}", "      - uses: actions/checkout@v4\n"
                                "        with:\n          persist-credentials: false\n")
        _, _, by_id = lint_text(content)
        self.assertNotIn("checkout-credentials", by_id)

    def test_other_action_with_key_is_safe(self) -> None:
        content = jobbody("{}", "      - uses: actions/setup-node@v4\n"
                                "        with:\n          persist-credentials: true\n")
        _, _, by_id = lint_text(content)
        self.assertNotIn("checkout-credentials", by_id)

    def test_non_checkout_dynamic_uses_is_safe(self) -> None:
        content = jobbody("{}", "      - uses: ${{ inputs.action }}\n"
                                "        with:\n          persist-credentials: true\n")
        _, _, by_id = lint_text(content, select=["checkout-credentials"])
        self.assertNotIn("checkout-credentials", by_id)

    def test_multi_job_only_bad_flagged(self) -> None:
        content = (
            "on: push\npermissions: {}\n"
            "jobs:\n"
            "  good:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n"
            "    steps:\n      - uses: actions/checkout@v4\n"
            "        with:\n          persist-credentials: false\n"
            "  bad:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n"
            "    steps:\n      - uses: actions/checkout@v4\n"
            "        with:\n          persist-credentials: true\n"
        )
        _, _, by_id = lint_text(content)
        self.assertEqual(len(by_id.get("checkout-credentials", [])), 1)

    def test_composite_action_steps_covered(self) -> None:
        content = ("name: hi\ndescription: hi\nruns:\n  using: composite\n  steps:\n"
                   "    - uses: actions/checkout@v4\n"
                   "      with:\n        persist-credentials: true\n")
        _, _, by_id = lint_text(content, filename="action.yml")
        self.assertIn("checkout-credentials", by_id)


class PermissionsTests(unittest.TestCase):
    def test_workflow_write_all_excessive(self) -> None:
        _, _, by_id = lint_text(jobbody("write-all", "      - run: echo hi\n"))
        self.assertIn("excessive-permissions", by_id)

    def test_job_write_all_excessive(self) -> None:
        content = ("on: push\npermissions: {}\njobs:\n  build:\n"
                   "    runs-on: ubuntu-latest\n    permissions: write-all\n"
                   "    steps:\n      - run: echo hi\n")
        _, _, by_id = lint_text(content)
        self.assertIn("excessive-permissions", by_id)

    def test_all_scopes_and_scalar_forms_handled(self) -> None:
        for top in ("read-all", "{}", "contents: read"):
            with self.subTest(top=top):
                _, _, by_id = lint_text(
                    jobbody(top, "      - run: echo hi\n"), select=["excessive-permissions"])
                self.assertNotIn("excessive-permissions", by_id)
        mapping = "permissions:\n  contents: read\n  pull-requests: read\n"
        content = ("on: push\n" + mapping + "jobs:\n  build:\n"
                   "    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
        _, _, by_id = lint_text(content, select=["excessive-permissions"])
        self.assertNotIn("excessive-permissions", by_id)

    def test_single_write_scope_is_lookalike_safe(self) -> None:
        content = ("on: push\npermissions:\n  contents: write\njobs:\n  build:\n"
                   "    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
        _, _, by_id = lint_text(content, select=["excessive-permissions"])
        self.assertNotIn("excessive-permissions", by_id)

    def test_dynamic_permissions_unknown(self) -> None:
        content = ("on: push\npermissions: ${{ inputs.perms }}\njobs:\n  build:\n"
                   "    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
        _, _, by_id = lint_text(content, select=["excessive-permissions",
                                                 "missing-permissions"])
        self.assertNotIn("excessive-permissions", by_id)

    def test_multi_job_privilege_scoped(self) -> None:
        content = ("on: push\npermissions: write-all\njobs:\n"
                   "  broad:\n    runs-on: ubuntu-latest\n"
                   "    steps:\n      - run: echo hi\n"
                   "  narrow:\n    runs-on: ubuntu-latest\n    permissions:\n"
                   "      contents: read\n    steps:\n      - run: echo hi\n")
        _, _, by_id = lint_text(content)
        self.assertIn("excessive-permissions", by_id)
        self.assertEqual(len(by_id.get("excessive-permissions", [])), 1)

    def test_missing_strict_only(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    steps:\n      - run: echo hi\n")
        _, _, by_default = lint_text(content)
        self.assertNotIn("missing-permissions", by_default)
        self.assertNotIn("excessive-permissions", by_default)
        _, _, by_strict = lint_text(content, profile="strict")
        self.assertIn("missing-permissions", by_strict)

    def test_empty_mapping_counts_as_set(self) -> None:
        _, _, by_id = lint_text(jobbody("{}", "      - run: echo hi\n"),
                                profile="strict",
                                select=["missing-permissions"])
        self.assertNotIn("missing-permissions", by_id)


class DangerousTriggerTests(unittest.TestCase):
    VULN = ("on:\n  pull_request_target:\npermissions: {}\n"
            "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
            "    permissions:\n      contents: write\n"
            "    steps:\n      - uses: actions/checkout@v4\n"
            "      - run: echo ${{ github.event.pull_request.title }}\n")

    SAFE_BARE = ("on:\n  pull_request_target:\npermissions:\n  contents: read\n"
                 "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
                 "    steps:\n      - run: echo hi\n")

    def test_vulnerable_combo_reported(self) -> None:
        _, _, by_id = lint_text(self.VULN)
        self.assertIn("dangerous-trigger", by_id)

    def test_bare_trigger_never_flagged(self) -> None:
        _, _, by_id = lint_text(self.SAFE_BARE)
        self.assertNotIn("dangerous-trigger", by_id)

    def test_trigger_without_checkout_is_safe(self) -> None:
        content = ("on:\n  issue_comment:\npermissions:\n  contents: write\n"
                   "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    steps:\n      - run: echo hi\n")
        _, _, by_id = lint_text(content)
        self.assertNotIn("dangerous-trigger", by_id)

    def test_push_with_same_context_is_safe(self) -> None:
        content = self.VULN.replace("pull_request_target", "push", 1)
        _, _, by_id = lint_text(content, select=["dangerous-trigger"])
        self.assertNotIn("dangerous-trigger", by_id)

    def test_workflow_run_with_checkout_and_execution(self) -> None:
        content = self.VULN.replace("pull_request_target", "workflow_run", 1)
        _, _, by_id = lint_text(content)
        self.assertIn("dangerous-trigger", by_id)

    def test_workflow_dispatch_readonly_no_checkout_safe(self) -> None:
        content = ("on:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
                   "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    steps:\n      - run: echo hi\n")
        _, _, by_id = lint_text(content)
        self.assertNotIn("dangerous-trigger", by_id)

    def test_static_interpolation_and_cross_job_privileges_are_safe(self) -> None:
        content = ("on:\n  pull_request_target:\npermissions: {}\njobs:\n"
                   "  build:\n    runs-on: ubuntu-latest\n    steps:\n"
                   "      - uses: actions/checkout@v4\n"
                   "      - run: echo ${{ github.workflow }}\n"
                   "  publish:\n    runs-on: ubuntu-latest\n"
                   "    permissions:\n      contents: write\n"
                   "    steps:\n      - run: echo release\n")
        _, _, by_id = lint_text(content, select=["dangerous-trigger"])
        self.assertNotIn("dangerous-trigger", by_id)

    def test_job_permissions_override_workflow_permissions(self) -> None:
        content = ("on:\n  pull_request_target:\npermissions: write-all\njobs:\n"
                   "  build:\n    runs-on: ubuntu-latest\n    permissions: {}\n"
                   "    steps:\n      - uses: actions/checkout@v4\n"
                   "      - run: echo safe\n")
        _, _, by_id = lint_text(content, select=["dangerous-trigger"])
        self.assertNotIn("dangerous-trigger", by_id)

    def test_correctness_profile_untouched(self) -> None:
        _, _, by_id = lint_text(self.VULN, profile="correctness")
        self.assertNotIn("dangerous-trigger", by_id)
        self.assertIn("unpinned-uses", by_id)


class TemplateInjectionTests(unittest.TestCase):
    def test_pr_body_vulnerable(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo ${{ github.event.pull_request.body }}\n"))
        self.assertIn("template-injection", by_id)

    def test_issue_title_and_comment_body(self) -> None:
        for src in ("github.event.issue.title", "github.event.comment.body",
                    "github.head_ref", "github.ref",
                    "github.event.head_commit.message"):
            with self.subTest(src=src):
                _, _, by_id = lint_text(jobbody(
                    "{}", "      - run: echo ${{ " + src + " }}\n"))
                self.assertIn("template-injection", by_id, src)

    def test_quoted_sink_still_vulnerable(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo '${{ github.event.issue.body }}'\n"))
        self.assertIn("template-injection", by_id)

    def test_boolean_expression_results_are_safe(self) -> None:
        for expression in (
                "github.ref == 'refs/heads/main'",
                "contains(github.event.issue.body, 'release')"):
            with self.subTest(expression=expression):
                content = jobbody("{}", f"      - run: echo ${{{{ {expression} }}}}\n")
                _, _, by_id = lint_text(content, select=["template-injection"])
                self.assertNotIn("template-injection", by_id)

    def test_env_indirection_is_lookalike_safe(self) -> None:
        content = jobbody("{}", "      - env:\n"
                                "          BODY: ${{ github.event.issue.body }}\n"
                                "        run: echo \"$BODY\"\n")
        _, _, by_id = lint_text(content, select=["template-injection"])
        self.assertNotIn("template-injection", by_id)

    def test_safe_contexts_not_flagged(self) -> None:
        for src in ("github.sha", "github.event.pull_request.number",
                    "github.run_id", "matrix.os"):
            with self.subTest(src=src):
                _, _, by_id = lint_text(jobbody(
                    "{}", "      - run: echo ${{ " + src + " }}\n"),
                    select=["template-injection"])
                self.assertNotIn("template-injection", by_id, src)

    def test_unknown_dynamic_never_flagged(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo ${{ fromJSON(inputs.cfg).body }}\n"),
            select=["template-injection"])
        self.assertNotIn("template-injection", by_id)

    def test_static_run_is_safe(self) -> None:
        _, _, by_id = lint_text(jobbody("{}", "      - run: echo hi\n"),
                                select=["template-injection"])
        self.assertNotIn("template-injection", by_id)

    def test_multi_job_only_sink_flagged(self) -> None:
        content = ("on: push\npermissions: {}\njobs:\n"
                   "  clean:\n    runs-on: ubuntu-latest\n    permissions:\n"
                   "      contents: read\n    steps:\n      - run: echo hi\n"
                   "  dirty:\n    runs-on: ubuntu-latest\n    permissions:\n"
                   "      contents: read\n    steps:\n"
                   "      - run: echo ${{ github.event.issue.body }}\n")
        _, _, by_id = lint_text(content)
        self.assertEqual(len(by_id.get("template-injection", [])), 1)

    def test_no_autofix_flag(self) -> None:
        findings, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo ${{ github.event.issue.body }}\n"))
        for item in by_id.get("template-injection", []):
            self.assertFalse(item.fixable)


class CredentialExposureTests(unittest.TestCase):
    def test_echo_secret_reported(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo ${{ secrets.PAT }}\n"))
        self.assertIn("credential-exposure", by_id)

    def test_secrets_dump_reported(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo ${{ toJSON(secrets) }}\n"))
        self.assertIn("credential-exposure", by_id)

    def test_github_output_sink_reported(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo \"tok=${{ secrets.PAT }}\" >> $GITHUB_OUTPUT\n"))
        self.assertIn("credential-exposure", by_id)

    def test_hardcoded_password_reported(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - uses: actions/setup-node@v4\n"
                  "        with:\n          password: hunter2hunter2\n"))
        self.assertIn("credential-exposure", by_id)

    def test_secret_ref_is_safe(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - uses: actions/setup-node@v4\n"
                  "        with:\n          token: ${{ secrets.PAT }}\n"),
                                select=["credential-exposure"])
        self.assertNotIn("credential-exposure", by_id)

    def test_empty_and_placeholder_safe(self) -> None:
        for value in ('""', "***", "xxx"):
            with self.subTest(value=value):
                _, _, by_id = lint_text(jobbody(
                    "{}", "      - uses: actions/setup-node@v4\n"
                          f"        with:\n          token: {value}\n"),
                    select=["credential-exposure"])
                self.assertNotIn("credential-exposure", by_id, value)

    def test_naive_token_words_not_flagged(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo my token is ready\n"),
            select=["credential-exposure"])
        self.assertNotIn("credential-exposure", by_id)
        _, _, by_id = lint_text(jobbody(
            "{}", "      - uses: actions/setup-node@v4\n"
                  "        with:\n          username: token-user\n"),
            select=["credential-exposure"])
        self.assertNotIn("credential-exposure", by_id)

    def test_env_pass_without_echo_is_safe(self) -> None:
        content = jobbody("{}", "      - env:\n"
                                "          TOKEN: ${{ secrets.PAT }}\n"
                                "        run: ./deploy.sh\n")
        _, _, by_id = lint_text(content, select=["credential-exposure"])
        self.assertNotIn("credential-exposure", by_id)

    def test_secret_in_non_output_command_is_safe(self) -> None:
        content = jobbody("{}", "      - run: echo done; git fetch --token ${{ secrets.PAT }}\n")
        _, _, by_id = lint_text(content, select=["credential-exposure"])
        self.assertNotIn("credential-exposure", by_id)

    def test_boolean_secret_expression_is_safe(self) -> None:
        content = jobbody("{}", "      - run: echo ${{ secrets.PAT == 'expected' }}\n")
        _, _, by_id = lint_text(content, select=["credential-exposure"])
        self.assertNotIn("credential-exposure", by_id)

    def test_quoted_separator_does_not_hide_secret_output(self) -> None:
        content = jobbody("{}", "      - run: echo \"x; ${{ secrets.PAT }}\"\n")
        _, _, by_id = lint_text(content, select=["credential-exposure"])
        self.assertIn("credential-exposure", by_id)

    def test_no_autofix_flag(self) -> None:
        _, _, by_id = lint_text(jobbody(
            "{}", "      - run: echo ${{ secrets.PAT }}\n"))
        for item in by_id.get("credential-exposure", []):
            self.assertFalse(item.fixable)


if __name__ == "__main__":
    unittest.main()
