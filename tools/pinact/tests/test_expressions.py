"""Expression lexer/parser/scanner/context tests.

Run with an isolated interpreter::

    python3 -I tools/pinact/tests/test_expressions.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SRC = HERE.parents[1] / "src"
sys.path.insert(0, str(SRC))

from pinact import expressions as E  # noqa: E402


class LexerTests(unittest.TestCase):
    def test_identifiers_strings_escapes(self) -> None:
        tokens, err = E.lex("github 'it''s' \"hi\"")
        self.assertIsNone(err)
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, ["ident", "string", "string"])
        self.assertEqual(tokens[1].value, "it's")

    def test_numbers_booleans_null(self) -> None:
        tokens, err = E.lex("123 true FALSE null 3.14")
        self.assertIsNone(err)
        self.assertEqual([t.kind for t in tokens], ["number", "bool", "bool", "null", "number"])

    def test_operators_parens_bang(self) -> None:
        tokens, err = E.lex("!a && b || c == d != e < f <= g > h >= i (j)")
        self.assertIsNone(err)
        self.assertIn("!", [t.kind for t in tokens])
        self.assertIn("op", [t.kind for t in tokens])

    def test_unterminated_string_is_error(self) -> None:
        _, err = E.lex("'abc")
        self.assertIsNotNone(err)

    def test_whitespace_multiline(self) -> None:
        tokens, err = E.lex("  contains(\n 'a',\n 'b' ) ")
        self.assertIsNone(err)
        self.assertEqual(tokens[0].value, "contains")


class ParserTests(unittest.TestCase):
    def test_precedence_and_parens(self) -> None:
        node, err = E.parse_expression("a || b && !c")
        self.assertIsNone(err)
        self.assertEqual(node.kind, "or")
        node, err = E.parse_expression("(a || b) && c")
        self.assertIsNone(err)
        self.assertEqual(node.kind, "and")

    def test_comparisons(self) -> None:
        for src in ("a == b", "a != b", "a < b", "a <= b", "a > b", "a >= b"):
            with self.subTest(src=src):
                node, err = E.parse_expression(src)
                self.assertIsNone(err)
                self.assertEqual(node.kind, "cmp")

    def test_property_index_wildcard(self) -> None:
        for src in ("github.ref", "matrix.os", "steps.build.outputs.x",
                    "fromJSON(matrix.include)[0]", "matrix.*", "steps.*"):
            with self.subTest(src=src):
                node, err = E.parse_expression(src)
                self.assertIsNone(err, src)

    def test_nested_calls(self) -> None:
        node, err = E.parse_expression("contains(toJSON(matrix.os), 'x')")
        self.assertIsNone(err)
        self.assertEqual(node.kind, "call")
        self.assertEqual(node.children[0].kind, "call")

    def test_syntax_errors(self) -> None:
        for src in ("", "a ==", "contains(", "a &&", "(a", "a)", ".foo"):
            with self.subTest(src=src):
                _, err = E.parse_expression(src)
                self.assertIsNotNone(err, src)


class ScannerTests(unittest.TestCase):
    def test_respects_quotes_and_delimiters(self) -> None:
        text = "${{ '}}' }} trailing"
        found, errors = E.scan_interpolations(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].inner.strip(), "'}}'")

    def test_double_quoted_braces(self) -> None:
        text = '${{ "}}" }}'
        found, errors = E.scan_interpolations(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(found), 1)

    def test_missing_delimiter(self) -> None:
        found, errors = E.scan_interpolations("${{ github.ref ")
        self.assertEqual(found, [])
        self.assertEqual(len(errors), 1)

    def test_multiple_and_multiline(self) -> None:
        text = "a ${{ github.ref }} b ${{\n matrix.os\n }} c"
        found, errors = E.scan_interpolations(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(found), 2)

    def test_naive_next_brace_would_fail(self) -> None:
        text = "${{ format('{0} }}', github.ref) }}"
        found, errors = E.scan_interpolations(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(found), 1)
        node, err = E.parse_expression(found[0].inner)
        self.assertIsNone(err, found[0].inner)


class ContextTests(unittest.TestCase):
    def setUp(self) -> None:
        E.reset_unsupported_count()
        self.ctx = E.Context(
            job_ids={"build", "test"},
            step_ids_by_job={"build": {"one"}},
            needs_by_job={"test": {"build"}},
            matrix_keys={"build": {"os"}},
            matrix_jobs={"build"},
            inputs={"name"},
            location="test",
        )
        self.build_ctx = E.Context(
            job_ids={"build", "test"},
            step_ids_by_job={"build": {"one"}},
            needs_by_job={"test": {"build"}},
            matrix_keys={"build": {"os"}},
            matrix_jobs={"build"},
            inputs={"name"},
            location="build",
        )

    def test_needs_known_vs_unknown(self) -> None:
        status, _ = E.analyze_expression("needs.build.outputs.x", self.ctx)
        self.assertIn(status, ("valid", "valid-unknown"))
        status, msg = E.analyze_expression("needs.nope.outputs.x", self.ctx)
        self.assertEqual(status, "semantic-error")
        self.assertIn("nope", msg)

    def test_static_vs_dynamic_matrix(self) -> None:
        status, msg = E.analyze_expression("matrix.bogus", self.build_ctx)
        self.assertEqual(status, "semantic-error")
        status, _ = E.analyze_expression("matrix.os", self.build_ctx)
        self.assertIn(status, ("valid", "valid-unknown"))
        status, _ = E.analyze_expression("fromJSON(inputs.name).os", self.ctx)
        self.assertEqual(status, "valid-unknown")

    def test_matrix_unavailable_without_strategy(self) -> None:
        ctx = E.Context(job_ids={"build"}, location="build")
        status, message = E.analyze_expression("matrix.os", ctx)
        self.assertEqual(status, "semantic-error")
        self.assertIn("matrix", message)

    def test_dynamic_matrix_keeps_keys_unknown(self) -> None:
        ctx = E.Context(job_ids={"build"}, matrix_jobs={"build"}, location="build")
        status, _ = E.analyze_expression("matrix.os", ctx)
        self.assertEqual(status, "valid-unknown")

    def test_steps_inputs(self) -> None:
        status, msg = E.analyze_expression("steps.bogus.outputs.x", self.build_ctx)
        self.assertEqual(status, "semantic-error")
        status, _ = E.analyze_expression("steps.one.outputs.x", self.build_ctx)
        self.assertIn(status, ("valid", "valid-unknown"))
        status, msg = E.analyze_expression("inputs.bogus", self.ctx)
        self.assertEqual(status, "semantic-error")


class BuiltinTests(unittest.TestCase):
    def test_case_insensitivity(self) -> None:
        for name in ("CONTAINS", "Contains", "contains"):
            with self.subTest(name=name):
                status, _ = E.analyze_expression(f"{name}('a', 'b')", E.Context())
                self.assertIn(status, ("valid", "valid-unknown", "semantic-error"))
                self.assertNotEqual(status, "unsupported")

    def test_arity_checks(self) -> None:
        cases = [
            ("contains('a')", True), ("contains('a','b','c')", True),
            ("contains('a','b')", False),
            ("startsWith('a','b')", False), ("endsWith('a','b')", False),
            ("format('x')", False), ("format('x','y')", False),
            ("join('a')", False), ("join('a','b','c')", True),
            ("toJSON('a')", False), ("fromJSON('a')", False),
            ("hashFiles('a')", False), ("hashFiles()", True),
            ("success()", False), ("success('a')", True),
            ("failure()", False), ("cancelled()", False), ("always()", False),
        ]
        for src, is_error in cases:
            with self.subTest(src=src):
                E.reset_unsupported_count()
                status, msg = E.analyze_expression(src, E.Context())
                if is_error:
                    self.assertEqual(status, "semantic-error", src)
                else:
                    self.assertIn(status, ("valid", "valid-unknown"), f"{src}: {msg}")

    def test_unknown_function_is_not_error(self) -> None:
        E.reset_unsupported_count()
        before = E.get_unsupported_count()
        status, _ = E.analyze_expression("mystery('a')", E.Context())
        self.assertEqual(status, "valid-unknown")
        self.assertGreater(E.get_unsupported_count(), before)

    def test_high_confidence_only(self) -> None:
        status, _ = E.analyze_expression("fromJSON(inputs.config).anything", E.Context(inputs={"config"}))
        self.assertEqual(status, "valid-unknown")
        status, _ = E.analyze_expression("github.ref", E.Context())
        self.assertIn(status, ("valid", "valid-unknown"))


class OutcomeTests(unittest.TestCase):
    def test_four_way_outcomes(self) -> None:
        E.reset_unsupported_count()
        status, _ = E.analyze_expression("github.ref", E.Context())
        self.assertIn(status, ("valid", "valid-unknown"))
        status, _ = E.analyze_expression("mystery('a')", E.Context())
        self.assertEqual(status, "valid-unknown")
        status, _ = E.analyze_expression("foo.*.bar", E.Context())
        self.assertEqual(status, "unsupported")
        status, _ = E.analyze_expression("a ==", E.Context())
        self.assertEqual(status, "syntax-error")
        status, _ = E.analyze_expression("contains('a')", E.Context())
        self.assertEqual(status, "semantic-error")

    def test_unsupported_rate_counter(self) -> None:
        E.reset_unsupported_count()
        E.analyze_expression("mystery('a')", E.Context())
        E.analyze_expression("foo.bar", E.Context())
        self.assertGreaterEqual(E.get_unsupported_count(), 2)


if __name__ == "__main__":
    unittest.main()
