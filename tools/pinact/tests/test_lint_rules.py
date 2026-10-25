"""Rule-by-rule regression tests for structural lint.

Run with an isolated interpreter::

    python3 -I tools/pinact/tests/test_lint_rules.py
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
        by_id = {}
        for item in findings:
            by_id.setdefault(item.id, []).append(item)
        return findings, error, by_id


def lint_cli(args: list[str]):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = L.main(args)
        except SystemExit as exc:
            code = int(exc.code)
    return code, out.getvalue(), err.getvalue()


BASE = (
    "on: push\n"
    "jobs:\n"
    "  build:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: echo hi\n"
)


class SyntaxTests(unittest.TestCase):
    def test_malformed_yaml_is_structured_diagnostic(self) -> None:
        findings, error, by_id = lint_text("::: bad: [", profile="correctness")
        self.assertIsNone(error)
        self.assertIn("yaml-syntax", by_id)
        self.assertEqual(findings[0].severity, "error")

    def test_malformed_yaml_never_tracebacks_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "w.yml"
            path.write_text("::: bad: [", encoding="utf-8")
            code, out, err = lint_cli(["--format=json", str(path)])
            self.assertEqual(code, 1)
            self.assertNotIn("Traceback", err)
            self.assertNotIn("Traceback", out)

    def test_duplicate_keys_reported(self) -> None:
        content = "on: push\non: pull_request\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("duplicate-key", by_id)

    def test_duplicate_job_ids_reported(self) -> None:
        _, _, by_id = lint_text("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n", profile="correctness")
        self.assertNotIn("duplicate-key", by_id)
        dup = "on: push\njobs:\n  a: 1\n  a: 2\n"
        _, _, by_id = lint_text(dup, profile="correctness")
        self.assertIn("duplicate-key", by_id)


class TopLevelTests(unittest.TestCase):
    def test_missing_jobs_and_on(self) -> None:
        _, _, by_id = lint_text("name: hi\n", profile="correctness")
        self.assertIn("missing-key", by_id)
        ids = [f.message for f in by_id["missing-key"]]
        self.assertTrue(any("jobs" in m for m in ids))
        self.assertTrue(any("'on'" in m for m in ids))

    def test_unknown_top_level_key_default_only(self) -> None:
        content = BASE.replace("jobs:", "bogus-key: 1\njobs:", 1)
        _, _, by_default = lint_text(content, profile="default")
        self.assertIn("unknown-key", by_default)
        _, _, by_correct = lint_text(content, profile="correctness")
        self.assertNotIn("unknown-key", by_correct)

    def test_invalid_jobs_type(self) -> None:
        _, _, by_id = lint_text("on: push\njobs: [1, 2]\n", profile="correctness")
        self.assertIn("invalid-type", by_id)

    def test_document_root_must_be_mapping(self) -> None:
        _, _, by_id = lint_text("- 1\n- 2\n", profile="correctness")
        self.assertIn("invalid-type", by_id)


class JobStepTests(unittest.TestCase):
    def test_invalid_job_id(self) -> None:
        content = "on: push\njobs:\n  'bad id':\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("invalid-job-id", by_id)

    def test_step_needs_uses_or_run(self) -> None:
        content = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: nothing\n"
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("missing-key", by_id)

    def test_step_both_uses_and_run(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
                   "      - uses: actions/checkout@v4\n        run: echo\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("invalid-type", by_id)

    def test_missing_runs_on(self) -> None:
        content = "on: push\njobs:\n  build:\n    steps:\n      - run: echo\n"
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertTrue(any("runs-on" in f.message for f in by_id.get("missing-key", [])))

    def test_empty_steps(self) -> None:
        content = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps: []\n"
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("missing-key", by_id)

    def test_invalid_step_id_and_duplicate(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
                   "      - id: 'bad id'\n        run: echo\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("invalid-type", by_id)
        dup = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
               "      - id: one\n        run: echo\n"
               "      - id: one\n        run: echo\n")
        _, _, by_id = lint_text(dup, profile="correctness")
        self.assertIn("duplicate-key", by_id)

    def test_unknown_step_key_default_only(self) -> None:
        content = BASE.replace("- run: echo hi", "- run: echo hi\n        bogus-step: 1", 1)
        _, _, by_default = lint_text(content, profile="default")
        self.assertIn("unknown-key", by_default)
        _, _, by_correct = lint_text(content, profile="correctness")
        self.assertNotIn("unknown-key", by_correct)

    def test_reusable_job_uses_ok(self) -> None:
        content = ("on: push\njobs:\n  call:\n    uses: octo/repo/.github/workflows/ci.yml@v4\n")
        findings, error, by_id = lint_text(content, profile="correctness")
        self.assertIsNone(error)
        self.assertNotIn("missing-key", by_id)


class NeedsTests(unittest.TestCase):
    def test_unknown_needs(self) -> None:
        content = ("on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"
                   "  b:\n    needs: nope\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("invalid-needs", by_id)

    def test_self_needs(self) -> None:
        content = ("on: push\njobs:\n  a:\n    needs: a\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertTrue(any("itself" in f.message for f in by_id.get("invalid-needs", [])))

    def test_duplicate_needs(self) -> None:
        content = ("on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"
                   "  b:\n    needs: [a, a]\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertTrue(any("duplicate" in f.message for f in by_id.get("invalid-needs", [])))

    def test_needs_cycle(self) -> None:
        content = ("on: push\njobs:\n  a:\n    needs: b\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"
                   "  b:\n    needs: a\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("needs-cycle", by_id)
        self.assertEqual(by_id["needs-cycle"][0].line, 3)


class MatrixCronTests(unittest.TestCase):
    def test_matrix_include_keys_are_known(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    strategy:\n      matrix:\n        include:\n          - custom: value\n"
                   "    steps:\n      - run: echo ${{ matrix.other }}\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("undefined-property", by_id)

    def test_dynamic_matrix_property_stays_unknown(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    strategy:\n      matrix: ${{ fromJSON('{\"os\":[\"ubuntu-latest\"]}') }}\n"
                   "    steps:\n      - run: echo ${{ matrix.os }}\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertNotIn("undefined-property", by_id)

    def test_invalid_matrix_shape(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    strategy:\n      matrix: [1, 2]\n"
                   "    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="default")
        self.assertIn("invalid-matrix", by_id)

    def test_matrix_include_must_be_list(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    strategy:\n      matrix:\n        os: [ubuntu-latest]\n        include: {}\n"
                   "    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="default")
        self.assertIn("invalid-matrix", by_id)

    def test_invalid_cron(self) -> None:
        content = "on:\n  schedule:\n    - cron: not-a-cron\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"
        _, _, by_id = lint_text(content, profile="default")
        self.assertIn("invalid-cron", by_id)

    def test_valid_cron_clean(self) -> None:
        content = "on:\n  schedule:\n    - cron: '0 0 * * *'\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"
        _, _, by_id = lint_text(content, profile="default")
        self.assertNotIn("invalid-cron", by_id)

    def test_schedule_missing_cron(self) -> None:
        content = "on:\n  schedule:\n    - {}\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("missing-key", by_id)


class EventPermissionTests(unittest.TestCase):
    def test_unknown_event(self) -> None:
        _, _, by_id = lint_text("on: nope-event\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n",
                                profile="default")
        self.assertIn("invalid-event", by_id)

    def test_event_filter_type(self) -> None:
        content = ("on:\n  push:\n    branches: main\n"
                   "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("invalid-type", by_id)

    def test_unknown_event_filter(self) -> None:
        content = ("on:\n  push:\n    branch: main\n"
                   "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("invalid-event-filter", by_id)

    def test_template_injection_is_in_correctness_profile(self) -> None:
        content = ("on: pull_request\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    steps:\n      - run: echo ${{ github.event.pull_request.title }}\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("template-injection", by_id)

    def test_unknown_matrix_property_is_in_correctness_profile(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                   "    steps:\n      - run: echo ${{ matrix.os }}\n")
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("undefined-property", by_id)

    def test_invalid_permissions(self) -> None:
        content = ("on: push\npermissions:\n  bogus: read\n"
                   "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="default")
        self.assertIn("invalid-permissions", by_id)
        bad_val = ("on: push\npermissions:\n  contents: everything\n"
                   "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(bad_val, profile="default")
        self.assertIn("invalid-permissions", by_id)

    def test_valid_permissions_clean(self) -> None:
        content = ("on: push\npermissions:\n  contents: read\n"
                   "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        _, _, by_id = lint_text(content, profile="default")
        self.assertNotIn("invalid-permissions", by_id)


class UsesScopeTests(unittest.TestCase):
    def test_malformed_uses_is_invalid_uses(self) -> None:
        _, _, by_id = lint_text("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: '${{ inputs.action }}'\n",
                                profile="correctness")
        self.assertIn("invalid-uses", by_id)

    def test_unpinned_uses_reported(self) -> None:
        _, _, by_id = lint_text("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
                                profile="correctness")
        self.assertIn("unpinned-uses", by_id)

    def test_env_uses_is_not_an_invocation(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
                   "      - uses: actions/checkout@v4\n"
                   "        env:\n          uses: some/text@latest\n")
        _, _, by_id = lint_text(content, profile="correctness", select=["unpinned-uses", "invalid-uses"])
        self.assertEqual(len(by_id.get("unpinned-uses", [])), 1)
        self.assertNotIn("invalid-uses", by_id)

    def test_with_uses_is_not_an_invocation(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
                   "      - uses: actions/checkout@v4\n"
                   "        with:\n          uses: other/tool@v9\n")
        _, _, by_id = lint_text(content, profile="correctness", select=["unpinned-uses", "invalid-uses"])
        self.assertEqual(len(by_id.get("unpinned-uses", [])), 1)

    def test_block_scalar_body_is_not_scanned(self) -> None:
        content = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
                   "      - run: |\n          uses: actions/checkout@v4\n")
        _, _, by_id = lint_text(content, profile="correctness", select=["unpinned-uses", "invalid-uses"])
        self.assertNotIn("unpinned-uses", by_id)
        self.assertNotIn("invalid-uses", by_id)

    def test_block_scalar_uses_value_rejected(self) -> None:
        for body in ("uses: >-\n  actions/checkout@v4\n", "uses: |\n  actions/checkout@v4\n"):
            with self.subTest(body=body):
                _, _, by_id = lint_text(body, profile="correctness")
                self.assertIn("invalid-uses", by_id)

    def test_composite_runs_steps_uses_reported(self) -> None:
        content = ("name: hi\ndescription: hi\nruns:\n  using: composite\n  steps:\n"
                   "    - uses: actions/checkout@v4\n")
        _, _, by_id = lint_text(content, profile="correctness", filename="action.yml")
        self.assertIn("unpinned-uses", by_id)

    def test_action_file_not_workflow_rooted(self) -> None:
        content = "name: hi\ndescription: hi\nruns:\n  using: composite\n  steps:\n    - run: echo\n"
        findings, _, by_id = lint_text(content, profile="correctness", filename="action.yml")
        self.assertNotIn("missing-key", by_id)
        for item in findings:
            self.assertNotIn("workflow is missing", item.message)

    def test_job_level_uses_reports_unpinned(self) -> None:
        content = "on: push\njobs:\n  call:\n    uses: octo/repo/.github/workflows/ci.yml@v4\n"
        _, _, by_id = lint_text(content, profile="correctness")
        self.assertIn("unpinned-uses", by_id)


class CliTests(unittest.TestCase):
    def test_profiles_select_format_catalog_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "clean.yml"
            clean.write_text(BASE, encoding="utf-8")
            code, out, _ = lint_cli(["--format=json", str(clean)])
            self.assertEqual(code, 0)
            dirty = Path(temp) / "dirty.yml"
            dirty.write_text(BASE.replace("- run: echo hi", "- uses: actions/checkout@v4", 1), encoding="utf-8")
            code, out, _ = lint_cli(["--format=json", "--profile=correctness", str(dirty)])
            self.assertEqual(code, 1)
            code, out, _ = lint_cli(["--format=json", "--select=unknown-key", str(dirty)])
            self.assertEqual(code, 0)
            code, _, err = lint_cli(["--format=json", "--select=not-a-rule", str(dirty)])
            self.assertEqual(code, 2)
            self.assertIn("unknown rule", err)
            code, _, err = lint_cli(["--format=json", "--catalog", str(Path(temp) / "nope.toml"), str(dirty)])
            self.assertEqual(code, 2)
            self.assertIn("catalog", err)
            code, _, err = lint_cli(["--format=json", str(Path(temp) / "missing.yml")])
            self.assertEqual(code, 2)

    def test_strict_adds_recommendations(self) -> None:
        _, _, by_default = lint_text(BASE, profile="default")
        self.assertNotIn("suggest-permissions", by_default)
        _, _, by_strict = lint_text(BASE, profile="strict")
        self.assertIn("suggest-permissions", by_strict)


if __name__ == "__main__":
    unittest.main()
