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

const EFFORTS: Record<string, { tone: string; fill: string }> = {
  low: { tone: "#64748b", fill: "#f3f4f6" },
  medium: { tone: "#3b5b9c", fill: "#f1f5fd" },
  high: { tone: "#2f6f5e", fill: "#f0f7f4" },
  xhigh: { tone: "#9a6a2f", fill: "#fbf5eb" },
  max: { tone: "#735a9a", fill: "#f7f3fb" },
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

function modelPill(value: string): string {
  return `<span class="model">${esc(value)}</span>`
}

function effortChip(value: string | undefined): string {
  if (!value) return ""
  const spec = EFFORTS[value] ?? EFFORTS.low!
  return `<span class="effort" style="--tone:${spec.tone};--fill:${spec.fill}">${esc(value)}</span>`
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
  model?: string
  models?: readonly string[]
  effort?: string
  detail?: string
}

function heading(option: LaneOptions): string {
  return `${rankLabel(option.rank)}<span class="kind">${LANES[option.kind].label}</span>` +
    (option.tier ? tierLabel(option.tier) : "") + `<strong>${esc(option.title)}</strong>`
}

function meta(option: LaneOptions): string {
  const parts: string[] = []
  if (option.model) parts.push(modelPill(option.model))
  if (option.models) parts.push(option.models.map(modelPill).join('<span class="sep">→</span>'))
  if (option.effort) parts.push(effortChip(option.effort))
  if (option.detail) parts.push(`<span class="detail">${inline(option.detail)}</span>`)
  return parts.length ? `<div class="meta">${parts.join(" ")}</div>` : ""
}

function laneRow(option: LaneOptions): string {
  return `<div class="lane" style="${laneStyle(option.kind, option.strength)}">${heading(option)}${meta(option)}</div>`
}

function mapCell(option: LaneOptions): string {
  return `<td class="cell" style="${laneStyle(option.kind, option.strength)}">${heading(option)}${meta(option)}</td>`
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
.legend{display:flex;flex-wrap:wrap;align-items:center;gap:4px 16px;font-size:12px;color:var(--muted)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);margin-right:5px;vertical-align:1px}
.thinking{display:inline-flex;flex-wrap:wrap;align-items:center;gap:4px}
.graph-scroll{overflow-x:auto;border-bottom:1px solid var(--line);padding-bottom:8px}
.graph-scroll svg{display:block;min-width:1000px}
.edge{fill:none;stroke:#b9c0cc;stroke-width:.9;marker-end:url(#g-arrow)}
.edge-label{font-size:10px;fill:#6b7280}
.g-node{height:100%;border-top:1px solid var(--accent);padding:5px 7px;overflow:hidden}
.g-node strong{display:block;font-size:11px;line-height:1.25}
.g-node .meta{margin-top:2px}
.g-node .detail{font-size:10px;line-height:1.25}
.g-node .model{font-size:9.5px;padding:0 4px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:26px}
.lane{padding:7px 11px;border-left:2px solid var(--accent);background:var(--fill);border-radius:4px;margin:5px 0}
.lane strong,.cell strong{font-weight:600;font-size:13px}
.kind{font-size:11px;color:var(--accent);font-weight:600;margin-right:6px}
.rank{font-size:11px;color:var(--accent);font-weight:600;margin-right:6px}
.tier{font-size:11px;color:var(--tone);font-weight:600;margin-right:6px}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px;margin-top:4px}
.model{font:11px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f6f7f9;border:1px solid #e6e8ec;border-radius:5px;padding:1px 6px;color:#374151;white-space:nowrap}
.effort{font-size:11px;font-weight:600;color:var(--tone);background:var(--fill);border-radius:5px;padding:1px 6px;white-space:nowrap}
.sep{color:#9ca3af;font-size:11px}
.detail{font-size:12px;color:var(--muted)}
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
  const kinds = (Object.keys(LANES) as LaneKind[]).map(kind =>
    `<span><i class="dot" style="--accent:${LANES[kind].accent}"></i>${LANES[kind].label}</span>`).join("")
  const efforts = ["low", "medium", "high", "xhigh", "max"].map(effortChip).join("")
  return [
    '<div class="legend">',
    kinds,
    '<span class="thinking">Thinking: ' + efforts + '</span>',
    '<span>Tint depth = thinking level</span>',
    '<span>Route rank: P1 primary, P2+ fallbacks</span>',
    '<span>Tier labels = assignment tier</span>',
    '</div>',
  ].join("\n")
}

type GraphNode = { id: string; x: number; y: number; w: number; h: number; option: LaneOptions }
type GraphEdge = { from: string; to: string; label?: string; path?: string; labelAt?: { x: number; y: number } }

function graphNodes(): GraphNode[] {
  const claude = POLICY.nativeFallback.claudeModels
  return [
    { id: "start", x: 400, y: 16, w: 200, h: 42, option: { kind: "primary", strength: 2, title: "Parent wants a subagent" } },
    { id: "tier", x: 400, y: 86, w: 200, h: 42, option: { kind: "primary", strength: 3, title: "Which tier?" } },
    { id: "expert", x: 80, y: 160, w: 220, h: 52, option: { kind: "native", strength: 4, tier: "expert", title: "Native expert", detail: "native in every harness" } },
    { id: "lower", x: 700, y: 160, w: 220, h: 52, option: { kind: "primary", strength: 3, title: "scout / mechanic / worker" } },
    { id: "harness", x: 40, y: 250, w: 270, h: 100, option: { kind: "native", strength: 3, title: "Harness-native expert lanes", detail: "OpenCode · Antigravity · Command Code · Devin · Codex · Pi · Claude Code · other" } },
    { id: "cwd", x: 700, y: 250, w: 220, h: 52, option: { kind: "primary", strength: 2, title: "Top-level native parent?", detail: "OpenCode · Devin · Command Code · Antigravity" } },
    { id: "native", x: 500, y: 345, w: 220, h: 72, option: { kind: "native", strength: 3, title: "Native tier lanes", detail: "native usr-* / run_subagent agents; never the bridge" } },
    { id: "bridge", x: 760, y: 345, w: 200, h: 60, option: { kind: "primary", strength: 3, title: "pi-subagent-bridge", detail: "worker_model_check → worker_start" } },
    { id: "plan", x: 760, y: 440, w: 200, h: 100, option: { kind: "primary", strength: 3, title: "Admitted ordered plan", models: POLICY.rootRoutes.worker.map(modelOf) } },
    { id: "available", x: 760, y: 580, w: 200, h: 46, option: { kind: "primary", strength: 2, title: "First route available?" } },
    { id: "admitted", x: 480, y: 660, w: 220, h: 70, option: { kind: "native", strength: 3, title: "worker_start: one scoped assignment", detail: "clean worktree · bounded attempts · scope enforced" } },
    { id: "next", x: 770, y: 660, w: 180, h: 60, option: { kind: "fallback", strength: 2, title: "Next admitted route", detail: "only before edits" } },
    { id: "watch", x: 480, y: 760, w: 220, h: 50, option: { kind: "native", strength: 3, title: "watch / worker_status", detail: "parent verifies proof and diff" } },
    { id: "fallback", x: 180, y: 760, w: 250, h: 80, option: { kind: "native", strength: 2, title: "Tier-matched native subagents", models: POLICY.nativeFallback.tiers.map(tier => claude[tier as "scout"]), detail: "Claude Code; same brief and scope" } },
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
    { from: "admitted", to: "watch" },
    { from: "next", to: "available", label: "retry", path: "M 950 690 H 978 V 603 H 960", labelAt: { x: 968, y: 642 } },
    { from: "available", to: "fallback", label: "exhausted", path: "M 760 603 H 305 V 760", labelAt: { x: 425, y: 596 } },
  ]
}

function svgEdge(edge: GraphEdge, nodes: readonly GraphNode[]): string {
  const source = nodes.find(node => node.id === edge.from)
  const target = nodes.find(node => node.id === edge.to)
  if (!source || !target) throw new Error(`Unknown graph edge ${edge.from} → ${edge.to}`)
  const sx = source.x + source.w / 2, sy = source.y + source.h
  const tx = target.x + target.w / 2, ty = target.y
  const mid = (sy + ty) / 2
  const path = edge.path ?? `M ${sx} ${sy} C ${sx} ${mid} ${tx} ${mid} ${tx} ${ty}`
  const label = edge.label
    ? `<text class="edge-label" x="${edge.labelAt?.x ?? (sx + tx) / 2}" y="${edge.labelAt?.y ?? mid - 4}">${esc(edge.label)}</text>`
    : ""
  return `<path class="edge" d="${path}"/>${label}`
}

function svgNode(node: GraphNode): string {
  const option = node.option
  const headingText = rankLabel(option.rank) +
    (option.tier ? tierLabel(option.tier) : "") + `<strong>${esc(option.title)}</strong>`
  return `<foreignObject x="${node.x}" y="${node.y}" width="${node.w}" height="${node.h}">` +
    `<div xmlns="http://www.w3.org/1999/xhtml" class="g-node" style="${laneStyle(option.kind, option.strength)}">` +
    `${headingText}${meta(option)}</div></foreignObject>`
}

function graph(): string {
  const nodes = graphNodes()
  return '<div class="graph-scroll"><svg viewBox="0 0 1000 830" width="1000" height="830" role="img" aria-label="Subagent delegation decision graph">' +
    '<defs><marker id="g-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="4" markerHeight="4" orient="auto-start-reverse">' +
    '<path d="M 0 0 L 8 4 L 0 8 z" fill="#aeb6c4"/></marker></defs>' +
    '<g>' + graphEdges().map(edge => svgEdge(edge, nodes)).join("") + '</g>' +
    '<g>' + nodes.map(svgNode).join("") + '</g>' +
    '</svg></div>'
}

function decisionGraph(): string {
  const opencode = POLICY.opencode
  const agy = POLICY.antigravityDirect
  const command = POLICY.commandNative
  const claude = POLICY.nativeFallback.claudeModels
  const piExpert = POLICY.nativePi.goModels.expert

  const expertLanes: LaneOptions[] = [
    { kind: "native", strength: level(opencode.efforts.expert), tier: "expert", title: "OpenCode native expert", model: opencode.model, effort: opencode.efforts.expert },
    { kind: "native", strength: level(agy.tiers.expert.effort), tier: "expert", title: "Antigravity native expert", model: agy.tiers.expert.model, effort: agy.tiers.expert.effort, detail: `${agy.tiers.expert.name} · selector ${agy.tiers.expert.selector}` },
    { kind: "native", strength: level(command.expert.effort), tier: "expert", title: "Command Code native expert", model: command.expert.model, effort: command.expert.effort, detail: command.expert.name },
    { kind: "native", strength: 1, tier: "expert", title: "Devin native run_subagent", detail: "subagent_general or subagent_explore · no per-tier pin" },
    { kind: "native", strength: 1, tier: "expert", title: "Codex native subagent", detail: "session-config model · no per-tier pin" },
    { kind: "native", strength: level(piExpert.variant), tier: "expert", title: "Pi native expert profile", model: `${piExpert.providerID}/${piExpert.id}`, effort: piExpert.variant },
    { kind: "native", strength: level(POLICY.nativeFallback.claudeEffort.expert), tier: "expert", title: "Claude Code native subagent", model: claude.expert, effort: POLICY.nativeFallback.claudeEffort.expert },
    { kind: "undefined", strength: 1, title: "Any other harness", detail: "No defined lane in this contract — report to the owner before delegating" },
  ]

  const nativeLanes: LaneOptions[] = []
  for (const tier of ["scout", "mechanic", "worker"] as const) {
    nativeLanes.push({ kind: "native", strength: level(opencode.efforts[tier]), tier, title: "OpenCode native tier agent", model: opencode.model, effort: opencode.efforts[tier] })
    nativeLanes.push({ kind: "native", strength: level(commandEffort(tier)), tier, title: "Command Code native agent", model: command[tier].model, effort: commandEffort(tier), detail: command[tier].name })
    const agyTier = agy.tiers[tier]
    nativeLanes.push({ kind: "native", strength: level(agyTier.effort), tier, title: "Antigravity native agent", model: agyTier.model, effort: agyTier.effort, detail: `${agyTier.name} · selector ${agyTier.selector}; verify actual model and effort` })
  }
  nativeLanes.push({ kind: "native", strength: 1, tier: "scout", title: "Devin subagent_explore", detail: "read-only inventory" })
  nativeLanes.push({ kind: "native", strength: 1, title: "Devin subagent_general", detail: "writes; no per-tier pin" })
  nativeLanes.push({ kind: "pilot", strength: 2, tier: "worker", title: "HY4-medium worker pilot", model: command.pilot.model, effort: command.pilot.effort, detail: `${command.pilot.name} — explicit comparison only` })

  return [
    '<section>',
    '<h2>Decision graph</h2>',
    graph(),
    '<h3>Lane details</h3>',
    '<div class="cols">',
    '<div><h3>' + tierLabel("expert") + 'native in every harness</h3>',
    expertLanes.map(laneRow).join("\n"),
    '</div>',
    '<div><h3>scout / mechanic / worker — top-level native parents</h3>',
    '<p>OpenCode, Devin, Command Code and Antigravity parents never use the bridge.</p>',
    nativeLanes.map(laneRow).join("\n"),
    laneRow({ kind: "primary", strength: 3, title: "Admitted ordered plan per tier", detail: "command-code → ordered Pi fallback → codex; worker ladder", models: POLICY.rootRoutes.worker.map(modelOf) }),
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
    mapCell({ kind: "native", strength: level(opencode.efforts.expert), title: "native expert", model: opencode.model, effort: opencode.efforts.expert }),
    mapCell({ kind: "native", strength: 1, title: "run_subagent", detail: "unpinned" }),
    mapCell({ kind: "native", strength: level(command.expert.effort), title: command.expert.name, model: command.expert.model, effort: command.expert.effort }),
    mapCell({ kind: "native", strength: 1, title: "native subagent", detail: "unpinned" }),
    mapCell({ kind: "native", strength: level(POLICY.nativePi.goModels.expert.variant), title: "native expert profile", model: `${POLICY.nativePi.goModels.expert.providerID}/${POLICY.nativePi.goModels.expert.id}`, effort: POLICY.nativePi.goModels.expert.variant }),
    mapCell({ kind: "native", strength: level(POLICY.nativeFallback.claudeEffort.expert), title: "native subagent", model: claude.expert, effort: POLICY.nativeFallback.claudeEffort.expert }),
    mapCell({ kind: "native", strength: level(agy.tiers.expert.effort), title: agy.tiers.expert.name, model: agy.tiers.expert.model, effort: agy.tiers.expert.effort }),
  ].join("") + "</tr>")

  for (const tier of ["scout", "mechanic", "worker"] as const) {
    const agyTier = agy.tiers[tier]
    const bridge = POLICY.rootRoutes[tier][0]!
    const bridgeStrength = level(bridge.effort)
    rows.push(`<tr><th>${tier}</th>` + [
      mapCell({ kind: "native", strength: level(opencode.efforts[tier]), title: "native tier agent", model: opencode.model, effort: opencode.efforts[tier] }),
      mapCell({ kind: "native", strength: 1, title: "run_subagent", detail: tier === "scout" ? "subagent_explore (read-only)" : "subagent_general" }),
      mapCell({ kind: "native", strength: level(commandEffort(tier)), title: command[tier].name, model: command[tier].model, effort: commandEffort(tier) }),
      mapCell({ kind: "primary", strength: bridgeStrength, title: "bridge", model: modelOf(bridge), effort: bridge.effort, detail: `→ ${tier} ladder` }),
      mapCell({ kind: "primary", strength: bridgeStrength, title: "bridge", model: modelOf(bridge), effort: bridge.effort, detail: `→ ${tier} ladder` }),
      mapCell({ kind: "primary", strength: bridgeStrength, title: "bridge", model: modelOf(bridge), effort: bridge.effort, detail: `→ ${tier} ladder` }),
      mapCell({ kind: "native", strength: level(agyTier.effort), title: agyTier.name, model: agyTier.model, effort: agyTier.effort, detail: `selector ${agyTier.selector}; verify` }),
    ].join("") + "</tr>")
  }

  rows.push('<tr><th>quota exhaustion</th>' + [
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge" }),
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge" }),
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge", detail: "do not silently switch native models" }),
    mapCell({ kind: "undefined", strength: 1, title: "not defined", detail: "report rather than substitute" }),
    mapCell({ kind: "undefined", strength: 1, title: "not defined", detail: "report rather than substitute" }),
    mapCell({ kind: "native", strength: 2, title: "native subagents", models: POLICY.nativeFallback.tiers.map(tier => claude[tier as "scout"]), detail: "scout / mechanic / worker; same brief, worktree and scope" }),
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
        `<div><strong>${esc(executorLabel(route))}</strong> ${modelPill(modelOf(route))}</div>` +
        `<div class="meta">${effortChip(route.effort)}</div></div>`
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
