"""Regression suite for vendored YAML and AST ``uses:`` discovery.

Run from the repository root with an isolated interpreter::

    python3 -I tools/pinact/tests/test_yaml.py

Covers plain/single/double-quoted scalars, folded/literal blocks, flow
mappings and sequences, comments, CRLF/LF, Unicode/BOM, anchors with multiple
alias uses, recursive aliases, malformed anchors, merge constructs, duplicate
keys, ``on:`` as a scalar key, multi-doc/empty docs, odd indentation, and
invalid-ref rejections.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SRC = HERE.parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinact._vendor import yaml  # noqa: E402
from pinact import pinning  # noqa: E402


def compose_one(source: str):
    return yaml.compose(source, Loader=yaml.BaseLoader)


def scan_text(content: str, refresh: bool = False):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "case.yml"
        path.write_text(content, encoding="utf-8", newline="")
        return pinning.scan(path, refresh=refresh)


class VendorTests(unittest.TestCase):
    def test_vendored_copy_is_used_without_c_extension(self) -> None:
        self.assertTrue(str(Path(yaml.__file__).resolve()).startswith(str(SRC)))
        self.assertFalse(yaml.__with_libyaml__)
        self.assertNotIn("yaml._yaml", sys.modules)
        self.assertEqual(yaml.__version__, "6.0.3")

    def test_provenance_and_license_ship_with_source(self) -> None:
        vendor = Path(yaml.__file__).resolve().parent
        self.assertTrue((vendor / "LICENSE").is_file())
        provenance = (vendor / "PROVENANCE.txt").read_text(encoding="utf-8")
        for token in ("6.0.3", "SHA-256", "d76623373421df22fb4cf8817020cbb7ef15c725b9d5e45f17e189bfc384190f",
                      "https://files.pythonhosted.org", "MIT", "BaseLoader"):
            self.assertIn(token, provenance)

    def test_on_stays_a_string(self) -> None:
        node = compose_one("on:\n  push:\n    branches: [main]\n")
        self.assertEqual(node.value[0][0].value, "on")


class ScalarStyleTests(unittest.TestCase):
    def test_plain_single_double_quoted_scalars(self) -> None:
        node = compose_one("a: plain\nb: 'single'\nc: \"double\"\n")
        values = {key.value: (val.value, val.style) for key, val in node.value}
        self.assertEqual(values["a"], ("plain", None))
        self.assertEqual(values["b"], ("single", "'"))
        self.assertEqual(values["c"], ("double", '"'))

    def test_folded_and_literal_blocks(self) -> None:
        node = compose_one("folded: >\n  a\n  b\nliteral: |\n  a\n  b\n")
        values = {key.value: (val.value, val.style) for key, val in node.value}
        self.assertEqual(values["folded"], ("a b\n", ">"))
        self.assertEqual(values["literal"], ("a\nb\n", "|"))

    def test_flow_mapping_and_sequence(self) -> None:
        node = compose_one("flow: {a: 1, b: [x, y]}\n")
        value = node.value[0][1]
        self.assertTrue(value.flow_style)
        inner = value.value[1][1]
        self.assertTrue(inner.flow_style)
        self.assertEqual([item.value for item in inner.value], ["x", "y"])

    def test_comments_crlf_unicode_bom(self) -> None:
        crlf = "a: 1 # comment\r\nb: caf\u00e9\r\n"
        lf = "a: 1 # comment\nb: caf\u00e9\n"
        bom = "\ufeffa: 1\nb: 2\n"
        for source in (crlf, lf, bom):
            node = compose_one(source)
            self.assertEqual(node.value[0][1].value, "1")
        node = compose_one(lf)
        self.assertEqual(node.value[1][1].value, "caf\u00e9")

    def test_multiline_plain_scalar_folds(self) -> None:
        node = compose_one("a: one\n  two\n")
        self.assertEqual(node.value[0][1].value, "one two")


class AnchorAliasTests(unittest.TestCase):
    def test_composer_shares_anchored_nodes_across_aliases(self) -> None:
        node = compose_one("base: &b 1\nfirst: *b\nsecond: *b\n")
        values = {key.value: val for key, val in node.value}
        self.assertIs(values["first"], values["base"])
        self.assertIs(values["second"], values["base"])
        self.assertEqual(values["base"].value, "1")

    def test_recursive_alias_terminates_compose_and_scan(self) -> None:
        node = compose_one("a: &x\n  b: *x\n")
        outer = node.value[0][1]
        self.assertIs(outer.value[0][1], outer)
        _, uses = scan_text("a: &x\n  b: *x\n")
        self.assertEqual(uses, [])

    def test_scan_never_follows_aliases(self) -> None:
        _, uses = scan_text(
            "base: &b\n  uses: actions/checkout@v1\n"
            "job:\n  needs: *b\n"
        )
        self.assertEqual([(use.index, use.repo, use.ref) for use in uses],
                         [(1, "actions/checkout", "v1")])

    def test_malformed_anchor_fails_closed(self) -> None:
        with self.assertRaises(yaml.YAMLError):
            compose_one("x: *nope\n")
        with self.assertRaises(pinning.PinError):
            scan_text("x: *nope\n")

    def test_merge_key_is_preserved_never_expanded(self) -> None:
        _, uses = scan_text(
            "base: &b\n  uses: actions/checkout@v1\n"
            "job:\n  <<: *b\n"
        )
        self.assertEqual([(use.index, use.repo, use.ref) for use in uses],
                         [(1, "actions/checkout", "v1")])


class DocumentShapeTests(unittest.TestCase):
    def test_duplicate_keys_both_visible(self) -> None:
        _, uses = scan_text(
            "steps:\n"
            "  - uses: actions/checkout@v1\n"
            "  - uses: actions/setup-node@v2\n"
        )
        self.assertEqual(len(uses), 2)
        node = compose_one("a: 1\na: 2\n")
        self.assertEqual([val.value for _, val in node.value], ["1", "2"])

    def test_multi_doc_and_empty_docs(self) -> None:
        _, uses = scan_text(
            "---\nsteps:\n  - uses: actions/checkout@v1\n"
            "---\n"
            "...\n"
            "---\nsteps:\n  - uses: actions/setup-node@v2\n"
        )
        self.assertEqual([(use.repo, use.ref) for use in uses],
                         [("actions/checkout", "v1"), ("actions/setup-node", "v2")])

    def test_empty_document_scans_clean(self) -> None:
        source, uses = scan_text("")
        self.assertEqual(source, "")
        self.assertEqual(uses, [])

    def test_odd_indentation(self) -> None:
        _, uses = scan_text(
            "jobs:\n"
            "   build:\n"
            "      steps:\n"
            "         - uses: actions/checkout@v1\n"
        )
        self.assertEqual([(use.index, use.repo, use.ref) for use in uses],
                         [(3, "actions/checkout", "v1")])

    def test_tab_indentation_fails_closed(self) -> None:
        with self.assertRaises(pinning.PinError) as ctx:
            scan_text("steps:\n\t- uses: actions/checkout@v1\n")
        self.assertIn("invalid YAML", str(ctx.exception))


class DiscoveryErrorTests(unittest.TestCase):
    def test_flow_inline_uses_fails_closed(self) -> None:
        with self.assertRaises(pinning.PinError) as ctx:
            scan_text("steps: [{uses: actions/checkout@v1}]\n")
        self.assertIn("unsupported inline uses syntax", str(ctx.exception))

    def test_block_scalar_uses_value_rejected(self) -> None:
        for content in ("uses: >-\n  actions/checkout@v1\n",
                        "uses: |\n  actions/checkout@v1\n"):
            with self.subTest(content=content), self.assertRaises(pinning.PinError):
                scan_text(content)

    def test_quoted_flow_looking_string_is_not_an_invocation(self) -> None:
        _, uses = scan_text('x: "{uses: y}"\n')
        self.assertEqual(uses, [])

    def test_comment_flow_text_is_not_an_invocation(self) -> None:
        _, uses = scan_text("x: 1 # {uses: y}\n")
        self.assertEqual(uses, [])

    def test_block_scalar_body_is_not_scanned(self) -> None:
        _, uses = scan_text(
            "steps:\n"
            "  - run: |\n"
            "      uses: actions/checkout@v1\n"
        )
        self.assertEqual(uses, [])

    def test_with_and_env_scopes_skipped(self) -> None:
        _, uses = scan_text(
            "steps:\n"
            "  - uses: actions/checkout@v1\n"
            "    with:\n"
            "      uses: other/tool@v9\n"
            "    env:\n"
            "      uses: some/text@latest\n"
        )
        self.assertEqual([(use.repo, use.ref) for use in uses], [("actions/checkout", "v1")])

    def test_invalid_refs_rejected(self) -> None:
        for content in (
            "uses: actions/checkout@x..y\n",
            "uses: actions/checkout@v1@v2\n",
            "uses: actions/../checkout@v1\n",
            "uses: ${{ inputs.action }}\n",
        ):
            with self.subTest(content=content), self.assertRaises(pinning.PinError):
                scan_text(content)

    def test_line_numbers_come_from_compose_marks(self) -> None:
        _, uses = scan_text(
            "# leading comment\n"
            "steps:\n"
            "  # inner comment\n"
            "  - uses: actions/checkout@v1\n"
        )
        self.assertEqual([use.index for use in uses], [3])


if __name__ == "__main__":
    unittest.main()
