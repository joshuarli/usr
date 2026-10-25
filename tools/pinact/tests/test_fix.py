"""Autofix engine + catalog regression tests (U5).

Run with an isolated interpreter::

    python3 -I tools/pinact/tests/test_fix.py

Covers the 10-step verification per fix (diagnostic, diff-only mode, bytes,
reparse, resolved, no new errors, idempotence, lint-clean,
ambiguous-input-unchanged) plus overlap/symlink/read-only/concurrent-change/
catalog-failure/network-silence cases, and stdlib-randomized property tests
over edit invariants (termination, no out-of-span edits, preservation,
idempotence).
"""

from __future__ import annotations

import io
import random
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve()
SRC = HERE.parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinact import fixes as F  # noqa: E402
from pinact import lint as L  # noqa: E402
from pinact import pinning  # noqa: E402


CATALOG = """["actions/checkout"]
channel = "v4"
version = "v4.2.2"
sha = "11bd71901bbe5b1630ceea73d27597364c9af683"
"""

PIN_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"

BASE = """on: push
permissions: {{}}
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
{steps}
"""


def write_tree(files: dict[str, str]) -> tempfile.TemporaryDirectory:
    temp = tempfile.TemporaryDirectory()
    for name, content in files.items():
        path = Path(temp.name) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
    return temp


def run_fix(args: list[str]):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = F.fix_main(args)
        except SystemExit as exc:
            code = int(exc.code)
    return code, out.getvalue(), err.getvalue()


def lint_ids(path: Path, profile: str = "default", catalog: str | None = None):
    findings, error = L.lint_one_file(path, profile, catalog=catalog)
    return sorted({item.id for item in findings}), findings, error


class EditEngineTests(unittest.TestCase):
    def test_apply_sorted_splice(self) -> None:
        src = b"aaa\nbbb\nccc\n"
        edits = [F.Edit(8, 11, b"ccc", b"CCC", "t"),
                 F.Edit(4, 7, b"bbb", b"BBB", "t")]
        self.assertEqual(F.apply_edits(src, edits), b"aaa\nBBB\nCCC\n")

    def test_overlap_rejected(self) -> None:
        src = b"abcdef"
        with self.assertRaises(F.EditRejected):
            F.apply_edits(src, [F.Edit(0, 3, b"abc", b"X", "a"),
                                F.Edit(2, 5, b"cde", b"Y", "b")])

    def test_expected_bytes_checked(self) -> None:
        with self.assertRaises(F.EditRejected):
            F.apply_edits(b"abcdef", [F.Edit(0, 3, b"ZZZ", b"X", "a")])

    def test_out_of_span_rejected(self) -> None:
        for edit in (F.Edit(-1, 2, b"ab", b"X", "a"),
                     F.Edit(0, 99, b"ab", b"X", "a"),
                     F.Edit(4, 2, b"", b"X", "a")):
            with self.subTest(edit=edit):
                with self.assertRaises(F.EditRejected):
                    F.apply_edits(b"abcdef", [edit])

    def test_unrelated_bytes_identical(self) -> None:
        src = b"one\ntwo\nthree\n"
        out = F.apply_edits(src, [F.Edit(4, 7, b"two", b"TWO", "t")])
        self.assertEqual(out, b"one\nTWO\nthree\n")
        self.assertEqual(out.split(b"\n")[2], b"three")

    def test_zero_edits_identity(self) -> None:
        src = b"abc\n"
        self.assertEqual(F.apply_edits(src, []), src)


class RandomizedEditPropertyTests(unittest.TestCase):
    def test_preservation_and_termination(self) -> None:
        rng = random.Random(20261025)
        for _ in range(300):
            nlines = rng.randint(1, 8)
            lines = []
            for _ in range(nlines):
                width = rng.randint(1, 12)
                lines.append("".join(rng.choice("ab: #'\"\n") for _ in range(width)))
            src = ("\n".join(lines) + "\n").encode()
            edits: list[F.Edit] = []
            for _ in range(rng.randint(0, 3)):
                start = rng.randint(0, len(src))
                end = rng.randint(start, min(len(src), start + 4))
                edits.append(F.Edit(start, end, src[start:end],
                                    bytes(rng.randint(0, 5)) + b"Q", "prop"))
            try:
                out = F.apply_edits(src, edits)
            except F.EditRejected:
                spans = sorted((e.start, e.end) for e in edits)
                self.assertTrue(any(b > c for (_, b), (c, _) in zip(spans, spans[1:])))
                continue
            ordered = sorted(edits, key=lambda e: (e.start, e.end))
            shift = 0
            prev_end = 0
            for edit in ordered:
                gap = src[prev_end:edit.start]
                at = prev_end + shift
                self.assertEqual(out[at:at + len(gap)], gap)
                shift += len(edit.replacement) - (edit.end - edit.start)
                prev_end = edit.end
            tail = src[prev_end:]
            self.assertEqual(out[len(out) - len(tail):] if tail else b"", tail)
            want = len(src) + sum(len(e.replacement) - (e.end - e.start) for e in edits)
            self.assertEqual(len(out), want)

    def test_expected_bytes_prevent_reapplication(self) -> None:
        edit = F.Edit(1, 4, b"bcd", b"X", "prop")
        updated = F.apply_edits(b"abcdef", [edit])
        with self.assertRaises(F.EditRejected):
            F.apply_edits(updated, [edit])

    def test_random_overlaps_always_rejected(self) -> None:
        rng = random.Random(7)
        rejected = 0
        for _ in range(200):
            src = b"0123456789abcdef"
            a, b, c, d = (rng.randint(0, 15) for _ in range(4))
            first, second = sorted([(min(a, b), max(a, b) + 1),
                                    (min(c, d), max(c, d) + 1)])
            edits = [F.Edit(first[0], first[1], src[first[0]:first[1]], b"X", "p"),
                     F.Edit(second[0], second[1], src[second[0]:second[1]], b"Y", "p")]
            overlaps = second[0] < first[1]
            try:
                F.apply_edits(src, edits)
                self.assertFalse(overlaps)
            except F.EditRejected:
                rejected += 1
                self.assertTrue(overlaps)
        self.assertGreater(rejected, 50)


class CatalogPinFixTests(unittest.TestCase):
    STEPS = "      - uses: actions/checkout@v4\n"

    def test_full_verification(self) -> None:
        temp = write_tree({"w.yml": BASE.format(steps=self.STEPS),
                           "cat.toml": CATALOG})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            before, _, _ = lint_ids(path)
            self.assertIn("unpinned-uses", before)
            code, out, _ = run_fix(["--diff", "--catalog", str(root / "cat.toml"),
                                    str(path)])
            self.assertEqual(code, 1)
            self.assertIn("checkout@" + PIN_SHA, out)
            self.assertIn("@v4\n", path.read_bytes().decode())
            code, _, _ = run_fix(["--catalog", str(root / "cat.toml"), str(path)])
            self.assertEqual(code, 0)
            text = path.read_text(encoding="utf-8")
            self.assertIn("actions/checkout@" + PIN_SHA + " # v4.2.2", text)
            after, findings, error = lint_ids(path)
            self.assertIsNone(error)
            self.assertNotIn("unpinned-uses", after)
            self.assertNotIn("unapproved-pin", after)
            snapshot = path.read_bytes()
            code, _, _ = run_fix(["--catalog", str(root / "cat.toml"), str(path)])
            self.assertEqual(code, 0)
            self.assertEqual(path.read_bytes(), snapshot)
            path.write_text(BASE.format(steps="      - uses: actions/checkout@v9\n"),
                            encoding="utf-8", newline="")
            code, _, err = run_fix(["--catalog", str(root / "cat.toml"), str(path)])
            self.assertEqual(code, 1)
            self.assertIn("major", err)
        finally:
            temp.cleanup()

    def test_explicit_pin_uses_only_stubbed_resolution(self) -> None:
        content = BASE.format(steps="      - uses: actions/checkout@v4\n")
        temp = write_tree({"w.yml": content})
        path = Path(temp.name) / "w.yml"
        real_resolve = pinning.resolve
        calls = []

        def resolve(requested, allow_branches):
            calls.append((requested, allow_branches))
            return {("actions/checkout", "v4"): PIN_SHA}

        pinning.resolve = resolve
        try:
            code, _, err = run_fix(["--pin", str(path)])
            self.assertEqual(code, 0, err)
            self.assertEqual(calls, [({"actions/checkout": {"v4"}}, False)])
            self.assertIn(PIN_SHA, path.read_text(encoding="utf-8"))
        finally:
            pinning.resolve = real_resolve
            temp.cleanup()

    def test_unlabeled_sha_never_rewritten(self) -> None:
        content = BASE.format(steps=f"      - uses: actions/checkout@{PIN_SHA}\n")
        temp = write_tree({"w.yml": content, "cat.toml": CATALOG})
        try:
            root = Path(temp.name)
            snapshot = (root / "w.yml").read_bytes()
            code, _, _ = run_fix(["--catalog", str(root / "cat.toml"),
                                  str(root / "w.yml")])
            self.assertEqual(code, 1)
            self.assertEqual((root / "w.yml").read_bytes(), snapshot)
        finally:
            temp.cleanup()

    def test_subpath_preserved(self) -> None:
        content = BASE.format(steps="      - uses: actions/checkout/sub/path@v4\n")
        temp = write_tree({"w.yml": content, "cat.toml": CATALOG})
        try:
            root = Path(temp.name)
            code, _, err = run_fix(["--catalog", str(root / "cat.toml"),
                                    str(root / "w.yml")])
            self.assertEqual(code, 0, err)
            text = (root / "w.yml").read_text(encoding="utf-8")
            self.assertIn("actions/checkout/sub/path@" + PIN_SHA, text)
        finally:
            temp.cleanup()

    def test_missing_approval_reported_not_guessed(self) -> None:
        content = BASE.format(steps="      - uses: evil/tool@v1\n")
        temp = write_tree({"w.yml": content, "cat.toml": CATALOG})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            before = path.read_bytes()
            code, _, err = run_fix(["--catalog", str(root / "cat.toml"), str(path)])
            self.assertEqual(code, 1)
            self.assertIn("no approved pin", err)
            self.assertEqual(path.read_bytes(), before)
            _, _, error = lint_ids(path, catalog=str(root / "cat.toml"))
            self.assertIsNone(error)
        finally:
            temp.cleanup()

    def test_no_silent_downgrade(self) -> None:
        other = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        content = BASE.format(steps=f"      - uses: actions/checkout@{other} # v4\n")
        temp = write_tree({"w.yml": content, "cat.toml": CATALOG})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            snapshot = path.read_bytes()
            code, _, _ = run_fix(["--catalog", str(root / "cat.toml"), str(path)])
            self.assertEqual(path.read_bytes(), snapshot)
        finally:
            temp.cleanup()

    def test_newer_same_major_ref_not_downgraded(self) -> None:
        content = BASE.format(steps="      - uses: actions/checkout@v4.99.0\n")
        temp = write_tree({"w.yml": content, "cat.toml": CATALOG})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            before = path.read_bytes()
            code, _, err = run_fix(["--catalog", str(root / "cat.toml"), str(path)])
            self.assertEqual(code, 1)
            self.assertIn("downgrade", err.lower())
            self.assertEqual(path.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_catalog_pin_records_approved_version(self) -> None:
        content = BASE.format(steps="      - uses: actions/checkout@v4.0.0 # v4.0.0\n")
        temp = write_tree({"w.yml": content, "cat.toml": CATALOG})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            code, _, err = run_fix(["--catalog", str(root / "cat.toml"), str(path)])
            self.assertEqual(code, 0, err)
            text = path.read_text(encoding="utf-8")
            self.assertIn("# v4.0.0 [pin:v4.2.2]", text)
        finally:
            temp.cleanup()

    def test_unapproved_pinned_sha_reported(self) -> None:
        unknown_sha = "a" * 40
        content = BASE.format(steps=f"      - uses: evil/tool@{unknown_sha}\n")
        temp = write_tree({"w.yml": content, "cat.toml": CATALOG})
        try:
            root = Path(temp.name)
            _, findings, error = lint_ids(
                root / "w.yml", catalog=str(root / "cat.toml"))
            self.assertIsNone(error)
            self.assertTrue(any(item.id == "unapproved-pin" for item in findings))
            code, _, err = run_fix(["--catalog", str(root / "cat.toml"),
                                    str(root / "w.yml")])
            self.assertEqual(code, 1)
            self.assertIn("no approved pin", err)
        finally:
            temp.cleanup()


class CatalogValidationTests(unittest.TestCase):
    def test_bad_records_rejected(self) -> None:
        cases = [
            ("empty", ""),
            ("missing-sha", '["actions/checkout"]\nchannel = "v4"\nversion = "v4.2.2"\n'),
            ("bad-sha", '["actions/checkout"]\nchannel = "v4"\nversion = "v4.2.2"\nsha = "zzz"\n'),
            ("major-mismatch", '["actions/checkout"]\nchannel = "v4"\nversion = "v5.0.0"\nsha = "' + PIN_SHA + '"\n'),
            ("ambiguous", '["actions/checkout"]\nchannel = "v4"\nversion = "v4.2.2"\nsha = "' + PIN_SHA + '"\n'
                          '["actions.checkout"]\nchannel = "v4"\nversion = "v4.2.3"\nsha = "' + PIN_SHA + '"\n'),
        ]
        for name, body in cases:
            with self.subTest(name=name):
                temp = write_tree({"w.yml": BASE.format(steps="      - run: echo hi\n"),
                                   "cat.toml": body})
                try:
                    root = Path(temp.name)
                    code, _, err = run_fix(["--catalog", str(root / "cat.toml"),
                                            str(root / "w.yml")])
                    self.assertEqual(code, 2, name)
                    self.assertIn("catalog", err.lower(), name)
                finally:
                    temp.cleanup()

    def test_lint_catalog_offline_shape(self) -> None:
        temp = write_tree({"w.yml": BASE.format(steps="      - run: echo hi\n"),
                           "cat.toml": "not toml [[[\n"})
        try:
            root = Path(temp.name)
            _, _, error = lint_ids(root / "w.yml", catalog=str(root / "cat.toml"))
            self.assertIsNotNone(error)
        finally:
            temp.cleanup()


class ObsoleteCommandFixTests(unittest.TestCase):
    def test_single_line_rewrite_verified(self) -> None:
        content = BASE.format(steps="      - run: echo \"::set-output name=foo::bar\"\n")
        temp = write_tree({"w.yml": content})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            path.chmod(0o640)
            mode = stat.S_IMODE(path.stat().st_mode)
            before, _, _ = lint_ids(path)
            self.assertIn("deprecated-command", before)
            code, out, _ = run_fix(["--diff", str(path)])
            self.assertEqual(code, 1)
            self.assertIn("GITHUB_OUTPUT", out)
            self.assertIn("::set-output", path.read_text(encoding="utf-8"))
            code, _, _ = run_fix([str(path)])
            self.assertEqual(code, 0)
            text = path.read_text(encoding="utf-8")
            self.assertIn('echo "foo=bar" >> "$GITHUB_OUTPUT"', text)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
            self.assertNotIn("::set-output", text)
            after, _, _ = lint_ids(path)
            self.assertNotIn("deprecated-command", after)
            snapshot = path.read_bytes()
            self.assertEqual(run_fix([str(path)])[0], 0)
            self.assertEqual(path.read_bytes(), snapshot)
        finally:
            temp.cleanup()

    def test_shell_expansion_is_not_rewritten(self) -> None:
        content = BASE.format(steps=(
            "      - run: echo \"::set-output name=foo::$(touch marker)\"\n"))
        temp = write_tree({"w.yml": content})
        try:
            path = Path(temp.name) / "w.yml"
            before = path.read_bytes()
            code, _, err = run_fix([str(path)])
            self.assertEqual(code, 1)
            self.assertIn("no known semantics", err)
            self.assertEqual(path.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_non_bash_shell_is_not_rewritten(self) -> None:
        content = BASE.format(steps=(
            "      - shell: pwsh\n"
            "        run: echo \"::set-output name=foo::bar\"\n"))
        temp = write_tree({"w.yml": content})
        try:
            path = Path(temp.name) / "w.yml"
            before = path.read_bytes()
            code, _, err = run_fix([str(path)])
            self.assertEqual(code, 1)
            self.assertIn("shell", err.lower())
            self.assertEqual(path.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_multiline_refused(self) -> None:
        content = BASE.format(steps="      - run: |\n"
                                    "          echo \"::set-output name=foo::bar\"\n"
                                    "          echo done\n")
        temp = write_tree({"w.yml": content})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            before = path.read_bytes()
            code, _, err = run_fix([str(path)])
            self.assertIn("multiline", err)
            self.assertEqual(path.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_save_state_and_add_path(self) -> None:
        for old, new in (("::save-state", "GITHUB_STATE"), ("::add-path", "GITHUB_PATH")):
            with self.subTest(old=old):
                if old == "::add-path":
                    step = "      - run: echo \"::add-path::/opt/bin\"\n"
                else:
                    step = "      - run: echo \"::save-state name=s::v\"\n"
                temp = write_tree({"w.yml": BASE.format(steps=step)})
                try:
                    root = Path(temp.name)
                    self.assertEqual(run_fix([str(root / "w.yml")])[0], 0)
                    self.assertIn(new, (root / "w.yml").read_text(encoding="utf-8"))
                finally:
                    temp.cleanup()


class PolicyFixTests(unittest.TestCase):
    CLEAN = ("on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
             "    steps:\n      - run: echo hi\n")

    def test_default_fix_never_adds_blocks(self) -> None:
        temp = write_tree({"w.yml": self.CLEAN})
        try:
            root = Path(temp.name)
            before = (root / "w.yml").read_bytes()
            code, _, _ = run_fix([str(root / "w.yml")])
            self.assertEqual((root / "w.yml").read_bytes(), before)
        finally:
            temp.cleanup()

    def test_explicit_policy_adds_minimum(self) -> None:
        temp = write_tree({"w.yml": self.CLEAN})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            code, _, err = run_fix(["--policy", "permissions=read-all",
                                    "--policy", "timeout-minutes=30", str(path)], )
            self.assertEqual(code, 0, err)
            text = path.read_text(encoding="utf-8")
            self.assertIn("permissions: read-all", text)
            self.assertIn("timeout-minutes: 30", text)
            snapshot = path.read_bytes()
            self.assertEqual(run_fix(["--policy", "permissions=read-all",
                                      "--policy", "timeout-minutes=30",
                                      str(path)])[0], 0)
            self.assertEqual(path.read_bytes(), snapshot)
        finally:
            temp.cleanup()

    def test_policy_insertion_preserves_crlf(self) -> None:
        temp = write_tree({"w.yml": self.CLEAN.replace("\n", "\r\n")})
        try:
            path = Path(temp.name) / "w.yml"
            code, _, err = run_fix([
                "--policy", "permissions=read-all", str(path)])
            self.assertEqual(code, 0, err)
            updated = path.read_bytes()
            self.assertNotIn(b"\n", updated.replace(b"\r\n", b""))
        finally:
            temp.cleanup()

    def test_privilege_add_refused(self) -> None:
        temp = write_tree({"w.yml": self.CLEAN})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            before = path.read_bytes()
            code, _, err = run_fix(["--policy", "permissions=write-all", str(path)])
            self.assertEqual(code, 1)
            self.assertIn("privilege", err)
            self.assertEqual(path.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_invalid_timeout_refused(self) -> None:
        temp = write_tree({"w.yml": self.CLEAN})
        try:
            root = Path(temp.name)
            code, _, err = run_fix(["--policy", "timeout-minutes=never",
                                    str(root / "w.yml")])
            self.assertEqual(code, 1)
            self.assertIn("timeout", err.lower())
        finally:
            temp.cleanup()

    def test_permissions_value_cannot_inject_yaml(self) -> None:
        temp = write_tree({"w.yml": self.CLEAN})
        try:
            path = Path(temp.name) / "w.yml"
            before = path.read_bytes()
            code, _, err = run_fix([
                "--policy", "permissions=contents: read\nname: injected", str(path)])
            self.assertEqual(code, 1)
            self.assertIn("permissions", err.lower())
            self.assertEqual(path.read_bytes(), before)
        finally:
            temp.cleanup()


class RobustnessTests(unittest.TestCase):
    def test_symlink_refused(self) -> None:
        temp = write_tree({"w.yml": BASE.format(steps="      - run: echo hi\n")})
        try:
            root = Path(temp.name)
            link = root / "link.yml"
            link.symlink_to(root / "w.yml")
            code, _, err = run_fix([str(link)])
            self.assertEqual(code, 2)
            self.assertIn("symlink", err)
        finally:
            temp.cleanup()

    def test_readonly_refused(self) -> None:
        temp = write_tree({"w.yml": BASE.format(
            steps="      - run: echo \"::set-output name=a::b\"\n")})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            try:
                code, _, err = run_fix([str(path)])
                self.assertEqual(code, 2)
                self.assertIn("read-only", err)
            finally:
                path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        finally:
            temp.cleanup()

    def test_concurrent_change_detected(self) -> None:
        temp = write_tree({"w.yml": BASE.format(
            steps="      - run: echo \"::set-output name=a::b\"\n")})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            original = path.read_bytes()
            updated = F.apply_edits(
                original,
                [F.Edit(0, 0, b"", b"# race\n", "t")])
            path.write_bytes(original + b"# concurrent\n")
            with self.assertRaises(pinning.PinError):
                pinning.write_file(path, original.decode(), updated.decode())
        finally:
            temp.cleanup()

    def test_catalog_failure_writes_nothing(self) -> None:
        content = BASE.format(steps="      - uses: actions/checkout@v4\n")
        temp = write_tree({"w.yml": content, "cat.toml": " Garbage [[[\n"})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            before = path.read_bytes()
            code, _, err = run_fix(["--catalog", str(root / "cat.toml"), str(path)])
            self.assertEqual(code, 2)
            self.assertIn("catalog", err.lower())
            self.assertEqual(path.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_default_fix_needs_no_network(self) -> None:
        content = BASE.format(steps="      - uses: actions/checkout@v4\n")
        temp = write_tree({"w.yml": content})
        try:
            root = Path(temp.name)
            path = root / "w.yml"
            before = path.read_bytes()
            real_resolve = pinning.resolve
            def fail(*args, **kwargs):
                raise AssertionError("network must stay silent")

            pinning.resolve = fail  # type: ignore[assignment]
            try:
                code, _, err = run_fix([str(path)])
            finally:
                pinning.resolve = real_resolve
            self.assertEqual(code, 1)
            self.assertIn("--pin", err)
            self.assertEqual(path.read_bytes(), before)
        finally:
            temp.cleanup()

    def test_lint_offline_with_network_stubbed(self) -> None:
        import subprocess
        content = BASE.format(steps="      - uses: actions/checkout@v4\n")
        temp = write_tree({"w.yml": content})
        try:
            root = Path(temp.name)
            real_run = subprocess.run

            def reject_network(command, *args, **kwargs):
                if "ls-remote" in command:
                    raise AssertionError("lint must stay offline")
                return real_run(command, *args, **kwargs)

            subprocess.run = reject_network  # type: ignore[assignment]
            try:
                findings, error = L.lint_one_file(root / "w.yml", "correctness")
            finally:
                subprocess.run = real_run
            self.assertIsNone(error)
            self.assertTrue(any(item.id == "unpinned-uses" for item in findings))
        finally:
            temp.cleanup()

    def test_unknown_paths_rejected(self) -> None:
        temp = write_tree({})
        try:
            code, _, err = run_fix([str(Path(temp.name) / "nope" / ".." / "w.yml")])
            self.assertEqual(code, 2)
        finally:
            temp.cleanup()

    def test_symlinked_parent_rejected(self) -> None:
        temp = write_tree({"real/w.yml": BASE.format(
            steps="      - uses: actions/checkout@v4\n")})
        try:
            root = Path(temp.name)
            (root / "alias").symlink_to(root / "real", target_is_directory=True)
            path = root / "alias" / "w.yml"
            original = (root / "real" / "w.yml").read_bytes()
            code, _, err = run_fix([str(path)])
            self.assertEqual(code, 2)
            self.assertIn("symlink", err)
            self.assertEqual((root / "real" / "w.yml").read_bytes(), original)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
