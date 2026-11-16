---
name: refactor-web-ui
description: "Use for /refactor-web-ui: redesign or substantially polish an existing web app through real-browser screenshots, independent visual critique, and iterative implementation."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Refactor Web UI

Web design is a product-quality engineering loop, not a one-pass CSS request. The deliverable is a coherent, readable daily-use interface that works across states and viewports; a passing build or hero screenshot is not enough.

No v0, paid design API, or image generation: a coding agent, a real browser, and an independent screenshot-capable critic suffice.

## Scope and ownership

- Read the repo's instructions, spec, frontend, styles, design system, fixtures, and browser tests first; the code and observed UI are the baseline.
- Redesign grants no permission to change execution contracts, accounts, infrastructure, or production data.
- This skill owns composition and visual refinement. Use refactor-dashboard-ui for dashboard signal, ranking, and history; refactor-css only when stylesheet ownership work is explicitly requested; jank-audit for audit-only requests. Do not import their unrelated constraints.
- Prefer `@laputa-systems/ui-dashboard` in products that use it; read the installed exports, styles, and peers first. Keep one source of tokens and themes.
- Add a shared-library primitive only for two plausible consumers, a stable contract, and isolated tests. No second design system, heavy dependency, or opportunistic rewrite.
- Preserve working transports, routing, state, keyboard behavior, and security semantics. A structural rewrite needs a parity gate before visual polish.

## Design thesis

Before styling, write a short brief:

1. The primary user, their top three jobs, and the decisions on the first screen.
2. The information hierarchy, primary action, read/write states, and recovery path.
3. Existing constraints: typography, spacing, color semantics, density, responsive behavior, themes.
4. At least two substantively different compositions as small rendered prototypes, and why one wins; prose mood boards prove nothing.

Borrow principles from strong products without copying branding. Favor calm hierarchy, consistent alignment, restrained color, readable long-form content. Remove what serves no user decision.

## Complete journeys, not a static frame

Cover the empty, busy, long, consequential, and broken states plus recovery; add loading, permission, search, keyboard, and touch variants where they apply.

- Keep context next to its action; do not hide essential provenance or failure behind hover.
- Label controls by native capability, including pending, unavailable, uncertain, and failed outcomes. Never fabricate success or add placeholder controls.
- Seed a failed and an interrupted case for every status indicator and check each screenshot shows it. Trace a wrong state to its client mapping or backend before restyling; file backend causes with their owner.
- Reconcile every count with its rows and the same count on other screens. A mismatch is S0, usually from a projection or classification, not markup.
- Preserve scroll position, focus, and drafts across updates and navigation. Narrow layouts keep their actions.
- Audit wrapping, line length, code blocks, and long identifiers. Never ellipsize primary information without a full-value path.
- Reserve color for state and emphasis. Avoid filler cards, decorative badges, over-boxing, gradients, and competing type scales.
- Keyboard operation, semantic names, visible focus, touch targets, contrast, and reduced motion are in scope.

## Preview and goldens (required)

Every designed UI ships `make preview`: the whole UI served locally on one canonical mock dataset that the integration tests also import. It covers every presented state, with distinct identities, realistic long content, and failed or interrupted outcomes. A golden test renders the same dataset and compares what each scenario shows (rows, states, controls, overflow), not pixels; updating a golden is a reviewed change.

## Visual loop

1. **Baseline.** Run `make preview`; capture before screenshots and record functional failures separately. Read `agent-browser skills get core` before driving it. Before restructuring, move browser-gate probes off class names, inline styles, and hard-coded colors onto test ids, ARIA state, and computed values.
2. **Build.** Implement in small slices with real content and state transitions, checking the browser after each. Delete superseded CSS and markup instead of stacking overrides.
3. **Independent critique.** Give rendered screenshots, the thesis, and the scenario to a screenshot-capable reviewer in a context that has not seen the builder's rationale. Require observed location, severity, and a concrete fix. Without such a critic, inspect the images yourself and say the review was not independent.
4. **Repair by cause.** Fix hierarchy, layout ownership, flow, and information structure before microstyling; rerun the affected journey.
5. **Repeat.** A major redesign gets three review/repair passes where the environment allows, at most five. Stop when no S0/S1 defects remain, the critical states pass two successive reviews, functional gates pass, and no `ACCEPTANCE: not met` verdict is outstanding; such a verdict is changed evidence, so the loop stays open until its findings are repaired or, when out of scope or disputed, filed as tickets, and a later review accepts. A review with no changed evidence is not a pass. A named fix left unmade and unfiled is an unfinished pass.

Severity: S0 unsafe or functionally impossible; S1 conspicuous or high-friction daily defect; S2 polish; S3 preference. S0–S2 need a screenshot location and reproduction.

## Evidence

Capture the primary journeys at 390, 768, 1024, and 1440 px (or project breakpoints), plus 320 px and 200% zoom. Cover each theme and reduced motion, with a fixed viewport height and the same seeded content before and after.

Check the built product: console and network errors; loading, failed, and offline feedback; no overflow, clipping, overlap, or broken scroll containers, proven by a scripted DOM check of every screen at each width (overflow, clipped text, intersecting boxes, empty states beside rows), which critics miss; keyboard traversal, focus return, screen-reader names; dialogs, menus, search, mobile back, submit and retry with no inert affordances; stability under polling updates; build, typecheck, browser tests, goldens, and asset-size deltas.

Label screenshots by scenario; keep a short defect ledger. An unviewed screenshot diff is not approval. List proof an absent environment prevents.

## Improve this skill from use

After each critique cycle record symptom, root cause, fix, and the check that would catch recurrence. Product-specific fixes stay in the product. Change this skill only for a transferable rule seen twice in one product or once in two products; prefer a checker or fixture over more prose. Re-read the edited skill and apply it to the ongoing work; commit skill changes separately with evidence. After a second product, delete rules that were overfit to the first.

**The test:** the important journeys pass in a real browser, before/after evidence at each breakpoint shows coherent improvement, independent critique finds no open S0/S1 defects, and behavioral checks pass. Missing independent review or environment proof stays explicitly open.

**Report:** chosen and rejected directions; preview and golden commands; scenarios reviewed; S0–S2 findings and fixes, and each open S2 fixed or filed; interaction, accessibility, and performance evidence; removed UI and CSS; skill revisions with evidence; commands run or unavailable; remaining limits and commit state.
