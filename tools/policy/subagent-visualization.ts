import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { POLICY, type Route } from "../pi-subagent-bridge/src/policy.ts"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const DESTINATION = "docs/subagents.html"
const SOURCE = "tools/policy/subagent-visualization.ts"
const NOTICE = `<!-- Generated from ${SOURCE}; run make subagent-visualization. -->`

type Tier = "scout" | "mechanic" | "worker" | "expert"
type LaneKind = "native" | "primary" | "fallback" | "undefined" | "pilot"

const LANES: Record<LaneKind, { label: string; accent: string; fills: readonly string[] }> = {
  native: { label: "Native", accent: "#2f6f5e", fills: ["#fbfdfc", "#f7faf9", "#f2f8f5", "#ecf5f0", "#e5f0ea"] },
  primary: { label: "Bridge primary", accent: "#3b5b9c", fills: ["#fbfcfe", "#f5f8fd", "#eef4fb", "#e7f0f9", "#dfeaf6"] },
  fallback: { label: "Bridge fallback", accent: "#9a6a2f", fills: ["#fdfbf8", "#fbf6ee", "#f8f0e3", "#f4e9d7", "#efe1ca"] },
  undefined: { label: "Undefined", accent: "#7a818c", fills: ["#fbfbfc", "#f7f8f9", "#f3f4f6", "#eceef1", "#e5e8ec"] },
  pilot: { label: "Pilot / opt-in", accent: "#735a9a", fills: ["#fcfbfd", "#f8f5fb", "#f3eef8", "#ece5f4", "#e5dbef"] },
}

const TIER_ACCENTS: Record<Tier, string> = {
  scout: "#0f766e",
  mechanic: "#4338a0",
  worker: "#b45309",
  expert: "#7e22ce",
}

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}

function esc(value: string): string {
  return value.replace(/[&<>"']/g, character => HTML_ESCAPES[character]!)
}

function inline(value: string): string {
  return esc(value).replace(/`([^`]+)`/g, "<code>$1</code>")
}

function code(value: string): string {
  return "<code>" + esc(value) + "</code>"
}

function level(effort: string | undefined): number {
  switch (effort) {
    case "none": case "low": return 1
    case "medium": return 2
    case "high": return 3
    case "xhigh": return 4
    case "max": return 5
    default: return 1
  }
}

function laneStyle(kind: LaneKind, strength: number): string {
  const spec = LANES[kind]
  const index = Math.max(0, Math.min(4, strength - 1))
  return `--accent:${spec.accent};--fill:${spec.fills[index]}`
}

function tierLabel(tier: Tier): string {
  return `<span class="tier" style="--tone:${TIER_ACCENTS[tier]}">${tier}</span>`
}

function rankLabel(rank: number | undefined): string {
  return rank === undefined ? "" : `<span class="rank">P${rank}</span>`
}

type LaneOptions = {
  kind: LaneKind
  strength: number
  title: string
  tier?: Tier
  rank?: number
  detail?: string
  note?: string
}

function heading(option: LaneOptions): string {
  return `${rankLabel(option.rank)}<span class="kind">${LANES[option.kind].label}</span>` +
    (option.tier ? tierLabel(option.tier) : "") + `<strong>${esc(option.title)}</strong>`
}

function laneRow(option: LaneOptions): string {
  const body = option.detail ? `<div class="detail">${inline(option.detail)}</div>` : ""
  const note = option.note ? `<div class="detail">${inline(option.note)}</div>` : ""
  return `<div class="lane" style="${laneStyle(option.kind, option.strength)}">${heading(option)}${body}${note}</div>`
}

function mapCell(option: LaneOptions): string {
  const detail = option.detail ? `<div class="detail">${inline(option.detail)}</div>` : ""
  return `<td class="cell" style="${laneStyle(option.kind, option.strength)}">${heading(option)}${detail}</td>`
}

function modelOf(route: Route): string {
  return route.executor === "pi" ? `${route.providerID}/${route.model}` : route.model
}

function executorLabel(route: Route): string {
  switch (route.executor) {
    case "command-code": return "Command Code"
    case "codex": return "Codex"
    case "pi": return "Pi"
  }
}

function commandEffort(tier: "scout" | "mechanic" | "worker"): string {
  const pin = POLICY.commandNative[tier]
  return "effort" in pin ? pin.effort : "medium"
}

function style(): string {
  return `<style>
:root{--ink:#20242b;--muted:#6b7280;--line:#e6e8ec}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1120px;margin:0 auto;padding:40px 24px 80px}
header{border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:8px}
h1{font-size:22px;font-weight:600;margin:0 0 8px;letter-spacing:-.01em}
h2{font-size:15px;font-weight:600;margin:30px 0 10px}
h3{font-size:13px;font-weight:600;margin:18px 0 8px;color:#374151}
p{margin:6px 0;color:var(--muted)}
code{font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f4f5f7;border-radius:4px;padding:1px 4px;color:#374151}
a{color:#2563eb;text-decoration:none}
a:hover{text-decoration:underline}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12px;color:var(--muted)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);margin-right:5px;vertical-align:1px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:26px}
.lane{padding:7px 11px;border-left:2px solid var(--accent);background:var(--fill);border-radius:4px;margin:5px 0}
.lane strong,.cell strong{font-weight:600;font-size:13px}
.kind{font-size:11px;color:var(--accent);font-weight:600;margin-right:6px}
.rank{font-size:11px;color:var(--accent);font-weight:600;margin-right:6px}
.tier{font-size:11px;color:var(--tone);font-weight:600;margin-right:6px}
.detail{font-size:12px;color:var(--muted);margin-top:2px}
.table-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;min-width:1040px;font-size:12px}
th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
thead th{color:var(--muted);font-weight:600;background:#fafafa}
tbody th{font-weight:600;background:#fafafa;width:110px}
.cell{border-left-width:2px}
.chain{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}
.route{padding:7px 10px;border-left:2px solid var(--accent);background:var(--fill);border-radius:4px;min-width:170px}
.rules{padding-left:20px;color:#374151}
.rules li{margin:6px 0}
footer{margin-top:34px;padding-top:14px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
@media (max-width:720px){main{padding:24px 14px 60px}}
</style>`
}

function legend(): string {
  const items = (Object.keys(LANES) as LaneKind[]).map(kind =>
    `<span><i class="dot" style="--accent:${LANES[kind].accent}"></i>${LANES[kind].label}</span>`).join("")
  return [
    '<div class="legend">',
    items,
    '<span>Tint depth = model effort (low → max)</span>',
    '<span>Route rank: P1 primary, P2+ fallbacks</span>',
    '<span>Tier labels = assignment tier</span>',
    '</div>',
  ].join("\n")
}

function decisionGraph(): string {
  const opencode = POLICY.opencode
  const agy = POLICY.antigravityDirect
  const command = POLICY.commandNative
  const claude = POLICY.nativeFallback.claudeModels
  const piExpert = POLICY.nativePi.goModels.expert

  const expertLanes: LaneOptions[] = [
    { kind: "native", strength: level(opencode.efforts.expert), tier: "expert", title: "OpenCode native expert", detail: `${opencode.model} · effort ${opencode.efforts.expert}` },
    { kind: "native", strength: level(agy.tiers.expert.effort), tier: "expert", title: "Antigravity native expert", detail: `${agy.tiers.expert.name} · ${agy.tiers.expert.model} · selector ${agy.tiers.expert.selector}` },
    { kind: "native", strength: level(command.expert.effort), tier: "expert", title: "Command Code native expert", detail: `${command.expert.name} · ${command.expert.model}, ${command.expert.effort}` },
    { kind: "native", strength: 1, tier: "expert", title: "Devin native run_subagent", detail: "subagent_general or subagent_explore · no per-tier pin" },
    { kind: "native", strength: 1, tier: "expert", title: "Codex native subagent", detail: "session-config model · no per-tier pin" },
    { kind: "native", strength: level(piExpert.variant), tier: "expert", title: "Pi native expert profile", detail: `${piExpert.providerID}/${piExpert.id}, ${piExpert.variant}` },
    { kind: "native", strength: level(POLICY.nativeFallback.claudeEffort.expert), tier: "expert", title: "Claude Code native subagent", detail: `${claude.expert}, ${POLICY.nativeFallback.claudeEffort.expert} effort` },
    { kind: "undefined", strength: 1, title: "Any other harness", detail: "No defined lane in this contract — report to the owner before delegating" },
  ]

  const nativeLanes: LaneOptions[] = []
  for (const tier of ["scout", "mechanic", "worker"] as const) {
    nativeLanes.push({ kind: "native", strength: level(opencode.efforts[tier]), tier, title: "OpenCode native tier agent", detail: `${opencode.model}#${opencode.efforts[tier]}` })
    nativeLanes.push({ kind: "native", strength: level(commandEffort(tier)), tier, title: "Command Code native agent", detail: `${command[tier].name} · ${command[tier].model}, ${commandEffort(tier)}` })
    const agyTier = agy.tiers[tier]
    nativeLanes.push({ kind: "native", strength: level(agyTier.effort), tier, title: "Antigravity native agent", detail: `${agyTier.name} → ${agyTier.model} · selector ${agyTier.selector}; verify actual model and effort` })
  }
  nativeLanes.push({ kind: "native", strength: 1, tier: "scout", title: "Devin subagent_explore", detail: "read-only inventory" })
  nativeLanes.push({ kind: "native", strength: 1, title: "Devin subagent_general", detail: "writes; no per-tier pin" })
  nativeLanes.push({ kind: "pilot", strength: 2, tier: "worker", title: "HY4-medium worker pilot", detail: `${command.pilot.name} · ${command.pilot.model}, ${command.pilot.effort} — explicit comparison only` })

  const plan = POLICY.rootRoutes.worker.map(route => modelOf(route)).join(" → ")
  const quota = POLICY.nativeFallback.tiers.map(tier => `${tier} ${claude[tier as "scout"]}`).join(" · ")

  return [
    '<section>',
    '<h2>Decision graph</h2>',
    '<p>Parent agent wants a coding subagent → choose a tier.</p>',
    '<div class="cols">',
    '<div><h3>' + tierLabel("expert") + 'native in every harness</h3>',
    expertLanes.map(laneRow).join("\n"),
    '</div>',
    '<div><h3>scout / mechanic / worker — top-level native parents</h3>',
    '<p>OpenCode, Devin, Command Code and Antigravity parents never use the bridge.</p>',
    nativeLanes.map(laneRow).join("\n"),
    '<h3>otherwise → pi-subagent-bridge</h3>',
    laneRow({ kind: "primary", strength: 3, title: "Admitted ordered plan per tier", detail: "command-code → ordered Pi fallback → codex; `worker` ladder: " + plan }),
    '<p>First route available → admitted → watch / worker_status; parent verifies proof and diff. No route before edits → next route. No approved backend → tier-matched native subagents (Claude Code), then back to bridge when capacity recovers.</p>',
    '<p>Quota fallback: ' + inline(quota) + '</p>',
    '</div></div>',
    '</section>',
  ].join("\n")
}

function laneMap(): string {
  const opencode = POLICY.opencode
  const agy = POLICY.antigravityDirect
  const command = POLICY.commandNative
  const claude = POLICY.nativeFallback.claudeModels
  const head = ["Assignment", "OpenCode", "Devin", "Command Code", "Codex", "Pi", "Claude Code", "Antigravity"]
  const rows: string[] = []

  rows.push("<tr><th>expert</th>" + [
    mapCell({ kind: "native", strength: level(opencode.efforts.expert), title: "native expert", detail: `${opencode.model}#${opencode.efforts.expert}` }),
    mapCell({ kind: "native", strength: 1, title: "run_subagent", detail: "unpinned" }),
    mapCell({ kind: "native", strength: level(command.expert.effort), title: command.expert.name, detail: `${command.expert.model}, ${command.expert.effort}` }),
    mapCell({ kind: "native", strength: 1, title: "native subagent", detail: "unpinned" }),
    mapCell({ kind: "native", strength: level(POLICY.nativePi.goModels.expert.variant), title: "native expert profile", detail: `${POLICY.nativePi.goModels.expert.providerID}/${POLICY.nativePi.goModels.expert.id}, ${POLICY.nativePi.goModels.expert.variant}` }),
    mapCell({ kind: "native", strength: level(POLICY.nativeFallback.claudeEffort.expert), title: "native subagent", detail: `${claude.expert}, ${POLICY.nativeFallback.claudeEffort.expert} effort` }),
    mapCell({ kind: "native", strength: level(agy.tiers.expert.effort), title: agy.tiers.expert.name, detail: agy.tiers.expert.model }),
  ].join("") + "</tr>")

  for (const tier of ["scout", "mechanic", "worker"] as const) {
    const agyTier = agy.tiers[tier]
    const bridge = `bridge → ${tier} ladder`
    const bridgeStrength = level(POLICY.rootRoutes[tier][0]!.effort)
    rows.push(`<tr><th>${tier}</th>` + [
      mapCell({ kind: "native", strength: level(opencode.efforts[tier]), title: "native tier agent", detail: `${opencode.model}#${opencode.efforts[tier]}` }),
      mapCell({ kind: "native", strength: 1, title: "run_subagent", detail: tier === "scout" ? "subagent_explore (read-only)" : "subagent_general" }),
      mapCell({ kind: "native", strength: level(commandEffort(tier)), title: command[tier].name, detail: `${command[tier].model}, ${commandEffort(tier)}` }),
      mapCell({ kind: "primary", strength: bridgeStrength, title: "bridge", detail: bridge }),
      mapCell({ kind: "primary", strength: bridgeStrength, title: "bridge", detail: bridge }),
      mapCell({ kind: "primary", strength: bridgeStrength, title: "bridge", detail: bridge }),
      mapCell({ kind: "native", strength: level(agyTier.effort), title: agyTier.name, detail: `${agyTier.model} · selector ${agyTier.selector}; verify` }),
    ].join("") + "</tr>")
  }

  rows.push('<tr><th>quota exhaustion</th>' + [
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge" }),
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge" }),
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge", detail: "do not silently switch native models" }),
    mapCell({ kind: "undefined", strength: 1, title: "not defined", detail: "report rather than substitute" }),
    mapCell({ kind: "undefined", strength: 1, title: "not defined", detail: "report rather than substitute" }),
    mapCell({ kind: "native", strength: 2, title: "native subagents", detail: POLICY.nativeFallback.tiers.map(tier => `${tier} ${claude[tier as "scout"]}`).join(" · ") + "; same brief, worktree and scope" }),
    mapCell({ kind: "undefined", strength: 1, title: "never uses bridge", detail: "block mismatched model" }),
  ].join("") + "</tr>")

  return [
    '<section>',
    '<h2>Lane map</h2>',
    '<div class="table-scroll"><table><thead><tr>' + head.map(header => `<th>${header}</th>`).join("") + '</tr></thead><tbody>',
    rows.join("\n"),
    '</tbody></table></div>',
    '</section>',
  ].join("\n")
}

function bridgeRoutes(): string {
  const rows = POLICY.tiers.map(tier => {
    const chain = POLICY.rootRoutes[tier].map((route, index) => {
      const kind = index === 0 ? "primary" : "fallback"
      return `<div class="route" style="${laneStyle(kind, level(route.effort))}">` +
        `${rankLabel(index + 1)}<span class="kind">${LANES[kind].label}</span>${tierLabel(tier)}` +
        `<div><strong>${esc(executorLabel(route))} · ${esc(modelOf(route))}</strong></div>` +
        `<div class="detail">effort ${esc(route.effort)}</div></div>`
    }).join("<span>→</span>")
    return `<h3>${tier}</h3><div class="chain">${chain}</div>`
  }).join("\n")
  return [
    '<section>',
    '<h2>The bridge, per tier</h2>',
    rows,
    '<p>A task failure, rejected acceptance check or scope change is not a provider failure: an admitted route is never replaced after edits.</p>',
    '</section>',
  ].join("\n")
}

function hardRules(): string {
  const opencode = POLICY.opencode
  const banned = POLICY.bannedModels.map(model => `\`${model}\``).join(" / ")
  const rules = [
    "The bridge admits `scout`, `mechanic`, `worker` only. `worker_model_check`, `worker_start`, resume, steer and the MCP schemas reject `expert`.",
    "Expert is harness-native everywhere; nothing routes to the bridge. Expert is terminal by lane: use it for exceptional architectural decisions and adversarial review, never as a size-based upgrade.",
    "Top-level OpenCode, Devin and Command Code sessions never use the bridge, at any tier or as a fallback. Command Code uses native `usr-*` agents; HY4-medium worker is an explicit pilot, not a default. When the OpenCode top-level model is free, every tier runs a free model (its configured tier agents use `" + opencode.model + "`).",
    "Top-level Antigravity CLI sessions use native usr-* subagents only. Its flash/pro model selectors do not enforce exact model IDs or efforts: verify or block the lane. God is a direct main-session mode.",
    "Claude Code, Codex and Pi sessions use the bridge for `scout`/`mechanic`/`worker`; the bridge owns provider fallback (Command Code → ordered Pi → Codex), only before edits, only along admitted routes.",
    "Command Code native children cannot spawn another subagent. Native frontmatter pins and parent scoping are instructions, not bridge-enforced admission; model overrides and unsupported effort can bypass intended settings.",
    "An admitted session keeps its recorded model and route. A task failure, rejected acceptance check or scope change is not a provider failure and never authorizes a replacement worker.",
    "Codex and Command Code workers are leaves. Pi workers may fan out one nested generation to equal-or-weaker approved tiers; the typed ceiling is enforced per child, depth is 2, and `options: { agentScope: \"user\" }` is required for nested calls.",
    `Ban on delegation of ${banned} families in every harness, including every effort variant.`,
    "The parent owns scope, worktrees, verification and integration in every harness. Agent output is a claim until the parent checks the diff and the acceptance proof.",
  ]
  return '<section><h2>Hard rules</h2><ol class="rules">' +
    rules.map(rule => `<li>${inline(rule)}</li>`).join("\n") +
    '</ol></section>'
}

function html(): string {
  const banned = POLICY.bannedModels.map(model => code(model)).join(" / ")
  return [
    "<!doctype html>",
    '<html lang="en">',
    "<head>",
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    "<title>Subagent architecture</title>",
    style(),
    "</head>",
    "<body><main>",
    NOTICE,
    '<header>',
    "<h1>Subagent architecture</h1>",
    `<p>Decision graph for delegating a coding subagent. Tiers: <code>scout</code> (read-only: no <code>bash</code>, <code>edit</code> or <code>write</code>), <code>mechanic</code>, <code>worker</code>, <code>expert</code>. There is no <code>god</code> tier, and the ${banned} families are prohibited everywhere, including every effort variant.</p>`,
    '<p>Expert is native everywhere; the bridge serves only <code>scout</code>/<code>mechanic</code>/<code>worker</code> in harnesses without a native top-level exception.</p>',
    legend(),
    '</header>',
    decisionGraph(),
    laneMap(),
    bridgeRoutes(),
    hardRules(),
    '<footer>See <a href="../dotfiles/base/.agents/skills/orchestrate/SKILL.md">orchestrate</a> for the routing contract and <a href="../tools/pi-subagent-bridge/README.md">the bridge reference</a> for admission, fallback and state semantics.</footer>',
    "</main></body>",
    "</html>",
    "",
  ].join("\n")
}

export function main(args: readonly string[], root = ROOT): number {
  if (args.length > 1 || (args.length === 1 && !["--check", "--json"].includes(args[0])))
    throw new Error("usage: node tools/policy/subagent-visualization.ts [--check] [--json]")
  if (args[0] === "--json") {
    process.stdout.write(JSON.stringify({ destination: DESTINATION, source: SOURCE }, null, 2) + "\n")
    return 0
  }
  const content = html()
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
