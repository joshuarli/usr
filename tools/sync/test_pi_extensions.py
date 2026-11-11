"""Pi sync must refuse all npm package declarations and never invoke the Pi updater."""
import json
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
        self.settings.write_text(json.dumps({"packages": []}))

    def test_no_package_downloads_or_update_command(self):
        self.assertEqual(pins(self.settings), [])
        self.assertEqual(missing(self.settings, self.ctx.home), [])
        self.assertTrue(main.pi_extensions_status(self.ctx).current)
        with patch.object(main, "command") as command:
            main.pi_extensions_apply(self.ctx)
            command.assert_not_called()

    def test_network_package_configuration_is_a_hard_conflict(self):
        for source in ["npm:pi-subagents@0.87.0", "git:github.com/x/y", "file:/tmp/pkg"]:
            self.settings.write_text(json.dumps({"packages": [source]}))
            self.assertTrue(main.pi_extensions_status(self.ctx).conflict)
            with self.assertRaisesRegex(ValueError, "forbidden"):
                main.pi_extensions_apply(self.ctx)
        self.settings.write_text(json.dumps({"packages": "invalid"}))
        self.assertTrue(main.pi_extensions_status(self.ctx).conflict)

    def test_graph_keeps_runtime_before_bridge(self):
        tasks = main.graph(self.ctx, [], setup=True).tasks
        self.assertIn("tool:pi", tasks["pi-extensions"].needs)
        for name in ("claude-mcp", "pi-mcp", "opencode-mcp"):
            self.assertIn("pi-extensions", tasks[name].needs)


if __name__ == "__main__":
    unittest.main()
