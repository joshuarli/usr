"""Graph construction and scoped action selection without real installs."""
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
        root = Path(self.tmp.name).resolve()
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

    def test_alternate_target_links_never_touch_home(self):
        target = self.ctx.root / "fixture-home"
        target.mkdir()
        source = self.ctx.root / "dotfiles/base/.profile"
        source.parent.mkdir(parents=True)
        source.write_text("managed")
        ctx = main.Context(self.ctx.root, self.ctx.home, "darwin", "desktop", self.ctx.env, target)
        # Only the pinact migration is external; planning and application are Python.
        with patch.object(main, "command") as run:
            run.return_value.returncode = 0
            main.apply_links(ctx)
        self.assertEqual(ctx.state, target / ".local/state/sync/dl-owned")
        self.assertTrue((target / ".profile").is_symlink())
        self.assertFalse((self.ctx.home / ".profile").exists())

    def test_alt_target_blocks_host_mutations(self):
        target = self.ctx.root / "fixture-home"
        target.mkdir()
        ctx = main.Context(self.ctx.root, self.ctx.home, "darwin", "desktop", self.ctx.env, target)
        with patch.object(main, "context", return_value=ctx):
            for operation in ([], ["tools", "cmd"], ["bridge"], ["uninstall"]):
                with self.subTest(operation=operation), self.assertRaisesRegex(main.GraphError, "TARGET different from HOME"):
                    main.main(list(operation))

    def test_global_link_plan_replaces_stale_other_layer(self):
        from links import discover
        from link_plan import plan_links
        from link_apply import apply
        base = self.ctx.root / "dotfiles/base"
        other = self.ctx.root / "dotfiles/darwin"
        base.mkdir(parents=True)
        other.mkdir(parents=True)
        source = base / ".moved"
        source.write_text("original")
        ctx = self.ctx
        plan = plan_links(discover(ctx.root, ctx.home, "darwin"), ctx.state)
        apply(plan, ctx.state)
        new = other / ".moved"
        source.rename(new)
        plan = plan_links(discover(ctx.root, ctx.home, "darwin"), ctx.state)
        self.assertEqual([item.kind for item in plan.actions], ["replace"])
        apply(plan, ctx.state)
        self.assertEqual((ctx.home / ".moved").resolve(), new)

    def test_server_profile_omits_claude_bridge(self):
        server = main.Context(self.ctx.root, self.ctx.home, "linux", "server", self.ctx.env)
        with patch.object(main, "is_alpine", return_value=False):
            tasks = main.graph(server, ["python3"], setup=True).tasks
        self.assertNotIn("claude-mcp", tasks)
        self.assertIn("tool:python3", tasks)


if __name__ == "__main__":
    unittest.main()
