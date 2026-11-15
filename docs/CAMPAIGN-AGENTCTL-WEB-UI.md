# Agentctl web UI: autonomous redesign and reusable design skill

**Status:** executed 2026-11-14 for agentctl. The redesigned client, its evidence, and the defect ledger are in agentctl `docs/ui/redesign.md` (commits `63fce07`, `ef8d9d8`, `a1f6124`). The skill baseline is usr `ed9b3eb`; its evidence-backed revision follows it. Follow-ups ACTL-22, ACTL-25 and ACTL-26 were fixed afterwards, and agentctl gained `make preview` and `make test-ui-goldens` on one canonical dataset. Still unproven: screen-reader, tailnet, and native-harness paths. The transfer to stats, stuff, and discover is deferred as USR-73.

**Launch prompt:** Execute this document unattended in the current repositories. Begin by auditing and, if evidence warrants, refining `dotfiles/base/.agents/skills/refactor-web-ui/SKILL.md` in `joshuarli/usr`. Apply it to the actual `joshuarli/agentctl` frontend, repeatedly test and visually critique the rendered result, and refine the skill from generalizable failures while implementing. Use no v0 or other paid design-generation service. Stop at a verified, polished, functional interface with an evidence-backed handoff. Do not silently broaden to other application repositories.

## Outcome and authority

The user wants a genuinely beautiful, minimal, fast, robust, keyboard-first web app for controlling remote coding agents. They do not want to guide dozens of visual decisions or identify obvious papercuts. The product should feel like a mature, integrated daily-use workbench; the design method should subsequently work for stats, stuff, and discover.

On a separately authorized launch, execution may edit and commit to `joshuarli/agentctl` and the reusable skill in `joshuarli/usr`, and may make narrowly scoped, tested reusable component improvements to `laputa-systems/laputa-ui-dashboard` when justified. Keep each repository's commits independent; integrate only verified results. This handoff's creation does not itself authorize deployment or an additional redesign of stats, stuff, or discover.

Do not access live provider sessions, credentials, paid quotas, real tailnet hosts, production data, or infrastructure. No live deployment, hosting migration, authentication policy change, or runtime/provider adapter rewrite. Use existing local fixture environments and safe branch/worktree practices. Do not introduce v0, commercial design MCPs, SaaS screenshots, or paid AI-generation dependencies. Locally available coding and multimodal agents plus browser tooling are the intended route.

## The first two repositories are real, not hypotheticals

- `usr` contains `dotfiles/base/.agents/skills/refactor-dashboard-ui/SKILL.md` (domain-specific dashboard/data presentation and textual fit checks), `refactor-css` (explicit-only CSS ownership rules), `agent-browser` (real browser driver), `jank-audit` (read-only product-friction audits), and `do`/`orchestrate` (execution/handoff rules). Reuse them within their own scopes. The new `refactor-web-ui` is the visual/design loop and must remain useful beyond chat.
- `agentctl` uses `apps/web/public/index.html`, `style.css`, and a hand-built Solid-backed DOM client in `app.js`. Its hub and its OpenOrange deployment paths serve static web assets. Read the current implementation before choosing migration tactics; documentation calling it a 'static Solid web client' does not mean it is already TSX.
- `agentctl/docs/inbox-and-interface.md` specifies the intended information architecture, message semantics, correlated permissions, and capability-aware composer. Preserve those contracts while improving appearance.
- `agentctl` already has `make dev`, `make check`, `make test-ui`, `make test-ui-polish`, and `make release-check`. Examine the actual commands and fixture assumptions. Existing screenshots under `docs/ui/screenshots/` are a baseline, not visual approval.
- `laputa-ui-dashboard` is the preferred shared design system. As last checked, published package 0.11.0 has CSS-only exports and optional Solid components, with Solid 2 release-candidate peers. Agentctl currently carries Solid 1, so resolve peer compatibility before importing components. Consult current package exports/types and docs rather than assuming all catalog plans are shipped.

Treat all version observations above as orientation, not pinned truth: inspect current heads, installed packages, and real runtime before implementing.

## Why the current interface needs a rethink

The current agentctl UI has a coherent protocol/fixture foundation but a weaker visual surface: awkward three-pane proportions, low conversation hierarchy, over-prominent permission cards, too little typographic differentiation among users/assistant/tools, and inconsistent use of space. Fix composition and task hierarchy first. A new palette or CSS-only facelift is insufficient.

Target principles, not a copy of another brand: Linear-like disciplined navigation and inbox, Claude-like comfortable long-form conversation, developer-tool-level execution provenance and controls. One quiet workbench, not a stack of dashboard cards or an imitation chat bubble app.

## Sequence and acceptance

### Slice 0 — Draft/verify the method first

- Inspect the newly seeded `refactor-web-ui` skill, existing dashboard UI and CSS skills, agent-browser guidance, repo instruction precedence, and usr skill validation/check tooling.
- Refine the skill only where a demonstrable contradiction, lack of scope coverage, or execution ambiguity exists. The initial version must be runnable without v0, installable without special connectors, and generic enough to apply to dashboard applications and non-dashboard applications.
- Verify the skill's metadata/frontmatter and auto-invocation description against usr conventions and run the relevant skill/check command(s). Confirm its behavior complements instead of overriding dashboard-specific and CSS-only skills.
- Commit a usable initial skill in usr before beginning frontend redesign. Record its commit so that later improvements can be compared to a real baseline. The seed in this campaign doc may already satisfy the initial draft; verify rather than duplicate.

**Acceptance:** another coding agent can discover when to use `refactor-web-ui` and carry out its visual loop from the skill alone. No v0 requirement.

### Slice 1 — Establish a truthful product baseline

- Read agentctl's architecture, interface contract, current frontend, auth, AHP hub proxy, attention projection, and browser tests. Trace the native action lifecycle end-to-end; keep uncertain/pending/success/failed distinct.
- Launch the documented local fixture only. Capture actual before screenshots at 390, 768, 1024 and 1440 px, covering empty, busy, transcript-heavy, permission, error/disconnect, and mobile states. Record console failures, clipped text, focus/scroll behavior, keyboard interactions, and rough size/performance data.
- Identify no more than 5 key user journeys and their first-screen decisions; list the interaction invariants that cannot regress. Test baseline behavior and distinguish known failures from environment gaps.
- Read the current Laputa library API, styles, examples, fixtures, dependency graph, themes, and build requirements; record which shipped primitives already solve agentctl needs, which are CSS-only, and genuine gaps.

**Acceptance:** reproducible fixture invocation, labeled baseline captures and a short design thesis tied to observed daily use.

### Slice 2 — Design without paid generation

- Explore three substantively different compositions using local HTML/CSS prototypes or small prototype branches rendered in a browser, with seeded realistic content. They must differ in information hierarchy, proportions, and workflow emphasis, not only accent color.
- Inspect all three visually. Use a distinct, screenshot-capable critic (a second model/subagent/context if available), supplying the brief and screenshots but not the builder's rationale. Score comprehensibility, attention prioritization, readability, information density, precision, responsiveness, keyboard/touch affordance, and aesthetic restraint. Require critique grounded in screenshot details; no vibes-only praise.
- Select one direction autonomously and write a concise choice rationale. Do not seek repeated owner preferences or ask the user to pick among minor variants. Borrow ideas from Linear/Claude/Cursor where helpful without using their code or copying branding.
- Test a representative transcript, permission request and mobile layout before committing to the selected architecture.

**Acceptance:** real renderings of the options, an independent comparison when reviewer capability exists, and a single recorded composition decision.

### Slice 3 — Build the structural frontend

- Default toward a well-structured compiled Solid/TSX client with typed presentational components and the actual Laputa UI package, rather than extending the monolithic `app.js` and override-driven `style.css`. Keep the decision conditional on proving compatibility and low-risk static deployment.
- First make the build pipeline consume the same static hub/OpenOrange asset contract, paths, authentication cookies, AHP WebSocket proxy, and shipped entrypoints as before; prove this with a small fixture gate before rewriting the main UI.
- Evaluate Solid 2 peer upgrade compatibility, not simply assume a published prerelease is safe. If upgrading is risky or blocked, use the Laputa CSS-only exports and a component structure compatible with the existing runtime; document the tradeoff and keep visual scope moving.
- Separate session/protocol state from rendering; preserve request IDs, idempotence, action receipts, unread/acknowledgment distinctions, and capability-aware controls. Keep important tests anchored to behavior instead of specific old DOM shapes.
- Build the inbox hierarchy, conversation document, tool activity disclosures, workspace context, permission/question controls, and composer. Integrate deliberate empty, loading, offline, failed, long-history and narrow-screen states.
- If the shared library lacks a reusable primitive, implement it there only if its behavior and API are independent of agentctl and tested in isolation. Otherwise keep it local and avoid framework bloat.
- Remove replaced renderers, styles, compatibility shims and selectors after parity; do not ship two frontends or a museum of overrides.

**Acceptance:** end-to-end native fixture actions retain their observed state semantics through the new UI; the built app is attractive and functional at all primary breakpoints, with no hidden dead-end controls.

### Slice 4 — Iterative critique and skill improvement

Use `refactor-web-ui` as the controlling method, not as passive documentation.

Perform at least three substantive screen-review/repair passes where tooling supports it; bound the process at five before explicit diminishing-returns or environment reporting. For each pass:

1. Recreate the same deterministic scenario/viewport set from the baseline, including meaningful permission, long transcript, offline, and mobile states.
2. Inspect actual screenshots with a multimodal critic in independent context. Check typography, line length, whitespace, density, alignment, layering, scrolling, focus visibility, hover/touch states, visual hierarchy, contrast, state messaging and perceived polish. Capture findings at specific screen locations and classify severity.
3. Fix root causes, not last-minute CSS overrides. Prefer removing noise over adding chrome. Rerun the relevant real-world browser journey; collect new screenshots and evaluate the delta.
4. Record a compact symptom → cause → fix → proof row. If the same class of error repeats twice in agentctl, or is independently seen in another project, update the generic skill in usr. Otherwise keep the design decision local to agentctl. Re-read the revised skill and apply the rule to the ongoing implementation.
5. Check that independent critique has not introduced regression or aesthetic churn. Do not count another model's textual advice as a visual pass unless it actually inspected the rendered captures.

If an independent screenshot-capable critic is unavailable, use direct screenshot inspection and existing browser controls, but report the missing independent proof. Do not invent reviews or repeat screenshot snapshots merely to meet a pass count.

**Acceptance:** no unresolved S0/S1 visual/UX defects; the primary scenarios survive two consecutive evidence-backed reviews; every general-purpose skill amendment has an observed cause and a reproducible check.

### Slice 5 — Functional, accessibility, and performance gates

Run `make check`, `make test-ui`, `make test-ui-polish`, and `make release-check` where supported; inspect what they actually verify. Preserve deterministic fixture control, permission correlation, command palette, keyboard navigation, focus/draft through polls, and responsive behavior. Do not erase failing tests by refreshing screenshots without image review.

Use the installed agent-browser skill to verify keyboard and touch journeys, 320/390/768/1024/1440 px, 200% zoom, light/dark themes where supported, and reduced-motion preference. Inspect scroll anchors for streaming/long transcripts, code horizontal scrolling, dynamic updates, dense lists, and reopening conversations after navigation.

Audit keyboard reachable controls, accessible names/roles, meaningful focus order, visible focus, contrast, live announcements, semantic headings, mobile back, screen-reader paths where tooling exists, errors/retries, and no horizontal clipping. Test the resulting *built* assets through the hub, not only source-level component demos.

Measure bundle size, interaction smoothness, startup time and memory against the baseline with comparable fixture data and method. A substantial regression needs analysis and mitigation, not a blanket exemption. Record baseline failure and unexecutable environment-specific gates as such; do not claim screen-reader or tailnet qualification without it.

**Acceptance:** all available relevant functional tests pass, no new critical accessibility defects, no unexplained major resource regressions, and specific missing proofs listed.

### Slice 6 — Land, verify and close

- Review diffs for dead code, duplicate CSS, invented features, unbounded logs, wrong state labels, unsafe HTML, leaked secrets, and newly introduced dependencies.
- Commit verified reusable components in Laputa first (when genuinely needed), then the agentctl consumer, and evidence-backed skill updates in usr. Observe each repo's explicit publishing/release rules; never assume a git commit updates a registry package.
- Recheck after integration; use actual commit SHAs and stable screenshot paths in the handoff. Keep before/after evidence adjacent to scenarios and name what materially improved. Preserve existing auth/runtime boundaries.
- Report: chosen direction, exact frontend architecture, screenshots reviewed, independent findings and fixes, component reuse and deletions, measured performance, exact test outcomes, missing environment proof, and skill changes proven reusable.
- The success condition is daily-use quality, not an attractive empty conversation screenshot. Do not silently start applying the skill to stats, stuff or discover.

## Transfer after agentctl

Once the first redesign is accepted, use the same `refactor-web-ui` skill on other existing apps by separate request:

- **stats:** apply domain-specific `refactor-dashboard-ui` for metrics/decisions/trends, then the generic skill for navigation, visual consistency, mobile density, interaction states, and end-to-end screenshot critique. Do not strip away useful analytical charts.
- **stuff:** use the generic skill for dependency visualization controls, catalog/forge workflows, and dense developer-tool navigation. Preserve domain-specific canvas rendering and performance invariants.
- **discover:** use the generic skill for reading, searching, research results, evidence/provenance hierarchy, and mobile comprehension. Do not invent new data relationships solely to fill a screen.

Use evidence from at least a second distinct product to decide whether a rule belongs in the shared skill, the Laputa component library, or a product-specific test. Consolidate or delete rules that turn out to be agentctl-specific; avoid a sprawling universal design checklist.

## Stop/park conditions

Keep work moving under reasonable choices. Do not ask for visual taste decisions that the design brief, evidence, or rubric already resolves. Park only when blocked by unavailable credentials/tooling, a breaking product contract outside this redesign, or a required deployment/publishing approval. Record the exact blocker and continue independent work. Never simulate browser proof, review, tests, or deployment.

**Done means:** a redesigned agentctl web frontend checked in with equivalent or better functionality and clear visual improvement across real states; a usable, tested reusable skill in usr that has been exercised and sharpened using the actual work; and a concise evidence-backed handoff.
