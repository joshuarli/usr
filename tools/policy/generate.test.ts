import test from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, unlinkSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { POLICY } from "../pi-subagent-bridge/src/policy.ts"
import { main, renderOutputs, replaceBlocks, writeOutputs, type Policy } from "./generate.ts"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const JSON_PATH = "tools/policy/policy.generated.json"

function fixture() {
  const scratch = join(ROOT, ".work/tmp")
  mkdirSync(scratch, { recursive: true })
  const root = mkdtempSync(join(scratch, "policy-"))
  const initial = renderOutputs(ROOT)
  for (const output of initial) {
    mkdirSync(dirname(join(root, output.path)), { recursive: true })
    writeFileSync(join(root, output.path), output.content)
  }
  return { root, paths: initial.map(output => output.path), close: () => rmSync(root, { recursive: true, force: true }) }
}

test("one expert pin change propagates to every representation and leaves other policy fields untouched", () => {
  const f = fixture()
  try {
    const policy: Policy = {
      ...POLICY,
      rootRoutes: { ...POLICY.rootRoutes, expert: [{ executor: "antigravity", model: "fixture-expert-model", effort: "high" }] },
    }
    const outputs = renderOutputs(f.root, policy)
    const changed = outputs.filter(output => output.content !== output.previous)
    assert.deepEqual(changed.map(output => output.path), [
      "docs/agent-setup.md", "docs/pi.md", "dotfiles/base/.agents/instructions/lean.md",
      "dotfiles/base/.agents/skills/orchestrate/SKILL.md", "dotfiles/base/.codex/AGENTS.md",
      "tools/pi-subagent-bridge/README.md", JSON_PATH,
    ])
    for (const output of changed) {
      assert.match(output.content, /fixture-expert-model/, output.path)
      assert.ok(!output.content.includes(POLICY.rootRoutes.expert[0].model), output.path)
    }
    const table = changed.find(output => output.path.endsWith("orchestrate/SKILL.md"))!
    assert.ok(table.content.includes("| expert | Antigravity CLI `fixture-expert-model` (`high`) | **None. Fail closed.** |"))
    const exported = JSON.parse(changed.find(output => output.path === JSON_PATH)!.content)
    assert.deepEqual(exported.rootRoutes.expert, [{ executor: "antigravity", model: "fixture-expert-model", effort: "high" }])
    assert.deepEqual(exported.nativePi, POLICY.nativePi)
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
    writeFileSync(path, readFileSync(path, "utf8").replace("gemini-4-hydrogen-xhigh", "stale-policy-model"))
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
    const settings = JSON.parse(readFileSync(pi, "utf8"))
    settings.defaultModel = "owner-session-default"
    settings.subagents.agentOverrides.scout.extra = "retained"
    settings.subagents.modelScope.agents.scout.extra = "retained"
    writeFileSync(pi, JSON.stringify(settings, null, 2) + "\n")
    const opencode = join(f.root, "dotfiles/base/.config/opencode/opencode.json")
    const native = JSON.parse(readFileSync(opencode, "utf8"))
    native.model = "owner-session-default"
    native.agents.scout.description = "Authored sentinel"
    native.agents.custom = { model: "owner-custom-agent" }
    writeFileSync(opencode, JSON.stringify(native, null, 2) + "\n")
    assert.deepEqual(writeOutputs(f.root, renderOutputs(f.root)), [])
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

test("retired roles cannot silently survive in native profiles or harness configuration", () => {
  const f = fixture()
  try {
    const policy = structuredClone(POLICY)
    Reflect.set(policy, "tiers", policy.tiers.filter(tier => tier !== "mechanic"))
    for (const record of [policy.rootRoutes, policy.nativePi.goModels, policy.nativePi.tools,
      policy.nativePi.delegation, policy.opencode.efforts, policy.nativeFallback.claudeModels])
      Reflect.deleteProperty(record, "mechanic")
    for (const [tier, children] of Object.entries(policy.nativePi.delegation))
      Reflect.set(policy.nativePi.delegation, tier, children.filter(child => child !== "mechanic"))
    Reflect.set(policy.nativePi.museDelegation, "worker", policy.nativePi.museDelegation.worker.filter(child => child !== "mechanic"))
    Reflect.set(policy.nativeFallback, "tiers", policy.nativeFallback.tiers.filter(tier => tier !== "mechanic"))
    const before = f.paths.map(path => readFileSync(join(f.root, path), "utf8"))
    assert.throws(() => renderOutputs(f.root, policy), /Retired native profile mechanic: explicitly remove/)
    assert.deepEqual(f.paths.map(path => readFileSync(join(f.root, path), "utf8")), before)
    unlinkSync(join(f.root, "dotfiles/base/.pi/agent/agents/mechanic.md"))
    const settingsPath = join(f.root, "dotfiles/base/.pi/agent/settings.json")
    const settings = JSON.parse(readFileSync(settingsPath, "utf8"))
    delete settings.subagents.agentOverrides.mechanic
    delete settings.subagents.modelScope.agents.mechanic
    writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + "\n")
    assert.throws(() => renderOutputs(f.root, policy), /Retired OpenCode tier mechanic: explicitly remove/)
    const openCodePath = join(f.root, "dotfiles/base/.config/opencode/opencode.json")
    const openCode = JSON.parse(readFileSync(openCodePath, "utf8"))
    delete openCode.agents.mechanic
    writeFileSync(openCodePath, JSON.stringify(openCode, null, 2) + "\n")
    const outputs = renderOutputs(f.root, policy)
    assert.ok(!outputs.some(output => output.path.endsWith("agents/mechanic.md")))
    for (const output of outputs) assert.ok(!output.content.includes("| mechanic |"), output.path)
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
    for (const model of ["gemini-4-argon-high", "google/gemini-4-argon-high", "antigravity/gemini-4-carbon-xhigh"]) {
      const policy: Policy = {
        ...POLICY,
        rootRoutes: { ...POLICY.rootRoutes, expert: [{ executor: "antigravity", model, effort: "high" }] },
      }
      assert.throws(() => writeOutputs(f.root, renderOutputs(f.root, policy)), /Prohibited model in active policy/)
      assert.deepEqual(f.paths.map(path => readFileSync(join(f.root, path), "utf8")), before)
    }
  } finally { f.close() }
})
