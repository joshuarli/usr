#!/usr/bin/env python3
"""Structural policy tests for cross-harness Pi SDK delegation."""
from collections import Counter
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "tools/policy/policy.generated.json").read_text())
TIERS = POLICY["tiers"]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def inline_code(text: str) -> list[str]:
    return re.findall(r"`([^`\n]+)`", text)


def parse_blocks(text: str, yaml: bool = False) -> dict[str, str]:
    if yaml:
        marker = re.compile(r"^# policy:(begin|end) ([a-z0-9-]+)$", re.MULTILINE)
        token = "# policy:"
    else:
        marker = re.compile(r"^<!-- policy:(begin|end) ([a-z0-9-]+) -->$", re.MULTILINE)
        token = "<!-- policy:"
    candidates = [line for line in text.splitlines() if token in line]
    matches = list(marker.finditer(text))
    if len(candidates) != len(matches):
        raise ValueError("malformed generated policy marker")
    blocks = {}
    active = None
    start = None
    for match in matches:
        kind, name = match.groups()
        if kind == "begin":
            if active is not None or name in blocks:
                raise ValueError("duplicate or nested generated policy block: " + name)
            active = name
            start = match.end()
        else:
            if active != name:
                raise ValueError("unmatched generated policy block: " + name)
            blocks[name] = text[start:match.start()]
            active = None
            start = None
    if active is not None:
        raise ValueError("unclosed generated policy block: " + active)
    return blocks


def html_blocks(path: str) -> dict[str, str]:
    return parse_blocks(read(path))


def yaml_blocks(path: str) -> dict[str, str]:
    return parse_blocks(read(path), yaml=True)


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def markdown_tables(text: str) -> list[list[dict[str, str]]]:
    tables = []
    lines = []
    for line in text.splitlines() + [""]:
        if line.startswith("|"):
            lines.append(line)
            continue
        if len(lines) >= 2:
            header = split_markdown_row(lines[0])
            rows = []
            for row in lines[1:]:
                cells = split_markdown_row(row)
                if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    continue
                if len(cells) != len(header):
                    raise ValueError("generated Markdown table row width mismatch")
                rows.append(dict(zip(header, cells)))
            tables.append(rows)
        lines = []
    return tables


def plain(cell: str) -> str:
    return cell.replace("`", "").strip()


def route_segments(cell: str) -> list[tuple[str, str, str]]:
    if not inline_code(cell):
        return []
    routes = []
    for part in cell.split(";"):
        match = re.fullmatch(r"\s*([^`]+?)\s*`([^`]+)`\s*\(`([^`]+)`\)\s*", part)
        if not match:
            raise ValueError("malformed generated route: " + part)
        label, model, effort = match.groups()
        routes.append((label.strip().lower().replace(" ", "-"), model, effort))
    return routes


def policy_route(route: dict[str, str]) -> tuple[str, str, str]:
    model = route["model"]
    if route["executor"] == "pi":
        model = route["providerID"] + "/" + model
    return (route["executor"], model, route["effort"])


def yaml_fields(block: str) -> dict[str, str | list[str]]:
    fields = {}
    current = None
    for line in block.strip().splitlines():
        if not line.strip() or line.startswith("# Generated"):
            continue
        if line.startswith("  - "):
            if current is None:
                raise ValueError("generated YAML list item without a key")
            fields[current].append(line[4:].strip())
            continue
        if line.startswith(" "):
            raise ValueError("unexpected generated YAML indentation: " + line)
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError("malformed generated YAML line: " + line)
        key = key.strip()
        value = value.strip()
        if value:
            fields[key] = value
            current = None
        else:
            fields[key] = []
            current = key
    return fields


class OrchestrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read("dotfiles/base/.agents/skills/orchestrate/SKILL.md")
        cls.skill_blocks = html_blocks("dotfiles/base/.agents/skills/orchestrate/SKILL.md")

    def block(self, name: str) -> str:
        self.assertIn(name, self.skill_blocks)
        return self.skill_blocks[name]

    def assert_summary_identifiers(self, block: str, bridge_identifier: bool = False) -> None:
        expert = POLICY["rootRoutes"]["expert"][0]
        expected = Counter(TIERS)
        expected.update(["expert", policy_route(expert)[1], expert["effort"], "god"])
        expected.update(POLICY["bannedModels"])
        if bridge_identifier:
            expected.update(["pi-subagent-bridge"])
        self.assertEqual(Counter(inline_code(block)), expected)

    def assert_generated_route_table(self):
        blocks = html_blocks("tools/pi-subagent-bridge/README.md")
        tables = markdown_tables(blocks["routing-summary"])
        self.assertEqual(len(tables), 1)
        rows = tables[0]
        self.assertEqual([row["Tier"] for row in rows], TIERS)
        for row in rows:
            tier = row["Tier"]
            routes = POLICY["rootRoutes"][tier]
            self.assertEqual(route_segments(row["Primary"]), [policy_route(routes[0])])
            self.assertEqual(route_segments(row["Fallback (in order)"]), [policy_route(route) for route in routes[1:]])

    def assert_generated_pi_nesting_table(self):
        blocks = html_blocks("tools/pi-subagent-bridge/README.md")
        tables = markdown_tables(blocks["pi-nesting"])
        self.assertEqual(len(tables), 1)
        rows = tables[0]
        delegation = POLICY["nativePi"]["delegation"]
        self.assertEqual([row["Pi parent"].split()[0] for row in rows], list(delegation))
        for row in rows:
            tier = row["Pi parent"].split()[0]
            children = [child.strip() for child in row["Allowed nested child"].split(",")]
            self.assertEqual(children, delegation[tier])

    def test_generated_policy_blocks_exist_exactly_once(self):
        html_expectations = {
            "dotfiles/base/.agents/skills/orchestrate/SKILL.md": {
                "routing-intro", "opencode", "devin", "command-code", "antigravity", "copilot", "native-fallback",
            },
            "dotfiles/base/.codex/AGENTS.md": {"delegation", "direct-models"},
            "dotfiles/base/.agents/instructions/lean.md": {"delegation"},
            "tools/pi-subagent-bridge/README.md": {"routing-summary", "pi-nesting"},
            "docs/pi.md": {"routing-summary"},
            "docs/agent-setup.md": {"routing-summary"},
        }
        for path, expected in html_expectations.items():
            self.assertEqual(set(html_blocks(path)), expected, path)
        yaml_paths = []
        yaml_paths += ["dotfiles/base/.gemini/config/agents/" + pin["name"] + ".md" for pin in POLICY["antigravityDirect"]["tiers"].values()]
        yaml_paths += ["dotfiles/base/.copilot/agents/" + pin["name"] + ".agent.md" for pin in POLICY["copilotNative"].values()]
        yaml_paths += ["dotfiles/base/.commandcode/agents/" + pin["name"] + ".md" for pin in POLICY["commandNative"].values()]
        yaml_paths += ["dotfiles/base/.config/devin/agents/" + pin["name"] + ".md" for pin in POLICY["devinNative"].values()]
        for path in yaml_paths:
            self.assertEqual(set(yaml_blocks(path)), {"native-agent"}, path)

    def test_every_harness_uses_shared_bridge(self):
        block = self.block("routing-intro")
        self.assert_summary_identifiers(block, bridge_identifier=True)
        for harness in ("OpenCode", "Devin", "Command Code", "Antigravity", "Copilot CLI"):
            self.assertIn(harness, block)
        methods = ("worker_model_check", "worker_start", "worker_status", "worker_resume")
        paragraphs = re.split(r"\n\s*\n", self.text)
        self.assertTrue(any(all("`" + method + "`" in paragraph for method in methods) for paragraph in paragraphs))
        self.assertIn("`pi-subagent-bridge`", self.text)

    def test_generated_policy_has_distinct_root_and_native_domains(self):
        self.assertEqual(len(set(TIERS)), len(TIERS))
        self.assertEqual(set(POLICY["rootRoutes"]), set(TIERS))
        self.assertEqual(set(POLICY["nativePi"]["goModels"]), set(TIERS))
        self.assertEqual(set(POLICY["nativePi"]["devinModels"]), set(TIERS))
        for tier in TIERS:
            self.assertTrue(POLICY["rootRoutes"][tier])
        self.assertEqual(len(POLICY["rootRoutes"]["expert"]), 1)
        self.assertNotIn("antigravity", {route["executor"] for routes in POLICY["rootRoutes"].values() for route in routes})
        self.assertNotIn("god", POLICY["rootRoutes"])
        for family in POLICY["bannedModels"]:
            for routes in POLICY["rootRoutes"].values():
                self.assertTrue(all(route["model"] != family and not route["model"].startswith(family + "-")
                                    for route in routes))
        self.assert_generated_route_table()
        self.assert_generated_pi_nesting_table()
        self.assert_summary_identifiers(html_blocks("docs/pi.md")["routing-summary"])
        self.assert_summary_identifiers(html_blocks("docs/agent-setup.md")["routing-summary"])
        readme_summary = html_blocks("tools/pi-subagent-bridge/README.md")["routing-summary"]
        self.assert_summary_identifiers(readme_summary.split("\n\n", 1)[0])

    def test_direct_antigravity_models_require_an_availability_check(self):
        contract_blocks = html_blocks("dotfiles/base/.codex/AGENTS.md")
        direct = contract_blocks["direct-models"]
        direct_models = POLICY["antigravityDirect"]
        for model in direct_models["models"]:
            self.assertIn("`" + model + "`", direct)
            self.assertNotIn(model, {route["model"] for routes in POLICY["rootRoutes"].values() for route in routes})
        expected = Counter([direct_models["main"]["model"], direct_models["main"]["effort"],
                            direct_models["god"]["model"], direct_models["god"]["effort"], "usr-*"])
        for pin in direct_models["tiers"].values():
            expected.update([pin["name"], pin["model"], pin["effort"]])
        expected.update(["pi-subagent-bridge", "model: flash/pro", "agy models"])
        expected.update(direct_models["models"])
        expected.update(direct_models["retired"])
        expected.update([direct_models["manualCarbon"]])
        self.assertEqual(Counter(inline_code(direct)), expected)
        block = self.block("antigravity")
        tables = markdown_tables(block)
        self.assertEqual(len(tables), 1)
        rows = tables[0]
        self.assertEqual(set(rows[0]), {"Tier", "Native agent", "Target model", "Target effort", "CLI selector"})
        self.assertEqual([row["Tier"] for row in rows], list(direct_models["tiers"]))
        for tier, pin in direct_models["tiers"].items():
            row = rows[list(direct_models["tiers"]).index(tier)]
            self.assertEqual(plain(row["Native agent"]), pin["name"])
            self.assertEqual(plain(row["Target model"]), pin["model"])
            self.assertEqual(plain(row["Target effort"]), pin["effort"])
            self.assertEqual(plain(row["CLI selector"]), pin["selector"])
            fields = yaml_fields(yaml_blocks("dotfiles/base/.gemini/config/agents/" + pin["name"] + ".md")["native-agent"])
            self.assertEqual(fields["model"], pin["selector"])
            self.assertEqual(fields["subagent"], "true")
            self.assertEqual(fields["mainAgent"], "false")
            self.assertNotIn(pin["model"], fields.values())
        for identifier in ("agy", "invoke_subagent", "usr-*"):
            self.assertIn("`" + identifier + "`", block)

    def test_orchestrate_defers_exact_pins_to_model_check(self):
        self.assertIn("`worker_model_check`", self.text)
        self.assertIn("tools/pi-subagent-bridge/README.md", self.text)
        for table in markdown_tables(self.text):
            self.assertNotEqual(set(table[0]), {"Tier", "Primary", "Fallback (in order)"})
        self.assert_generated_route_table()

    def test_no_old_mcp_registration(self):
        codex = read("dotfiles/base/.codex/config.toml")
        section = re.search(r"(?ms)^\[mcp_servers\.pi-subagent-bridge\]\n(.*?)(?=^\[|\Z)", codex)
        self.assertIsNotNone(section)
        self.assertIn('command = "pi-subagent-bridge"', section.group(1))
        self.assertIn('"mcp"', section.group(1))
        self.assertNotIn("usr-opencode-worker", codex)
        opencode = json.loads(read("dotfiles/base/.config/opencode/opencode.json"))
        self.assertNotIn("pi-subagent-bridge", json.dumps(opencode.get("mcp", {})))
        self.assertNotIn("usr-opencode-worker", json.dumps(opencode))

    def test_native_subagents_cover_claude_code(self):
        for harness in ("OpenCode", "Devin", "Codex", "Pi", "Claude Code"):
            self.assertIn(harness, self.text)
        block = self.block("native-fallback")
        mappings = re.findall(r"\b(scout|mechanic|worker|expert)\s*:\s*`([^`]+)`", block)
        fallback = POLICY["nativeFallback"]
        self.assertEqual(set(fallback["claudeModels"]), set(fallback["tiers"]))
        expected = Counter((tier, fallback["claudeModels"][tier]) for tier in fallback["tiers"])
        self.assertEqual(Counter(mappings), expected)
        self.assertNotIn("expert", fallback["tiers"])
        self.assertNotIn("expert", fallback["claudeModels"])
        self.assertIn("expert", inline_code(block))
        self.assertIn("`USR_DELEGATION=native`", block)
        self.assertIn("pi-subagent-bridge scope-check CWD SCOPE_JSON_FILE BRANCH --register TITLE", self.text)
        self.assertIn("pi-subagent-bridge scope-check --lane ID", self.text)
        for path, block_name in (
            ("dotfiles/base/.codex/AGENTS.md", "delegation"),
            ("dotfiles/base/.agents/instructions/lean.md", "delegation"),
        ):
            generated = html_blocks(path)[block_name]
            self.assertIn("`USR_DELEGATION=native`", generated)
            self.assertRegex(generated, r"quota|exhaust")
        settings = json.loads(read("dotfiles/base/.claude/settings.json"))
        self.assertNotIn("PreToolUse", settings.get("hooks", {}))
        self.assertFalse((ROOT / "dotfiles/base/.local/bin/agent-tier-gate").exists())

    def test_opencode_exception(self):
        block = self.block("opencode")
        policy = POLICY["opencode"]
        tables = markdown_tables(block)
        self.assertEqual(len(tables), 1)
        rows = tables[0]
        self.assertEqual(set(rows[0]), {"Tier", "Effort"})
        self.assertEqual({row["Tier"].split()[0]: plain(row["Effort"]) for row in rows}, policy["efforts"])
        self.assertEqual(inline_code(block).count(policy["model"]), 1)
        self.assertIn("free", policy["model"])
        for identifier in ("pi-subagent-bridge", "general", "explore", "shell", "edit"):
            self.assertIn("`" + identifier + "`", block)
        config = json.loads(read("dotfiles/base/.config/opencode/opencode.json"))
        agents = config["agents"]
        self.assertEqual(
            {tier: agents[tier]["model"] for tier in policy["efforts"]},
            {tier: policy["model"] + "#" + policy["efforts"][tier] for tier in policy["efforts"]},
        )
        self.assertNotIn("god", agents)
        scout_rules = agents["scout"]["permissions"]
        denied = {(rule["action"], rule["effect"]) for rule in scout_rules}
        self.assertIn(("shell", "deny"), denied)
        self.assertIn(("edit", "deny"), denied)
        for path in ("dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.agents/instructions/lean.md"):
            self.assertIn("OpenCode", html_blocks(path)["delegation"])

    def test_devin_native_agents_pin_swe21_variants(self):
        block = self.block("devin")
        pins = POLICY["devinNative"]
        self.assertEqual(set(pins), set(TIERS))
        tables = markdown_tables(block)
        self.assertEqual(len(tables), 1)
        rows = tables[0]
        self.assertEqual(set(rows[0]), {"Tier", "Native agent", "Model"})
        self.assertEqual([row["Tier"] for row in rows], list(pins))
        for tier, pin in pins.items():
            row = rows[list(pins).index(tier)]
            self.assertEqual(plain(row["Native agent"]), pin["name"])
            self.assertEqual(plain(row["Model"]), pin["model"])
            self.assertEqual(pin["name"], "usr-" + tier)
            self.assertEqual(pin["model"], "swe-2-1-" + pin["effort"])
            content = yaml_blocks("dotfiles/base/.config/devin/agents/" + pin["name"] + ".md")
            fields = yaml_fields(content["native-agent"])
            self.assertEqual(fields, {"model": pin["model"]})
        for identifier in ("pi-subagent-bridge", "run_subagent", "subagent_explore", "subagent_general"):
            self.assertIn("`" + identifier + "`", block)
        scout = read("dotfiles/base/.config/devin/agents/usr-scout.md")
        self.assertNotIn("  - exec\n", scout)
        self.assertNotIn("  - edit\n", scout)
        self.assertNotIn("  - write\n", scout)

    def test_copilot_native_pilot_has_required_pins_and_leaf_tools(self):
        directory = ROOT / "dotfiles/base/.copilot"
        pins = POLICY["copilotNative"]
        self.assertEqual(set(pins), set(TIERS))
        block = self.block("copilot")
        tables = markdown_tables(block)
        self.assertEqual(len(tables), 1)
        rows = tables[0]
        self.assertEqual(set(rows[0]), {"Tier", "Native agent", "Candidate model", "Effort"})
        self.assertEqual([row["Tier"] for row in rows], list(pins))
        self.assertNotIn("copilot", {route["executor"] for routes in POLICY["rootRoutes"].values() for route in routes})
        settings = json.loads((directory / "settings.json").read_text())
        self.assertNotEqual(settings["model"], "auto")
        self.assertFalse(settings["remoteExport"])
        self.assertEqual(settings["subagents"]["maxDepth"], 1)
        for tier, pin in pins.items():
            row = rows[list(pins).index(tier)]
            self.assertEqual(plain(row["Native agent"]), pin["name"])
            self.assertEqual(plain(row["Candidate model"]), pin["model"])
            self.assertEqual(plain(row["Effort"]), pin["effort"])
            self.assertEqual(pin["name"], "usr-" + tier)
            self.assertNotEqual(pin["model"].lower(), "auto")
            profile = (directory / "agents" / (pin["name"] + ".agent.md")).read_text()
            fields = yaml_fields(parse_blocks(profile, yaml=True)["native-agent"])
            self.assertEqual(fields, {
                "model": pin["model"],
                "reasoning-effort": pin["effort"],
                "model-policy": "required",
            })
            self.assertNotIn("reasoningEffort:", profile)
            self.assertNotIn("modelPolicy:", profile)
            self.assertIn("strict-tools-list: true", profile)
            self.assertIn("infer: false", profile)
            if tier == "scout":
                match = re.search(r"^tools:\s*(\[.*\])$", profile, re.MULTILINE)
                self.assertIsNotNone(match)
                self.assertEqual(json.loads(match.group(1)), ["read", "grep", "glob"])
        for identifier in ("task", "Auto"):
            self.assertIn(identifier, block)

    def test_command_code_native_agents_are_pinned(self):
        block = self.block("command-code")
        config = POLICY["commandNative"]
        self.assertEqual(set(config), set(TIERS) | {"pilot"})
        tables = markdown_tables(block)
        self.assertEqual(len(tables), 1)
        rows = tables[0]
        self.assertEqual(set(rows[0]), {"Tier", "Native agent", "Model", "Effort"})
        self.assertEqual(len(rows), len(config))
        for row in rows:
            tier = "pilot" if "pilot" in row["Tier"] else row["Tier"].split()[0]
            self.assertIn(tier, config)
            pin = config[tier]
            self.assertEqual(plain(row["Native agent"]), pin["name"])
            self.assertEqual(plain(row["Model"]), pin["model"])
            if "effort" in pin:
                self.assertEqual(plain(row["Effort"]), pin["effort"])
            else:
                self.assertEqual(inline_code(row["Effort"]), [])
            content = yaml_blocks("dotfiles/base/.commandcode/agents/" + pin["name"] + ".md")
            expected = {"model": pin["model"]}
            if "effort" in pin:
                expected["reasoningEffort"] = pin["effort"]
            self.assertEqual(yaml_fields(content["native-agent"]), expected)
        scout_name = config["scout"]["name"]
        scout = read("dotfiles/base/.commandcode/agents/" + scout_name + ".md")
        tools_line = re.search(r"^tools:\s*(.+)$", scout, re.MULTILINE)
        self.assertIsNotNone(tools_line)
        tools = [tool.strip() for tool in tools_line.group(1).split(",")]
        self.assertEqual(tools, ["read_file", "read_directory", "grep", "glob"])
        self.assertNotIn("shell_command", tools)
        self.assertNotIn("edit_file", tools)
        for identifier in ("agent", "pi-subagent-bridge", "cmd --list-models", "/model", "agent_output", "scope-check --lane"):
            self.assertIn("`" + identifier + "`", block)

    def test_global_rule(self):
        expert = POLICY["rootRoutes"]["expert"][0]
        for path in ("dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.agents/instructions/lean.md"):
            generated = html_blocks(path)["delegation"]
            self.assertIn("`pi-subagent-bridge`", generated)
            self.assertIn("`orchestrate`", generated)
            self.assertIn("`god`", generated)
            for family in POLICY["bannedModels"]:
                self.assertIn("`" + family + "`", generated)
            for harness in ("OpenCode", "Devin", "Command Code", "Antigravity", "Copilot CLI"):
                self.assertIn(harness, generated)
        generated = html_blocks("dotfiles/base/.codex/AGENTS.md")["delegation"]
        self.assertIn("`" + policy_route(expert)[1] + "`", generated)
        self.assertIn("`" + expert["effort"] + "`", generated)


    def test_policy_claim_guidance(self):
        self.assertIn("make policy-claim", self.text)
        self.assertIn("make policy-release", self.text)
        self.assertIn("make policy-claims", self.text)
        self.assertIn("Before editing model policy", self.text)

if __name__ == "__main__":
    unittest.main()
