"""Pi extension pins and sync reconciliation without network access."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main
from pi_extensions import missing, pins


class PiExtensionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        home = root / "home"
        home.mkdir()
        self.ctx = main.Context(root, home, "darwin", "desktop", {"HOME": str(home)})
        self.settings = root / "dotfiles/base/.pi/agent/settings.json"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({"packages": ["npm:pi-subagents@0.87.0"]}))
        self.package_file = home / ".pi/agent/npm/node_modules/pi-subagents/package.json"
        self.launcher = home / ".local/bin/pi"
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("#!/bin/sh\nexit 0\n")
        self.launcher.chmod(0o755)

    def test_package_status_detects_missing_and_stale_pins(self):
        self.assertEqual(pins(self.settings), [("npm:pi-subagents@0.87.0", "pi-subagents", "0.87.0")])
        self.assertEqual(len(missing(self.settings, self.ctx.home)), 1)
        probe = main.pi_extensions_status(self.ctx)
        self.assertFalse(probe.current)
        self.assertFalse(probe.conflict)
        self.package_file.parent.mkdir(parents=True)
        self.package_file.write_text(json.dumps({"version": "0.86.0"}))
        self.assertIn("0.86.0", main.pi_extensions_status(self.ctx).detail)
        self.package_file.write_text(json.dumps({"version": "0.87.0"}))
        self.assertTrue(main.pi_extensions_status(self.ctx).current)

    def test_reconciliation_repairs_missing_pin_and_invokes_extension_update(self):
        calls = []

        def command(_ctx, *args, **kwargs):
            calls.append((args, kwargs))
            if args[1] == "install":
                self.package_file.parent.mkdir(parents=True, exist_ok=True)
                self.package_file.write_text(json.dumps({"version": "0.87.0"}))
            return subprocess.CompletedProcess(args, 0)

        with patch.object(main, "command", side_effect=command):
            main.pi_extensions_apply(self.ctx)
            self.assertTrue(main.pi_extensions_status(self.ctx).current)
            main.pi_extensions_apply(self.ctx)
        self.assertEqual([args for args, _ in calls], [
            (str(self.launcher), "install", "npm:pi-subagents@0.87.0", "--no-approve"),
            (str(self.launcher), "update", "--extensions", "--no-approve"),
            (str(self.launcher), "update", "--extensions", "--no-approve"),
        ])
        for _, options in calls:
            self.assertEqual(options["extra"]["PI_CODING_AGENT_DIR"], str(self.ctx.home / ".pi/agent"))
            self.assertTrue(options["extra"]["PATH"].startswith(str(self.ctx.home / ".local/bin")))

    def test_invalid_unpinned_package_is_rejected_before_mutation(self):
        self.settings.write_text(json.dumps({"packages": ["npm:pi-subagents@latest"]}))
        probe = main.pi_extensions_status(self.ctx)
        self.assertTrue(probe.conflict)
        with patch.object(main, "command") as command:
            with self.assertRaisesRegex(ValueError, "exact npm version"):
                main.pi_extensions_apply(self.ctx)
            command.assert_not_called()

    def test_scoped_pinned_package(self):
        self.settings.write_text(json.dumps({"packages": [{"source": "npm:@team/agent@1.2.3"}]}))
        self.assertEqual(pins(self.settings), [("npm:@team/agent@1.2.3", "@team/agent", "1.2.3")])

    def test_graph_serializes_extension_reconciliation_before_mcp(self):
        tasks = main.graph(self.ctx, [], setup=True).tasks
        self.assertEqual(tasks["pi-extensions"].needs, ("links", "tool:pi"))
        self.assertTrue(tasks["pi-extensions"].reconcile)
        for name in ("claude-mcp", "pi-mcp", "opencode-mcp"):
            self.assertIn("pi-extensions", tasks[name].needs)
        server = main.Context(self.ctx.root, self.ctx.home, "linux", "server", self.ctx.env)
        with patch.object(main, "is_alpine", return_value=False):
            self.assertNotIn("pi-extensions", main.graph(server, [], setup=True).tasks)


if __name__ == "__main__":
    unittest.main()
