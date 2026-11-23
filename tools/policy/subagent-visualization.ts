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

const LANES: Record<LaneKind, { label: string; accent: string }> = {
  native: { label: "Native", accent: "#2f6f5e" },
  primary: { label: "Bridge primary", accent: "#3b5b9c" },
  fallback: { label: "Bridge fallback", accent: "#9a6a2f" },
  undefined: { label: "Undefined", accent: "#8a9099" },
  pilot: { label: "Pilot / opt-in", accent: "#735a9a" },
}

const EFFORTS: Record<string, string> = {
  low: "#64748b",
  medium: "#3b5b9c",
  high: "#2f6f5e",
  xhigh: "#9a6a2f",
  max: "#735a9a",
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

function dot(accent: string): string {
  return `<i class="dot" style="--tone:${accent}"></i>`
}

function modelPill(value: string): string {
  return `<span class="model">${esc(value)}</span>`
}

function effortLabel(value: string | undefined): string {
  if (!value) return ""
  return `<span class="effort">${dot(EFFORTS[value] ?? EFFORTS.low!)}${esc(value)}</span>`
}

function tierLabel(tier: Tier): string {
  return `<span class="tier">${dot(TIER_ACCENTS[tier])}${tier}</span>`
}

type Item = {
  kind: LaneKind
  title: string
  model?: string
  models?: readonly string[]
  effort?: string
  detail?: string
  tier?: Tier
  rank?: number
  compact?: boolean
}

function displayModel(value: string, compact: boolean | undefined): string {
  return compact ? value.slice(value.lastIndexOf("/") + 1) : value
}

function meta(item: Item): string {
  const parts: string[] = []
  if (item.model) parts.push(modelPill(displayModel(item.model, item.compact)))
  if (item.models) parts.push(item.models.map(model => modelPill(displayModel(model, item.compact))).join('<span class="arrow">→</span>'))
  if (item.effort) parts.push(effortLabel(item.effort))
  if (item.detail) parts.push(`<span class="detail">${inline(item.detail)}</span>`)
  return parts.length ? `<div class="meta">${parts.join(" ")}</div>` : ""
}

function style(): string {
  return `<style>
:root{--ink:#1f2937;--muted:#6b7280;--line:#e5e7eb;--link:#2563eb}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1120px;margin:0 auto;padding:36px 24px 72px}
h1{font-size:22px;font-weight:600;margin:0 0 8px;letter-spacing:-.01em}
h2{font-size:15px;font-weight:600;margin:32px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
p{margin:6px 0;color:var(--muted);max-width:100ch}
code{font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f4f5f7;border-radius:4px;padding:1px 4px;color:#374151}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
.key{display:flex;flex-wrap:wrap;align-items:center;gap:4px 18px;font-size:12px;color:var(--muted);margin-top:10px}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--tone);margin-right:5px;vertical-align:1px}
.model{font:11px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;border:1px solid var(--line);border-radius:4px;padding:0 5px;color:#374151;white-space:nowrap}
.effort,.tier{font-size:11px;color:var(--muted);white-space:nowrap}
.tier{font-weight:600;color:var(--ink)}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin-top:3px}
.arrow{color:#9ca3af;font-size:11px}
.detail{font-size:11px;color:var(--muted)}
.graph-scroll{overflow-x:auto;padding-bottom:6px;border-bottom:1px solid var(--line)}
.graph-scroll svg{display:block;min-width:1000px}
.edge{fill:none;stroke:#c2c9d4;stroke-width:1;marker-end:url(#g-arrow)}
.edge-label{font-size:10px;fill:var(--muted);paint-order:stroke;stroke:#fff;stroke-width:3px}
.node-box{height:100%;border:1px solid var(--line);border-radius:5px;background:#fff;padding:6px 9px;position:relative;overflow:hidden}
.node-box::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;background:var(--tone)}
.node-title{font-size:12px;font-weight:600;line-height:1.3}
.node-box .tier{margin-right:6px}
.node-meta{font-size:10.5px;color:var(--muted);margin-top:2px}
.node-meta .model{font-size:9.5px;padding:0 3px}
.table-scroll{overflow-x:auto}
table{border-collapse:collapse;table-layout:fixed;width:100%;min-width:1000px;font-size:12px}
th,td{padding:6px 6px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
td .model{font-size:9.5px;padding:0 3px}
thead th{color:var(--muted);font-weight:600;background:#fafafa}
tbody th{font-weight:600;width:100px;background:#fafafa}
td .name{font-weight:600}
td .meta{margin-top:1px}
.route-row{padding:9px 0;border-bottom:1px solid var(--line);display:grid;grid-template-columns:64px repeat(5,minmax(0,1fr));gap:4px 8px;align-items:center}
.route-row .tier{white-space:nowrap}
.route{display:flex;flex-direction:column;align-items:flex-start;gap:1px;min-width:0}
.route-top{display:flex;align-items:center;gap:4px;min-width:0}
.route .model{font-size:9.5px;padding:0 3px}
.rank{font:11px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 4px}
.rules{padding-left:20px;color:#374151}
.rules li{margin:6px 0}
footer{margin-top:28px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
@media (max-width:720px){main{padding:24px 14px 56px}.route-row{grid-template-columns:1fr;gap:2px}}
</style>`
}

function key(): string {
  const kinds = (Object.keys(LANES) as LaneKind[]).map(kind =>
    `<span>${dot(LANES[kind].accent)}${LANES[kind].label}</span>`).join("")
  const efforts = ["low", "medium", "high", "xhigh", "max"].map(value =>
    `<span>${dot(EFFORTS[value]!)}${value}</span>`).join("")
  return '<div class="key">' + kinds + '<span>Thinking: ' + efforts + '</span>' +
    '<span>Route rank: P1 primary, P2+ fallbacks</span></div>'
}

type GraphNode = { id: string; x: number; y: number; w: number; h: number; item: Item }
type GraphEdge = { from: string; to: string; label?: string; path?: string; labelAt?: { x: number; y: number } }

function graphNodes(): GraphNode[] {
  const claude = POLICY.nativeFallback.claudeModels
  return [
    { id: "start", x: 400, y: 12, w: 200, h: 42, item: { kind: "primary", title: "Parent wants a subagent" } },
    { id: "tier", x: 400, y: 76, w: 200, h: 42, item: { kind: "primary", title: "Which tier?" } },
    { id: "expert", x: 90, y: 148, w: 220, h: 60, item: { kind: "native", tier: "expert", title: "Native expert", detail: "native in every harness" } },
    { id: "lower", x: 690, y: 148, w: 220, h: 54, item: { kind: "primary", title: "scout / mechanic / worker" } },
    { id: "harness", x: 40, y: 240, w: 280, h: 110, item: { kind: "native", title: "Harness-native expert lanes", detail: "OpenCode · Antigravity · Command Code · Devin · Codex · Pi · Claude Code · Copilot pilot (attest first) · other" } },
    { id: "cwd", x: 690, y: 240, w: 220, h: 96, item: { kind: "primary", title: "Top-level native parent?", detail: "OpenCode · Devin · Command Code · Antigravity · Copilot pilot" } },
    { id: "native", x: 470, y: 365, w: 240, h: 96, item: { kind: "native", title: "Native tier lanes", detail: "native usr-* / run_subagent; Copilot: attest or block; never the bridge" } },
    { id: "bridge", x: 760, y: 365, w: 200, h: 84, item: { kind: "primary", title: "pi-subagent-bridge", detail: "worker_model_check → worker_start" } },
    { id: "plan", x: 700, y: 465, w: 300, h: 130, item: { kind: "primary", title: "Admitted ordered plan", models: POLICY.rootRoutes.worker.map(modelOf) } },
    { id: "available", x: 770, y: 625, w: 180, h: 42, item: { kind: "primary", title: "First route available?" } },
    { id: "admitted", x: 480, y: 705, w: 240, h: 100, item: { kind: "native", title: "worker_start: one scoped assignment", detail: "clean worktree · bounded attempts · scope; parent verifies proof and diff" } },
    { id: "next", x: 770, y: 705, w: 180, h: 60, item: { kind: "fallback", title: "Next admitted route", detail: "only before edits" } },
    { id: "fallback", x: 180, y: 705, w: 260, h: 80, item: { kind: "native", title: "Tier-matched native subagents", models: POLICY.nativeFallback.tiers.map(tier => claude[tier as "scout"]), detail: "Claude Code; same brief and scope" } },
  ]
}

function graphEdges(): GraphEdge[] {
  return [
    { from: "start", to: "tier" },
    { from: "tier", to: "expert", label: "expert" },
    { from: "tier", to: "lower", label: "lower tiers" },
    { from: "expert", to: "harness" },
    { from: "lower", to: "cwd" },
    { from: "cwd", to: "native", label: "yes" },
    { from: "cwd", to: "bridge", label: "otherwise" },
    { from: "bridge", to: "plan" },
    { from: "plan", to: "available" },
    { from: "available", to: "admitted", label: "yes" },
    { from: "available", to: "next", label: "no" },
    { from: "next", to: "available", label: "retry", path: "M 950 735 H 978 V 646 H 950", labelAt: { x: 968, y: 690 } },
    { from: "available", to: "fallback", label: "exhausted", path: "M 770 646 H 310 V 705", labelAt: { x: 425, y: 639 } },
  ]
}

function svgEdge(edge: GraphEdge, nodes: readonly GraphNode[]): string {
  const source = nodes.find(node => node.id === edge.from)
  const target = nodes.find(node => node.id === edge.to)
  if (!source || !target) throw new Error(`Unknown graph edge ${edge.from} → ${edge.to}`)
  const sx = source.x + source.w / 2, sy = source.y + source.h
  const tx = target.x + target.w / 2, ty = target.y
  const mid = sy + (ty - sy) / 2
  const path = edge.path ?? `M ${sx} ${sy} L ${sx} ${mid} L ${tx} ${mid} L ${tx} ${ty}`
  const label = edge.label
    ? `<text class="edge-label" x="${edge.labelAt?.x ?? (sx + tx) / 2}" y="${edge.labelAt?.y ?? mid - 4}">${esc(edge.label)}</text>`
    : ""
  return `<path class="edge" d="${path}"/>${label}`
}

function svgNode(node: GraphNode): string {
  const item = node.item
  const heading = (item.rank ? `<span class="rank">P${item.rank}</span>` : "") +
    (item.tier ? tierLabel(item.tier) : "") + `<span class="node-title">${esc(item.title)}</span>`
  const detail = item.model || item.models || item.effort || item.detail
    ? `<div class="node-meta">${meta(item)}</div>` : ""
  return `<foreignObject x="${node.x}" y="${node.y}" width="${node.w}" height="${node.h}">` +
    `<div xmlns="http://www.w3.org/1999/xhtml" class="node-box" style="--tone:${LANES[item.kind].accent}">` +
    `${heading}${detail}</div></foreignObject>`
}

function graph(): string {
  const nodes = graphNodes()
  return '<div class="graph-scroll"><svg viewBox="0 0 1000 820" width="1000" height="820" role="img" aria-label="Subagent delegation decision graph">' +
    '<defs><marker id="g-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto-start-reverse">' +
    '<path d="M 0 0 L 8 4 L 0 8 z" fill="#aeb6c4"/></marker></defs>' +
    '<g>' + graphEdges().map(edge => svgEdge(edge, nodes)).join("") + '</g>' +
    '<g>' + nodes.map(svgNode).join("") + '</g>' +
    '</svg></div>'
}

function modelOf(route: Route): string {
  return route.executor === "pi" ? `${route.providerID}/${route.model}` : route.model
}

function commandEffort(tier: "scout" | "mechanic" | "worker"): string | undefined {
  const pin = POLICY.commandNative[tier]
  return "effort" in pin ? pin.effort : undefined
}

function laneMap(): string {
  const opencode = POLICY.opencode
  const agy = POLICY.antigravityDirect
  const command = POLICY.commandNative
  const copilot = POLICY.copilotNative
  const claude = POLICY.nativeFallback.claudeModels
  const head = ["Assignment", "OpenCode", "Devin", "Command Code", "Codex", "Pi", "Claude Code", "Antigravity", "Copilot (unqualified pilot)"]
  const rows: string[] = []

  function cell(item: Item): string {
    const compact = { ...item, compact: true }
    return `<td><span class="name">${esc(item.title)}</span>${meta(compact)}</td>`
  }

  rows.push("<tr><th>expert</th>" + [
    cell({ kind: "native", title: "native expert", model: opencode.model, effort: opencode.efforts.expert }),
    cell({ kind: "native", title: "run_subagent", detail: "unpinned" }),
    cell({ kind: "native", title: command.expert.name, model: command.expert.model, effort: command.expert.effort }),
    cell({ kind: "native", title: "native subagent", detail: "unpinned" }),
    cell({ kind: "native", title: "native expert profile", model: `${POLICY.nativePi.goModels.expert.providerID}/${POLICY.nativePi.goModels.expert.id}`, effort: POLICY.nativePi.goModels.expert.variant }),
    cell({ kind: "native", title: "native subagent", model: claude.expert, effort: POLICY.nativeFallback.claudeEffort.expert }),
    cell({ kind: "native", title: agy.tiers.expert.name, model: agy.tiers.expert.model, effort: agy.tiers.expert.effort }),
    cell({ kind: "pilot", title: copilot.expert.name, model: copilot.expert.model, effort: copilot.expert.effort, detail: "candidate; attest first" }),
  ].join("") + "</tr>")

  for (const tier of ["scout", "mechanic", "worker"] as const) {
    const agyTier = agy.tiers[tier]
    const bridge = POLICY.rootRoutes[tier][0]!
    rows.push(`<tr><th>${tier}</th>` + [
      cell({ kind: "native", title: "native tier agent", model: opencode.model, effort: opencode.efforts[tier] }),
      cell({ kind: "native", title: tier === "scout" ? "subagent_explore" : "subagent_general", detail: tier === "scout" ? "read-only" : "writes" }),
      cell({ kind: "native", title: command[tier].name, model: command[tier].model, effort: commandEffort(tier), detail: commandEffort(tier) ? undefined : "model default" }),
      cell({ kind: "primary", title: "bridge", model: modelOf(bridge), effort: bridge.effort, detail: `${tier} ladder` }),
      cell({ kind: "primary", title: "bridge", model: modelOf(bridge), effort: bridge.effort, detail: `${tier} ladder` }),
      cell({ kind: "primary", title: "bridge", model: modelOf(bridge), effort: bridge.effort, detail: `${tier} ladder` }),
      cell({ kind: "native", title: agyTier.name, model: agyTier.model, effort: agyTier.effort, detail: `selector ${agyTier.selector}; verify` }),
      cell({ kind: "pilot", title: copilot[tier].name, model: copilot[tier].model, effort: copilot[tier].effort, detail: "candidate; attest first" }),
    ].join("") + "</tr>")
  }

  rows.push('<tr><th>quota exhaustion</th>' + [
    cell({ kind: "undefined", title: "no bridge" }),
    cell({ kind: "undefined", title: "no bridge" }),
    cell({ kind: "undefined", title: "no bridge", detail: "no model switch" }),
    cell({ kind: "undefined", title: "not defined", detail: "report instead" }),
    cell({ kind: "undefined", title: "not defined", detail: "report instead" }),
    cell({ kind: "native", title: "native subagents", models: POLICY.nativeFallback.tiers.map(tier => claude[tier as "scout"]), detail: "same scope" }),
    cell({ kind: "undefined", title: "no bridge", detail: "block mismatch" }),
    cell({ kind: "undefined", title: "blocked", detail: "no bridge fallback" }),
  ].join("") + "</tr>")

  return '<section><h2>Lane map</h2><div class="table-scroll"><table><thead><tr>' +
    head.map(header => `<th>${header}</th>`).join("") + '</tr></thead><tbody>' +
    rows.join("\n") + '</tbody></table></div></section>'
}

function bridgeRoutes(): string {
  const rows = POLICY.tiers.map(tier => {
    const routes = POLICY.rootRoutes[tier].map((route, index) => {
      const model = modelOf(route)
      return `<div class="route"><span class="route-top"><span class="rank">P${index + 1}</span>` +
        modelPill(model.slice(model.lastIndexOf("/") + 1)) + '</span>' + effortLabel(route.effort) + '</div>'
    }).join("")
    return `<div class="route-row">${tierLabel(tier)}${routes}</div>`
  }).join("\n")
  return '<section><h2>The bridge, per tier</h2>' + rows +
    '<p>A task failure, rejected acceptance check or scope change is not a provider failure: an admitted route is never replaced after edits.</p></section>'
}

function hardRules(): string {
  const opencode = POLICY.opencode
  const banned = POLICY.bannedModels.map(model => `\`${model}\``).join(" / ")
  const rules = [
    "The bridge admits `scout`, `mechanic`, `worker` only. `worker_model_check`, `worker_start`, resume, steer and the MCP schemas reject `expert`.",
    "Expert is harness-native everywhere; nothing routes to the bridge. Expert is terminal by lane: use it for exceptional architectural decisions and adversarial review, never as a size-based upgrade.",
    "Top-level OpenCode, Devin and Command Code sessions never use the bridge, at any tier or as a fallback. Command Code uses native `usr-*` agents; HY4-medium worker is an explicit pilot, not a default. When the OpenCode top-level model is free, every tier runs a free model (its configured tier agents use `" + opencode.model + "`).",
    "Top-level Antigravity CLI sessions use native usr-* subagents only. Its flash/pro model selectors do not enforce exact model IDs or efforts: verify or block the lane. God is a direct main-session mode.",
    "Copilot CLI is an unqualified native-only pilot. Its named usr-* lanes require observed model and effort attestation before dispatch. Block unavailable or unattested lanes; never use Auto, built-in agents or the bridge as a fallback. Children are leaves.",
    "Claude Code, Codex and Pi sessions use the bridge for `scout`/`mechanic`/`worker`; the bridge owns provider fallback (Command Code → ordered Pi → Codex), only before edits, only along admitted routes.",
    "Command Code native children cannot spawn another subagent. Native frontmatter pins and parent scoping are instructions, not bridge-enforced admission; model overrides and unsupported effort can bypass intended settings.",
    "An admitted session keeps its recorded model and route. A task failure, rejected acceptance check or scope change is not a provider failure and never authorizes a replacement worker.",
    "Codex and Command Code workers are leaves. Pi workers may fan out one nested generation to equal-or-weaker approved tiers; the typed ceiling is enforced per child, depth is 2, and `options: { agentScope: \"user\" }` is required for nested calls.",
    `Ban on delegation of ${banned} families in every harness, including every effort variant.`,
    "The parent owns scope, worktrees, verification and integration in every harness. Agent output is a claim until the parent checks the diff and the acceptance proof.",
  ]
  return '<section><h2>Hard rules</h2><ol class="rules">' +
    rules.map(rule => `<li>${inline(rule)}</li>`).join("\n") + '</ol></section>'
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
    key(),
    '</header>',
    '<section><h2>Decision graph</h2>' + graph() + '</section>',
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
