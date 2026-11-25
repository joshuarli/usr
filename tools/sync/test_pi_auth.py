"""Pi auth seeding against disposable homes."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pi_auth


class PiAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.env = {"HOME": str(self.home)}
        self.agent = self.home / ".pi" / "agent"

    def auth_file(self) -> Path:
        return self.agent / "auth.json"

    def test_missing_file_is_seeded_with_runtime_credential_command(self):
        probe = pi_auth.status(self.home, self.env)
        self.assertFalse(probe.current)
        self.assertFalse(probe.conflict)
        pi_auth.apply(self.home, self.env)
        data = json.loads(self.auth_file().read_text())
        self.assertEqual(data, {"opencode-go": pi_auth.ENTRY})
        self.assertIn("!opencode auth export opencode", data["opencode-go"]["key"])
        self.assertEqual(self.auth_file().stat().st_mode & 0o777, 0o600)
        self.assertTrue(pi_auth.status(self.home, self.env).current)

    def test_existing_providers_are_preserved(self):
        self.agent.mkdir(parents=True)
        original = {"devin": {"type": "oauth", "access": "x"}, "muse": {"type": "api_key", "key": "y"}}
        self.auth_file().write_text(json.dumps(original))
        pi_auth.apply(self.home, self.env)
        data = json.loads(self.auth_file().read_text())
        self.assertEqual(data["devin"], original["devin"])
        self.assertEqual(data["muse"], original["muse"])
        self.assertEqual(data["opencode-go"], pi_auth.ENTRY)

    def test_existing_opencode_go_entry_is_not_overwritten(self):
        self.agent.mkdir(parents=True)
        mine = {"type": "api_key", "key": "static-user-token"}
        self.auth_file().write_text(json.dumps({"opencode-go": mine}))
        self.assertTrue(pi_auth.status(self.home, self.env).current)
        pi_auth.apply(self.home, self.env)
        self.assertEqual(json.loads(self.auth_file().read_text())["opencode-go"], mine)

    def test_invalid_json_is_a_conflict_and_never_rewritten(self):
        self.agent.mkdir(parents=True)
        self.auth_file().write_text("{not json")
        probe = pi_auth.status(self.home, self.env)
        self.assertFalse(probe.current)
        self.assertTrue(probe.conflict)
        with self.assertRaises(RuntimeError):
            pi_auth.apply(self.home, self.env)
        self.assertEqual(self.auth_file().read_text(), "{not json")

    def test_non_object_json_is_a_conflict(self):
        self.agent.mkdir(parents=True)
        self.auth_file().write_text("[\"opencode-go\"]")
        probe = pi_auth.status(self.home, self.env)
        self.assertTrue(probe.conflict)
        with self.assertRaises(RuntimeError):
            pi_auth.apply(self.home, self.env)

    def test_symlinked_auth_file_is_refused(self):
        self.agent.mkdir(parents=True)
        target = self.home / "elsewhere.json"
        target.write_text("{}")
        os.symlink(target, self.auth_file())
        probe = pi_auth.status(self.home, self.env)
        self.assertTrue(probe.conflict)
        with self.assertRaises(RuntimeError):
            pi_auth.apply(self.home, self.env)
        self.assertEqual(target.read_text(), "{}")

    def test_agent_dir_env_override_is_honoured(self):
        agent = self.home / "custom-pi"
        env = dict(self.env, PI_CODING_AGENT_DIR=str(agent))
        pi_auth.apply(self.home, env)
        self.assertTrue((agent / "auth.json").is_file())

    def test_relative_agent_dir_falls_back_to_home(self):
        env = dict(self.env, PI_CODING_AGENT_DIR="relative-dir")
        pi_auth.apply(self.home, env)
        self.assertTrue(self.auth_file().is_file())

    def test_apply_is_idempotent(self):
        pi_auth.apply(self.home, self.env)
        first = self.auth_file().read_bytes()
        pi_auth.apply(self.home, self.env)
        self.assertEqual(self.auth_file().read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
