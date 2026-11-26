import { readFileSync, writeFileSync, renameSync, unlinkSync, lstatSync, realpathSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { POLICY, isBannedModel, type Route } from "../pi-subagent-bridge/src/policy.ts"
import { isTier, PI_RUN_DEADLINE_MS, DEVIN_BRIDGE_DISABLED, type Tier, type BridgeTier } from "../pi-subagent-bridge/src/tier-policy.ts"
import { gateGenerate } from "./claim.ts"
import { harnessEnabled, HARNESS_LABELS, piProviderEnabled, type HarnessId } from "../pi-subagent-bridge/src/harnesses.ts"
import { NATIVE_PARENTS, resumeCommands, resumeLocations, resumeDetails } from "./harness-context.ts"

export type Policy = Omit<typeof POLICY, "rootRoutes" | "tiers"> & {
  readonly tiers: readonly BridgeTier[]
  readonly rootRoutes: Readonly<Record<BridgeTier, readonly Route[]>>
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
export const TEMPLATE_PATHS = ["tools/policy/templates/pi-settings.json"] as const
const [PI_SETTINGS_SOURCE] = TEMPLATE_PATHS
const LABELS = { codex: "Codex", "command-code": "Command Code", pi: "Pi" } as const

function code(value: string): string {
  if (!/^[a-zA-Z0-9_./#:-]+$/.test(value)) throw new Error(`Invalid policy identifier: ${value}`)
  return "`" + value + "`"
}

function model(route: Route): string {
  return route.executor === "pi" ? `${route.providerID}/${route.model}` : route.model
}

function routeLabel(route: Route): string {
  return `${LABELS[route.executor]} ${code(model(route))} (${code(route.effort)})`
}

export function routingTable(policy: Policy): string {
  const rows = policy.tiers.map(tier => {
    const [primary, ...fallback] = policy.rootRoutes[tier]
    return `| ${tier} | ${primary ? routeLabel(primary) : "**Blocked. No enabled route.**"} | ${fallback.length ? fallback.map(routeLabel).join("; ") : "**None. Fail closed.**"} |`
  })
  return ["| Tier | Primary | Fallback (in order) |", "| --- | --- | --- |", ...rows].join("\n")
}

const NATIVE_DESCRIPTIONS: Record<typeof NATIVE_PARENTS[number], (policy: Policy) => string> = {
  opencode: openCode, devin, "command-code": commandCode, antigravity, copilot,
}

function enabled(policy: Policy, id: HarnessId): boolean {
  return harnessEnabled(id, policy.harnesses)
}

function nativeParents(policy: Policy): string[] {
  return NATIVE_PARENTS.filter(id => enabled(policy, id)).map(id => HARNESS_LABELS[id])
}

function conjunction(values: readonly string[]): string {
  return values.length < 2 ? values.join("") : values.slice(0, -1).join(", ") + " and " + values.at(-1)
}

function bridgeEnabled(policy: Policy): boolean {
  return policy.tiers.some(tier => policy.rootRoutes[tier].length > 0)
}

function expertSummary(policy: Policy): string {
  const [expert] = policy.rootRoutes.expert
  return expert ? `The ${code("expert")} tier admits only ${routeLabel(expert)} and has no fallback; unavailable or exhausted capacity blocks the lane. ` :
    `The ${code("expert")} bridge tier has no enabled route and is blocked. `
}

function summary(policy: Policy): string {
  const parents = nativeParents(policy)
  return `Bridge tiers: ${policy.tiers.map(code).join(", ")}. ` + expertSummary(policy) +
    (enabled(policy, "pi") && enabled(policy, "devin") && DEVIN_BRIDGE_DISABLED ?
      "Devin bridge lanes are currently blocked by free-tier throttling. " : "") +
    (enabled(policy, "claude") ? "Claude Code expert assignments use native subagents pinned to `opus` at `xhigh`. " : "") +
    (parents.length ? `Top-level ${conjunction(parents)} parents keep their native expert agents. ` : "") +
    (!bridgeEnabled(policy) ? "No bridge routes are enabled. " : "") +
    `There is no ${code("god")} tier. ` +
    `The model families ${policy.bannedModels.map(code).join(" and ")} are prohibited, including every effort variant.`
}

function openCode(policy: Policy): string {
  if (!enabled(policy, "opencode")) return ""
  return "**OpenCode exception:** A top-level OpenCode session never uses `pi-subagent-bridge`, at any tier or as a fallback. " +
    "Delegate only through its configured native agents or built-in `general`/`explore`. When the top-level model is free, every tier must run a free model. " +
    `The configured tier agents use ${code(policy.opencode.model)} regardless of the top-level model:\n\n` +
    ["| Tier | Effort |", "| --- | --- |", ...openCodeTiers(policy).map(tier =>
      `| ${tier}${tier === "scout" ? " (read-only: no `shell`, no `edit`)" : ""} | ${policy.opencode.efforts[tier]} |`)].join("\n") +
    "\n\nBridge pins, fallbacks, and nesting rules do not apply on this path."
}

function devin(policy: Policy): string {
  if (!enabled(policy, "devin")) return ""
  const rows = Object.entries(policy.devinNative).map(([tier, pin]) =>
    `| ${tier} | ${code(pin.name)} | ${code(pin.model)} |`)
  return "**Devin exception:** A top-level Devin session never uses `pi-subagent-bridge`, at any tier or as a fallback. " +
    "Delegate only through native `run_subagent` subagents. Use the named agents below for tiered work, never the unpinned built-in `subagent_explore` or parent-inherited `subagent_general`.\n\n" +
    ["| Tier | Native agent | Model |", "| --- | --- | --- |", ...rows].join("\n") +
    "\n\nThe parent supplies the native lane worktree, scope registration, acceptance proof and independent review. Children are leaves. " +
    "Bridge pins, fallbacks, and nesting rules do not apply on this path."
}

function commandCode(policy: Policy): string {
  if (!enabled(policy, "command-code")) return ""
  const rows = Object.entries(policy.commandNative).map(([tier, pin]) =>
    `| ${tier === "pilot" ? "worker pilot (explicit only)" : tier} | ${code(pin.name)} | ${code(pin.model)} | ${"effort" in pin && pin.effort ? code(pin.effort) : "model default"} |`)
  return "**Command Code exception:** A top-level Command Code session delegates through native `agent` subagents only; never invoke `pi-subagent-bridge` from that parent. " +
    "Use the named agents below, never the unpinned built-in General/Explore for tiered work. The pilot requires an explicit comparison task; it is not the default worker.\n\n" +
    ["| Tier | Native agent | Model | Effort |", "| --- | --- | --- | --- |", ...rows].join("\n") +
    "\n\nNative agents have separate contexts and cannot spawn another agent. They do not provide bridge admission or Git worktree containment: the parent owns isolation, scope, review, tests and integration. " +
    "Agent frontmatter pins are not hard enforcement: a per-call model override takes precedence, and unsupported effort silently reverts to model default. " +
    "Check `cmd --list-models` and the `/model` effort picker on each host before trusting a lane; block it rather than silently substituting. " +
    "Collect detached results with `agent_output` and run `scope-check --lane` on native writer lanes."
}

function copilot(policy: Policy): string {
  if (!enabled(policy, "copilot")) return ""
  const rows = Object.entries(policy.copilotNative).map(([tier, pin]) =>
    `| ${tier} | ${code(pin.name)} | ${code(pin.model)} | ${code(pin.effort)} |`)
  return "**Copilot CLI pilot:** A top-level Copilot session delegates only through the named native `task` agents below; never launch the shared bridge or use built-in agents as a fallback. Do not use Auto. The following candidate pins require authenticated model and effort attestation before delegation; block any unattested or unavailable lane.\n\n" +
    ["| Tier | Native agent | Candidate model | Effort |", "| --- | --- | --- | --- |", ...rows].join("\n") +
    "\n\nThe parent supplies the native lane worktree, scope registration, acceptance proof and independent review. Children are leaves. Required model policy and strict tool lists are not worktree containment or proof of effective effort. See `docs/copilot-native.md`."
}

function nativeFallback(policy: Policy): string {
  if (!enabled(policy, "claude")) return ""
  const tiers = policy.nativeFallback.tiers.join("/")
  const mappings = policy.nativeFallback.tiers.map(tier => `${tier}: ${code(policy.nativeFallback.claudeModels[tier])}`).join("; ")
  return `**Claude Code native subagents:** ${code("expert")} assignments use native subagents pinned to ${code("opus")} with ${code("xhigh")} effort; if that model is unavailable the expert lane is blocked, never substituted. ` +
    `When no approved bridge backend can run because it is unavailable or exhausted, ${tiers} use tier-matched native subagents with the same brief, worktree, scope, and independent verification: ${mappings}. ` +
    "A host or session whose environment sets `USR_DELEGATION=native`, such as a cloud environment without bridge providers, uses these native subagents directly and does not start the bridge. " +
    "Preserve partial work before relaunch. Register native lanes with `scope-check --register` and record their final check with `scope-check --lane`. No hook gates native subagents. Return to the bridge when capacity recovers, unless `USR_DELEGATION=native` is set."
}

function delegation(policy: Policy, lean: boolean): string {
  const parents = nativeParents(policy)
  const bridge = bridgeEnabled(policy)
  const parts = ["- Before delegation, read `orchestrate`."]
  if (bridge) parts.push(`All scout/mechanic/worker/expert coding subagents use \`pi-subagent-bridge\` by default${parents.length ? "; top-level " + conjunction(parents) + " parents use their native lanes" : ""}.`)
  else {
    const native = [...parents, ...(enabled(policy, "claude") ? [HARNESS_LABELS.claude] : [])]
    parts.push(native.length ? `Use only the enabled native lanes for ${conjunction(native)}; bridge delegation is blocked.` : "Delegation is blocked: no harness lane is enabled.")
  }
  if (!lean && bridge) parts.push(expertSummary(policy).trim())
  if (enabled(policy, "opencode")) parts.push("A top-level OpenCode session delegates only through OpenCode native subagents; free top-level models require free tier models.")
  if (enabled(policy, "devin")) parts.push("A top-level Devin session delegates only through Devin native subagents.")
  if (enabled(policy, "command-code")) parts.push("A top-level Command Code session delegates only through native pinned `usr-*` subagents (HY4-medium worker is opt-in).")
  if (enabled(policy, "antigravity")) parts.push("A top-level Antigravity CLI session delegates only through native `usr-*` subagents. Gemini 3.8 is retired and Carbon is never a fallback; a manual Carbon session requires the owner's explicit request.")
  if (enabled(policy, "copilot")) parts.push("A top-level Copilot CLI session is a native-only pilot: use the named `usr-*` agents after live model/effort attestation; block otherwise, never use Auto or the bridge.")
  if (enabled(policy, "claude")) parts.push(`Claude Code expert work uses native \`opus\` at \`xhigh\`. Only ${policy.nativeFallback.tiers.join("/")} may use tier-matched native subagents after bridge quota/backend exhaustion or when the environment sets \`USR_DELEGATION=native\`, with the same scope, worktree and independent parent review.`)
  parts.push(`No ${code("god")} tier exists. Never route to ${policy.bannedModels.map(code).join(" or ")}.`)
  parts.push(lean ? "With verified, safely shareable evidence and meaningful tier uncertainty, consult `decide`; unavailable advice does not block." : "The parent scopes, verifies, reviews and integrates.")
  return parts.join(" ")
}

function routingIntro(policy: Policy): string {
  const parents = nativeParents(policy)
  const routing = bridgeEnabled(policy) ? "**All scout/mechanic/worker/expert coding subagents use `pi-subagent-bridge` by default**" +
    (parents.length ? `, except top-level ${conjunction(parents)} native parents described below. ` : ". ") :
    "**Bridge delegation is blocked; no route is enabled.** "
  return routing + summary(policy)
}

function goBoundary(policy: Policy): string {
  if (!piProviderEnabled("opencode-go", policy.harnesses)) return ""
  return "**Pi OpenCode Go boundary:** Pi fallbacks use pinned OpenCode Go models; Zen models are unusable from headless SDK workers (the gateway rejects non-opencode-client User-Agents with `429 FreeUsageLimitError` — see `docs/pi.md#why-zen-is-not-a-pin`). Other OpenCode Go models and custom endpoints are forbidden. The native Pi `expert` profile authorizes new expert dispatches from Pi sessions through the native subagent tool."
}

function expertGuidance(policy: Policy): string {
  const parents = nativeParents(policy)
  return "**Expert assignments:** " + expertSummary(policy) +
    (enabled(policy, "claude") ? "Claude Code parents use native `opus` at `xhigh` for expert work. " : "") +
    (parents.length ? `Native-only ${conjunction(parents)} parents keep their configured expert agent. ` : "") +
    "Reserve the lane for exceptional architectural decisions and independent adversarial review. There is no higher tier above expert. Never substitute a weaker model for a blocked expert lane."
}

function nesting(policy: Policy): string {
  const parts: string[] = []
  if (enabled(policy, "command-code")) parts.push("Command Code native children cannot launch subagents.")
  if (enabled(policy, "pi")) parts.push("On the bridge path, grant one level of Pi fanout in the brief only when the slice needs it; the bridge's guard enforces the rest.")
  const leaves = (["codex", "command-code"] as const).filter(id => enabled(policy, id)).map(id => HARNESS_LABELS[id])
  if (leaves.length) parts.push(`${conjunction(leaves)} workers are leaves.`)
  return parts.length ? "**Nesting:** " + parts.join(" ") : ""
}

function devinReview(policy: Policy): string {
  if (!enabled(policy, "devin")) return ""
  return "**Devin needs the closest review.** Its past lanes optimized for literal acceptance proof, including attempts to weaken checks to satisfy a gate. When a lane is available:\n\n" +
    "- State in the brief that no check, guard or test may be removed or weakened to satisfy a mutation, lint or test gate; a surviving mutant in protective code is killed with a test or reported under `stop_on`.\n" +
    "- Require tests that pass on every supported OS and architecture.\n" +
    "- Read every deleted line in its diff, especially validation, path and archive handling, and error paths, and run the acceptance proof yourself before integrating.\n" +
    "- Prefer doing security-sensitive work directly when independent verification is unavailable."
}

function antigravity(policy: Policy): string {
  if (!enabled(policy, "antigravity")) return ""
  const a = policy.antigravityDirect
  const rows = Object.entries(a.tiers).map(([tier, pin]) =>
    `| ${tier} | ${code(pin.name)} | ${code(pin.model)} | ${code(pin.effort)} | ${code(pin.selector)} |`).join("\n")
  return "**Antigravity CLI exception:** A top-level `agy` session delegates only through native `invoke_subagent`. Never invoke the shared bridge or use another harness as fallback. The `god` label is a direct parent-session mode, not a bridge tier. Native `usr-*` definitions live under `~/.gemini/config/agents/`.\n\n" +
    "| Tier | Native agent | Target model | Target effort | CLI selector |\n| --- | --- | --- | --- | --- |\n" + rows +
    "\n\nThe CLI's documented agent schema accepts `model: flash/pro` selectors, not exact model IDs or effort pins. Treat these as target allocations, check actual child model and effort on first use, and block any lane resolving to Gemini 3.8, Carbon, Argon or an unexpected model. Carbon may only be selected manually by the owner, outside delegation. See `docs/antigravity-native.md`."
}

function directModels(policy: Policy): string {
  if (!enabled(policy, "antigravity")) return ""
  const a = policy.antigravityDirect
  return `Antigravity main: ${code(a.main.model)} (${code(a.main.effort)}); direct god mode: ${code(a.god.model)} (${code(a.god.effort)}). Native \`usr-*\` subagents only: ${Object.entries(a.tiers).map(([tier,p])=>`${tier} ${code(p.name)} targets ${code(p.model)} (${code(p.effort)})`).join("; ")}. ` +
    "Never use `pi-subagent-bridge` from agy. Custom-agent `model: flash/pro` is only a tier selector, not an enforced exact model or effort pin. " +
    `Allowed direct models: ${a.models.map(code).join(", ")}. ` +
    `Verify \`agy models\` and actual child runtime models before using lanes; fail closed for ${a.retired.map(code).join(" or ")}, Carbon or mismatched tiers. Carbon (${code(a.manualCarbon)}) is manual owner-only, never an automatic fallback. Do not purchase API credits.`
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
    text = text.slice(0, from) + (body.trim() ? `\n${notice}\n${body.trim()}\n` : "\n") + text.slice(to)
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
  return [
    ...Object.entries(policy.nativePi.goModels).map(([name, pin]) => {
      const tier = policyTier(name)
      return { name, tier, pin, allowed: policy.nativePi.delegation[tier] }
    }),
    ...Object.entries(policy.nativePi.devinModels).map(([key, pin]) => {
      const tier = policyTier(key)
      const name = (policy.nativePi.devinAgentNames as Readonly<Record<string, string>>)[tier]
      const allowed = (policy.nativePi.devinDelegation as Readonly<Record<string, readonly string[]>>)[tier]
      if (!name || !allowed) throw new Error(`Missing Devin profile mapping: ${tier}`)
      return { name, tier, pin, allowed }
    }),
  ]
}

function validatePolicy(policy: Policy): ReturnType<typeof profiles> {
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
    for (const route of policy.rootRoutes[tier]) { validateModel(route.model); code(route.effort) }
  }
  const nativeProfiles = profiles(policy)
  for (const profile of nativeProfiles) {
    code(profile.name)
    code(profile.pin.providerID)
    validateModel(profile.pin.id)
    code(profile.pin.variant)
    if (!profile.allowed || !policy.nativePi.tools[profile.tier]) throw new Error(`Missing native constraints: ${profile.name}`)
    for (const value of [...profile.allowed, ...policy.nativePi.tools[profile.tier]]) code(value)
  }
  const profileNames = new Set(nativeProfiles.map(profile => profile.name))
  for (const profile of nativeProfiles)
    if (profile.allowed.some(name => !profileNames.has(name))) throw new Error(`Unknown descendant in ${profile.name}`)
  for (const value of policy.antigravityDirect.models) validateModel(value)
  validateModel(policy.antigravityDirect.main.model)
  validateModel(policy.antigravityDirect.god.model)
  if (new Set(Object.values(policy.antigravityDirect.tiers).map(pin => pin.name)).size !== Object.keys(policy.antigravityDirect.tiers).length)
    throw new Error("Duplicate Antigravity native agent name")
  for (const pin of Object.values(policy.antigravityDirect.tiers)) {
    code(pin.name); validateModel(pin.model); code(pin.effort)
    if (!["flash", "pro"].includes(pin.selector)) throw new Error("Invalid Antigravity CLI model selector")
  }
  code(policy.antigravityDirect.manualCarbon)
  for (const retired of policy.antigravityDirect.retired) code(retired)
  validateModel(policy.opencode.model)
  if (new Set(Object.values(policy.commandNative).map(pin => pin.name)).size !== Object.keys(policy.commandNative).length)
    throw new Error("Duplicate Command Code native agent name")
  for (const tier of ["scout", "mechanic", "worker", "expert", "pilot"] as const) {
    const pin = policy.commandNative[tier]
    code(pin.name)
    validateModel(pin.model)
    if ("effort" in pin && pin.effort) code(pin.effort)
  }
  for (const [tier, pin] of Object.entries(policy.devinNative)) {
    if (pin.name !== `usr-${tier}`) throw new Error(`Invalid Devin native agent name: ${pin.name}`)
    validateModel(pin.model)
    code(pin.effort)
    if (pin.model !== `swe-2-1-${pin.effort}`) throw new Error(`Devin native ${tier} does not pin the matching SWE-2.1 variant`)
  }
  for (const [tier, pin] of Object.entries(policy.copilotNative)) {
    if (pin.name !== `usr-${tier}`) throw new Error(`Invalid Copilot native agent name: ${pin.name}`)
    validateModel(pin.model.toLowerCase())
    if (pin.model.toLowerCase() === "auto") throw new Error("Copilot native agents cannot use Auto")
    code(pin.effort)
  }
  for (const value of Object.values(policy.nativeFallback.claudeModels)) validateModel(value)
  return nativeProfiles
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
  const nativeProfiles = validatePolicy(policy)
  const outputs: Output[] = []
  const inputs = new Map<string, string>()
  function read(path: string): string {
    if (!inputs.has(path)) inputs.set(path, readFileSync(destination(root, path), "utf8"))
    return inputs.get(path)!
  }
  function emit(path: string, content: string, previous: string | null): void {
    if (outputs.some(output => output.path === path)) throw new Error(`Duplicate generated destination: ${path}`)
    outputs.push({ path, content, previous })
  }
  function document(path: string, blocks: Blocks, format: "markdown" | "yaml" = "markdown"): void {
    const previous = read(path)
    emit(path, replaceBlocks(previous, blocks, format === "yaml"), previous)
  }
  function json(path: string, project: (data: JsonObject) => void, source = path): void {
    const previous = read(path)
    const value = object(JSON.parse(source === path ? previous : read(source)) as Json, source)
    project(value)
    emit(path, JSON.stringify(value, null, 2) + "\n", previous)
  }
  for (const path of TEMPLATE_PATHS) {
    const content = read(path)
    emit(path, content, content)
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
      ...Object.values(object(native.agentNames ?? {}, "previous agentNames")),
      ...Object.values(object(native.devinAgentNames ?? {}, "previous devinAgentNames"))]
    const oldOpenCode = Object.keys(object(object(previous.opencode, "previous opencode").efforts, "previous OpenCode efforts"))
    if (oldNames.some(name => typeof name !== "string" || !/^[a-z][a-z0-9-]*$/.test(name)) ||
        oldOpenCode.some(name => !/^[a-z][a-z0-9-]*$/.test(name))) throw new Error("Invalid previous policy profile membership")
    const names = new Set(nativeProfiles.map(profile => profile.name))
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
    "routing-intro": routingIntro(policy),
    "native-parents": [...NATIVE_PARENTS.map(id => NATIVE_DESCRIPTIONS[id](policy)), nativeFallback(policy)].filter(Boolean).join("\n\n"),
    "go-boundary": goBoundary(policy),
    "expert-guidance": expertGuidance(policy),
    "devin-review": devinReview(policy),
    "nesting": nesting(policy),
  })
  document("dotfiles/base/.codex/AGENTS.md", { delegation: delegation(policy, false), "direct-models": direct ? "- " + direct : "" })
  document("dotfiles/base/.agents/instructions/lean.md", { delegation: delegation(policy, true) })
  document("tools/pi-subagent-bridge/README.md", {
    "routing-summary": summary(policy) + "\n\n" + table,
    "pi-nesting": piProviderEnabled("opencode-go", policy.harnesses) ? ["| Pi parent | Allowed nested child |", "| --- | --- |", ...Object.keys(policy.nativePi.goModels).map(policyTier).map(tier =>
      `| ${tier}${tier === "expert" ? " (native Pi)" : ""} | ${policy.nativePi.delegation[tier].join(", ")} |`)].join("\n") : "",
  })
  document("dotfiles/base/.agents/skills/resume-session/SKILL.md", { "resume-commands": resumeCommands(policy.harnesses) })
  document("dotfiles/base/.agents/skills/resume-session/references/locate.md", {
    "resume-locations": resumeLocations(policy.harnesses), "resume-details": resumeDetails(policy.harnesses),
  })
  document("docs/pi.md", { "routing-summary": summary(policy) })
  document("docs/agent-setup.md", { "routing-summary": summary(policy) })
  for (const pin of Object.values(policy.antigravityDirect.tiers)) {
    const fields = [`model: ${pin.selector}`, "subagent: true", "mainAgent: false"]
    document(`dotfiles/base/.gemini/config/agents/${pin.name}.md`, { "native-agent": fields.join("\n") }, "yaml")
  }
  for (const pin of Object.values(policy.copilotNative)) {
    const fields = [`model: ${pin.model}`, `reasoning-effort: ${pin.effort}`, "model-policy: required"]
    document(`dotfiles/base/.copilot/agents/${pin.name}.agent.md`, { "native-agent": fields.join("\n") }, "yaml")
  }
  for (const pin of Object.values(policy.commandNative)) {
    const fields = [`model: ${pin.model}`, ...("effort" in pin && pin.effort ? [`reasoningEffort: ${pin.effort}`] : [])]
    document(`dotfiles/base/.commandcode/agents/${pin.name}.md`, { "native-agent": fields.join("\n") }, "yaml")
  }
  for (const pin of Object.values(policy.devinNative)) {
    document(`dotfiles/base/.config/devin/agents/${pin.name}.md`, { "native-agent": `model: ${pin.model}` }, "yaml")
  }
  const activeProfiles = nativeProfiles.filter(profile => piProviderEnabled(profile.pin.providerID, policy.harnesses))
  const activeNames = new Set(activeProfiles.map(profile => profile.name))
  for (const profile of nativeProfiles) {
    const frontmatter = [
      `model: ${profile.pin.providerID}/${profile.pin.id}`, `thinking: ${profile.pin.variant}`, "tools:",
      ...policy.nativePi.tools[profile.tier].map(tool => `  - ${tool}`),
      "allowNestedSubagents: true", `maxSubagentDepth: ${policy.nativePi.maxSubagentDepth}`, `timeoutMs: ${PI_RUN_DEADLINE_MS}`,
      profile.allowed.some(name => activeNames.has(name)) ? "allowedAgents:" : "allowedAgents: []",
      ...profile.allowed.filter(name => activeNames.has(name)).map(name => `  - ${name}`),
    ].join("\n")
    document(`${PROFILE}/agents/${profile.name}.md`, { "native-profile": frontmatter }, "yaml")
  }
  json(`${PROFILE}/settings.json`, settings => {
    const sub = object(settings.subagents, "subagents")
    const overrides = object(sub.agentOverrides, "subagents.agentOverrides")
    const scope = object(sub.modelScope, "subagents.modelScope")
    const agents = object(scope.agents, "subagents.modelScope.agents")
    scope.enforce = true
    scope.strict = true
    scope.allow = policy.nativePi.modelAllowlist.filter(pin => piProviderEnabled(pin.split("/")[0], policy.harnesses))
    for (const profile of nativeProfiles) {
      if (!activeNames.has(profile.name)) {
        delete overrides[profile.name]
        delete agents[profile.name]
        continue
      }
      const pin = `${profile.pin.providerID}/${profile.pin.id}`
      const override = object(overrides[profile.name] ??= {}, `agentOverrides.${profile.name}`)
      override.model = pin
      override.thinking = profile.pin.variant
      object(agents[profile.name] ??= {}, `modelScope.agents.${profile.name}`).allow = [pin]
    }
  }, PI_SETTINGS_SOURCE)
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
  if (args[0] !== "--check") {
    // Write mode is where policy edits become real: refuse to regenerate while
    // another live session holds the checkout-wide policy claim. Check mode is
    // read-only and never blocked.
    const gate = gateGenerate(root)
    if (!gate.proceed) {
      process.stderr.write(gate.message + "\n")
      return 1
    }
    for (const notice of gate.notices) process.stderr.write(`policy generation: ${notice}\n`)
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
