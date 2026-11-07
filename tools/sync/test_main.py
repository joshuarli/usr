"""Graph construction and scoped action selection without real installs."""
import json
import shutil
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

    def test_python_update_requires_jaq(self):
        dag = main.graph(self.ctx, ["python3"], setup=False).select(["tool:python3"])
        self.assertEqual([t.name for t in dag.order()], ["tool:jaq", "tool:python3"])

    def test_bridge_requires_node_command_and_claude(self):
        dag = main.graph(self.ctx, [], setup=True).select(["claude-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "tool:cmd", "tool:claude", "tool:opencode2", "claude-mcp"} <= names)

    def test_pi_bridge_requires_node_command_and_pi(self):
        dag = main.graph(self.ctx, [], setup=True).select(["pi-mcp"])
        names = {task.name for task in dag.order()}
        self.assertTrue({"links", "tool:nodejs", "tool:cmd", "tool:pi", "tool:opencode2", "pi-mcp"} <= names)

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

    def agent_memory_fixture(self):
        source = self.ctx.home / "d/agent-memory"
        source.mkdir(parents=True)
        (source / "pyproject.toml").write_text("[project]\nname = 'agent-memory'\n")
        venv = self.ctx.home / ".local/share/agent-memory/venv"
        for command in main.AGENT_MEMORY_COMMANDS:
            script = venv / "bin" / command
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("#!/bin/sh\n")
            script.chmod(0o755)
        return source, venv

    def write_pin(self, sha="abc1234"):
        path = self.ctx.root / "tools/sync/agent-memory.pin"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sha + "\n")
        return sha

    def write_metadata(self, source, venv, editable, commit=None):
        metadata = venv / "lib/python3.15/site-packages/agent_memory-0.1.0.dist-info"
        metadata.mkdir(parents=True, exist_ok=True)
        record = {
            "url": source.as_uri(), "dir_info": {"editable": True} if editable else {},
        }
        if commit is not None:
            record["vcs_info"] = {"vcs": "git", "commit_id": commit}
        (metadata / "direct_url.json").write_text(json.dumps(record))

    def test_agent_memory_requires_uv(self):
        dag = main.graph(self.ctx, ["agent-memory"], setup=True).select(["tool:agent-memory"])
        self.assertEqual([task.name for task in dag.order()], ["links", "tool:uv", "tool:agent-memory"])

    def test_agent_memory_probe_requires_editable_install_when_checkout_present(self):
        source, venv = self.agent_memory_fixture()
        self.assertFalse(main.agent_memory_status(self.ctx).current)
        self.write_metadata(source, venv, editable=False)
        probe = main.agent_memory_status(self.ctx)
        self.assertFalse(probe.current)
        self.assertIn("not an editable install", probe.detail)
        self.write_metadata(source, venv, editable=True)
        self.assertTrue(main.agent_memory_status(self.ctx).current)
        (venv / "bin/agent-sessions-serve").unlink()
        self.assertFalse(main.agent_memory_status(self.ctx).current)

    def test_agent_memory_probe_requires_pinned_install_without_checkout(self):
        self.write_pin("abc1234")
        probe = main.agent_memory_status(self.ctx)
        self.assertFalse(probe.current)
        self.assertFalse(probe.conflict)
        self.assertIn("environment missing", probe.detail)

    def test_agent_memory_probe_accepts_pinned_install(self):
        source, venv = self.agent_memory_fixture()
        shutil.rmtree(self.ctx.home / "d/agent-memory")
        sha = self.write_pin("abc1234")
        self.write_metadata(source, venv, editable=False, commit=sha)
        probe = main.agent_memory_status(self.ctx)
        self.assertTrue(probe.current)
        self.assertIn("pinned install", probe.detail)

    def test_agent_memory_apply_installs_editable_environment(self):
        source, venv = self.agent_memory_fixture()
        uv = self.ctx.home / ".local/bin/uv"
        uv.parent.mkdir(parents=True)
        uv.write_text("#!/bin/sh\n")
        uv.chmod(0o755)
        calls = []

        def run(_ctx, *args, **_kwargs):
            calls.append(args)
            return type("Completed", (), {"returncode": 0})()

        with patch.object(main, "command", side_effect=run):
            main.agent_memory_apply(self.ctx)
        self.assertEqual(calls, [
            (str(uv), "venv", "--allow-existing", "--python", ">=3.15", str(venv)),
            (str(uv), "pip", "install", "--python", str(venv / "bin/python"), "-e " + str(source)),
        ])

    def test_agent_memory_apply_installs_pinned_commit_without_checkout(self):
        sha = self.write_pin("abc1234")
        uv = self.ctx.home / ".local/bin/uv"
        uv.parent.mkdir(parents=True)
        uv.write_text("#!/bin/sh\n")
        uv.chmod(0o755)
        venv = self.ctx.home / ".local/share/agent-memory/venv"
        calls = []

        def run(_ctx, *args, **_kwargs):
            calls.append(args)
            return type("Completed", (), {"returncode": 0})()

        with patch.object(main, "command", side_effect=run):
            main.agent_memory_apply(self.ctx)
        self.assertEqual(calls, [
            (str(uv), "venv", "--allow-existing", "--python", ">=3.15", str(venv)),
            (str(uv), "pip", "install", "--python", str(venv / "bin/python"),
             "agent-memory @ git+ssh://git@github.com/joshuarli/agent-memory@" + sha),
        ])

    def test_server_profile_omits_mcp_bridges(self):
        server = main.Context(self.ctx.root, self.ctx.home, "linux", "server", self.ctx.env)
        with patch.object(main, "is_alpine", return_value=False):
            tasks = main.graph(server, ["python3"], setup=True).tasks
        self.assertNotIn("claude-mcp", tasks)
        self.assertNotIn("pi-mcp", tasks)
        self.assertIn("tool:python3", tasks)


if __name__ == "__main__":
    unittest.main()
