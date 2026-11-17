/** Renders docs/subagents.md from the typed policy. Never import the generated JSON here. */
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { POLICY } from "../pi-subagent-bridge/src/policy.ts"
import { routingTable } from "./generate.ts"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const DESTINATION = "docs/subagents.md"
const SOURCE = "tools/policy/subagent-visualization.ts"
const NOTICE = `<!-- Generated from ${SOURCE}; run make subagent-visualization. -->`

function markdown(): string {
  const opencode = POLICY.opencode
  const expertPi = POLICY.nativePi.goModels.expert
  const expertClaude = `\`${POLICY.nativeFallback.claudeModels.expert}\`, \`${POLICY.nativeFallback.claudeEffort.expert}\` effort`
  const quota = POLICY.nativeFallback.tiers.map(tier => `\`${tier}\` \`${POLICY.nativeFallback.claudeModels[tier as "scout"]}\``).join(" · ")
  const opencodeTier = (tier: "scout" | "mechanic" | "worker" | "expert") => `\`${opencode.model}#${opencode.efforts[tier]}\``
  const bannedFamilies = POLICY.bannedModels.map(model => `\`${model}\``).join(" / ")
  const lines: string[] = [
    "# Subagent architecture",
    "",
    NOTICE,
    "<!-- Hand-edit the generator, not this file. Policy inputs come from `tools/pi-subagent-bridge/src/policy.ts` via the typed `POLICY` export. -->",
    "",
    `Decision graph for delegating a coding subagent. Tiers: \`scout\` (read-only: no \`bash\`, \`edit\` or \`write\`), \`mechanic\`, \`worker\`, \`expert\`. There is no \`god\` tier, and the ${bannedFamilies} families are prohibited everywhere, including every effort variant.`,
    "",
    "```mermaid",
    "flowchart TD",
    '  start["Parent agent wants a coding subagent"] --> tier{"Which tier?"}',
    "",
    '  tier -->|expert| harness{"Harness of the parent session?"}',
    '  harness -->|OpenCode top-level| oc_exp["OpenCode native expert agent<br/>' + opencode.model + "<br/>effort " + opencode.efforts.expert + '"]',
    '  harness -->|Devin top-level| dv_exp["Devin native run_subagent<br/>subagent_general or subagent_explore<br/>no per-tier pin"]',
    '  harness -->|Codex| cx_exp["Codex native subagent<br/>session-config model, no per-tier pin"]',
    '  harness -->|Pi| pi_exp["Pi native expert profile<br/>' + `${expertPi.providerID}/${expertPi.id}, ${expertPi.variant}` + '"]',
    '  harness -->|Claude Code| cc_exp["Claude Code native subagent<br/>' + POLICY.nativeFallback.claudeModels.expert + ", " + POLICY.nativeFallback.claudeEffort.expert + ' effort"]',
    '  harness -->|any other harness| other["No defined lane in this contract<br/>report to the owner before delegating"]',
    "",
    '  tier -->|scout / mechanic / worker| cwd{"Top-level OpenCode or Devin session?"}',
    '  cwd -->|OpenCode| oc["OpenCode native tier agent<br/>scout ' + opencode.efforts.scout + ' · mechanic ' + opencode.efforts.mechanic + ' · worker ' + opencode.efforts.worker + '<br/>' + opencode.model + '"]',
    '  cwd -->|Devin| dv["Devin native run_subagent<br/>subagent_explore (read-only) · subagent_general (changes)"]',
    '  cwd -->|otherwise| bridge["pi-subagent-bridge<br/>worker_model_check → worker_start"]',
    "",
    '  bridge --> plan["Admitted ordered plan per tier<br/>codex → command-code → ordered Pi fallback"]',
    '  plan --> fallback{"First route available?"}',
    '  fallback -->|yes| admitted["worker_start admits one scoped assignment<br/>clean linked worktree · bounded attempts · scope enforced"]',
    '  fallback -->|no| next["Next admitted route in order<br/>only before edits · only along admitted routes"]',
    "  next --> fallback",
    "  admitted --> watch[\"watch / worker_status<br/>parent independently verifies proof and diff\"]",
    '  bridge -->|no approved backend: quota or exhausted| native["Tier-matched native subagents (Claude Code)<br/>scout ' + POLICY.nativeFallback.claudeModels.scout + " · mechanic " + POLICY.nativeFallback.claudeModels.mechanic + " · worker " + POLICY.nativeFallback.claudeModels.worker + '<br/>same brief, worktree, scope; independent parent review"]',
    "  native -->|capacity recovers| bridge",
    "```",
    "",
    "## Lane map",
    "",
    "Expert is native everywhere; the bridge is reserved for `scout`/`mechanic`/`worker` in harnesses without a top-level native exception.",
    "",
    "| Assignment | OpenCode (top-level) | Devin (top-level) | Codex | Pi | Claude Code |",
    "| --- | --- | --- | --- | --- | --- |",
    `| expert | native \`expert\` agent (${opencodeTier("expert")}) | \`run_subagent\`, unpinned | native subagent, unpinned | native \`expert\` profile (\`${expertPi.providerID}/${expertPi.id}\`, \`${expertPi.variant}\`) | native subagent (${expertClaude}) |`,
    `| quota exhaustion (scout/mechanic/worker) | never uses the bridge | never uses the bridge | not defined; report rather than substitute | not defined; report rather than substitute | native subagents: ${quota}, same brief, worktree and scope |`,
    "",
    "Codex, Pi and Claude Code route `scout`/`mechanic`/`worker` through the bridge; the admitted routes are:",
    "",
    "## The bridge, per tier",
    "",
    routingTable(POLICY),
    "",
    "## Hard rules",
    "",
    "- The bridge admits `scout`, `mechanic`, `worker` only. `worker_model_check`, `worker_start`, resume, steer and the MCP schemas reject `expert`.",
    "- Expert is harness-native everywhere; nothing routes to the bridge. Expert is terminal by lane: use it for exceptional architectural decisions and adversarial review, never as a size-based upgrade.",
    "- Top-level OpenCode and Devin sessions never use the bridge, at any tier or as a fallback. When the OpenCode top-level model is free, every tier runs a free model (the configured tier agents use `opencode/inkling-2-small-free` regardless of the top-level model).",
    "- Claude Code, Codex and Pi sessions use the bridge for `scout`/`mechanic`/`worker`; the bridge owns provider fallback (Codex → Command Code → ordered Pi), only before edits, only along admitted routes.",
    "- An admitted session keeps its recorded model and route. A task failure, rejected acceptance check or scope change is not a provider failure and never authorizes a replacement worker.",
    "- Codex and Command Code workers are leaves. Pi workers may fan out one nested generation to equal-or-weaker approved tiers; the typed ceiling is enforced per child, depth is 2, and `options: { agentScope: \"user\" }` is required for nested calls.",
    `- Ban on delegation of ${bannedFamilies} families in every harness, including every effort variant.`,
    "- The parent owns scope, worktrees, verification and integration in every harness. Agent output is a claim until the parent checks the diff and the acceptance proof.",
    "",
    "See [orchestrate](../dotfiles/base/.agents/skills/orchestrate/SKILL.md) for the routing contract and [the bridge reference](../tools/pi-subagent-bridge/README.md) for admission, fallback and state semantics.",
    "",
  ]
  return lines.join("\n")
}

export function main(args: readonly string[], root = ROOT): number {
  if (args.length > 1 || (args.length === 1 && !["--check", "--json"].includes(args[0])))
    throw new Error("usage: node tools/policy/subagent-visualization.ts [--check]")
  if (args[0] === "--json") {
    process.stdout.write(JSON.stringify({ destination: DESTINATION, source: SOURCE }, null, 2) + "\n")
    return 0
  }
  const content = markdown()
  const destination = join(root, DESTINATION)
  let previous: string | null = null
  try { previous = readFileSync(destination, "utf8") } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
  }
  if (args[0] === "--check") {
    if (previous !== content) {
      process.stderr.write(`Stale ${DESTINATION}; run make subagent-visualization\n`)
      return 1
    }
    return 0
  }
  if (previous === content) return 0
  writeFileSync(destination, content, "utf8")
  process.stdout.write(DESTINATION + "\n")
  return 0
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { process.exitCode = main(process.argv.slice(2)) }
  catch (error) {
    process.stderr.write(`subagent-visualization: ${error instanceof Error ? error.message : String(error)}\n`)
    process.exitCode = 1
  }
}
