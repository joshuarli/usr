"""Graph construction and scoped action selection without real installs."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import main


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.ctx = main.Context(root, root / "home", "darwin", "desktop", {"HOME": str(root / "home")})
        self.ctx.home.mkdir()

    def test_explicit_npm_tool_fetches_node_first_without_host_steps(self):
        dag = main.graph(self.ctx, ["cmd"], setup=False).select(["tool:cmd"])
        names = [task.name for task in dag.order()]
        self.assertEqual(names, ["tool:nodejs", "tool:cmd"])

    def test_dsh_requires_pnpm_and_node(self):
        dag = main.graph(self.ctx, ["dsh"], setup=False).select(["tool:dsh"])
        self.assertEqual([t.name for t in dag.order()], ["tool:nodejs", "tool:pnpm", "tool:dsh"])

    def test_python_update_requires_jaq(self):
        dag = main.graph(self.ctx, ["python3"], setup=False).select(["tool:python3"])
        self.assertEqual([t.name for t in dag.order()], ["tool:jaq", "tool:python3"])

    def test_bridge_requires_node_command_and_claude(self):
        dag = main.graph(self.ctx, [], setup=True).select(["claude-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "tool:cmd", "tool:claude", "tool:opencode2", "claude-mcp"} <= names)

    def test_server_profile_omits_claude_bridge(self):
        server = main.Context(self.ctx.root, self.ctx.home, "linux", "server", self.ctx.env)
        with patch.object(main, "is_alpine", return_value=False):
            tasks = main.graph(server, ["python3"], setup=True).tasks
        self.assertNotIn("claude-mcp", tasks)
        self.assertIn("tool:python3", tasks)


if __name__ == "__main__":
    unittest.main()
