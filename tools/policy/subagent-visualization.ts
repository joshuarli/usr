import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { POLICY, type Route } from "../pi-subagent-bridge/src/policy.ts"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const DESTINATION = "docs/subagents.html"
const SOURCE = "tools/policy/subagent-visualization.ts"
const NOTICE = `<!-- Generated from ${SOURCE}; run make subagent-visualization. -->`

const TIERS = ["scout", "mechanic", "worker", "expert"] as const
type Tier = typeof TIERS[number]
type LaneKind = "native" | "primary" | "fallback" | "undefined" | "pilot"

const LANES: Record<LaneKind, { label: string; accent: string; fills: readonly string[] }> = {
  native: { label: "Native", accent: "#0e7a58", fills: ["#eaf7f1", "#cceede", "#a2ddc4", "#6cc6a3", "#39ad84"] },
  primary: { label: "Bridge primary", accent: "#2459c9", fills: ["#eef3ff", "#dbe6ff", "#b6ccfa", "#89acf4", "#5590ea"] },
  fallback: { label: "Bridge fallback", accent: "#b56a0a", fills: ["#fff6e8", "#ffe9c8", "#ffd49a", "#f8b964", "#ed9d33"] },
  undefined: { label: "Undefined", accent: "#8a97a8", fills: ["#f5f6f8", "#e9ecf1", "#d9dfe8", "#c5cedb", "#aab7c8"] },
  pilot: { label: "Pilot / opt-in", accent: "#7a3bb5", fills: ["#f6effc", "#e9daf8", "#d4b7ee", "#b98adf", "#9a5fd0"] },
}

const TIER_ACCENTS: Record<Tier, string> = {
  scout: "#0d8f86",
  mechanic: "#4f46c9",
  worker: "#d25a12",
  expert: "#8b32c2",
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
  return `--accent:${spec.accent};--fill:${spec.fills[index]};--pct:${strength * 20}%`
}

function meter(): string {
  return '<span class="meter" aria-hidden="true"></span>'
}

function tierBadge(tier: Tier): string {
  return `<span class="tier" style="--tone:${TIER_ACCENTS[tier]}">${tier}</span>`
}

function rankBadge(rank: number | undefined): string {
  if (rank === undefined) return ""
  return `<span class="rank ${rank === 1 ? "rank-primary" : "rank-fallback"}">P${rank}</span>`
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

function laneCard(option: LaneOptions): string {
  const spec = LANES[option.kind]
  return [
    `<div class="lane" style="${laneStyle(option.kind, option.strength)}">`,
    `<div class="lane-top">${option.tier ? tierBadge(option.tier) : ""}<span class="kind">${spec.label}</span>${rankBadge(option.rank)}</div>`,
    `<div class="lane-title">${esc(option.title)} ${meter()}</div>`,
    option.detail ? `<div class="lane-detail">${inline(option.detail)}</div>` : "",
    option.note ? `<div class="lane-note">${inline(option.note)}</div>` : "",
    "</div>",
  ].filter(Boolean).join("\n")
}

function mapCell(option: LaneOptions): string {
  return `<td class="cell" style="${laneStyle(option.kind, option.strength)}">` +
    `<div class="cell-top">${option.tier ? tierBadge(option.tier) : ""}<span class="kind">${LANES[option.kind].label}</span></div>` +
    `<div class="cell-title">${esc(option.title)} ${meter()}</div>` +
    (option.detail ? `<div class="cell-detail">${inline(option.detail)}</div>` : "") + "</td>"
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

function style(): string {
  return `<style>
:root{--bg:#f5f7fb;--ink:#172033;--muted:#56637a;--line:#dae1ed;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1320px;margin:0 auto;padding:28px 24px 64px}
.hero{background:linear-gradient(135deg,#101f3c 0%,#1d3f7b 60%,#2857a0 100%);color:#fff;border-radius:18px;padding:28px 32px;box-shadow:0 12px 32px #10204a26}
.hero h1{margin:0 0 6px;font-size:30px;letter-spacing:-.02em}
.hero p{margin:5px 0;max-width:105ch;color:#dbe6ff}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.88em;background:#edf1f8;border-radius:5px;padding:1px 5px;color:#1e3a6d}
.hero code{background:#ffffff24;color:#fff}
section{margin-top:26px}
h2{font-size:20px;margin:0 0 12px;display:flex;align-items:center;gap:10px}
h2::before{content:"";width:6px;height:22px;border-radius:3px;background:#2f6bd8}
h3{margin:0;font-size:15px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.muted{color:var(--muted)}
.legend-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.legend-item{background:#f9fbff;border:1px solid var(--line);border-radius:10px;padding:12px}
.legend-item strong{display:block;margin-bottom:7px;font-size:13px}
.swatch{width:18px;height:18px;border-radius:5px;border-left:6px solid var(--accent);background:var(--fill);display:inline-block;vertical-align:middle;margin-right:8px}
.scale{display:flex;gap:4px;align-items:flex-end;margin-top:4px}
.scale-step{width:38px;text-align:center}
.scale-step i{height:14px;border-radius:3px;display:block}
.scale-step em{font-size:10px;font-style:normal;color:var(--muted)}
.flow{display:flex;flex-direction:column;align-items:center;gap:9px}
.node{border-radius:10px;padding:11px 18px;font-weight:650;text-align:center;background:#eef3ff;border:1px solid #b6ccfa;color:#1b3f8c}
.node.native{background:#eaf7f1;border-color:#a2ddc4;color:#0c5f46}
.arrow{color:#98a5ba;font-weight:800;line-height:1}
.branches{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px;width:100%;margin-top:8px}
.branch{background:#f9fbff;border:1px solid var(--line);border-radius:12px;padding:14px}
.branch-head{font-weight:700;margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.branch-note{font-weight:400;font-size:12px;color:var(--muted)}
.lane-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:9px}
.lane{background:var(--fill);border:1px solid #0a1f3d12;border-left:6px solid var(--accent);border-radius:10px;padding:10px 12px}
.lane-top,.cell-top{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:5px}
.kind{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--accent);font-weight:800}
.rank{font-size:10px;font-weight:800;border-radius:999px;padding:1px 7px}
.rank-primary{background:var(--accent);color:#fff}
.rank-fallback{background:#ffffffaa;border:1px solid var(--accent);color:var(--accent)}
.tier{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#fff;background:var(--tone);border-radius:999px;padding:1px 7px}
.lane-title,.cell-title{font-weight:650;font-size:13.5px}
.lane-detail,.cell-detail{font-size:12px;color:#334059;margin-top:3px;word-break:break-word}
.lane-note{font-size:11.5px;color:var(--muted);margin-top:4px;font-style:italic}
.meter{display:inline-block;width:44px;height:6px;border-radius:3px;background:#ffffffb8;overflow:hidden;vertical-align:middle;margin-left:4px}
.meter::after{content:"";display:block;height:100%;width:var(--pct);background:var(--accent)}
.table-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:#fff}
table{border-collapse:collapse;width:100%;min-width:1180px}
th,td{border-bottom:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}
thead th{background:#eef3fb;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#40506b}
tbody th{background:#f7f9fd;font-size:13px;width:120px}
.cell{background:var(--fill);border-left:5px solid var(--accent);border-radius:8px;min-width:155px}
.tier-row{display:grid;grid-template-columns:118px 1fr;gap:12px;align-items:start;padding:13px 0;border-top:1px solid var(--line)}
.tier-row:first-of-type{border-top:0}
.chain{display:flex;flex-wrap:wrap;align-items:stretch;gap:8px}
.chain-arrow{align-self:center;color:#9aa7bb;font-weight:800}
.route{flex:1 1 175px;min-width:165px;background:var(--fill);border:1px solid #0a1f3d12;border-left:6px solid var(--accent);border-radius:10px;padding:9px 11px}
.route .lane-title{font-size:12.5px}
.rules li{margin:8px 0;padding-left:2px}
footer{margin-top:26px;font-size:12.5px;color:var(--muted)}
a{color:#2157bd}
@media (max-width:720px){main{padding:16px 12px 40px}.hero{padding:20px}.tier-row{grid-template-columns:1fr}}
</style>`
}

function legend(): string {
  const kinds = (Object.keys(LANES) as LaneKind[]).map(kind =>
    `<div class="legend-item"><strong><span class="swatch" style="--accent:${LANES[kind].accent};--fill:${LANES[kind].fills[2]}"></span>${LANES[kind].label}</strong>` +
    `<span class="muted">Lane kind — the hue and left border tell you where the assignment runs.</span></div>`).join("\n")
  const scale = ["low", "medium", "high", "xhigh", "max"].map((name, index) =>
    `<span class="scale-step"><i style="background:${LANES.primary.fills[index]}"></i><em>${name}</em></span>`).join("")
  return [
    '<section id="legend">',
    '<h2>Reading the lanes</h2>',
    '<div class="panel"><div class="legend-grid">',
    kinds,
    `<div class="legend-item"><strong>Strength / model effort</strong><span class="muted">Fill shade and the small bar grow with model effort.</span><div class="scale">${scale}</div></div>`,
    '<div class="legend-item"><strong>Route rank</strong><span class="muted"><span class="rank rank-primary">P1</span> is the primary route; <span class="rank rank-fallback">P2</span> and later are ordered fallbacks, tried only before edits.</span></div>',
    '<div class="legend-item"><strong>Tier badges</strong><span class="muted">scout (read-only) → mechanic → worker → expert. Expert is terminal and native everywhere; no `god` tier exists.</span></div>',
    '</div></div>',
    '</section>',
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
    nativeLanes.push({ kind: "native", strength: level(COMMAND_EFFORT(tier)), tier, title: "Command Code native agent", detail: `${command[tier].name} · ${command[tier].model}, ${COMMAND_EFFORT(tier)}` })
    const agyTier = agy.tiers[tier]
    nativeLanes.push({ kind: "native", strength: level(agyTier.effort), tier, title: "Antigravity native agent", detail: `${agyTier.name} → ${agyTier.model} · selector ${agyTier.selector}; verify actual model and effort` })
  }
  nativeLanes.push({ kind: "native", strength: 1, tier: "scout", title: "Devin subagent_explore", detail: "read-only inventory" })
  nativeLanes.push({ kind: "native", strength: 1, title: "Devin subagent_general", detail: "writes; no per-tier pin" })
  nativeLanes.push({ kind: "pilot", strength: 2, tier: "worker", title: "HY4-medium worker pilot", detail: `${command.pilot.name} · ${command.pilot.model}, ${command.pilot.effort} — explicit comparison only` })

  const bridgeRoutes = POLICY.rootRoutes.worker.map((route, index) => ({
    kind: index === 0 ? "primary" as const : "fallback" as const,
    strength: level(route.effort),
    title: `${executorLabel(route)} · ${modelOf(route)}`,
    rank: index + 1,
  }))

  const quotaLanes = POLICY.nativeFallback.tiers.map(tier => ({
    kind: "native" as const,
    strength: level(POLICY.nativeFallback.claudeModels[tier as "scout"]),
    title: "Claude Code native fallback",
    detail: `${tier} → ${POLICY.nativeFallback.claudeModels[tier as "scout"]}`,
  }))

  return [
    '<section id="decision">',
    '<h2>Decision graph</h2>',
    '<div class="panel flow">',
    '<div class="node">Parent agent wants a coding subagent</div>',
    '<div class="arrow">↓</div>',
    '<div class="node">Which tier?</div>',
    '<div class="arrow">↓</div>',
    '<div class="branches">',
    '<div class="branch"><div class="branch-head">' + tierBadge("expert") + 'Expert — native in every harness</div><div class="lane-list">',
    expertLanes.map(laneCard).join("\n"),
    '</div></div>',
    '<div class="branch"><div class="branch-head">scout / mechanic / worker <span class="branch-note">top-level native parents never use the bridge</span></div><div class="lane-list">',
    nativeLanes.map(laneCard).join("\n"),
    '</div><div class="flow" style="margin-top:12px">',
    '<div class="node native">Otherwise → pi-subagent-bridge: worker_model_check → worker_start</div>',
    '<div class="arrow">↓</div>',
    '<div class="lane" style="' + laneStyle("primary", 3) + '"><div class="lane-top"><span class="kind">Bridge primary</span>' + rankBadge(1) + '</div><div class="lane-title">Admitted ordered plan per tier ' + meter() + '</div><div class="lane-detail">' + inline("command-code → ordered Pi fallback → codex; `worker` ladder: " + bridgeRoutes.map(route => modelOf(POLICY.rootRoutes.worker[route.rank! - 1]!)).join(" → ")) + '</div></div>',
    '<div class="arrow">↓</div>',
    '<div class="arrow">first route available? yes → admitted · no → next route, only before edits</div>',
    '<div class="node native">watch / worker_status — parent verifies proof and diff independently</div>',
    '<div class="arrow">↓</div>',
    '<div class="branch-note">no approved backend (quota or exhausted) →</div>',
    '<div class="lane" style="' + laneStyle("native", 3) + '"><div class="lane-top"><span class="kind">Native</span></div><div class="lane-title">Tier-matched native subagents (Claude Code) ' + meter() + '</div><div class="lane-detail">same brief, worktree, scope; independent parent review; return to bridge when capacity recovers</div></div>',
    '</div></div>',
    '</div></div>',
    '<div class="muted" style="margin-top:10px">Quota fallback pins: ' + quotaLanes.map(lane => inline(lane.detail!)).join(" · ") + '</div>',
    '</section>',
  ].join("\n")
}

function COMMAND_EFFORT(tier: "scout" | "mechanic" | "worker"): string {
  const pin = POLICY.commandNative[tier]
  return "effort" in pin ? pin.effort : "medium"
}

function laneMap(): string {
  const opencode = POLICY.opencode
  const agy = POLICY.antigravityDirect
  const command = POLICY.commandNative
  const claude = POLICY.nativeFallback.claudeModels
  const head = ["Assignment", "OpenCode (top-level)", "Devin (top-level)", "Command Code (top-level)", "Codex", "Pi", "Claude Code", "Antigravity CLI"]
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
    const bridgeDetail = `bridge → ${tier} ladder (see below)`
    rows.push(`<tr><th>${tier}</th>` + [
      mapCell({ kind: "native", strength: level(opencode.efforts[tier]), title: "native tier agent", detail: `${opencode.model}#${opencode.efforts[tier]}` }),
      mapCell({ kind: "native", strength: 1, title: "run_subagent", detail: tier === "scout" ? "subagent_explore (read-only)" : "subagent_general" }),
      mapCell({ kind: "native", strength: level(COMMAND_EFFORT(tier)), title: command[tier].name, detail: `${command[tier].model}, ${COMMAND_EFFORT(tier)}` }),
      mapCell({ kind: "primary", strength: level(POLICY.rootRoutes[tier][0]!.effort), title: "bridge", detail: bridgeDetail }),
      mapCell({ kind: "primary", strength: level(POLICY.rootRoutes[tier][0]!.effort), title: "bridge", detail: bridgeDetail }),
      mapCell({ kind: "primary", strength: level(POLICY.rootRoutes[tier][0]!.effort), title: "bridge", detail: bridgeDetail }),
      mapCell({ kind: "native", strength: level(agyTier.effort), title: agyTier.name, detail: `${agyTier.model} · selector ${agyTier.selector}; verify` }),
    ].join("") + "</tr>")
  }

  rows.push('<tr><th>quota exhaustion<br><span class="branch-note">scout / mechanic / worker</span></th>' + [
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge" }),
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge" }),
    mapCell({ kind: "undefined", strength: 1, title: "never uses the bridge", detail: "do not silently switch native models" }),
    mapCell({ kind: "undefined", strength: 1, title: "not defined", detail: "report rather than substitute" }),
    mapCell({ kind: "undefined", strength: 1, title: "not defined", detail: "report rather than substitute" }),
    mapCell({ kind: "native", strength: 2, title: "native subagents", detail: POLICY.nativeFallback.tiers.map(tier => `${tier} ${claude[tier as "scout"]}`).join(" · ") + "; same brief, worktree and scope" }),
    mapCell({ kind: "undefined", strength: 1, title: "never uses bridge", detail: "block mismatched model" }),
  ].join("") + "</tr>")

  return [
    '<section id="lane-map">',
    '<h2>Lane map</h2>',
    '<div class="table-scroll"><table><thead><tr>' + head.map(header => `<th>${header}</th>`).join("") + '</tr></thead><tbody>',
    rows.join("\n"),
    '</tbody></table></div>',
    '</section>',
  ].join("\n")
}

function bridgeRoutes(): string {
  const rows = POLICY.tiers.map(tier => {
    const routes = POLICY.rootRoutes[tier]
    const chain = routes.map((route, index) => {
      const kind = index === 0 ? "primary" : "fallback"
      const strength = level(route.effort)
      return [
        `<div class="route" style="${laneStyle(kind, strength)}">`,
        `<div class="lane-top">${tierBadge(tier)}<span class="kind">${LANES[kind].label}</span>${rankBadge(index + 1)}</div>`,
        `<div class="lane-title">${esc(executorLabel(route))} · ${esc(modelOf(route))} ${meter()}</div>`,
        `<div class="lane-detail">effort ${esc(route.effort)}</div>`,
        "</div>",
      ].join("\n")
    }).join('<div class="chain-arrow">→</div>')
    return `<div class="tier-row"><h3>${tier}</h3><div class="chain">${chain}</div></div>`
  }).join("\n")
  return [
    '<section id="bridge-routes">',
    '<h2>The bridge, per tier</h2>',
    '<div class="panel">' + rows + '</div>',
    '<p class="muted">A task failure, rejected acceptance check or scope change is not a provider failure: an admitted route is never replaced after edits.</p>',
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
  return '<section id="hard-rules"><h2>Hard rules</h2><div class="panel"><ol class="rules">' +
    rules.map(rule => `<li>${inline(rule)}</li>`).join("\n") +
    '</ol></div></section>'
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
    '<header class="hero">',
    "<h1>Subagent architecture</h1>",
    `<p>Decision graph for delegating a coding subagent. Tiers: <code>scout</code> (read-only: no <code>bash</code>, <code>edit</code> or <code>write</code>), <code>mechanic</code>, <code>worker</code>, <code>expert</code>. There is no <code>god</code> tier, and the ${banned} families are prohibited everywhere, including every effort variant.</p>`,
    '<p>Color encodes lane kind; shade and the bar encode model effort; the <code>P</code> badge encodes route rank. Expert is native everywhere; the bridge serves only <code>scout</code>/<code>mechanic</code>/<code>worker</code> in harnesses without a native top-level exception.</p>',
    "</header>",
    legend(),
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
