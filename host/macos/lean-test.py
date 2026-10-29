#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import plistlib
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("macos_lean", Path(__file__).with_name("lean.py"))
assert spec is not None
lean = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = lean
spec.loader.exec_module(lean)


class CommandFailureTests(unittest.TestCase):
    def run_sudo(self, argv, *, check):
        return subprocess.run(argv, capture_output=True, text=True, check=check)

    def sudo_worker(self):
        return SimpleNamespace(run=self.run_sudo)

    def failed_command(self, argv, **kwargs):
        result = subprocess.CompletedProcess(argv, 7, "", "permission denied")
        if kwargs.get("check"):
            result.check_returncode()
        return result

    def test_requested_mutations_abort_before_success(self):
        operations = (
            (lean.apply_spotlight_tmutil, "Indexing disabled", "Spotlight indexing re-enabled"),
            (lean.apply_pmset, "Power Nap, TCP keepalive", "pmset battery defaults restored"),
            (lean.apply_ipv6, "IPv6 disabled", "IPv6 restored"),
            (lean.apply_logging, "Unified logging disabled", "Unified logging restored"),
        )
        for operation, apply_success, revert_success in operations:
            for mode, success in (("apply", apply_success), ("revert", revert_success)):
                step = "mutation %s %s aborts before success" % (operation.__name__, mode)
                state = lean.State(mode, 501, "27.0", "Golden Gate", "27")
                output = io.StringIO()
                with patch.object(lean, "sudo_worker", self.sudo_worker()), \
                        patch.object(lean.subprocess, "run", side_effect=self.failed_command), \
                        patch.object(lean, "list_network_services", return_value=["Wi-Fi"]), \
                        contextlib.redirect_stdout(output):
                    with self.assertRaises(subprocess.CalledProcessError, msg=step) as caught:
                        operation(state)
                self.assertEqual(caught.exception.returncode, 7, step)
                self.assertEqual(caught.exception.stderr, "permission denied", step)
                self.assertNotIn(success, output.getvalue(), step)

    def test_missing_mutation_executable_raises(self):
        with patch.object(lean, "sudo_worker", self.sudo_worker()), \
                patch.object(lean.subprocess, "run", side_effect=FileNotFoundError("missing tool")):
            with self.assertRaises(FileNotFoundError):
                lean.run(["mdutil", "-a", "-i", "off"], sudo=True)

    def test_failed_preferences_and_service_mutations_do_not_count_as_applied(self):
        for mode in ("apply", "revert"):
            for domain in ("user", "system"):
                step = "failed %s %s mutation counts nothing as applied" % (mode, domain)
                state = lean.State(mode, 501, "27.0", "Golden Gate", "27")
                state.real_labels.add("com.apple.example")
                with patch.object(lean, "sudo_worker", self.sudo_worker()), \
                        patch.object(lean.subprocess, "run", side_effect=self.failed_command), \
                        contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(subprocess.CalledProcessError, msg=step):
                        if domain == "user":
                            lean.disable_user(state, "com.apple.example")
                        else:
                            lean.disable_system(state, "com.apple.example")
                            lean.flush_system(state)
                self.assertEqual(state.n_applied, 0, step)
                self.assertEqual(state.disabled_user, set(), step)
                self.assertEqual(state.disabled_system, set(), step)
        with patch.object(lean, "sudo_worker", self.sudo_worker()), \
                patch.object(lean.subprocess, "run", side_effect=self.failed_command):
            with self.assertRaises(subprocess.CalledProcessError):
                lean.ensure_default(lean.MDNS_DEFAULT)
            with self.assertRaises(subprocess.CalledProcessError):
                lean.defaults_delete("example", "key")

    def test_failed_service_discovery_does_not_report_empty_network(self):
        with patch.object(lean.subprocess, "run", side_effect=self.failed_command):
            with self.assertRaises(subprocess.CalledProcessError):
                lean.list_network_services()

    def test_defaults_delete_already_absent_key_is_unchanged(self):
        exported = subprocess.CompletedProcess(["defaults", "export", "example", "-"], 0,
                                               plistlib.dumps({}).decode(), "")
        with patch.object(lean, "run", return_value=exported) as command:
            lean.defaults_delete("example", "MissingKey", sudo=True)
        command.assert_called_once_with(["defaults", "export", "example", "-"], sudo=True)

    def test_defaults_delete_existing_key_propagates_delete_failure(self):
        exported = subprocess.CompletedProcess(["defaults", "export", "example", "-"], 0,
                                               plistlib.dumps({"ExistingKey": True}).decode(), "")
        failure = subprocess.CalledProcessError(1, ["defaults", "delete", "example", "ExistingKey"],
                                               stderr="permission denied")
        with patch.object(lean, "run", side_effect=[exported, failure]) as command:
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                lean.defaults_delete("example", "ExistingKey")
        self.assertIs(caught.exception, failure)
        self.assertEqual(command.call_args.args[0], ["defaults", "delete", "example", "ExistingKey"])

    def test_expected_unsuccessful_probes_return_status(self):
        with patch.object(lean, "sudo_worker", self.sudo_worker()), \
                patch.object(lean.subprocess, "run", side_effect=self.failed_command):
            self.assertIsNone(lean.defaults_read(lean.MDNS_DEFAULT))
            self.assertEqual(lean.sw_vers("buildVersion"), "unknown")
            self.assertEqual(lean.run(["pgrep", "-x", "Dock"], check=False).returncode, 7)

    def test_performance_defaults_attempt_every_preference(self):
        values = [True] + [False] * (len(lean.PERFORMANCE_DEFAULTS) - 1)
        state = lean.State("apply", 501, "27.0", "Golden Gate", "27")
        with patch.object(lean, "ensure_default", side_effect=values) as ensure_default, \
                patch.object(lean, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()):
            lean.apply_performance_defaults(state)
        self.assertEqual(ensure_default.call_count, len(lean.PERFORMANCE_DEFAULTS))
        run.assert_called_once_with(["killall", "Dock"])

    def test_failed_cli_command_reports_failure_and_stops_keepalive(self):
        output, errors = io.StringIO(), io.StringIO()
        failure = subprocess.CalledProcessError(7, ["sudo", "mdutil"], stderr="permission denied")
        with patch.object(lean, "sw_vers", return_value="27.0"), \
                patch.object(lean, "build_label_index", return_value=set()), \
                patch.object(lean, "load_disabled_state"), \
                patch.object(lean, "DISABLE_SECTIONS", []), \
                patch.object(lean, "SudoWorker") as worker, \
                patch.object(lean, "apply_spotlight_tmutil", side_effect=failure), \
                patch.object(lean, "print_summary") as summary, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(lean.main([]), 1)
        worker.return_value.stop.assert_called_once()
        summary.assert_not_called()
        self.assertIn("mdutil", errors.getvalue())
        self.assertIn("permission denied", errors.getvalue())

    def test_failed_preserved_service_verification_returns_failure(self):
        check = lean.PreserveCheck("com.apple.example", "Example", "user")
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(lean, "sw_vers", side_effect=["15.0", "build"]), \
                patch.object(lean, "build_label_index", return_value={check.label}), \
                patch.object(lean, "load_disabled_state"), \
                patch.object(lean, "DISABLE_SECTIONS", []), \
                patch.object(lean, "PRESERVE_SECTIONS", [("Preserved", [check])]), \
                patch.object(lean, "run", return_value=subprocess.CompletedProcess(
                    ["launchctl", "print"], 1, "", "")), \
                patch.object(lean, "SudoWorker"), \
                patch.object(lean, "apply_spotlight_tmutil"), \
                patch.object(lean, "apply_user_defaults"), \
                patch.object(lean, "apply_performance_defaults"), \
                patch.object(lean, "apply_pmset"), \
                patch.object(lean, "apply_ipv6"), \
                patch.object(lean, "apply_mdns_captive"), \
                patch.object(lean, "apply_logging"), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(lean.main([]), 1)
        self.assertIn("FAIL Example", output.getvalue())
        self.assertIn("WARNING: 1 preserved service(s) not loaded.", output.getvalue())
        self.assertEqual(errors.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
