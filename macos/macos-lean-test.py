#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import plistlib
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("macos_lean", Path(__file__).with_name("macos-lean.py"))
lean = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lean
spec.loader.exec_module(lean)


class CommandFailureTests(unittest.TestCase):
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
                with self.subTest(operation=operation.__name__, mode=mode):
                    state = lean.State(mode, 501, "27.0", "Golden Gate", "27")
                    output = io.StringIO()
                    with patch.object(lean.subprocess, "run", side_effect=self.failed_command), \
                            patch.object(lean, "list_network_services", return_value=["Wi-Fi"]), \
                            contextlib.redirect_stdout(output):
                        with self.assertRaises(subprocess.CalledProcessError) as caught:
                            operation(state)
                    self.assertEqual(caught.exception.returncode, 7)
                    self.assertEqual(caught.exception.stderr, "permission denied")
                    self.assertNotIn(success, output.getvalue())

    def test_missing_mutation_executable_raises(self):
        with patch.object(lean.subprocess, "run", side_effect=FileNotFoundError("missing tool")):
            with self.assertRaises(FileNotFoundError):
                lean.run(["mdutil", "-a", "-i", "off"], sudo=True)

    def test_failed_preferences_and_service_mutations_do_not_count_as_applied(self):
        for mode in ("apply", "revert"):
            for domain in ("user", "system"):
                with self.subTest(mode=mode, domain=domain):
                    state = lean.State(mode, 501, "27.0", "Golden Gate", "27")
                    state.real_labels.add("com.apple.example")
                    with patch.object(lean.subprocess, "run", side_effect=self.failed_command), \
                            contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaises(subprocess.CalledProcessError):
                            if domain == "user":
                                lean.disable_user(state, "com.apple.example")
                            else:
                                lean.disable_system(state, "com.apple.example")
                                lean.flush_system(state)
                    self.assertEqual(state.n_applied, 0)
                    self.assertEqual(state.disabled_user, set())
                    self.assertEqual(state.disabled_system, set())
        with patch.object(lean.subprocess, "run", side_effect=self.failed_command):
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
        with patch.object(lean.subprocess, "run", side_effect=self.failed_command):
            self.assertIsNone(lean.defaults_read(lean.MDNS_DEFAULT))
            self.assertEqual(lean.sw_vers("buildVersion"), "unknown")
            self.assertEqual(lean.run(["pgrep", "-x", "Dock"], check=False).returncode, 7)

    def test_failed_cli_command_reports_failure_and_stops_keepalive(self):
        output, errors = io.StringIO(), io.StringIO()
        failure = subprocess.CalledProcessError(7, ["sudo", "mdutil"], stderr="permission denied")
        with patch.object(lean, "sw_vers", return_value="27.0"), \
                patch.object(lean, "build_label_index", return_value=set()), \
                patch.object(lean, "load_disabled_state"), \
                patch.object(lean, "DISABLE_SECTIONS", []), \
                patch.object(lean, "SudoKeepalive") as keepalive, \
                patch.object(lean, "apply_spotlight_tmutil", side_effect=failure), \
                patch.object(lean, "print_summary") as summary, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(lean.main([]), 1)
        keepalive.return_value.stop.assert_called_once()
        summary.assert_not_called()
        self.assertIn("mdutil", errors.getvalue())
        self.assertIn("permission denied", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
