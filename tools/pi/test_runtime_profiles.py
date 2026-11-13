"""Check launcher paths and broker configuration when switching runtime profiles."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sync"))
import pi_offline


class RuntimeProfileTests(unittest.TestCase):
    def test_broker_switches_both_directions_and_preserves_custom_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            runtime = home / "runtime"
            loader = runtime / "node_modules/tsx/dist/loader.mjs"
            broker = runtime / "node_modules/@dataforxyz/agent-intercom-pi/broker/broker.js"
            for path in (loader, broker):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            config = home / ".pi/agent/intercom/config.json"
            self.assertTrue(pi_offline.configure_intercom(home, runtime))
            for profile, expected in (("headless-usr", []), ("full", ["--import", str(loader)])):
                self.assertTrue(pi_offline.configure_intercom(home, runtime, profile))
                data = json.loads(config.read_text())
                self.assertEqual(data["brokerArgs"], expected)
                self.assertTrue(data["confirmSend"])
                self.assertEqual(data["inboundTrigger"], "never")
                self.assertFalse(pi_offline.configure_intercom(home, runtime, profile))
            for command, args in (("node", []), ("node", ["--import", "/opt/custom.mjs"]), ("/opt/broker", ["custom"])):
                data = {"brokerCommand": command, "brokerArgs": args, "confirmSend": False,
                        "inboundTrigger": "always", "customField": 42}
                config.write_text(json.dumps(data))
                self.assertFalse(pi_offline.configure_intercom(home, runtime, "headless-usr"))
                self.assertEqual(json.loads(config.read_text()), data)
                self.assertFalse(pi_offline.configure_intercom(home, runtime, "full"))
                self.assertEqual(json.loads(config.read_text()), data)
            loader.unlink()
            config.unlink()
            self.assertTrue(pi_offline.configure_intercom(home, runtime, "headless-usr"))
            broker.unlink()
            with self.assertRaisesRegex(pi_offline.OfflinePiError, "missing compiled"):
                pi_offline.configure_intercom(home, runtime, "headless-usr")

    def test_launcher_uses_selected_profile_and_rejects_unknown_profile(self):
        root = Path("/runtime with spaces")
        for profile, suffix in (("full", "ts"), ("headless-usr", "js")):
            wrapper = pi_offline.wrapper(root, profile)
            self.assertIn(f"pi-subagents/index.{suffix}'", wrapper)
            self.assertIn(f"agent-intercom-pi/index.{suffix}'", wrapper)
            self.assertIn('"$@"', wrapper)
            self.assertIn("PI_OFFLINE=1", wrapper)
        with self.assertRaises(KeyError):
            pi_offline.wrapper(root, "unknown")


if __name__ == "__main__":
    unittest.main()
