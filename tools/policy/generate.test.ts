import test from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, unlinkSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { POLICY, policyForHarnesses } from "../pi-subagent-bridge/src/policy.ts"
import { HARNESS_IDS, type HarnessSwitches } from "../pi-subagent-bridge/src/harnesses.ts"
import { main, renderOutputs, replaceBlocks, writeOutputs, TEMPLATE_PATHS, type Policy } from "./generate.ts"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const JSON_PATH = "tools/policy/policy.generated.json"

const ALL_ENABLED = Object.fromEntries(HARNESS_IDS.map(id => [id, true])) as HarnessSwitches
const ENABLED_POLICY = policyForHarnesses(ALL_ENABLED)

function fixture(policy: Policy = POLICY) {
  const scratch = join(ROOT, ".work/tmp")
  mkdirSync(scratch, { recursive: true })
  const root = mkdtempSync(join(scratch, "policy-"))
  const initial = renderOutputs(ROOT, policy)
  for (const output of initial) {
    mkdirSync(dirname(join(root, output.path)), { recursive: true })
    writeFileSync(join(root, output.path), output.content)
  }
  return { root, paths: initial.map(output => output.path), close: () => rmSync(root, { recursive: true, force: true }) }
}

test("a root route pin change propagates to the README table and JSON export, leaving native policy untouched", () => {
  const f = fixture(ENABLED_POLICY)
  try {
    const policy: Policy = {
      ...ENABLED_POLICY,
      rootRoutes: { ...ENABLED_POLICY.rootRoutes, worker: [{ ...ENABLED_POLICY.rootRoutes.worker[0], model: "fixture-worker-model" }, ...ENABLED_POLICY.rootRoutes.worker.slice(1)] },
    }
    const outputs = renderOutputs(f.root, policy)
    const changed = outputs.filter(output => output.content !== output.previous)
    assert.deepEqual(changed.map(output => output.path), ["tools/pi-subagent-bridge/README.md", JSON_PATH])
    const table = changed.find(output => output.path === "tools/pi-subagent-bridge/README.md")!
    assert.ok(table.content.includes("| worker | Command Code `fixture-worker-model` (`high`) |"))
    const exported = JSON.parse(changed.find(output => output.path === JSON_PATH)!.content)
    assert.equal(exported.rootRoutes.worker[0].model, "fixture-worker-model")
    assert.deepEqual(exported.nativePi, ENABLED_POLICY.nativePi)
    assert.deepEqual(writeOutputs(f.root, outputs), changed.map(output => output.path))
    const mtimes = f.paths.map(path => statSync(join(f.root, path)).mtimeMs)
    assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root, policy)), [])
    assert.deepEqual(f.paths.map(path => statSync(join(f.root, path)).mtimeMs), mtimes)
  } finally { f.close() }
})

test("check mode detects stale generated content without repairing or rewriting any file", () => {
  const f = fixture()
  try {
    assert.equal(main(["--check"], f.root), 0)
    const path = join(f.root, "docs/pi.md")
    writeFileSync(path, readFileSync(path, "utf8").replace("gemini-4-argon", "stale-policy-model"))
    const before = f.paths.map(path => readFileSync(join(f.root, path), "utf8"))
    const mtimes = f.paths.map(path => statSync(join(f.root, path)).mtimeMs)
    assert.equal(main(["--check"], f.root), 1)
    assert.deepEqual(f.paths.map(path => readFileSync(join(f.root, path), "utf8")), before)
    assert.deepEqual(f.paths.map(path => statSync(join(f.root, path)).mtimeMs), mtimes)
    assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root)), ["docs/pi.md"])
    assert.equal(main(["--check"], f.root), 0)
  } finally { f.close() }
})

test("generation preserves authored prose, profile descriptions and unrelated JSON settings", () => {
  const f = fixture()
  try {
    const doc = join(f.root, "docs/pi.md")
    writeFileSync(doc, readFileSync(doc, "utf8") + "\nAuthored sentinel outside policy.\n")
    const profile = join(f.root, "dotfiles/base/.pi/agent/agents/scout.md")
    writeFileSync(profile, readFileSync(profile, "utf8").replace("description: Read-only inventory and evidence gathering.", "description: Authored sentinel."))
    const pi = join(f.root, "dotfiles/base/.pi/agent/settings.json")
    const source = join(f.root, TEMPLATE_PATHS[0])
    const authored = JSON.parse(readFileSync(source, "utf8"))
    authored.defaultModel = "owner-session-default"
    authored.subagents.agentOverrides.scout = { extra: "retained" }
    authored.subagents.modelScope.agents.scout = { extra: "retained" }
    writeFileSync(source, JSON.stringify(authored, null, 2) + "\n")
    const settings = JSON.parse(readFileSync(pi, "utf8"))
    settings.defaultModel = authored.defaultModel
    settings.subagents.agentOverrides.scout.extra = "retained"
    settings.subagents.modelScope.agents.scout.extra = "retained"
    const opencode = join(f.root, "dotfiles/base/.config/opencode/opencode.json")
    const native = JSON.parse(readFileSync(opencode, "utf8"))
    native.model = "owner-session-default"
    native.agents.scout.description = "Authored sentinel"
    native.agents.custom = { model: "owner-custom-agent" }
    writeFileSync(opencode, JSON.stringify(native, null, 2) + "\n")
    assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root)), ["dotfiles/base/.pi/agent/settings.json"])
    assert.match(readFileSync(doc, "utf8"), /Authored sentinel outside policy/)
    assert.match(readFileSync(profile, "utf8"), /description: Authored sentinel/)
    assert.deepEqual(JSON.parse(readFileSync(pi, "utf8")), settings)
    assert.deepEqual(JSON.parse(readFileSync(opencode, "utf8")), native)
  } finally { f.close() }
})

test("all markers validate before any output is written", () => {
  const f = fixture()
  try {
    const path = join(f.root, "docs/agent-setup.md")
    writeFileSync(path, readFileSync(path, "utf8").replace("policy:begin routing-summary", "policy:begin unknown"))
    const before = f.paths.map(path => readFileSync(join(f.root, path), "utf8"))
    assert.throws(() => writeOutputs(f.root, renderOutputs(f.root)), /Unknown generated policy block/)
    assert.deepEqual(f.paths.map(path => readFileSync(join(f.root, path), "utf8")), before)
  } finally { f.close() }
})

test("missing, duplicate, nested, malformed and unknown template blocks are rejected", () => {
  const valid = "before\n<!-- policy:begin rule -->\nold\n<!-- policy:end rule -->\nafter\n"
  assert.match(replaceBlocks(valid, { rule: "new" }), /before[\s\S]*new[\s\S]*after/)
  for (const invalid of [
    valid.replace("<!-- policy:end rule -->", ""), valid + valid,
    valid.replace("old", "<!-- policy:begin rule -->"), valid.replace("begin rule", "begin Rule"),
    valid.replaceAll("rule", "unknown"), valid.replace("begin rule", "end rule"),
  ]) assert.throws(() => replaceBlocks(invalid, { rule: "new" }), /generated policy|policy marker/)
})

test("generation refuses input changes after planning instead of overwriting concurrent edits", () => {
  const f = fixture()
  try {
    const outputs = renderOutputs(f.root)
    const path = join(f.root, "docs/pi.md")
    const edited = readFileSync(path, "utf8") + "\nConcurrent author edit.\n"
    writeFileSync(path, edited)
    assert.throws(() => writeOutputs(f.root, outputs), /input changed while rendering/)
    assert.equal(readFileSync(path, "utf8"), edited)
  } finally { f.close() }
})

test("a concurrent template edit rejects stale projections before writing any output", () => {
  const f = fixture()
  try {
    const policy = structuredClone(POLICY)
    Reflect.set(policy.rootRoutes.worker[0], "model", "pending-route-update")
    const outputs = renderOutputs(f.root, policy)
    const source = join(f.root, TEMPLATE_PATHS[0])
    const authored = JSON.parse(readFileSync(source, "utf8"))
    authored.defaultModel = "concurrent-owner-choice"
    const edited = JSON.stringify(authored, null, 2) + "\n"
    writeFileSync(source, edited)
    const before = f.paths.map(path => readFileSync(join(f.root, path), "utf8"))
    assert.throws(() => writeOutputs(f.root, outputs), /input changed while rendering: tools\/policy\/templates\/pi-settings\.json/)
    assert.deepEqual(f.paths.map(path => readFileSync(join(f.root, path), "utf8")), before)
    assert.equal(readFileSync(source, "utf8"), edited)
  } finally { f.close() }
})

test("retired roles cannot silently survive in native profiles or harness configuration", () => {
  const f = fixture()
  try {
    const policy = structuredClone(POLICY)
    Reflect.set(policy, "tiers", policy.tiers.filter(tier => tier !== "mechanic"))
    for (const record of [policy.rootRoutes, policy.nativePi.goModels, policy.nativePi.tools,
      policy.nativePi.delegation, policy.nativePi.devinModels, policy.nativePi.devinAgentNames,
      policy.nativePi.devinDelegation, policy.opencode.efforts, policy.nativeFallback.claudeModels])
      Reflect.deleteProperty(record, "mechanic")
    for (const record of [policy.nativePi.delegation, policy.nativePi.devinDelegation])
      for (const [tier, children] of Object.entries(record))
        Reflect.set(record, tier, (children as readonly string[]).filter(child => child !== "mechanic" && child !== "devin-mechanic"))
    Reflect.set(policy.nativeFallback, "tiers", policy.nativeFallback.tiers.filter(tier => tier !== "mechanic"))
    const before = f.paths.map(path => readFileSync(join(f.root, path), "utf8"))
    assert.throws(() => renderOutputs(f.root, policy), /Retired native profile mechanic: explicitly remove/)
    assert.deepEqual(f.paths.map(path => readFileSync(join(f.root, path), "utf8")), before)
    unlinkSync(join(f.root, "dotfiles/base/.pi/agent/agents/mechanic.md"))
    unlinkSync(join(f.root, "dotfiles/base/.pi/agent/agents/devin-mechanic.md"))
    const settingsPath = join(f.root, "dotfiles/base/.pi/agent/settings.json")
    const settings = JSON.parse(readFileSync(settingsPath, "utf8"))
    delete settings.subagents.agentOverrides.mechanic
    delete settings.subagents.modelScope.agents.mechanic
    delete settings.subagents.agentOverrides["devin-mechanic"]
    delete settings.subagents.modelScope.agents["devin-mechanic"]
    writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + "\n")
    assert.throws(() => renderOutputs(f.root, policy), /Retired OpenCode tier mechanic: explicitly remove/)
    const openCodePath = join(f.root, "dotfiles/base/.config/opencode/opencode.json")
    const openCode = JSON.parse(readFileSync(openCodePath, "utf8"))
    delete openCode.agents.mechanic
    writeFileSync(openCodePath, JSON.stringify(openCode, null, 2) + "\n")
    const outputs = renderOutputs(f.root, policy)
    assert.ok(!outputs.some(output => output.path.endsWith("agents/mechanic.md")))
    for (const output of outputs) {
      if (output.path === "dotfiles/base/.agents/skills/orchestrate/SKILL.md") {
        assert.ok(output.content.includes("| mechanic | `usr-mechanic` |"))
        continue
      }
      assert.ok(!output.content.includes("| mechanic |"), output.path)
    }
    writeOutputs(f.root, outputs)
    assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root, policy)), [])
  } finally { f.close() }
})

test("malformed prior ownership snapshots fail before changing files", () => {
  const f = fixture()
  try {
    for (const invalid of ["{", JSON.stringify({ schema_version: 99 }),
      JSON.stringify({ ...POLICY, nativePi: { ...POLICY.nativePi, agentNames: { worker: "../foreign" } } })]) {
      writeFileSync(join(f.root, JSON_PATH), invalid)
      const before = f.paths.map(path => readFileSync(join(f.root, path), "utf8"))
      assert.throws(() => writeOutputs(f.root, renderOutputs(f.root)))
      assert.deepEqual(f.paths.map(path => readFileSync(join(f.root, path), "utf8")), before)
    }
  } finally { f.close() }
})

test("provider-qualified prohibited models fail before any projection is written", () => {
  const f = fixture()
  try {
    const before = f.paths.map(path => readFileSync(join(f.root, path), "utf8"))
    for (const model of ["gemini-4-argon-high", "google/gemini-4-argon-high", "antigravity/gemini-4-carbon-xhigh", "claude-fable-5-2", "anthropic/claude-fable-5-2"]) {
      const policy: Policy = {
        ...POLICY,
        rootRoutes: { ...POLICY.rootRoutes, worker: [{ ...POLICY.rootRoutes.worker[0], model }, ...POLICY.rootRoutes.worker.slice(1)] },
      }
      assert.throws(() => writeOutputs(f.root, renderOutputs(f.root, policy)), /Prohibited model in active policy/)
      assert.deepEqual(f.paths.map(path => readFileSync(join(f.root, path), "utf8")), before)
    }
  } finally { f.close() }
})

test("prohibited native Claude aliases cannot be projected", () => {
  const f = fixture()
  try {
    for (const model of ["fable", "claude-fable-5-2"]) {
      const policy = structuredClone(POLICY)
      Reflect.set(policy.nativeFallback.claudeModels, "worker", model)
      assert.throws(() => renderOutputs(f.root, policy), /Prohibited model in active policy/)
    }
  } finally { f.close() }
})

type Pin = { providerID: string; id: string; variant: string }
type MutablePolicy = {
  rootRoutes: Record<string, Array<{ executor: string; providerID?: string; model: string; effort: string }>>
  nativePi: {
    goModels: Record<string, Pin>
    delegation: Record<string, string[]>; tools: Record<string, string[]>
    maxSubagentDepth: number; modelAllowlist: string[]
  }
  opencode: { model: string; efforts: Record<string, string> }
  commandNative: Record<string, { name: string; model: string; effort?: string }>
  devinNative: Record<string, { name: string; model: string; effort: string }>
  copilotNative: Record<string, { name: string; model: string; effort: string }>
  nativeFallback: { tiers: string[]; claudeModels: Record<string, string> }
  antigravityDirect: { models: string[]; main: { model: string; effort: string }; god: { model: string; effort: string }; tiers: Record<string, { name: string; model: string; effort: string; selector: string }>; manualCarbon: string; retired: string[] }
  bannedModels: string[]
}
type Dimension = { name: string; mutate: (policy: MutablePolicy) => void; rejects?: RegExp }

const FIXTURE_MODEL = "fixture-model"
const otherEffort = (value: string) => (["low", "medium", "high", "xhigh", "max"] as const).find(effort => effort !== value)!
const dimensions: Dimension[] = [
  { name: "command scout model", mutate: p => { p.rootRoutes.scout[0].model = FIXTURE_MODEL } },
  { name: "command scout effort", mutate: p => { p.rootRoutes.scout[0].effort = "low" } },
  { name: "command mechanic model", mutate: p => { p.rootRoutes.mechanic[0].model = FIXTURE_MODEL } },
  { name: "command mechanic effort", mutate: p => { p.rootRoutes.mechanic[0].effort = "low" } },
  { name: "command worker model", mutate: p => { p.rootRoutes.worker[0].model = FIXTURE_MODEL } },
  { name: "command worker effort", mutate: p => { p.rootRoutes.worker[0].effort = "low" } },

  { name: "pi scout model", mutate: p => { p.rootRoutes.scout[1].model = FIXTURE_MODEL } },
  { name: "pi scout provider", mutate: p => { p.rootRoutes.scout[1].providerID = "fixture-provider" } },
  { name: "pi scout effort", mutate: p => { p.rootRoutes.scout[1].effort = "low" } },
  { name: "pi mechanic model", mutate: p => { p.rootRoutes.mechanic[1].model = FIXTURE_MODEL } },
  { name: "pi mechanic effort", mutate: p => { p.rootRoutes.mechanic[1].effort = "low" } },
  { name: "pi worker first model", mutate: p => { p.rootRoutes.worker[1].model = FIXTURE_MODEL } },
  { name: "pi worker second effort", mutate: p => { p.rootRoutes.worker[2].effort = "low" } },
  { name: "pi worker order", mutate: p => { p.rootRoutes.worker.splice(2, 0, ...p.rootRoutes.worker.splice(1, 1)) } },
  { name: "pi worker list length", mutate: p => { p.rootRoutes.worker.splice(1, 1) } },
  { name: "expert Devin route model", mutate: p => { p.rootRoutes.expert[0].model = FIXTURE_MODEL } },
  { name: "expert Devin route effort", mutate: p => { p.rootRoutes.expert[0].effort = "xhigh" } },

  { name: "codex scout model", mutate: p => { p.rootRoutes.scout.at(-1)!.model = FIXTURE_MODEL } },
  { name: "codex scout effort", mutate: p => { p.rootRoutes.scout.at(-1)!.effort = "xhigh" } },
  { name: "codex mechanic model", mutate: p => { p.rootRoutes.mechanic.at(-1)!.model = FIXTURE_MODEL } },
  { name: "codex mechanic effort", mutate: p => { p.rootRoutes.mechanic.at(-1)!.effort = "low" } },
  { name: "codex worker model", mutate: p => { p.rootRoutes.worker.at(-1)!.model = FIXTURE_MODEL } },
  { name: "codex worker effort", mutate: p => { p.rootRoutes.worker.at(-1)!.effort = "max" } },

  ...(["scout", "mechanic", "worker", "expert"] as const).flatMap(tier => [
    { name: "Copilot " + tier + " model", mutate: (p: MutablePolicy) => { p.copilotNative[tier].model = FIXTURE_MODEL } },
    { name: "Copilot " + tier + " effort", mutate: (p: MutablePolicy) => { p.copilotNative[tier].effort = otherEffort(p.copilotNative[tier].effort) } },
  ]),
  { name: "Copilot banned model", mutate: p => { p.copilotNative.worker.model = "claude-fable-5-2" }, rejects: /Prohibited model in active policy/ },
  { name: "Copilot Auto model", mutate: p => { p.copilotNative.scout.model = "auto" }, rejects: /cannot use Auto/ },
  { name: "Copilot uppercase Auto model", mutate: p => { p.copilotNative.scout.model = "Auto" }, rejects: /cannot use Auto/ },
  { name: "Copilot case-insensitive banned model", mutate: p => { p.copilotNative.worker.model = "Anthropic/Claude-Fable-5-2" }, rejects: /Prohibited model in active policy/ },
  { name: "command native scout model", mutate: p => { p.commandNative.scout.model = FIXTURE_MODEL } },
  { name: "command native mechanic model", mutate: p => { p.commandNative.mechanic.model = FIXTURE_MODEL } },
  { name: "command native mechanic effort", mutate: p => { p.commandNative.mechanic.effort = "low" } },
  { name: "command native worker model", mutate: p => { p.commandNative.worker.model = FIXTURE_MODEL } },
  { name: "command native worker effort", mutate: p => { p.commandNative.worker.effort = "medium" } },
  { name: "command native expert model", mutate: p => { p.commandNative.expert.model = FIXTURE_MODEL } },
  { name: "command native expert effort", mutate: p => { p.commandNative.expert.effort = "medium" } },
  { name: "command native HY4 pilot model", mutate: p => { p.commandNative.pilot.model = FIXTURE_MODEL } },
  { name: "command native HY4 pilot effort", mutate: p => { p.commandNative.pilot.effort = "high" } },
  { name: "command native banned model", mutate: p => { p.commandNative.worker.model = "gemini-4-argon-high" }, rejects: /Prohibited model in active policy/ },
  ...(["scout", "mechanic", "worker", "expert"] as const).flatMap(tier => [
    { name: "Devin native " + tier + " model", mutate: (p: MutablePolicy) => { p.devinNative[tier].model = FIXTURE_MODEL }, rejects: /does not pin the matching SWE-2\.1 variant/ },
    { name: "Devin native " + tier + " effort", mutate: (p: MutablePolicy) => { p.devinNative[tier].effort = otherEffort(p.devinNative[tier].effort) }, rejects: /does not pin the matching SWE-2\.1 variant/ },
  ]),
  { name: "Devin native mismatched pin", mutate: p => { p.devinNative.expert.model = "swe-2-1-high" }, rejects: /does not pin the matching SWE-2\.1 variant/ },
  { name: "opencode model", mutate: p => { p.opencode.model = "opencode/fixture-free" } },
  { name: "opencode scout effort", mutate: p => { p.opencode.efforts.scout = otherEffort(p.opencode.efforts.scout) } },
  { name: "opencode mechanic effort", mutate: p => { p.opencode.efforts.mechanic = otherEffort(p.opencode.efforts.mechanic) } },
  { name: "opencode worker effort", mutate: p => { p.opencode.efforts.worker = otherEffort(p.opencode.efforts.worker) } },
  { name: "opencode expert effort", mutate: p => { p.opencode.efforts.expert = otherEffort(p.opencode.efforts.expert) } },

  { name: "native fallback tiers", mutate: p => { p.nativeFallback.tiers = ["scout", "mechanic"] } },
  { name: "native fallback scout Claude model", mutate: p => { p.nativeFallback.claudeModels.scout = "opus" } },
  { name: "native fallback mechanic Claude model", mutate: p => { p.nativeFallback.claudeModels.mechanic = "haiku" } },
  { name: "native fallback worker Claude model", mutate: p => { p.nativeFallback.claudeModels.worker = "opus" } },

  { name: "antigravity direct first model", mutate: p => { p.antigravityDirect.models[0] = "fixture-direct-a" } },
  { name: "antigravity direct second model", mutate: p => { p.antigravityDirect.models[1] = "fixture-direct-b" } },
  { name: "antigravity direct list length", mutate: p => { p.antigravityDirect.models.push("fixture-direct-c") } },
  { name: "antigravity main model", mutate: p => { p.antigravityDirect.main.model = "fixture-main-model" } },
  { name: "antigravity god model", mutate: p => { p.antigravityDirect.god.model = "fixture-god-model" } },
  { name: "antigravity worker model", mutate: p => { p.antigravityDirect.tiers.worker.model = "fixture-worker-model" } },
  { name: "antigravity scout effort", mutate: p => { p.antigravityDirect.tiers.scout.effort = "medium" } },
  { name: "antigravity native selector", mutate: p => { p.antigravityDirect.tiers.mechanic.selector = "pro" } },
  { name: "antigravity manual Carbon", mutate: p => { p.antigravityDirect.manualCarbon = "fixture-carbon-model" } },
  { name: "antigravity retired model", mutate: p => { p.antigravityDirect.retired.push("fixture-retired-model") } },
  { name: "antigravity invalid selector", mutate: p => { p.antigravityDirect.tiers.worker.selector = "invalid" }, rejects: /Invalid Antigravity CLI model selector/ },

  { name: "banned family list", mutate: p => { p.bannedModels = ["gemini-4-argon"] } },
  { name: "banned family covering the direct Antigravity model", mutate: p => { p.bannedModels.push("gemini-4-hydrogen") }, rejects: /Prohibited model in active policy/ },
  { name: "banned family covering a Pi route", mutate: p => { p.bannedModels.push("muse-spark-1.3-contributor") }, rejects: /Prohibited model in active policy/ },

  { name: "native scout model", mutate: p => { p.nativePi.goModels.scout.id = FIXTURE_MODEL } },
  { name: "native scout provider", mutate: p => { p.nativePi.goModels.scout.providerID = "fixture-provider" } },
  { name: "native scout variant", mutate: p => { p.nativePi.goModels.scout.variant = "low" } },
  { name: "native mechanic model", mutate: p => { p.nativePi.goModels.mechanic.id = FIXTURE_MODEL } },
  { name: "native mechanic variant", mutate: p => { p.nativePi.goModels.mechanic.variant = "low" } },
  { name: "native worker model", mutate: p => { p.nativePi.goModels.worker.id = FIXTURE_MODEL } },
  { name: "native worker variant", mutate: p => { p.nativePi.goModels.worker.variant = "low" } },
  { name: "native expert model", mutate: p => { p.nativePi.goModels.expert.id = FIXTURE_MODEL } },
  { name: "native expert variant", mutate: p => { p.nativePi.goModels.expert.variant = "low" } },
  { name: "native banned model", mutate: p => { p.nativePi.goModels.worker.id = "gemini-4-argon-high" }, rejects: /Prohibited model in active policy/ },
  { name: "scout delegation", mutate: p => { p.nativePi.delegation.scout.push("mechanic") } },
  { name: "mechanic delegation", mutate: p => { p.nativePi.delegation.mechanic = ["mechanic"] } },
  { name: "worker delegation", mutate: p => { p.nativePi.delegation.worker.pop() } },
  { name: "expert delegation", mutate: p => { p.nativePi.delegation.expert.shift() } },
  { name: "delegation to an unknown profile", mutate: p => { p.nativePi.delegation.scout.push("unknown-profile") }, rejects: /Unknown descendant in scout/ },

  { name: "scout tools", mutate: p => { p.nativePi.tools.scout.push("fixture-tool") } },
  { name: "mechanic tools", mutate: p => { p.nativePi.tools.mechanic.push("fixture-tool") } },
  { name: "worker tools", mutate: p => { p.nativePi.tools.worker.pop() } },
  { name: "expert tools", mutate: p => { p.nativePi.tools.expert.shift() } },

  { name: "native depth", mutate: p => { p.nativePi.maxSubagentDepth = 3 } },
  { name: "invalid native depth", mutate: p => { p.nativePi.maxSubagentDepth = 0 }, rejects: /Invalid native Pi depth/ },
  { name: "native model allowlist", mutate: p => { p.nativePi.modelAllowlist.push("opencode-go/fixture-model") } },
]

test("every policy dimension reaches a rendered output or is rejected before generation", () => {
  assert.equal(new Set(dimensions.map(dimension => dimension.name)).size, dimensions.length)
  const f = fixture(ENABLED_POLICY)
  try {
    for (const dimension of dimensions) {
      const mutated: MutablePolicy = JSON.parse(JSON.stringify(ENABLED_POLICY))
      dimension.mutate(mutated)
      const policy: Policy = Object.assign({}, ENABLED_POLICY, mutated)
      if (dimension.rejects) {
        assert.throws(() => renderOutputs(f.root, policy), dimension.rejects, dimension.name)
        continue
      }
      const changed = renderOutputs(f.root, policy).filter(output => output.content !== output.previous).map(output => output.path)
      assert.ok(changed.some(path => path !== JSON_PATH), dimension.name + " changed only the JSON export: " + changed.join(", "))
    }
  } finally { f.close() }
})

const CONTEXT_PATHS = [
  "dotfiles/base/.codex/AGENTS.md",
  "dotfiles/base/.agents/instructions/lean.md",
  "dotfiles/base/.agents/skills/orchestrate/SKILL.md",
  "dotfiles/base/.agents/skills/resume-session/SKILL.md",
  "dotfiles/base/.agents/skills/resume-session/references/locate.md",
]
const HARNESS_TEXT = {
  claude: /Claude Code/,
  codex: /\bCodex\b/,
  "command-code": /Command Code|cmd --|COMMANDCODE_HOME/,
  pi: /\bPi\b/,
  opencode: /OpenCode(?! Go)/,
  "opencode-go": /OpenCode Go/,
  devin: /\bDevin\b/,
  antigravity: /Antigravity/,
  copilot: /Copilot/,
  fx: /\bfx\b/,
  muse: /Muse Code/,
  deepseek: /DeepSeek (?:Harness|TUI)/,
} as const

function context(outputs: ReturnType<typeof renderOutputs>): string {
  return outputs.filter(output => CONTEXT_PATHS.includes(output.path)).map(output => output.content).join("\n")
}

test("each disabled harness disappears from shared instructions and restores without losing its source", () => {
  const f = fixture(ENABLED_POLICY)
  try {
    const baseline = context(renderOutputs(f.root, ENABLED_POLICY))
    for (const id of HARNESS_IDS) {
      assert.match(baseline, HARNESS_TEXT[id], `${id} has an enabled context projection`)
      const policy = policyForHarnesses({ ...ALL_ENABLED, [id]: false })
      const disabled = renderOutputs(f.root, policy)
      assert.doesNotMatch(context(disabled), HARNESS_TEXT[id], `${id} leaked into shared context`)
      writeOutputs(f.root, disabled)
      assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root, policy)), [], `${id} disabled regeneration is idempotent`)
      const restored = renderOutputs(f.root, ENABLED_POLICY)
      assert.equal(context(restored), baseline, `${id} enable restores the original instructions`)
      writeOutputs(f.root, restored)
      assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root, ENABLED_POLICY)), [])
    }
  } finally { f.close() }
})

test("all harnesses can be disabled without a missing-route crash or implicit fallback", () => {
  const f = fixture(ENABLED_POLICY)
  try {
    const policy = policyForHarnesses(Object.fromEntries(HARNESS_IDS.map(id => [id, false])) as HarnessSwitches)
    const outputs = renderOutputs(f.root, policy)
    const rendered = context(outputs)
    for (const id of HARNESS_IDS) assert.doesNotMatch(rendered, HARNESS_TEXT[id], id)
    assert.match(rendered, /Delegation is blocked: no harness lane is enabled/)
    const exported = JSON.parse(outputs.find(output => output.path === JSON_PATH)!.content)
    assert.ok(Object.values(exported.rootRoutes).every(routes => Array.isArray(routes) && routes.length === 0))
    const table = outputs.find(output => output.path === "tools/pi-subagent-bridge/README.md")!.content
    assert.equal((table.match(/Blocked\. No enabled route\./g) ?? []).length, policy.tiers.length)
    writeOutputs(f.root, outputs)
    assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root, policy)), [])
    assert.equal(context(renderOutputs(f.root, ENABLED_POLICY)), context(renderOutputs(ROOT, ENABLED_POLICY)))
  } finally { f.close() }
})

test("the shipped disabled Command Code switch removes all of its active context", () => {
  assert.equal(POLICY.harnesses["command-code"], false)
  const outputs = renderOutputs(ROOT)
  assert.doesNotMatch(context(outputs), HARNESS_TEXT["command-code"])
  assert.match(context(renderOutputs(ROOT, ENABLED_POLICY)), /Command Code/)
  assert.ok(CONTEXT_PATHS.every(path => outputs.some(output => output.path === path)))
})

test("disabled Pi providers leave no missing-profile settings and preserve authored extras on reenable", () => {
  const f = fixture(ENABLED_POLICY)
  try {
    const source = join(f.root, TEMPLATE_PATHS[0])
    const authored = JSON.parse(readFileSync(source, "utf8"))
    authored.subagents.agentOverrides.scout = { extra: "keep-owner-override" }
    authored.subagents.modelScope.agents["devin-expert"] = { extra: "keep-owner-scope" }
    writeFileSync(source, JSON.stringify(authored, null, 2) + "\n")
    const baseline = renderOutputs(f.root, ENABLED_POLICY)
    const settingsPath = "dotfiles/base/.pi/agent/settings.json"
    const original = baseline.find(output => output.path === settingsPath)!.content
    for (const disabled of ["opencode-go", "devin", "pi"] as const) {
      const policy = policyForHarnesses({ ...ALL_ENABLED, [disabled]: false })
      const outputs = renderOutputs(f.root, policy)
      const settings = JSON.parse(outputs.find(output => output.path === settingsPath)!.content)
      const activeNames = Object.keys(settings.subagents.agentOverrides)
      assert.deepEqual([...activeNames].sort(), Object.keys(settings.subagents.modelScope.agents).sort())
      assert.ok(settings.subagents.modelScope.allow.every((pin: string) => disabled !== "pi" && !pin.startsWith(disabled + "/")))
      for (const [name, override] of Object.entries(settings.subagents.agentOverrides)) {
        assert.ok(disabled !== "pi" && !(override as { model: string }).model.startsWith(disabled + "/"), name)
        const profile = outputs.find(output => output.path === `dotfiles/base/.pi/agent/agents/${name}.md`)!.content
        const allowed = profile.split("allowedAgents:")[1].split("# policy:end")[0].trim()
        const children = allowed === "[]" ? [] : allowed.split("\n").map(line => line.trim().slice(2))
        assert.ok(children.every(child => activeNames.includes(child)), `${name} names an unavailable child`)
      }
      writeOutputs(f.root, outputs)
      assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root, policy)), [])
      assert.equal(renderOutputs(f.root, ENABLED_POLICY).find(output => output.path === settingsPath)!.content, original)
      assert.deepEqual(JSON.parse(readFileSync(source, "utf8")), authored)
    }
  } finally { f.close() }
})
