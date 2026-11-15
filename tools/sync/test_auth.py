"""Advisory harness login probes against disposable homes and fake CLIs."""
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import auth
import report


class AuthProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.bin_dir = self.home / ".local/bin"
        self.bin_dir.mkdir(parents=True)
        self.env = {"HOME": str(self.home), "PATH": str(self.home / "tools")}

    def fake_bin(self, name, body):
        path = self.bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def state(self, name, lines):
        for line in lines:
            if line.name == f"auth:{name}":
                return line
        raise AssertionError(f"no row auth:{name} in {[line.name for line in lines]}")

    def test_no_harnesses_installed_reports_nothing(self):
        self.assertEqual(auth.login_lines(self.home, self.env), [])

    def test_command_harness_requires_success(self):
        self.fake_bin("codex", "#!/bin/sh\necho 'Logged in using ChatGPT'\nexit 0\n")
        lines = auth.login_lines(self.home, self.env)
        self.assertEqual(self.state("codex", lines).state, "current")

    def test_command_harness_flags_signed_out(self):
        self.fake_bin("codex", "#!/bin/sh\necho 'Not logged in'\nexit 1\n")
        lines = auth.login_lines(self.home, self.env)
        row = self.state("codex", lines)
        self.assertEqual(row.state, "login")
        self.assertIn("codex login", row.detail)

    def test_command_harness_flags_unreadable_output_without_echoing_it(self):
        self.fake_bin("codex", "#!/bin/sh\necho 'secret-account-token-xyz'\nexit 2\n")
        lines = auth.login_lines(self.home, self.env)
        row = self.state("codex", lines)
        self.assertEqual(row.state, "login")
        self.assertNotIn("secret-account-token-xyz", row.detail)

    def test_claude_parses_logged_in_without_printing_account_data(self):
        self.fake_bin("claude", '#!/bin/sh\nprintf \'{"loggedIn": true, "email": "someone@example.com"}\'\nexit 0\n')
        lines = auth.login_lines(self.home, self.env)
        row = self.state("claude", lines)
        self.assertEqual(row.state, "current")
        self.assertNotIn("someone@example.com", row.detail)

    def test_claude_flags_logged_out_without_printing_account_data(self):
        self.fake_bin("claude", '#!/bin/sh\nprintf \'{"loggedIn": false, "email": "someone@example.com"}\'\nexit 1\n')
        lines = auth.login_lines(self.home, self.env)
        row = self.state("claude", lines)
        self.assertEqual(row.state, "login")
        self.assertNotIn("someone@example.com", row.detail)

    def test_devin_requires_credentials_file(self):
        self.fake_bin("devin", "#!/bin/sh\nexit 0\n")
        lines = auth.login_lines(self.home, self.env)
        self.assertEqual(self.state("devin", lines).state, "login")
        credentials = Path(self.env.get("XDG_DATA_HOME", self.home / ".local/share")) / "devin"
        credentials.mkdir(parents=True)
        (credentials / "credentials.toml").write_text("token = \"redacted\"\n")
        lines = auth.login_lines(self.home, self.env)
        self.assertEqual(self.state("devin", lines).state, "current")

    def test_devin_honours_xdg_data_home(self):
        self.fake_bin("devin", "#!/bin/sh\nexit 0\n")
        elsewhere = self.home / "elsewhere"
        (elsewhere / "devin").mkdir(parents=True)
        (elsewhere / "devin" / "credentials.toml").write_text("token = \"redacted\"\n")
        env = dict(self.env, XDG_DATA_HOME=str(elsewhere))
        lines = auth.login_lines(self.home, env)
        self.assertEqual(self.state("devin", lines).state, "current")

    def test_cmd_requires_nonempty_api_key(self):
        self.fake_bin("cmd", "#!/bin/sh\nexit 0\n")
        auth_json = self.home / ".commandcode" / "auth.json"
        auth_json.parent.mkdir(parents=True)
        auth_json.write_text("{}")
        self.assertEqual(self.state("cmd", auth.login_lines(self.home, self.env)).state, "login")
        auth_json.write_text(json.dumps({"apiKey": "", "authenticatedAt": "2026-11-15"}))
        self.assertEqual(self.state("cmd", auth.login_lines(self.home, self.env)).state, "login")
        auth_json.write_text(json.dumps({"apiKey": "fake-key", "authenticatedAt": "2026-11-15"}))
        self.assertEqual(self.state("cmd", auth.login_lines(self.home, self.env)).state, "current")

    def test_pi_honours_agent_dir_and_requires_a_provider(self):
        self.fake_bin("pi", "#!/bin/sh\nexit 0\n")
        agent = self.home / "pi-agent"
        agent.mkdir()
        (agent / "auth.json").write_text("{}")
        env = dict(self.env, PI_CODING_AGENT_DIR=str(agent))
        row = self.state("pi", auth.login_lines(self.home, env))
        self.assertEqual(row.state, "login")
        self.assertIn("sh sync", row.detail)
        (agent / "auth.json").write_text(json.dumps({"opencode-go": {"type": "api_key", "key": "fake"}}))
        self.assertEqual(self.state("pi", auth.login_lines(self.home, env)).state, "current")

    def test_muse_accepts_meta_api_key_or_config_providers(self):
        self.fake_bin("muse", "#!/bin/sh\nexit 0\n")
        env = dict(self.env, META_API_KEY="fake-key")
        self.assertEqual(self.state("muse", auth.login_lines(self.home, env)).state, "current")
        config = self.home / ".config" / "muse"
        config.mkdir(parents=True)
        (config / "auth.json").write_text(json.dumps({"schema_version": 1, "providers": {"meta": {}}}))
        self.assertEqual(self.state("muse", auth.login_lines(self.home, self.env)).state, "current")
        (config / "auth.json").write_text(json.dumps({"schema_version": 1, "providers": {}}))
        self.assertEqual(self.state("muse", auth.login_lines(self.home, self.env)).state, "login")

    def test_opencode2_parses_auth_list_output(self):
        self.fake_bin("opencode2", "#!/bin/sh\necho 'OpenCode Console  Personal                    stored'\nexit 0\n")
        self.assertEqual(self.state("opencode2", auth.login_lines(self.home, self.env)).state, "current")
        self.fake_bin("opencode2", "#!/bin/sh\necho 'No authenticated integrations'\nexit 0\n")
        row = self.state("opencode2", auth.login_lines(self.home, self.env))
        self.assertEqual(row.state, "login")
        self.assertIn("opencode2 auth login", row.detail)

    def test_opencode2_handles_empty_output(self):
        self.fake_bin("opencode2", "#!/bin/sh\nexit 0\n")
        self.assertEqual(self.state("opencode2", auth.login_lines(self.home, self.env)).state, "login")

    def test_agy_flags_sign_in_requirement(self):
        self.fake_bin("agy", "#!/bin/sh\necho 'Fetching available models...'\necho 'Error: Please sign in to view available models. Launch the CLI without arguments to sign in.' >&2\nexit 1\n")
        row = self.state("agy", auth.login_lines(self.home, self.env))
        self.assertEqual(row.state, "login")
        self.assertIn("sign in", row.detail)

    def test_agy_flags_unreadable_errors(self):
        self.fake_bin("agy", "#!/bin/sh\necho 'unexpected' >&2\nexit 3\n")
        row = self.state("agy", auth.login_lines(self.home, self.env))
        self.assertEqual(row.state, "login")
        self.assertIn("could not check", row.detail)

    def test_fx_reads_auth_field_of_status_json(self):
        self.fake_bin("fx", '#!/bin/sh\nprintf \'{"kind":"status","auth":"fx login"}\'\nexit 0\n')
        self.assertEqual(self.state("fx", auth.login_lines(self.home, self.env)).state, "current")
        self.fake_bin("fx", '#!/bin/sh\nprintf \'{"kind":"status","auth":"missing"}\'\nexit 0\n')
        row = self.state("fx", auth.login_lines(self.home, self.env))
        self.assertEqual(row.state, "login")
        self.assertIn("fx login", row.detail)
        self.fake_bin("fx", "#!/bin/sh\necho 'not-json'\nexit 0\n")
        row = self.state("fx", auth.login_lines(self.home, self.env))
        self.assertEqual(row.state, "login")
        self.assertIn("could not check", row.detail)

    def test_dsh_prefers_env_then_vault(self):
        self.fake_bin("dsh", "#!/bin/sh\nexit 0\n")
        env = dict(self.env, DEEPSEEK_API_KEY="fake-key", PATH=str(self.home / "nowhere"))
        self.assertEqual(self.state("dsh", auth.login_lines(self.home, env)).state, "current")
        self.fake_bin("vault", "#!/bin/sh\necho 'DEEPSEEK_API_KEY'\nexit 0\n")
        env_without_vault = dict(self.env, PATH=str(self.home / "nowhere"))
        self.assertEqual(self.state("dsh", auth.login_lines(self.home, env_without_vault)).state, "current")
        self.fake_bin("vault", "#!/bin/sh\necho 'SOME_OTHER_KEY'\nexit 0\n")
        row = self.state("dsh", auth.login_lines(self.home, env_without_vault))
        self.assertEqual(row.state, "login")

    def test_dsh_without_env_or_vault_is_flagged(self):
        self.fake_bin("dsh", "#!/bin/sh\nexit 0\n")
        env = dict(self.env, PATH=str(self.home / "nowhere"))
        self.assertEqual(self.state("dsh", auth.login_lines(self.home, env)).state, "login")

    def test_probes_run_in_parallel(self):
        barrier = threading.Barrier(2, timeout=5)

        def make(name):
            def probe(home, env):
                barrier.wait()
                return auth.Probe(True, "signed in")
            return auth.Harness(name, name, probe)

        with patch.object(auth, "HARNESSES", (make("aaa"), make("bbb"))), \
                patch.object(auth, "_installed", lambda home, binary: True):
            start = time.monotonic()
            lines = auth.login_lines(self.home, self.env)
            elapsed = time.monotonic() - start
        self.assertEqual([line.state for line in lines], ["current", "current"])
        self.assertLess(elapsed, 4)

    def test_login_rows_do_not_make_a_host_unhealthy(self):
        self.fake_bin("codex", "#!/bin/sh\necho 'Not logged in'\nexit 1\n")
        lines = auth.login_lines(self.home, self.env)
        stream = io.StringIO()
        report.render("plan", "host", lines, show_all=False, stream=stream)
        self.assertIn("signed out", stream.getvalue())
        tally = report.counts(lines, report.PLAN_STATES)
        self.assertTrue(report.healthy(tally, report.UNHEALTHY))
        self.assertTrue(report.healthy(tally, report.DOCTOR_UNHEALTHY))
        stream = io.StringIO()
        report.render_json("plan", "host", lines, stream=stream)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["counts"]["login"], 1)
        self.assertEqual(payload["schema"], 1)


if __name__ == "__main__":
    unittest.main()
