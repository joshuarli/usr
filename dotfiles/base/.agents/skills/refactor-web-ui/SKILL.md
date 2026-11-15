---
name: refactor-web-ui
description: "Redesign or substantially polish an existing web app through real-browser screenshots, independent visual critique, and iterative implementation. Use for chat/workbench UIs, consoles, developer tools, and broad cross-page visual-quality work. Skip isolated CSS cleanup (refactor-css), dashboard data/trend restructuring (refactor-dashboard-ui), and read-only UX audits (jank-audit)."
---

# Refactor Web UI

Treat web design as a product-quality engineering loop, not a one-pass CSS request. The deliverable is a coherent, readable daily-use interface whose interactions work across states and viewports. A passing build, an attractive hero screenshot, or a collection of generically styled components is not enough.

The method is provider-independent: no v0, paid design API, image generation, or particular model vendor. A coding agent, a real browser, the existing component system, and an independent screenshot-capable critic suffice.

## Scope and ownership

- Read the target repository's instructions, product spec, real workflows, current frontend and styles, dependencies, design system, fixtures, and browser tests first. The code and observed UI are the baseline, not proposals.
- Redesign does not grant permission to change native execution contracts, real accounts, infrastructure, or production data. Use seeded local fixtures.
- This skill owns composition and visual refinement. Use refactor-dashboard-ui for dashboard signal, ranking, and history; refactor-css only when stylesheet ownership work is explicitly requested; jank-audit for audit-only requests. Do not import their unrelated constraints.
- Prefer `@laputa-systems/ui-dashboard` where the product uses or targets it. Read the installed package's exports, styles, and peer dependencies first; do not assume backlog components exist. Keep one source of tokens and themes.
- Add a primitive to the shared library only when two consumers can plausibly use it, its contract is stable, and it is tested in isolation. Otherwise keep it local. No second design system, heavy component dependency, or opportunistic framework rewrite.
- Preserve working transports, routing, state, keyboard behavior, and security semantics. A structural rewrite needs a parity gate before visual polish.

## Design thesis

Before styling, write a short brief:

1. The primary user, their top three jobs, and the decisions visible on the first screen.
2. The information hierarchy, primary action, read/write states, and recovery path.
3. Existing constraints: typography, spacing, color semantics, density, responsive behavior, themes.
4. At least two substantively different compositions, rendered as small real prototypes for a major redesign, and the reason to prefer one. Prose mood boards prove nothing visual.

Borrow interaction principles from strong products without copying branding or shipping generic SaaS chrome. Favor calm hierarchy, purposeful whitespace, consistent alignment, restrained color, and readable long-form content. Remove elements that serve no real user decision.

## Complete journeys, not a static frame

Cover the product's empty state, busy everyday state, long or dense content, a consequential action, an error or disconnected state, and recovery; add loading, permission, search, keyboard, and touch variants where they apply.

- Keep context next to the action it explains; do not hide essential provenance or failure behind hover.
- Label controls by native capability, including pending, unavailable, uncertain, and failed outcomes. Never fabricate success or add placeholder controls.
- Preserve scroll position, focus, and drafts across updates and navigation; do not auto-scroll a reader studying history. Narrow layouts keep their actions.
- Audit clipping, wrapping, line length, code blocks, and long identifiers. Never ellipsize primary information without a full-value path.
- Reserve color for state and emphasis. Avoid filler cards, decorative badges, over-boxing, gradients, competing type scales, and unconstrained animation.
- Keyboard operation, semantic names, visible focus, touch targets, contrast, and reduced motion are in scope.

## Visual loop

1. **Baseline.** Run the app with its documented fixture commands; capture before screenshots and record functional failures separately. Read the agent-browser skill and `agent-browser skills get core` before driving it. A code skim is not a browser inspection.
2. **Build.** Implement a coherent pass with real content and state transitions in small slices, with a browser check after each. Delete superseded CSS and markup instead of stacking overrides.
3. **Independent critique.** Give rendered screenshots, the thesis, and the scenario to a screenshot-capable reviewer in a context that has not seen the builder's rationale. Require observed location, severity, and a concrete fix. Without such a critic, inspect the images yourself and say the review was not independent.
4. **Repair by cause.** Fix hierarchy, layout ownership, flow, and information structure before microstyling; rerun the affected journey.
5. **Repeat.** A major redesign gets three review/repair passes where the environment allows, at most five. Stop when no S0/S1 defects remain, the critical states pass two successive reviews, and functional gates pass. A review with no changed evidence is not a pass.

Severity: S0 unsafe or functionally impossible; S1 conspicuous or high-friction daily-use defect; S2 polish; S3 preference. S0–S2 need a screenshot location and reproduction.

## Evidence

Capture the primary journeys at 390, 768, 1024, and 1440 px (or project breakpoints), plus 320 px and 200% zoom for overflow. Cover each supported theme and reduced motion. Use a fixed viewport height and the same seeded content before and after.

Check the built product, not component previews:

- Console and network errors; loading, failed, and offline feedback.
- No horizontal overflow, clipped text, overlapping controls, or broken scroll containers.
- Keyboard traversal, focus return, shortcuts that do not steal input, screen-reader names.
- Dialogs, menus, search, mobile back, submit, errors and retries; no inert affordances.
- Stability under variable text and streaming or polling updates.
- Build, typecheck, browser tests, and performance and asset-size deltas.

Label screenshots by scenario and keep a short defect ledger. An unviewed screenshot diff is not approval. When an environment is absent, list the exact missing proof.

## Improve this skill from use

After each critique cycle record symptom, state, root cause, fix, and the check that would catch recurrence. Product-specific fixes stay in the product repository. Change this skill only for a transferable rule seen twice in one product or once in two products; prefer a checker or fixture over more prose. Re-read the edited skill and apply it to the ongoing work, and commit skill changes separately with their evidence. After a second product, delete rules that were overfit to the first.

**The test:** the important journeys pass in a real browser, before/after evidence at each breakpoint shows a coherent improvement, independent critique finds no open S0/S1 defects, and behavioral checks pass. Missing independent review or environment proof stays explicitly open.

**Report:** chosen direction and rejected alternatives; scenarios reviewed; S0–S2 findings and fixes; interaction, accessibility, and performance evidence; removed UI and CSS; skill revisions and their evidence; commands run or unavailable; remaining limits and commit state.
