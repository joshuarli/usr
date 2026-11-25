"""Graph construction and scoped action selection without real installs."""
from pathlib import Path
import json
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
        self.switches = main.read_switches()
        (root / "harnesses.json").write_text(json.dumps(self.switches))
        self.ctx = main.Context(root, root / "home", "darwin", "desktop", {"HOME": str(root / "home")})
        self.ctx.home.mkdir()

    def test_explicit_npm_tool_fetches_node_first_without_host_steps(self):
        dag = main.graph(self.ctx, ["cmd"], setup=False).select(["tool:cmd"])
        names = [task.name for task in dag.order()]
        self.assertEqual(names, ["tool:nodejs", "tool:cmd"])

    def test_pnpm_is_a_standalone_native_install(self):
        dag = main.graph(self.ctx, ["pnpm"], setup=False).select(["tool:pnpm"])
        self.assertEqual([task.name for task in dag.order()], ["tool:pnpm"])

    def test_dsh_requires_pnpm_and_node(self):
        dag = main.graph(self.ctx, ["dsh"], setup=False).select(["tool:dsh"])
        self.assertEqual([t.name for t in dag.order()], ["tool:nodejs", "tool:pnpm", "tool:dsh"])

    def test_player_requires_ffmpeg_runtime(self):
        dag = main.graph(self.ctx, ["player"], setup=False).select(["tool:player"])
        self.assertEqual([t.name for t in dag.order()], ["tool:ffmpeg", "tool:player"])

    def test_codex_has_no_tool_prerequisites(self):
        dag = main.graph(self.ctx, ["codex"], setup=False).select(["tool:codex"])
        self.assertEqual([t.name for t in dag.order()], ["tool:codex"])

    def test_bridge_registration_tasks_serialize_their_sdk_install(self):
        tasks = main.graph(self.ctx, [], setup=True).tasks
        for name in ("claude-mcp", "pi-mcp"):
            self.assertIn("pi-sdk-install", tasks[name].resources)
        self.assertNotIn("pi-sdk-install", tasks["opencode-mcp"].resources)

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

    def test_bridge_requires_only_offline_pi_and_node(self):
        dag = main.graph(self.ctx, [], setup=True).select(["claude-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "tool:pi", "pi-extensions", "claude-mcp"} <= names)
        self.assertFalse({"tool:cmd", "tool:opencode", "tool:claude"} & names,
                         "bridge registration must not install npm-managed provider harnesses")

    def test_pi_bridge_requires_only_offline_pi_and_node(self):
        dag = main.graph(self.ctx, [], setup=True).select(["pi-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "tool:pi", "pi-extensions", "pi-mcp"} <= names)
        self.assertFalse({"tool:cmd", "tool:opencode", "tool:claude"} & names,
                         "bridge registration must not install npm-managed provider harnesses")

    def test_opencode_task_only_enforces_bridge_absence(self):
        dag = main.graph(self.ctx, [], setup=True).select(["opencode-mcp"])
        names = {task.name for task in dag.order()}
        self.assertEqual(names, {"links", "opencode-mcp"})

    def test_disabled_pi_does_not_get_reinstalled_through_bridge_dependencies(self):
        self.switches["pi"] = False
        (self.ctx.root / "harnesses.json").write_text(json.dumps(self.switches))
        goals = main.default_goals(self.ctx)
        names = {task.name for task in main.graph(self.ctx, main.tool_list(self.ctx), setup=True).select(goals).order()}
        self.assertNotIn("tool:pi", names)
        self.assertFalse({"pi-auth", "pi-mcp", "pi-extensions"} & names)
        self.assertIn("claude-mcp", names)

    def test_claude_bridge_without_pi_registers_core_using_only_links_and_node(self):
        self.switches["pi"] = False
        (self.ctx.root / "harnesses.json").write_text(json.dumps(self.switches))
        dag = main.graph(self.ctx, [], setup=True).select(["claude-mcp"])
        self.assertEqual({task.name for task in dag.order()}, {"links", "tool:nodejs", "claude-mcp"})
        with patch.object(main, "command") as run:
            run.return_value.returncode = 0
            self.assertTrue(main.bridge_status(self.ctx).current)
            main.bridge_apply(self.ctx)
        self.assertEqual([call.args[4:] for call in run.call_args_list], [("check", "--core"), ("install", "--core")])

    def test_claude_bridge_requires_an_enabled_parent_and_leaf(self):
        self.switches.update({"pi": False, "codex": False, "command-code": False})
        (self.ctx.root / "harnesses.json").write_text(json.dumps(self.switches))
        self.assertNotIn("claude-mcp", main.bridge_goals(self.ctx))
        self.switches["command-code"] = True
        (self.ctx.root / "harnesses.json").write_text(json.dumps(self.switches))
        self.assertIn("claude-mcp", main.bridge_goals(self.ctx))
        self.switches["claude"] = False
        (self.ctx.root / "harnesses.json").write_text(json.dumps(self.switches))
        self.assertNotIn("claude-mcp", main.bridge_goals(self.ctx))

    def test_all_harnesses_disabled_keeps_only_unrelated_setup(self):
        (self.ctx.root / "harnesses.json").write_text(json.dumps(dict.fromkeys(self.switches, False)))
        self.assertEqual(main.bridge_goals(self.ctx), [])
        self.assertNotIn("tool:cmd", main.default_goals(self.ctx))
        self.assertFalse({"codex", "claude", "devin", "opencode", "pi", "cmd"} & set(main.tool_list(self.ctx)))

    def test_disabled_explicit_install_stops_before_dependencies(self):
        with patch.object(main, "context", return_value=self.ctx), \
                patch.object(main, "graph", side_effect=AssertionError("constructed install graph")):
            with self.assertRaisesRegex(main.GraphError, "disabled in harnesses.json: cmd"):
                main.main(["tools", "cmd"])

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

    def test_server_profile_can_select_bridges_on_demand(self):
        server = main.Context(self.ctx.root, self.ctx.home, "linux", "server", self.ctx.env)
        with patch.object(main, "is_alpine", return_value=False):
            dag = main.graph(server, ["python3"], setup=True).select(["claude-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "claude-mcp"} <= names)
        with patch.object(main, "tool_list", return_value=["python3"]):
            defaults = main.default_goals(server)
        self.assertNotIn("claude-mcp", defaults)
        self.assertNotIn("pi-mcp", defaults)
        self.assertNotIn("pi-auth", defaults)
        self.assertNotIn("opencode-mcp", defaults)

    def test_pi_auth_needs_only_links_and_pi(self):
        dag = main.graph(self.ctx, [], setup=True).select(["pi-auth"])
        self.assertEqual({task.name for task in dag.order()}, {"links", "tool:nodejs", "tool:pi", "pi-auth"})

    def test_desktop_default_goals_include_pi_auth(self):
        with patch.object(main, "tool_list", return_value=["python3"]):
            self.assertIn("pi-auth", main.default_goals(self.ctx))

    def test_cargo_test_tools_follow_rustup_and_server_profile(self):
        tools = {"cargo-mutants", "cargo-llvm-cov"}
        linux = main.Context(self.ctx.root, self.ctx.home, "linux", "desktop", self.ctx.env)
        self.assertFalse(tools & set(main.tool_list(linux)))
        rustup = self.ctx.home / ".cargo/bin/rustup"
        rustup.parent.mkdir(parents=True)
        rustup.write_text("#!/bin/sh\n")
        rustup.chmod(0o755)
        self.assertTrue(tools <= set(main.tool_list(linux)))
        server_file = self.ctx.root / "host/alpine/tools-server.txt"
        server_file.parent.mkdir(parents=True)
        server_file.write_text("fd\n")
        server = main.Context(self.ctx.root, self.ctx.home, "linux", "server", self.ctx.env)
        self.assertFalse(tools & set(main.tool_list(server)))

    def test_server_profile_omits_mcp_bridges_from_default_sync(self):
        server = main.Context(self.ctx.root, self.ctx.home, "linux", "server", self.ctx.env)
        with patch.object(main, "tool_list", return_value=["python3"]):
            defaults = main.default_goals(server)
        self.assertNotIn("claude-mcp", defaults)
        self.assertNotIn("pi-mcp", defaults)
        self.assertNotIn("pi-auth", defaults)
        self.assertNotIn("opencode-mcp", defaults)
        self.assertIn("tool:python3", defaults)

    def test_all_delegates_apply_plan_and_doctor_to_the_fleet(self):
        with patch("fleet.main", return_value=0) as fleet_main:
            self.assertEqual(main.main(["apply", "--all"]), 0)
            self.assertEqual(main.main(["plan", "--all"]), 0)
            self.assertEqual(main.main(["doctor", "--all", "--show-all"]), 0)
        self.assertEqual([call.args[0] for call in fleet_main.call_args_list],
                         [["apply"], ["plan"], ["doctor", "--show-all"]])

    def test_all_rejects_display_only_commands_and_json(self):
        with self.assertRaisesRegex(main.GraphError, "hosts apply"):
            main.main(["links", "--all"])
        with patch("fleet.main") as fleet_main:
            with self.assertRaisesRegex(main.GraphError, "--json"):
                main.main(["apply", "--all", "--json"])
            with self.assertRaisesRegex(main.GraphError, "lisa"):
                main.main(["apply", "--all", "lisa"])
        fleet_main.assert_not_called()

    def test_show_all_is_the_display_flag(self):
        self.assertEqual(main.output_flags(["--show-all", "--json"]), ([], True, True))
        self.assertEqual(main.output_flags([]), ([], False, False))


if __name__ == "__main__":
    unittest.main()
