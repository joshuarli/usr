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

    def test_player_requires_ffmpeg_runtime(self):
        dag = main.graph(self.ctx, ["player"], setup=False).select(["tool:player"])
        self.assertEqual([t.name for t in dag.order()], ["tool:ffmpeg", "tool:player"])

    def test_codex_requires_jaq(self):
        dag = main.graph(self.ctx, ["codex"], setup=False).select(["tool:codex"])
        self.assertEqual([t.name for t in dag.order()], ["tool:jaq", "tool:codex"])

    def test_tool_tasks_have_disjoint_resources(self):
        tasks = main.graph(self.ctx, ["cmd", "pnpm", "fd"], setup=False).tasks
        resources = [tasks[name].resources for name in ("tool:cmd", "tool:pnpm", "tool:fd", "tool:nodejs")]
        self.assertTrue(all(resources))
        for index, first in enumerate(resources):
            for second in resources[index + 1:]:
                self.assertFalse(first & second)

    def test_python_update_does_not_require_jaq(self):
        dag = main.graph(self.ctx, ["python3"], setup=False).select(["tool:python3"])
        self.assertEqual([t.name for t in dag.order()], ["tool:python3"])

    def test_bridge_requires_node_command_and_claude(self):
        dag = main.graph(self.ctx, [], setup=True).select(["claude-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "tool:cmd", "tool:claude", "tool:opencode2", "claude-mcp"} <= names)

    def test_pi_bridge_requires_node_command_and_pi(self):
        dag = main.graph(self.ctx, [], setup=True).select(["pi-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "tool:cmd", "tool:pi", "tool:opencode2", "pi-mcp"} <= names)

    def test_opencode_bridge_requires_node_command_and_opencode2(self):
        dag = main.graph(self.ctx, [], setup=True).select(["opencode-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "tool:cmd", "tool:opencode2", "opencode-mcp"} <= names)

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

    def test_apply_tool_merges_claims_and_removals(self):
        from ownership import read_manifest, records
        ownership = self.ctx.state
        ownership.parent.mkdir(parents=True, exist_ok=True)
        ownership.write_text("D\t/home/old-release\n")
        installed = self.ctx.home / ".local/bin/fd"
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_text("binary")
        installed.chmod(0o755)

        class FakeInstaller:
            def __init__(self, *args, **kwargs):
                self.claims = [("F", installed)]
                self.removed = {Path("/home/old-release")}
                self.changed = True

            def install(self, tool):
                pass

        with patch.object(main, "Installer", FakeInstaller):
            main.apply_tool(self.ctx, "fd")
        self.assertEqual(records(ownership), {("F", installed)})
        self.assertIn(str(installed), read_manifest(ownership))

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

    def test_server_profile_omits_mcp_bridges(self):
        server = main.Context(self.ctx.root, self.ctx.home, "linux", "server", self.ctx.env)
        with patch.object(main, "is_alpine", return_value=False):
            tasks = main.graph(server, ["python3"], setup=True).tasks
        self.assertNotIn("claude-mcp", tasks)
        self.assertNotIn("pi-mcp", tasks)
        self.assertNotIn("opencode-mcp", tasks)
        self.assertIn("tool:python3", tasks)


if __name__ == "__main__":
    unittest.main()
