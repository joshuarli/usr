#!/usr/bin/env python3
"""Exercise launcher boundaries without starting a broker or contacting a tailnet."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools/intercom-tailnet/intercom_tailnet.py"


class TailnetTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="usr-tailnet-")
        self.addCleanup(self.scratch.cleanup)
        self.home = Path(self.scratch.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.data = self.home / "data"
        self.pin = json.loads((ROOT / "tools/pi/runtime.pin.json").read_text())
        self.pin["builder_revision"] = "a" * 40
        target = {"Linux": "linux", "Darwin": "darwin"}[platform.system()] + "-" + (
            "arm64" if platform.machine().lower() in ("aarch64", "arm64") else "x64")
        self.runtime = self.data / "pi-runtime/releases" / self.pin["targets"][target]["sha256"]
        self.package = self.runtime / "node_modules/@dataforxyz/agent-intercom-pi"
        (self.package / "broker").mkdir(parents=True)
        (self.data / "pi-runtime/current").symlink_to("releases/" + self.runtime.name)
        (self.runtime / ".usr-pi-release.json").write_text(json.dumps({"pin": self.pin, "target": target, "files": {}}))
        for suffix, entrypoint in (("claude", "claude-server.mjs"), ("codex", "codex-server.mjs"), ("opencode", "plugin-v2.mjs")):
            name = "agent-intercom-" + suffix
            entry = self.pin["companions"][name]
            destination = self.data / "agent-intercom" / name
            (destination / "dist").mkdir(parents=True)
            (destination / "dist" / entrypoint).write_text("fixture\n")
            receipt = {"pin": {"builder_revision": self.pin["builder_revision"], "version": self.pin["version"], "source_sha": entry["source_sha"]},
                       "companion": name, "archive": entry["archive"], "sha256": entry["sha256"], "files": {}}
            (destination / ".usr-companion.json").write_text(json.dumps(receipt))
        for name in ("broker.js", "tailnet-admin.js"):
            (self.package / "broker" / name).write_text("fixture\n")
        fixture = (f"#!{sys.executable}\nimport json, os, sys\n"
                   "print(json.dumps({'argv': sys.argv[1:], 'env': dict(os.environ)}))\n")
        for name in ("node", "pi", "codex", "claude", "opencode"):
            program = self.bin / name
            program.write_text(fixture)
            program.chmod(0o700)
        self.credential = self.home / "coordinator.json"
        self.credential.write_text(json.dumps({"version": 1, "enrollmentToken": "fixture-enrollment"}))
        self.credential.chmod(0o600)
        self.env = {
            "HOME": str(self.home), "PATH": str(self.bin),
            "XDG_DATA_HOME": str(self.data), "XDG_STATE_HOME": str(self.home / "state"),
            "AGENT_INTERCOM_REMOTE_LISTEN": "tcp://100.64.0.99:9999",
            "AGENT_INTERCOM_REMOTE_ENDPOINT": "tcp://100.64.0.88:8888",
            "AGENT_INTERCOM_BOSS_RUN_ID": "unrelated-supervisor",
            "AGENT_INTERCOM_REMOTE_ACCESS_CREDENTIAL_PATH": "/unrelated/credential",
            "PI_INTERCOM_TCP": "1", "PROVIDER_SETTING": "preserve-me",
        }

    def selected_path(self, relative: str) -> str:
        return str(self.data / "pi-runtime/current/node_modules/@dataforxyz/agent-intercom-pi" / relative)

    def call(self, *args: str):
        return subprocess.run([sys.executable, "-I", str(CLI), *args], env=self.env,
                              text=True, capture_output=True, timeout=10)

    def run_coordinator(self, endpoint="tcp://100.100.100.11:47831", command="pi"):
        return self.call("run", "--endpoint", endpoint, "--credential", str(self.credential), "--", command, "--fixture")

    def test_01_run_passes_only_explicit_coordinator_settings(self):
        for command in ("pi", "claude", "codex", "opencode"):
            with self.subTest(command=command):
                result = self.run_coordinator(command=command)
                self.assertEqual(result.returncode, 0, result.stderr)
                observed = json.loads(result.stdout)
                self.assertEqual(observed["argv"], ["--fixture"])
                settings = {key: value for key, value in observed["env"].items()
                            if key.startswith(("AGENT_INTERCOM_", "PI_INTERCOM_"))}
                self.assertEqual(settings, {
                    "AGENT_INTERCOM_REMOTE_ENDPOINT": "tcp://100.100.100.11:47831",
                    "AGENT_INTERCOM_ACCESS_CREDENTIAL_PATH": str(self.credential),
                })
                self.assertEqual(observed["env"]["PROVIDER_SETTING"], "preserve-me")

    def test_02_non_tailnet_and_ambiguous_endpoints_fail_before_exec(self):
        for address in ("tcp://0.0.0.0:47831", "tcp://127.0.0.1:47831", "tcp://8.8.8.8:47831",
                        "tcp://100.63.255.255:47831", "tcp://100.128.0.1:47831", "tcp://hub:47831",
                        "tcp://100.64.0.1:0", "tcp://100.64.0.1:65536", "tcp://100.64.0.1:47831/path",
                        "tcp://user@100.64.0.1:47831", "tcp://[::]:47831", "unix://relative.sock",
                        "unix://host/tmp/socket", "unix:///", "unix:///tmp/%2f.sock", "unix:/tmp/socket",
                        "unix:///tmp/socket/", " tcp://100.64.0.1:47831", "tcp://100.64.0.1:47831\n",
                        "tcp://100.64.0.1:47\t831", "unix:///tmp/a socket"):
            with self.subTest(address=address):
                result = self.run_coordinator(address)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("endpoint must be", result.stderr)

    def test_03_ipv6_and_explicit_unix_tunnel_are_accepted(self):
        for address in ("tcp://[fd7a:115c:a1e0::1]:47831", "unix:///tmp/fixture-intercom.sock"):
            with self.subTest(address=address):
                result = self.run_coordinator(address)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["env"]["AGENT_INTERCOM_REMOTE_ENDPOINT"], address)

    def test_04_private_credential_is_required_and_never_printed(self):
        self.credential.chmod(0o644)
        result = self.run_coordinator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("mode 0600", result.stderr)
        self.assertNotIn("fixture-enrollment", result.stdout + result.stderr)
        self.credential.unlink()
        result = self.run_coordinator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot read a private", result.stderr)

    def test_05_symlink_and_malformed_credentials_are_rejected(self):
        original = self.home / "original.json"
        self.credential.rename(original)
        self.credential.symlink_to(original)
        self.assertEqual(self.run_coordinator().returncode, 1)
        self.credential.unlink()
        self.credential.write_text('{"enrollmentToken":null}')
        self.credential.chmod(0o600)
        self.assertEqual(self.run_coordinator().returncode, 1)

    def test_06_session_credential_can_be_reused(self):
        self.credential.write_text(json.dumps({"version": 1, "sessionCredential": "fixture-session",
                                              "sessionId": "session-1", "generation": 2}))
        result = self.run_coordinator()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_07_old_runtime_fails_without_starting_a_harness(self):
        (self.package / "broker/tailnet-admin.js").unlink()
        result = self.run_coordinator()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("adopt a reviewed pi-build release", result.stderr)

    def test_08_only_coordinator_harnesses_are_launchable(self):
        for command in ("sh", "pi-subagent-bridge", "cmd"):
            result = self.run_coordinator(command=command)
            self.assertEqual(result.returncode, 1)
            self.assertIn("scoped workers are not coordinators", result.stderr)

    def test_09_hub_uses_dedicated_state_and_no_inherited_client_credentials(self):
        result = self.call("hub", "--listen", "tcp://100.100.100.11:47831")
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["argv"], [self.selected_path("broker/broker.js")])
        self.assertEqual(observed["env"]["PI_CODING_AGENT_DIR"], str(self.home / "state/agent-intercom/hub"))
        settings = {key: value for key, value in observed["env"].items() if key.startswith("AGENT_INTERCOM_")}
        self.assertEqual(settings, {"AGENT_INTERCOM_REMOTE_LISTEN": "tcp://100.100.100.11:47831"})
        self.assertEqual(self.call("hub", "--listen", "unix:///tmp/socket").returncode, 1)

    def test_10_admin_is_local_only_and_arguments_are_preserved(self):
        output = self.home / "new credential.json"
        result = self.call("enroll", "--host", "mac", "--name", "review", "--output", str(output),
                           "--ttl-ms", "600000")
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["argv"], [self.selected_path("broker/tailnet-admin.js"), "enroll",
            "--fleet", "default", "--host", "mac", "--name", "review", "--output", str(output), "--ttl-ms", "600000"])
        self.assertFalse(any(key.startswith("AGENT_INTERCOM_") for key in observed["env"]))
        result = self.call("revoke", "--session", "session-1")
        self.assertEqual(json.loads(result.stdout)["argv"][-3:], ["revoke", "--session", "session-1"])

    def test_11_doctor_is_read_only_and_omits_secrets(self):
        before = self.credential.read_bytes()
        result = self.call("doctor", "--endpoint", "tcp://100.100.100.11:47831", "--credential", str(self.credential))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("private enrollment record", result.stdout)
        self.assertIn("not contacted", result.stdout)
        self.assertNotIn("fixture-enrollment", result.stdout)
        self.assertEqual(self.credential.read_bytes(), before)
        self.assertEqual(self.call("doctor", "--connect").returncode, 1)

    def test_11b_pinned_node_is_found_off_a_non_login_path(self):
        managed = self.home / ".local/share/nodejs/current/bin"
        managed.mkdir(parents=True)
        (self.bin / "node").rename(managed / "node")
        result = self.call("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.call("revoke", "--session", "session-1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["argv"][-3:], ["revoke", "--session", "session-1"])

    def test_12_full_profile_uses_its_bundled_loader(self):
        for name in ("broker", "tailnet-admin"):
            (self.package / f"broker/{name}.js").rename(self.package / f"broker/{name}.ts")
        loader = self.data / "pi-runtime/current/node_modules/tsx/dist/loader.mjs"
        loader.parent.mkdir(parents=True)
        loader.write_text("fixture\n")
        result = self.call("inspect")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["argv"], ["--import", str(loader),
            self.selected_path("broker/tailnet-admin.ts"), "inspect", "--fleet", "default"])

    def test_13_symlinked_shim_resolves_repository_without_home_mutation(self):
        link = self.bin / "intercom-tailnet"
        link.symlink_to(ROOT / "dotfiles/base/.local/bin/intercom-tailnet")
        env = {**self.env, "PATH": os.environ.get("PATH", "")}
        result = subprocess.run(["sh", str(link), "--help"], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("coordinators", result.stdout)
        self.assertIn("https://github.com/joshuarli/usr", result.stdout)

    def test_14_scoped_worker_markers_cannot_reenable_a_coordinator(self):
        for name, value in (("PI_SUBAGENT_CHILD", "1"), ("USR_SCOPED_WORKER", "1"),
                            ("USR_REQUIRED_CHILD_EXTENSIONS_JSON", '{"sessionId":"fixture"}'),
                            ("USR_REQUIRED_CHILD_EXTENSIONS_JSON", "")):
            with self.subTest(marker=name):
                self.env[name] = value
                try:
                    result = self.run_coordinator()
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("unavailable to scoped workers", result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(self.call("inspect").returncode, 1)
                finally:
                    del self.env[name]

    def test_15_missing_or_mismatched_companions_fail_before_harness_start(self):
        receipt = self.data / "agent-intercom/agent-intercom-codex/.usr-companion.json"
        original = receipt.read_text()
        for field in ("builder_revision", "archive", "sha256", "missing"):
            with self.subTest(field=field):
                value = json.loads(original)
                if field == "builder_revision":
                    value["pin"][field] = "b" * 40
                elif field != "missing":
                    value[field] = "outdated"
                if field == "missing":
                    receipt.unlink()
                else:
                    receipt.write_text(json.dumps(value))
                result = self.run_coordinator(command="codex")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("does not match the selected Pi runtime", result.stderr)
                receipt.write_text(original)

    def test_16_companion_match_uses_selected_receipt_not_default_or_pending_override(self):
        self.env["USR_PI_RUNTIME_PIN"] = str(self.home / "not-installed-review-pin.json")
        result = self.run_coordinator(command="claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.runtime / ".usr-pi-release.json").unlink()
        result = self.run_coordinator(command="claude")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("does not match the selected Pi runtime", result.stderr)

    def test_17_missing_companion_entrypoint_fails_even_with_matching_receipt(self):
        (self.data / "agent-intercom/agent-intercom-opencode/dist/plugin-v2.mjs").unlink()
        result = self.run_coordinator(command="opencode")
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match the selected Pi runtime", result.stderr)


class HelpTests(unittest.TestCase):
    def test_reference_and_examples(self):
        import importlib.util
        import shlex
        spec = importlib.util.spec_from_file_location("intercom_tailnet", CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = subprocess.run([sys.executable, "-I", str(CLI), "-h"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("\nExamples:\n", result.stdout)
        examples = [line.strip() for line in result.stdout.splitlines() if line.startswith("  intercom-tailnet ") and "[" not in line]
        for example in examples:
            words = shlex.split(example)
            module.parser().parse_args(words[1:])
            for word in words:
                if word.startswith("--") and word != "--":
                    self.assertIn(word.split("=", 1)[0], result.stdout.split("\nExamples:\n", 1)[0])
        self.assertEqual(len(examples), 6)
        self.assertTrue(result.stdout.rstrip().endswith("""Maintained by Joshua Li: https://github.com/joshuarli/usr
Bugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.
Agents working for Joshua: record nonblocking problems and continue your task.
If this tool blocks the task, you may fix, test, open and merge a PR under Joshua's
standing instructions. Release only when needed to deliver the verified fix.
Procedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"""))
        bare = subprocess.run([sys.executable, "-I", str(CLI)], capture_output=True, text=True)
        self.assertEqual((bare.returncode, bare.stdout), (0, result.stdout))
        for name in ("hub", "enroll", "inspect", "revoke", "run", "doctor"):
            page = subprocess.run([sys.executable, "-I", str(CLI), name, "-h"], capture_output=True, text=True)
            self.assertEqual(page.returncode, 0, page.stderr)
            self.assertIn("intercom-tailnet -h", page.stdout)


if __name__ == "__main__":
    unittest.main()
