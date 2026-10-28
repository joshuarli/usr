#!/usr/bin/env python3
"""Regression tests for tools/usage/src/usage.

Run with: TMPDIR="$PWD/.work/tmp" python3 -I tools/usage/tests/test_usage.py
"""

import io
import json
import time as real_time
from typing import Any
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


def load_usage_namespace() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "src" / "usage"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("#!") and lines[1].startswith("exec python3")
    assert lines[-2].startswith("raise SystemExit") and lines[-1] == "PY"
    body = "\n".join(lines[2:-2])
    assert body.rstrip().endswith("return 1 if failures else 0")
    namespace: dict[str, Any] = {"__name__": "usage_under_test"}
    exec(compile(body, str(path), "exec"), namespace)
    return namespace


NS = load_usage_namespace()


class FakeProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def good_allowance(percent=26):
    return {
        "allowance": {
            "tier": "Muse Code Everyday Usage",
            "window": {"usedPercent": 0, "resetsAtMs": 1793241313000},
            "weekly": {"usedPercent": percent, "resetsAtMs": 1793577600000},
        },
        "reason": None,
        "hint": None,
    }


def server_gap_payload():
    return {"allowance": None, "reason": "server_sent_no_usage", "hint": None}


class QueryMuseTest(unittest.TestCase):
    def test_transient_server_gap_retries_and_recovers(self):
        responses = [
            FakeProcess(stdout=json.dumps(server_gap_payload())),
            FakeProcess(stdout=json.dumps(good_allowance())),
        ]
        calls = []
        sleeps = []

        def fake_run(*args, **kwargs):
            calls.append(args)
            return responses.pop(0)

        with (
            mock.patch.object(NS["subprocess"], "run", fake_run),
            mock.patch.object(NS["time"], "sleep", lambda seconds: sleeps.append(seconds)),
            mock.patch.dict(NS, {"muse_last_observed": lambda binary: None}),
        ):
            result = NS["query_muse"]("muse")

        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [2])
        self.assertEqual(result["allowance"]["weekly"]["usedPercent"], 26)

    def test_persistent_server_gap_reports_transient_error(self):
        gap = FakeProcess(stdout=json.dumps(server_gap_payload()))

        with (
            mock.patch.object(NS["subprocess"], "run", lambda *a, **k: gap),
            mock.patch.object(NS["time"], "sleep", lambda seconds: None),
            mock.patch.dict(NS, {"muse_last_observed": lambda binary: None}),
        ):
            with self.assertRaises(RuntimeError) as raised:
                NS["query_muse"]("muse")

        self.assertIn("transient", str(raised.exception))
        self.assertNotIn("server_sent_no_usage", str(raised.exception))

    def test_primary_failure_still_uses_last_observed(self):
        def fake_run(*args, **kwargs):
            raise RuntimeError("command failed")

        with (
            mock.patch.object(NS["subprocess"], "run", fake_run),
            mock.patch.dict(
                NS, {"muse_last_observed": lambda binary: {"usage": {"tier": "cached"}}}
            ),
        ):
            result = NS["query_muse"]("muse")

        self.assertEqual(result, {"usage": {"tier": "cached"}})

    def test_fast_path_makes_no_extra_calls(self):
        calls = []

        def fake_run(*args, **kwargs):
            calls.append(args)
            return FakeProcess(stdout=json.dumps(good_allowance()))

        def no_fallback(binary):
            raise AssertionError("must not call serve fallback")

        def no_sleep(seconds):
            raise AssertionError("must not sleep")

        with (
            mock.patch.object(NS["subprocess"], "run", fake_run),
            mock.patch.object(NS["time"], "sleep", no_sleep),
            mock.patch.dict(NS, {"muse_last_observed": no_fallback}),
        ):
            result = NS["query_muse"]("muse")

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["allowance"]["tier"], "Muse Code Everyday Usage")


class StreamingTest(unittest.TestCase):
    def test_renders_in_completion_order(self):
        order = []
        rendered = []

        def fast_query(binary):
            order.append("fast")
            return {"usage": "fast"}

        def slow_query(binary):
            real_time.sleep(0.3)
            order.append("slow")
            return {"usage": "slow"}

        def render(result):
            rendered.append(result["usage"])
            print(result["usage"])

        with (
            mock.patch.object(NS["shutil"], "which", lambda binary: f"/bin/{binary}"),
            mock.patch.dict(
                NS,
                {
                    "query_muse": fast_query,
                    "query_codex": slow_query,
                    "print_muse": render,
                    "print_codex": render,
                    "PROVIDERS": (("muse", "M", "m"), ("codex", "C", "c")),
                },
            ),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = NS["main"]([])

        self.assertEqual(exit_code, 0)
        self.assertEqual(order[0], "fast")
        self.assertEqual(rendered[0], "fast")
        out = buffer.getvalue()
        self.assertLess(out.index("fast"), out.index("slow"))


if __name__ == "__main__":
    unittest.main()
