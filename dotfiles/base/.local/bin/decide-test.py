#!/usr/bin/env python3

import importlib.util
import importlib.machinery
import http.server
import io
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import unittest
from typing import Any
from unittest import mock
import urllib.error
from pathlib import Path


SCRIPT = Path(__file__).with_name("decide")
LOADER = importlib.machinery.SourceFileLoader("decide", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("decide", LOADER)  # ty: ignore[invalid-argument-type] # typeshed LoaderProtocol still requires legacy load_module, which spec_from_loader never calls
assert SPEC is not None
DECIDE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = DECIDE
SPEC.loader.exec_module(DECIDE)


def sample_request() -> dict[str, Any]:
    return {
        "state": {"ticket": "checkout errors"},
        "questions": {
            "urgent": {
                "type": "noul",
                "instructions": "Is this urgent?",
                "criteria": {"true": "Blocks checkout", "false": "Minor issue"},
            },
            "team": {
                "type": "choice",
                "instructions": "Which team should respond?",
                "criteria": {"billing": "Payments", "technical": None},
            },
            "severity": {
                "type": "score",
                "instructions": {"question": "Rate the impact"},
                "criteria": ["Minor", "Major"],
            },
        },
    }


def sample_result(request, model="clef-flash") -> dict[str, Any]:
    answers = {}
    for question_id, question in request["questions"].items():
        if question["type"] == "noul":
            answers[question_id] = {"type": "noul", "noul": 0.8}
        elif question["type"] == "choice":
            options = list(question["criteria"])
            probabilities = {options[0]: 0.7, options[1]: 0.3}
            answers[question_id] = {
                "type": "choice",
                "choice": options[0],
                "probabilities": probabilities,
                "confidence": 0.7,
            }
        else:
            answers[question_id] = {
                "type": "score",
                "score": 0.3,
                "legend": {"0": "Minor", "1": "Major"},
                "probabilities": {"0": 0.7, "1": 0.3},
                "confidence": 0.7,
            }
    return {
        "model": model,
        "answers": answers,
        "usage": {"input_tokens": 32, "output_tokens": 12},
    }


def envelope(result, success=True, errors=None):
    return json.dumps(
        {
            "success": success,
            "errors": errors or [],
            "messages": [],
            "result": result,
        }
    ).encode()


def sample_eval_case(
    case_id,
    source_group,
    expected_tier="worker",
    acceptable_tiers=None,
    prediction=None,
    split="development",
    existing_choice="mechanic",
) -> dict[str, Any]:
    case = {
        "case_id": case_id,
        "source_group": source_group,
        "split": split,
        "state": {"synthetic": case_id},
        "question": {
            "type": "choice",
            "instructions": "Choose the appropriate orchestration tier.",
            "criteria": {tier: tier for tier in DECIDE.EVAL_TIERS},
        },
    }
    if expected_tier is not None:
        case["expected_tier"] = expected_tier
    if acceptable_tiers is not None:
        case["acceptable_tiers"] = acceptable_tiers
    if existing_choice is not None:
        case["existing_choice"] = existing_choice
    if prediction is not None:
        case["prediction"] = prediction
    return case


def recorded_prediction(status, tier=None, confidence=None, **metadata):
    prediction = {"status": status}
    if tier is not None:
        prediction["tier"] = tier
    if confidence is not None:
        prediction["confidence"] = confidence
    prediction.update(metadata)
    return prediction


def eval_jsonl(*cases):
    return b"\n".join(
        json.dumps(case, separators=(",", ":")).encode() for case in cases
    ) + b"\n"


class DecideTests(unittest.TestCase):
    def setUp(self):
        self.request = sample_request()
        self.env = {
            "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
            "CLOUDFLARE_API_TOKEN": "test-secret-value",
        }

    def response(self, result=None, status=200, body=None):
        return DECIDE.HttpResponse(
            status,
            body if body is not None else envelope(result or sample_result(self.request)),
        )

    def test_valid_request_supports_every_documented_question_type(self):
        self.assertEqual(DECIDE.validate_request(self.request), self.request)

    def test_request_rejects_unknown_fields_media_invalid_ids_and_models(self):
        cases = []
        extra = sample_request()
        extra["images"] = []
        cases.append(extra)
        bad_id = sample_request()
        bad_id["questions"]["bad/id"] = bad_id["questions"].pop("urgent")
        cases.append(bad_id)
        bad_question = sample_request()
        bad_question["questions"]["urgent"]["extra"] = True
        cases.append(bad_question)
        bad_choice = sample_request()
        bad_choice["questions"]["team"]["criteria"] = {"only": "One"}
        cases.append(bad_choice)
        bad_score = sample_request()
        bad_score["questions"]["severity"]["criteria"] = ["Only one"]
        cases.append(bad_score)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(DECIDE.InvalidInput):
                    DECIDE.validate_request(value)
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.parse_model("@cf/cloudflare/clef-flash")

    def test_input_rejects_nonfinite_values_duplicate_keys_and_excess_nesting(self):
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.parse_request_bytes(b'{"state":NaN,"questions":{}}')
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.parse_request_bytes(b'{"state":"a","state":"b","questions":{}}')
        nested = {"value": None}
        for _ in range(DECIDE.MAX_JSON_DEPTH + 2):
            nested = {"value": nested}
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.validate_request({"state": nested, "questions": {"q": {"type": "noul", "instructions": "q"}}})
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.parse_request_bytes(b" " * (DECIDE.MAX_REQUEST_BYTES + 1))

    def test_input_accepts_unicode_scalars_and_rejects_unpaired_surrogates(self):
        unicode_request = (
            b'{"state":"caf\xc3\xa9 \\ud83d\\ude00","questions":{"q":'
            b'{"type":"noul","instructions":"Is this true?"}}}'
        )
        request = DECIDE.parse_request_bytes(unicode_request)
        self.assertEqual(request["state"], "café 😀")
        serialized = []
        outcome = DECIDE.run_decision(
            request,
            env=self.env,
            transport=lambda url, headers, body, timeout: (
                serialized.append(body.decode("utf-8"))
                or DECIDE.HttpResponse(200, envelope(sample_result(request)))
            ),
        )
        self.assertEqual(outcome["status"], "ok")
        self.assertIn("café 😀", serialized[0])

        for escaped in (b"\\ud800", b"\\udfff"):
            data = b'{"state":"' + escaped + b'","questions":{"q":' + (
                b'{"type":"noul","instructions":"Is this true?"}}}'
            )
            with self.subTest(escaped=escaped):
                with self.assertRaises(DECIDE.InvalidInput):
                    DECIDE.parse_request_bytes(data)

        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.parse_request_bytes(
                b'{"state":"safe","questions":{"q":{"type":"noul",'
                b'"instructions":"\xff"}}}'
            )

    def test_jsonl_evaluation_rejects_surrogates_and_malformed_utf8(self):
        case = sample_eval_case(
            "unicode", "synthetic-unicode", prediction=recorded_prediction("ok", "worker")
        )
        case["state"] = "\ud800"
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.load_eval_cases(eval_jsonl(case))

        case["state"] = "sensitive-state"
        malformed = eval_jsonl(case).replace(b'"sensitive-state"', b'"\xff"')
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.load_eval_cases(malformed)

    def test_cli_malformed_unicode_has_one_safe_invalid_result(self):
        env = dict(os.environ)
        env.pop("CLOUDFLARE_ACCOUNT_ID", None)
        env.pop("CLOUDFLARE_API_TOKEN", None)
        inputs = (
            b'{"state":"private \\ud800","questions":{"q":'
            b'{"type":"noul","instructions":"Is this true?"}}}',
            b'{"state":"private \\udfff","questions":{"q":'
            b'{"type":"noul","instructions":"Is this true?"}}}',
            b'{"state":"private \xff","questions":{"q":'
            b'{"type":"noul","instructions":"Is this true?"}}}',
        )
        for data in inputs:
            with self.subTest(data=data):
                process = subprocess.run(
                    [sys.executable, "-I", str(SCRIPT)],
                    env=env,
                    input=data,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(process.returncode, 2)
                self.assertEqual(len(process.stdout.splitlines()), 1)
                self.assertEqual(json.loads(process.stdout)["status"], "invalid")
                self.assertNotIn(b"private", process.stdout + process.stderr)
                self.assertEqual(process.stderr, b"")

    def test_input_rejects_unhashable_question_types_and_null_criteria(self):
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.parse_request_bytes(
                b'{"state":"safe","questions":{"q":{"type":[],"instructions":"q"}}}'
            )
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.validate_request(
                {
                    "state": "safe",
                    "questions": {"q": {"type": "noul", "instructions": "q", "criteria": None}},
                }
            )
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.parse_model([])

    def test_valid_provider_result_preserves_all_question_types_and_usage(self):
        result = sample_result(self.request)
        self.assertEqual(DECIDE.validate_result(self.request, "clef-flash", result), result)

    def test_provider_result_rejects_missing_extra_wrong_id_type_model_and_probabilities(self):
        result = sample_result(self.request)
        invalid_results = []
        missing = sample_result(self.request)
        del missing["answers"]["team"]
        invalid_results.append(missing)
        extra = sample_result(self.request)
        extra["answers"]["unexpected"] = {"type": "noul", "noul": 0.4}
        invalid_results.append(extra)
        wrong_id = sample_result(self.request)
        wrong_id["answers"]["other"] = wrong_id["answers"].pop("urgent")
        invalid_results.append(wrong_id)
        wrong_type = sample_result(self.request)
        wrong_type["answers"]["team"]["type"] = "noul"
        invalid_results.append(wrong_type)
        wrong_model = sample_result(self.request, "clef")
        invalid_results.append(wrong_model)
        bad_choice = sample_result(self.request)
        bad_choice["answers"]["team"]["choice"] = "unknown"
        invalid_results.append(bad_choice)
        bad_distribution = sample_result(self.request)
        bad_distribution["answers"]["team"]["probabilities"] = {"billing": 0.4, "technical": 0.4}
        invalid_results.append(bad_distribution)
        bad_score = sample_result(self.request)
        bad_score["answers"]["severity"]["score"] = 2
        invalid_results.append(bad_score)
        bad_usage = sample_result(self.request)
        bad_usage["usage"]["input_tokens"] = -1
        invalid_results.append(bad_usage)
        nonfinite = sample_result(self.request)
        nonfinite["answers"]["urgent"]["noul"] = float("nan")
        invalid_results.append(nonfinite)
        for candidate in invalid_results:
            with self.subTest(candidate=candidate):
                with self.assertRaises(DECIDE.InvalidProviderResponse):
                    DECIDE.validate_result(self.request, "clef-flash", candidate)
        self.assertIsNotNone(result)

    def test_provider_result_rejects_wrong_choice_type_and_unbounded_numbers(self):
        wrong_choice = sample_result(self.request)
        wrong_choice["answers"]["team"]["choice"] = ["billing"]
        with self.assertRaises(DECIDE.InvalidProviderResponse):
            DECIDE.validate_result(self.request, "clef-flash", wrong_choice)
        huge_score = sample_result(self.request)
        huge_score["answers"]["severity"]["score"] = 10**4000
        with self.assertRaises(DECIDE.InvalidProviderResponse):
            DECIDE.validate_result(self.request, "clef-flash", huge_score)

    def test_provider_response_with_unpaired_surrogate_is_unavailable(self):
        result = sample_result(self.request)
        result["answers"]["severity"]["legend"]["0"] = "\ud800"
        outcome = DECIDE.run_decision(
            self.request,
            env=self.env,
            transport=lambda *args: DECIDE.HttpResponse(200, envelope(result)),
        )
        self.assertEqual(outcome, {"status": "unavailable", "reason": "invalid_provider_response"})
        self.assertNotIn("\\ud800", json.dumps(outcome))
        output = io.StringIO()
        DECIDE.print_json(outcome, output)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(json.loads(output.getvalue()), outcome)

    def test_http_redirect_does_not_read_response_body(self):
        body = mock.Mock()
        body.read.side_effect = AssertionError("redirect body must not be read")
        headers: Any = {}
        error = urllib.error.HTTPError("https://example.invalid", 302, "Found", headers, body)
        opener = mock.Mock()
        opener.open.side_effect = error
        with mock.patch.object(DECIDE.urllib.request, "build_opener", return_value=opener):
            response = DECIDE.http_post(
                "https://example.invalid", {"Authorization": "Bearer test"}, b"{}", 1
            )
        self.assertEqual(response, DECIDE.HttpResponse(302, b""))
        body.read.assert_not_called()

    def test_http_redirect_does_not_forward_authorization_or_change_cli_output(self):
        origin_authorization = []
        destination_requests = []

        class DestinationHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                destination_requests.append(("GET", self.headers.get("Authorization")))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):
                destination_requests.append(("POST", self.headers.get("Authorization")))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                return

        destination = http.server.ThreadingHTTPServer(("127.0.0.1", 0), DestinationHandler)
        destination_thread = None
        destination_url = f"http://localhost:{destination.server_port}/collect"

        class OriginHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                origin_authorization.append(self.headers.get("Authorization"))
                self.send_response(302)
                self.send_header("Location", destination_url)
                self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                return

        origin = None
        origin_thread = None
        try:
            destination_thread = threading.Thread(target=destination.serve_forever, daemon=True)
            destination_thread.start()
            origin = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OriginHandler)
            origin_thread = threading.Thread(target=origin.serve_forever, daemon=True)
            origin_thread.start()
            output = io.StringIO()
            with mock.patch.object(
                DECIDE, "endpoint", return_value=f"http://127.0.0.1:{origin.server_port}/run"
            ):
                status = DECIDE.main(
                    [],
                    env=self.env,
                    stdin=io.BytesIO(json.dumps(self.request).encode()),
                    stdout=output,
                )
            self.assertEqual(status, 0)
            self.assertEqual(len(origin_authorization), 1)
            self.assertEqual(origin_authorization, ["Bearer test-secret-value"])
            self.assertEqual(destination_requests, [])
            self.assertEqual(len(output.getvalue().splitlines()), 1)
            self.assertEqual(
                json.loads(output.getvalue()),
                {"status": "unavailable", "reason": "provider_failure"},
            )
            self.assertNotIn("test-secret-value", output.getvalue())
        finally:
            if origin_thread is not None and origin_thread.is_alive():
                origin.shutdown()
            if origin is not None:
                origin.server_close()
            if origin_thread is not None:
                origin_thread.join()
            if destination_thread is not None and destination_thread.is_alive():
                destination.shutdown()
            destination.server_close()
            if destination_thread is not None:
                destination_thread.join()

    def test_client_serializes_selected_model_and_uses_one_bounded_request(self):
        calls = []
        ticks = iter([10.0, 10.025])

        def transport(url, headers, body, timeout):
            calls.append((url, headers, json.loads(body), timeout))
            return self.response(result=sample_result(self.request, "clef"))

        outcome = DECIDE.run_decision(
            self.request, "clef", self.env, transport=transport, clock=lambda: next(ticks)
        )
        self.assertEqual(outcome["status"], "ok")
        self.assertEqual(outcome["elapsed_ms"], 25.0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], DECIDE.endpoint(self.env["CLOUDFLARE_ACCOUNT_ID"], "clef"))
        self.assertEqual(calls[0][1]["Authorization"], "Bearer test-secret-value")
        self.assertEqual(calls[0][2]["model"], "clef")
        self.assertEqual(calls[0][3], DECIDE.REQUEST_TIMEOUT_SECONDS)

    def test_invalid_input_never_calls_transport(self):
        outcome = DECIDE.run_decision(
            {"state": "safe", "questions": {}},
            "clef-flash",
            self.env,
            transport=lambda *args: self.fail("transport called"),
        )
        self.assertEqual(outcome["status"], "invalid")

    def test_missing_credentials_are_unavailable_without_transport(self):
        outcome = DECIDE.run_decision(
            self.request,
            "clef-flash",
            {},
            transport=lambda *args: self.fail("transport called"),
        )
        self.assertEqual(outcome["status"], "unavailable")
        self.assertEqual(outcome["reason"], "missing_configuration")
        self.assertEqual(
            outcome["missing"], ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"]
        )

    def test_transport_failures_map_to_stable_reasons_without_details(self):
        failures = [
            (TimeoutError("secret-bearing detail"), "timeout"),
            (urllib.error.URLError(socket.gaierror("private hostname")), "dns_error"),
            (urllib.error.URLError(ssl.SSLError("private TLS detail")), "tls_error"),
        ]
        for failure, reason in failures:
            with self.subTest(reason=reason):
                outcome = DECIDE.run_decision(
                    self.request,
                    "clef-flash",
                    self.env,
                    transport=lambda *args, failure=failure: (_ for _ in ()).throw(failure),
                )
                self.assertEqual(outcome["status"], "unavailable")
                self.assertEqual(outcome["reason"], reason)
                self.assertNotIn(str(failure), json.dumps(outcome))

    def test_http_and_cloudflare_errors_map_auth_quota_capacity_and_provider_failure(self):
        cases = [
            (401, b"not-json", "authentication"),
            (403, b"not-json", "authentication"),
            (429, envelope({}, success=False, errors=[{"code": 3036, "message": "secret"}]), "quota_exhausted"),
            (429, envelope({}, success=False, errors=[{"code": 3040}]), "capacity"),
            (429, b"not-json", "rate_limited"),
            (503, b"private response body", "provider_failure"),
            (200, envelope({}, success=False, errors=[{"code": 9999, "message": "private"}]), "provider_failure"),
        ]
        for status, body, reason in cases:
            with self.subTest(status=status, reason=reason):
                outcome = DECIDE.run_decision(
                    self.request,
                    "clef-flash",
                    self.env,
                    transport=lambda *args, status=status, body=body: DECIDE.HttpResponse(status, body),
                )
                self.assertEqual(outcome["status"], "unavailable")
                self.assertEqual(outcome["reason"], reason)
                self.assertNotIn("private", json.dumps(outcome))
                self.assertNotIn("secret", json.dumps(outcome))

    def test_malformed_or_truncated_provider_response_is_unavailable(self):
        cases = [
            b"not-json",
            json.dumps({"success": True, "errors": [], "messages": []}).encode(),
            b" " * (DECIDE.MAX_RESPONSE_BYTES + 1),
        ]
        for body in cases:
            with self.subTest(length=len(body)):
                outcome = DECIDE.run_decision(
                    self.request,
                    "clef-flash",
                    self.env,
                    transport=lambda *args, body=body: DECIDE.HttpResponse(200, body),
                )
                self.assertEqual(outcome["status"], "unavailable")
                self.assertEqual(outcome["reason"], "invalid_provider_response")

    def test_context_limit_makes_advice_unavailable(self):
        result = sample_result(self.request)
        result["usage"]["input_tokens"] = DECIDE.CONTEXT_WINDOW_TOKENS
        outcome = DECIDE.run_decision(
            self.request,
            "clef-flash",
            self.env,
            transport=lambda *args: self.response(result=result),
        )
        self.assertEqual(outcome["status"], "unavailable")
        self.assertEqual(outcome["reason"], "context_limit")

    def test_doctor_is_local_only_and_does_not_print_secret_values(self):
        env = dict(os.environ)
        env["CLOUDFLARE_ACCOUNT_ID"] = self.env["CLOUDFLARE_ACCOUNT_ID"]
        env["CLOUDFLARE_API_TOKEN"] = self.env["CLOUDFLARE_API_TOKEN"]
        process = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "doctor"],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(len(process.stdout.splitlines()), 1)
        self.assertNotIn(self.env["CLOUDFLARE_API_TOKEN"], process.stdout + process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "ok")

        missing_env = dict(os.environ)
        missing_env.pop("CLOUDFLARE_ACCOUNT_ID", None)
        missing_env.pop("CLOUDFLARE_API_TOKEN", None)
        missing = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "doctor"],
            env=missing_env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertEqual(json.loads(missing.stdout)["reason"], "missing_configuration")

    def test_cli_emits_one_json_result_with_fail_open_and_invalid_exit_codes(self):
        env = dict(os.environ)
        env.pop("CLOUDFLARE_ACCOUNT_ID", None)
        env.pop("CLOUDFLARE_API_TOKEN", None)
        valid = subprocess.run(
            [sys.executable, "-I", str(SCRIPT)],
            env=env,
            input=json.dumps(self.request),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(valid.returncode, 0)
        self.assertEqual(len(valid.stdout.splitlines()), 1)
        self.assertEqual(json.loads(valid.stdout)["reason"], "missing_configuration")
        self.assertEqual(valid.stderr, "")

        invalid_request = {
            "state": "safe",
            "questions": {"q": {"type": [], "instructions": "q"}},
        }
        invalid = subprocess.run(
            [sys.executable, "-I", str(SCRIPT)],
            env=env,
            input=json.dumps(invalid_request),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(len(invalid.stdout.splitlines()), 1)
        self.assertEqual(json.loads(invalid.stdout)["status"], "invalid")
        self.assertEqual(invalid.stderr, "")

    def test_offline_evaluation_reports_agreement_errors_confidence_and_unknown_usage(self):
        cases = [
            sample_eval_case(
                "exact",
                "synthetic-source-a",
                prediction=recorded_prediction(
                    "ok",
                    "worker",
                    0.9,
                    input_tokens=20,
                    elapsed_ms=15.0,
                    model="clef-flash",
                ),
            ),
            sample_eval_case(
                "acceptable",
                "synthetic-source-a",
                expected_tier=None,
                acceptable_tiers=["expert", "worker"],
                prediction=recorded_prediction(
                    "ok", "expert", 0.7, model="clef-flash"
                ),
                existing_choice="worker",
            ),
            sample_eval_case(
                "down-tier",
                "synthetic-source-b",
                expected_tier="expert",
                prediction=recorded_prediction(
                    "ok", "mechanic", 0.3, input_tokens=8, model="clef"
                ),
                existing_choice="expert",
            ),
            sample_eval_case(
                "escalation",
                "synthetic-source-c",
                expected_tier="mechanic",
                prediction=recorded_prediction(
                    "ok", "god", 0.8, input_tokens=4, model="clef"
                ),
                existing_choice="mechanic",
            ),
            sample_eval_case(
                "both-wrong",
                "synthetic-source-f",
                expected_tier="expert",
                prediction=recorded_prediction(
                    "ok", "mechanic", 0.4, model="clef-flash"
                ),
                existing_choice="worker",
            ),
            sample_eval_case(
                "abstain",
                "synthetic-source-d",
                prediction=recorded_prediction("abstain"),
                existing_choice=None,
            ),
            sample_eval_case(
                "unavailable",
                "synthetic-source-e",
                prediction=recorded_prediction("unavailable"),
                split="held-out",
                existing_choice="worker",
            ),
        ]
        report = DECIDE.evaluate_jsonl(
            eval_jsonl(*cases), transport=lambda *args: self.fail("network used")
        )
        self.assertEqual(report["mode"], "offline")
        self.assertEqual(report["request_count"], 0)
        self.assertEqual(report["cases"], 7)
        self.assertEqual(report["exact_agreement"], {"correct": 1, "cases": 6, "rate": 0.167})
        self.assertEqual(report["acceptable_agreement"], {"correct": 2, "cases": 7, "rate": 0.286})
        self.assertEqual(report["wrong_down_tier_choices"], 2)
        self.assertEqual(report["unnecessary_escalations"], 1)
        self.assertEqual(report["abstentions"], 1)
        self.assertEqual(report["unavailable"], 1)
        self.assertEqual(report["confidence_by_correctness"]["high"], {"correct": 1, "incorrect": 1})
        self.assertEqual(report["input_tokens"]["known_total"], 32)
        self.assertEqual(report["input_tokens"]["total"], "unknown")
        self.assertEqual(report["cost"], "unknown")
        self.assertEqual(report["models"], ["clef", "clef-flash"])
        self.assertEqual(report["latency"]["median_ms"], "unknown")
        self.assertEqual(report["existing_choice_comparison"]["higher"], 3)
        policy = report["policy_comparison"]
        self.assertEqual(policy["cases_with_existing_choice"], 6)
        self.assertEqual(policy["cases_without_existing_choice"], 1)
        self.assertEqual(
            policy["existing_policy_acceptable_agreement"],
            {"correct": 4, "cases": 6, "rate": 0.667},
        )
        self.assertEqual(
            policy["standalone_clef"]["acceptable_tier_agreement"],
            {"correct": 2, "cases": 5, "rate": 0.4},
        )
        self.assertEqual(policy["standalone_clef"]["unavailable_cases"], 1)
        self.assertEqual(
            policy["unavailable_clef_decisions"],
            {"with_existing_choice": 1, "without_existing_choice": 0},
        )
        comparison = policy["matched_successful_comparison"]
        self.assertEqual(
            comparison["existing_policy_acceptable_agreement"],
            {"correct": 3, "cases": 5, "rate": 0.6},
        )
        self.assertEqual(
            comparison["clef_acceptable_tier_agreement"],
            {"correct": 2, "cases": 5, "rate": 0.4},
        )
        self.assertEqual(comparison["correctness_delta"], {"correct": -1, "cases": 5, "rate": -0.2})
        self.assertEqual(comparison["clef_improves_existing_policy"], 1)
        self.assertEqual(comparison["clef_makes_correct_existing_policy_worse"], 2)
        self.assertEqual(comparison["both_wrong"], 1)
        self.assertEqual(comparison["wrong_down_tier_recommendations"], 2)
        self.assertEqual(
            policy["hypothetical_unconditional_adoption"]["acceptable_tier_agreement"],
            {"correct": 3, "cases": 6, "rate": 0.5},
        )
        self.assertEqual(
            policy["hypothetical_unconditional_adoption"][
                "fallback_cases_to_existing_choice"
            ],
            1,
        )
        self.assertEqual(report["by_split"]["held-out"]["unavailable"], 1)
        self.assertEqual(
            report["by_split"]["held-out"]["policy_comparison"]["hypothetical_unconditional_adoption"]["acceptable_tier_agreement"],
            {"correct": 1, "cases": 1, "rate": 1.0},
        )
        self.assertNotIn("synthetic", json.dumps(report))
        matrix = {tuple(row["expected"]): row["predicted"] for row in report["confusion_matrix"]}
        self.assertEqual(matrix[("worker",)]["worker"], 1)
        self.assertEqual(matrix[("worker",)]["abstain"], 1)
        self.assertEqual(matrix[("worker",)]["unavailable"], 1)
        self.assertEqual(sum(sum(row.values()) for row in matrix.values()), 7)

    def test_evaluation_rejects_duplicate_ids_source_leakage_and_bad_labels(self):
        first = sample_eval_case(
            "same-source-dev",
            "shared",
            prediction=recorded_prediction("ok", "worker", 0.8),
        )
        second = sample_eval_case(
            "same-source-held-out",
            "shared",
            prediction=recorded_prediction("ok", "worker", 0.8),
            split="held-out",
        )
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.load_eval_cases(eval_jsonl(first, first), live=False, max_calls=None)
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.load_eval_cases(eval_jsonl(first, second), live=False, max_calls=None)
        bad_label = sample_eval_case(
            "bad-label",
            "bad-source",
            expected_tier="unlisted",
            prediction=recorded_prediction("ok", "worker", 0.8),
        )
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.load_eval_cases(eval_jsonl(bad_label), live=False, max_calls=None)

    def test_live_evaluation_requires_an_explicit_bounded_dataset_and_uses_client(self):
        cases = [
            sample_eval_case(
                "live-1", "synthetic-live-1", expected_tier="worker", prediction=None
            )
        ]
        cases[0]["question"]["criteria"] = {
            tier: tier for tier in DECIDE.LIVE_EVAL_TIERS
        }
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.evaluate_jsonl(eval_jsonl(*cases), transport=lambda *args: self.fail("network used"))
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.evaluate_jsonl(
                eval_jsonl(*cases), live=True, max_calls=None, transport=lambda *args: self.fail("network used")
            )
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.evaluate_jsonl(
                eval_jsonl(*cases), live=True, max_calls=51, transport=lambda *args: self.fail("network used")
            )
        too_many = cases * 2
        with self.assertRaises(DECIDE.InvalidInput):
            DECIDE.evaluate_jsonl(
                eval_jsonl(*too_many), live=True, max_calls=1, transport=lambda *args: self.fail("network used")
            )

        calls = []

        def transport(url, headers, body, timeout):
            calls.append((url, headers, body, timeout))
            request = json.loads(body)
            tiers = list(request["questions"]["tier"]["criteria"])
            other_probability = 0.4 / (len(tiers) - 1)
            probabilities = {
                tier: (0.6 if tier == "worker" else other_probability)
                for tier in tiers
            }
            result = {
                "model": "clef-flash",
                "answers": {
                    "tier": {
                        "type": "choice",
                        "choice": "worker",
                        "probabilities": probabilities,
                        "confidence": 0.6,
                    }
                },
                "usage": {"input_tokens": 10, "output_tokens": 2},
            }
            return DECIDE.HttpResponse(200, envelope(result))

        report = DECIDE.evaluate_jsonl(
            eval_jsonl(*cases),
            live=True,
            max_calls=1,
            env=self.env,
            transport=transport,
            clock=lambda: 1.0,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["request_count"], 1)
        self.assertEqual(report["acceptable_agreement"]["correct"], 1)
        self.assertEqual(report["input_tokens"]["total"], 10)

    def test_live_evaluation_rejects_ineligible_tier_options(self):
        for forbidden_tier in ("scout", "god"):
            with self.subTest(forbidden_tier=forbidden_tier):
                case = sample_eval_case(
                    f"live-{forbidden_tier}",
                    f"synthetic-live-{forbidden_tier}",
                    prediction=None,
                    existing_choice="worker",
                )
                case["question"]["criteria"] = {
                    "worker": "Known method",
                    "expert": "Uncertain path",
                    forbidden_tier: "Not eligible for live routing",
                }
                with self.assertRaises(DECIDE.InvalidInput):
                    DECIDE.load_eval_cases(
                        eval_jsonl(case), live=True, max_calls=1
                    )

        case = sample_eval_case(
            "live-eligible",
            "synthetic-live-eligible",
            prediction=None,
        )
        case["question"]["criteria"] = {
            tier: tier for tier in DECIDE.LIVE_EVAL_TIERS
        }
        loaded = DECIDE.load_eval_cases(eval_jsonl(case), live=True, max_calls=1)
        self.assertEqual(
            set(loaded[0]["request"]["questions"]["tier"]["criteria"]),
            set(DECIDE.LIVE_EVAL_TIERS),
        )

    def test_latency_uses_median_and_nearest_rank_p95_only_after_twenty_successes(self):
        cases = [
            sample_eval_case(
                f"latency-{index}",
                f"synthetic-latency-{index}",
                prediction=recorded_prediction(
                    "ok", "worker", 0.8, elapsed_ms=float(index + 1), model="clef-flash"
                ),
            )
            for index in range(20)
        ]
        report = DECIDE.evaluate_jsonl(eval_jsonl(*cases))
        self.assertEqual(report["latency"]["median_ms"], 10.5)
        self.assertEqual(report["latency"]["p95_ms"], 19.0)

        short_report = DECIDE.evaluate_jsonl(eval_jsonl(*cases[:19]))
        self.assertEqual(short_report["latency"]["median_ms"], "unknown")
        self.assertEqual(short_report["latency"]["p95_ms"], "unknown")


if __name__ == "__main__":
    unittest.main()
