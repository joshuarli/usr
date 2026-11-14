import { readFileSync, writeFileSync, renameSync, unlinkSync, lstatSync, realpathSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { POLICY, isBannedModel, type Route } from "../pi-subagent-bridge/src/policy.ts"
import { isTier, type Tier } from "../pi-subagent-bridge/src/tier-policy.ts"

export type Policy = Omit<typeof POLICY, "rootRoutes" | "tiers"> & {
  readonly tiers: readonly Tier[]
  readonly rootRoutes: Readonly<Record<Tier, readonly Route[]>>
}
type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
type JsonObject = { [key: string]: Json }
type Blocks = Readonly<Record<string, string>>
export type Output = { readonly path: string; readonly content: string; readonly previous: string | null }

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const SOURCE = "tools/pi-subagent-bridge/src/policy.ts"
const NOTICE = `<!-- Generated from ${SOURCE}; run make generate. -->`
const JSON_PATH = "tools/policy/policy.generated.json"
const PROFILE = "dotfiles/base/.pi/agent"
const LABELS = { codex: "Codex", "command-code": "Command Code", antigravity: "Antigravity CLI", pi: "Pi" } as const

function code(value: string): string {
  if (!/^[a-zA-Z0-9_./#-]+$/.test(value)) throw new Error(`Invalid policy identifier: ${value}`)
  return "`" + value + "`"
}

function model(route: Route): string {
  return route.executor === "pi" ? `${route.providerID}/${route.model}` : route.model
}

function routeLabel(route: Route): string {
  return `${LABELS[route.executor]} ${code(model(route))} (${code(route.effort)})`
}

function expert(policy: Policy): Route {
  const routes = policy.rootRoutes.expert
  if (routes.length !== 1 || routes[0].executor !== "antigravity")
    throw new Error("The expert projection requires one terminal Antigravity route")
  return routes[0]
}

export function routingTable(policy: Policy): string {
  const rows = policy.tiers.map(tier => {
    const [primary, ...fallback] = policy.rootRoutes[tier]
    if (!primary) throw new Error(`Missing route for ${tier}`)
    return `| ${tier} | ${routeLabel(primary)} | ${fallback.length ? fallback.map(routeLabel).join("; ") : "**None. Fail closed.**"} |`
  })
  return ["| Tier | Primary | Fallback (in order) |", "| --- | --- | --- |", ...rows].join("\n")
}

function summary(policy: Policy): string {
  return `New ${code("expert")} assignments use ${routeLabel(expert(policy))} exclusively, with no fallback. ` +
    `The available tiers are ${policy.tiers.map(code).join(", ")}; there is no ${code("god")} tier. ` +
    `The model families ${policy.bannedModels.map(code).join(" and ")} are prohibited, including every effort variant. ` +
    "Already-admitted sessions retain their recorded models and routes."
}

function openCode(policy: Policy): string {
  if (policy.opencode.usesBridge || !policy.opencode.freeOnlyWhenParentFree)
    throw new Error("OpenCode projection requires the native-only, free-parent policy")
  return "**OpenCode exception:** A top-level OpenCode session never uses `pi-subagent-bridge`, at any tier or as a fallback. " +
    "Delegate only through its configured native agents or built-in `general`/`explore`. When the top-level model is free, every tier must run a free model. " +
    `The configured tier agents use ${code(policy.opencode.model)} regardless of the top-level model:\n\n` +
    ["| Tier | Effort |", "| --- | --- |", ...openCodeTiers(policy).map(tier =>
      `| ${tier}${tier === "scout" ? " (read-only: no `shell`, no `edit`)" : ""} | ${policy.opencode.efforts[tier]} |`)].join("\n") +
    "\n\nBridge pins, fallbacks, and nesting rules do not apply on this path."
}

function nativeFallback(policy: Policy): string {
  const tiers = policy.nativeFallback.tiers.join("/")
  const mappings = policy.nativeFallback.tiers.map(tier => `${tier}: ${code(policy.nativeFallback.claudeModels[tier])}`).join("; ")
  return `**Quota fallback for ${tiers} only:** When no approved bridge backend can run because it is unavailable or exhausted, ` +
    `use tier-matched native subagents with the same brief, worktree, scope, and independent verification. In Claude Code use ${mappings}. ` +
    "Preserve partial work before relaunch. Expert unavailability or quota exhaustion is a blocker; never substitute another model. No hook gates native subagents. Return to the bridge when capacity recovers.\n\n" +
    `**Host-access exception for ${tiers}:** use the same native mapping when the slice's proof needs host access Codex's sandbox cannot grant ` +
    "(Docker, VMs, `taskpolicy`, hardware), with unchanged scope and parent review. Dependency fetching uses scope `network: true` and does not qualify."
}

function delegation(policy: Policy, lean: boolean): string {
  const pin = expert(policy)
  const head = lean ? "- Before delegation, read `orchestrate` and use `pi-subagent-bridge` for every tier." :
    "- All coding subagents, in every harness and skill, MUST launch through `pi-subagent-bridge` MCP tools or its CLI shim; follow `orchestrate`."
  return head + " A top-level OpenCode session delegates only through OpenCode native subagents; free top-level models require free tier models. " +
    `Expert pins ${code(pin.model)} at ${code(pin.effort)} without fallback. No ${code("god")} tier exists. ` +
    `Never route to ${policy.bannedModels.map(code).join(" or ")}. ` +
    `Only ${policy.nativeFallback.tiers.join("/")} may use tier-matched native subagents after bridge quota/backend exhaustion or when proof needs host access Codex's sandbox cannot grant ` +
    "(Docker, VMs, `taskpolicy`, hardware); retain the same scope, worktree and independent parent review. Expert failures block rather than downgrade." +
    (lean ? " With verified, safely shareable evidence and meaningful tier uncertainty, consult `decide`; unavailable advice does not block." :
      " The parent scopes, verifies, reviews and integrates.")
}

function directModels(policy: Policy): string {
  return `Antigravity main sessions replacing Gemini 3.8 Flash must explicitly select an available approved model: ${policy.antigravityDirect.models.map(code).join(" or ")}. ` +
    "Verify it with `agy models`; never silently substitute a model or purchase API credits. Delegated expert assignments use the exact root pin above."
}

export function replaceBlocks(text: string, blocks: Blocks, yaml = false): string {
  const marker = yaml ? /^# policy:(begin|end) ([a-z0-9-]+)$/gm : /^<!-- policy:(begin|end) ([a-z0-9-]+) -->$/gm
  const candidates = text.split("\n").filter(line => line.includes(yaml ? "# policy:" : "<!-- policy:"))
  const found = [...text.matchAll(marker)]
  if (found.length !== candidates.length) throw new Error("Malformed generated policy marker")
  const seen = new Set<string>()
  let active: string | null = null
  for (const match of found) {
    const [, kind, id] = match
    if (!(id in blocks)) throw new Error(`Unknown generated policy block: ${id}`)
    if (kind === "begin") {
      if (active !== null || seen.has(id)) throw new Error(`Duplicate or nested generated policy block: ${id}`)
      active = id
      seen.add(id)
    } else {
      if (active !== id) throw new Error(`Unmatched generated policy block: ${id}`)
      active = null
    }
  }
  if (active !== null || Object.keys(blocks).some(id => !seen.has(id))) throw new Error("Missing generated policy block marker")
  for (const [id, body] of Object.entries(blocks)) {
    if (body.includes("policy:begin") || body.includes("policy:end")) throw new Error("Generated content contains a marker")
    const start = yaml ? `# policy:begin ${id}` : `<!-- policy:begin ${id} -->`
    const end = yaml ? `# policy:end ${id}` : `<!-- policy:end ${id} -->`
    const from = text.indexOf(start) + start.length
    const to = text.indexOf(end, from)
    const notice = yaml ? `# Generated from ${SOURCE}; run make generate.` : NOTICE
    text = text.slice(0, from) + `\n${notice}\n${body.trim()}\n` + text.slice(to)
  }
  return text
}

function object(value: Json | undefined, name: string): JsonObject {
  if (!value || Array.isArray(value) || typeof value !== "object") throw new Error(`Expected object: ${name}`)
  return value
}

function policyTier(name: string): Tier {
  if (!isTier(name)) throw new Error(`Unknown native policy tier: ${name}`)
  return name
}

function openCodeTiers(policy: Policy): Tier[] {
  return Object.keys(policy.opencode.efforts).map(policyTier)
}

function profiles(policy: Policy) {
  const names: Partial<Record<Tier, string>> = policy.nativePi.agentNames
  const children: Partial<Record<Tier, readonly string[]>> = policy.nativePi.museDelegation
  return [
    ...Object.entries(policy.nativePi.goModels).map(([name, pin]) => {
      const tier = policyTier(name)
      return { name, tier, pin, allowed: policy.nativePi.delegation[tier] }
    }),
    ...Object.entries(policy.nativePi.museModels).map(([key, pin]) => {
      const tier = policyTier(key)
      const name = names[tier], allowed = children[tier]
      if (!name || !allowed) throw new Error(`Missing Muse profile mapping: ${tier}`)
      return { name, tier, pin, allowed }
    }),
  ]
}

function validatePolicy(policy: Policy): void {
  if (new Set(policy.tiers).size !== policy.tiers.length) throw new Error("Duplicate policy tier")
  if (!Number.isSafeInteger(policy.nativePi.maxSubagentDepth) || policy.nativePi.maxSubagentDepth < 1)
    throw new Error("Invalid native Pi depth")
  const validateModel = (value: string) => {
    code(value)
    if (isBannedModel(value, policy.bannedModels))
      throw new Error(`Prohibited model in active policy: ${value}`)
  }
  for (const tier of policy.tiers) {
    code(tier)
    if (!policy.rootRoutes[tier].length) throw new Error(`Missing route for ${tier}`)
    for (const route of policy.rootRoutes[tier]) { validateModel(route.model); code(route.effort) }
  }
  for (const profile of profiles(policy)) {
    code(profile.name)
    code(profile.pin.providerID)
    validateModel(profile.pin.id)
    code(profile.pin.variant)
    if (!profile.allowed || !policy.nativePi.tools[profile.tier]) throw new Error(`Missing native constraints: ${profile.name}`)
    for (const value of [...profile.allowed, ...policy.nativePi.tools[profile.tier]]) code(value)
  }
  const profileNames = new Set(profiles(policy).map(profile => profile.name))
  for (const profile of profiles(policy))
    if (profile.allowed.some(name => !profileNames.has(name))) throw new Error(`Unknown descendant in ${profile.name}`)
  for (const value of policy.antigravityDirect.models) validateModel(value)
  validateModel(policy.opencode.model)
  expert(policy)
}

function destination(root: string, path: string): string {
  const full = resolve(root, path)
  const parent = realpathSync(dirname(full))
  const base = realpathSync(root)
  if (parent !== base && !parent.startsWith(base + "/")) throw new Error(`Generated destination escapes repository: ${path}`)
  try {
    if (lstatSync(full).isSymbolicLink()) throw new Error(`Generated destination is a symlink: ${path}`)
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
  }
  return full
}

export function renderOutputs(root: string, policy: Policy = POLICY): Output[] {
  validatePolicy(policy)
  const outputs: Output[] = []
  function read(path: string): string {
    return readFileSync(destination(root, path), "utf8")
  }
  function emit(path: string, content: string, previous: string | null): void {
    if (outputs.some(output => output.path === path)) throw new Error(`Duplicate generated destination: ${path}`)
    outputs.push({ path, content, previous })
  }
  function document(path: string, blocks: Blocks): void {
    const previous = read(path)
    emit(path, replaceBlocks(previous, blocks), previous)
  }
  function json(path: string, project: (data: JsonObject) => void): void {
    const previous = read(path)
    const value = object(JSON.parse(previous) as Json, path)
    project(value)
    emit(path, JSON.stringify(value, null, 2) + "\n", previous)
  }
  let previousPolicy: string | null = null
  try { previousPolicy = read(JSON_PATH) } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
  }
  if (previousPolicy !== null) {
    const previous = object(JSON.parse(previousPolicy) as Json, "previous policy snapshot")
    if (previous.schema_version !== 1) throw new Error("Unsupported previous policy snapshot schema")
    const native = object(previous.nativePi, "previous nativePi")
    const oldNames = [...Object.keys(object(native.goModels, "previous goModels")),
      ...Object.values(object(native.agentNames, "previous agentNames"))]
    const oldOpenCode = Object.keys(object(object(previous.opencode, "previous opencode").efforts, "previous OpenCode efforts"))
    if (oldNames.some(name => typeof name !== "string" || !/^[a-z][a-z0-9-]*$/.test(name)) ||
        oldOpenCode.some(name => !/^[a-z][a-z0-9-]*$/.test(name))) throw new Error("Invalid previous policy profile membership")
    const names = new Set(profiles(policy).map(profile => profile.name))
    const settings = object(JSON.parse(read(`${PROFILE}/settings.json`)) as Json, "Pi settings")
    const sub = object(settings.subagents, "Pi subagents")
    const overrides = object(sub.agentOverrides, "Pi overrides")
    const scopes = object(object(sub.modelScope, "Pi modelScope").agents, "Pi modelScope agents")
    for (const name of oldNames) {
      if (typeof name !== "string" || names.has(name)) continue
      const path = `${PROFILE}/agents/${name}.md`
      let present = name in overrides || name in scopes
      try { read(path); present = true } catch (error) {
        if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
      }
      if (present) throw new Error(`Retired native profile ${name}: explicitly remove ${path} and its Pi agentOverrides/modelScope entries, then regenerate`)
    }
    const open = object(JSON.parse(read("dotfiles/base/.config/opencode/opencode.json")) as Json, "OpenCode settings")
    const agents = object(open.agents, "OpenCode agents")
    const current = new Set<string>(openCodeTiers(policy))
    for (const name of oldOpenCode)
      if (!current.has(name) && name in agents)
        throw new Error(`Retired OpenCode tier ${name}: explicitly remove its managed agents entry, then regenerate`)
  }
  const table = routingTable(policy)
  const direct = directModels(policy)
  document("dotfiles/base/.agents/skills/orchestrate/SKILL.md", {
    "routing-intro": "**All coding subagents from any harness use `pi-subagent-bridge`**, subject to the OpenCode and native exceptions below. " + summary(policy),
    "opencode": openCode(policy),
    "native-fallback": nativeFallback(policy),
    "routing-table": table,
    "direct-models": direct,
  })
  document("dotfiles/base/.codex/AGENTS.md", { delegation: delegation(policy, false), "direct-models": "- " + direct })
  document("dotfiles/base/.agents/instructions/lean.md", { delegation: delegation(policy, true) })
  document("tools/pi-subagent-bridge/README.md", {
    "routing-summary": summary(policy) + "\n\n" + table,
    "pi-nesting": ["| Pi parent | Allowed nested child |", "| --- | --- |", ...Object.keys(policy.nativePi.goModels).map(policyTier).map(tier =>
      `| ${tier}${tier === "expert" ? " (native Pi)" : ""} | ${policy.nativePi.delegation[tier].join(", ")} |`)].join("\n"),
  })
  document("docs/pi.md", { "routing-summary": summary(policy) })
  document("docs/agent-setup.md", { "routing-summary": summary(policy) })
  for (const profile of profiles(policy)) {
    const path = `${PROFILE}/agents/${profile.name}.md`
    const previous = read(path)
    const frontmatter = [
      `model: ${profile.pin.providerID}/${profile.pin.id}`, `thinking: ${profile.pin.variant}`, "tools:",
      ...policy.nativePi.tools[profile.tier].map(tool => `  - ${tool}`),
      "allowNestedSubagents: true", `maxSubagentDepth: ${policy.nativePi.maxSubagentDepth}`, "allowedAgents:",
      ...profile.allowed.map(name => `  - ${name}`),
    ].join("\n")
    emit(path, replaceBlocks(previous, { "native-profile": frontmatter }, true), previous)
  }
  json(`${PROFILE}/settings.json`, settings => {
    const sub = object(settings.subagents, "subagents")
    const overrides = object(sub.agentOverrides, "subagents.agentOverrides")
    const scope = object(sub.modelScope, "subagents.modelScope")
    const agents = object(scope.agents, "subagents.modelScope.agents")
    scope.enforce = true
    scope.strict = true
    scope.allow = [...policy.nativePi.modelAllowlist]
    for (const profile of profiles(policy)) {
      const pin = `${profile.pin.providerID}/${profile.pin.id}`
      const override = object(overrides[profile.name], `agentOverrides.${profile.name}`)
      override.model = pin
      override.thinking = profile.pin.variant
      object(agents[profile.name], `modelScope.agents.${profile.name}`).allow = [pin]
    }
  })
  json(`${PROFILE}/extensions/subagent/config.json`, settings => { settings.maxSubagentDepth = policy.nativePi.maxSubagentDepth })
  json("dotfiles/base/.config/opencode/opencode.json", settings => {
    const agents = object(settings.agents, "OpenCode agents")
    for (const tier of openCodeTiers(policy))
      object(agents[tier], `OpenCode agents.${tier}`).model = `${policy.opencode.model}#${policy.opencode.efforts[tier]}`
  })
  emit(JSON_PATH, JSON.stringify(policy, null, 2) + "\n", previousPolicy)
  return outputs.sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0)
}

export function writeOutputs(root: string, outputs: readonly Output[]): string[] {
  const changed = outputs.filter(output => output.content !== output.previous)
  for (const output of outputs) {
    const full = destination(root, output.path)
    let actual: string | null = null
    try { actual = readFileSync(full, "utf8") } catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
    }
    if (actual !== output.previous) throw new Error(`Generated input changed while rendering: ${output.path}`)
  }
  const staged: { path: string; destination: string }[] = []
  try {
    for (const output of changed) {
      const target = destination(root, output.path)
      const path = target + ".policy-tmp"
      writeFileSync(path, output.content, { flag: "wx", mode: 0o644 })
      staged.push({ path, destination: target })
    }
    for (const file of staged) renameSync(file.path, file.destination)
  } finally {
    for (const file of staged) {
      try { unlinkSync(file.path) } catch (error) {
        if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
      }
    }
  }
  return changed.map(output => output.path)
}

export function main(args: readonly string[], root = ROOT): number {
  if (args.length > 1 || (args.length === 1 && !["--check", "--json"].includes(args[0])))
    throw new Error("usage: node tools/policy/generate.ts [--check|--json]")
  if (args[0] === "--json") {
    process.stdout.write(JSON.stringify(POLICY, null, 2) + "\n")
    return 0
  }
  const outputs = renderOutputs(root)
  const changed = outputs.filter(output => output.content !== output.previous)
  if (args[0] === "--check") {
    for (const output of changed) process.stderr.write(`Stale policy output: ${output.path}; run make generate\n`)
    return changed.length ? 1 : 0
  }
  for (const path of writeOutputs(root, outputs)) process.stdout.write(path + "\n")
  return 0
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { process.exitCode = main(process.argv.slice(2)) }
  catch (error) {
    process.stderr.write(`policy generation: ${error instanceof Error ? error.message : String(error)}\n`)
    process.exitCode = 1
  }
}
