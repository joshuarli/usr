---
name: refactor-web-ui
description: "Redesign or substantially polish an existing web app through real-browser screenshots, independent visual critique, and iterative implementation. Use for chat/workbench UIs, consoles, developer tools, and broad cross-page visual-quality work. Skip isolated CSS cleanup (refactor-css), dashboard data/trend restructuring (refactor-dashboard-ui), and read-only UX audits (jank-audit)."
---

# Refactor Web UI

Treat web design as a product-quality engineering loop, not a one-pass CSS request. The deliverable is a coherent, readable, enjoyable daily-use interface with working interactions across states and viewports. A passing build, attractive hero screenshot, or generically styled component collection is not enough.

This method is provider-independent: do not require v0, a paid design API, image generation, or any particular model vendor. A capable coding agent, real browser, existing component system, and independent screenshot-capable critic are sufficient.

## Scope and ownership

- First read the target repository's instructions, product spec, real workflows, current frontend and styles, dependencies, assets, design system, fixtures, and browser tests. Distinguish implemented behavior from proposals; use the code and observed UI as the baseline.
- Honor the request's edit, deploy, and publication authority. Redesign does not grant permission to change native execution contracts, real accounts, infrastructure, or production data. Use seeded local fixtures and safe test environments.
- This skill owns end-to-end composition and visual refinement. Use refactor-dashboard-ui for dashboard-specific signal, ranking, and historical data; refactor-css only when explicitly requested for stylesheet ownership work; jank-audit for audit-only requests. Do not import their unrelated constraints.
- Prefer @laputa-systems/ui-dashboard for products that already use it or explicitly target it, but inspect the installed package's exports, styles, peer dependencies, and current documentation first. Preserve one source of tokens and themes. Do not assume components described in a backlog exist.
- A missing reusable primitive may belong in the shared library only if at least two consumers can plausibly use it, its contract is stable, and it can be tested in isolation. Otherwise keep it application-local. Avoid a second design system, large component dependencies, gratuitous frameworks, or an opportunistic rewrite.
- Choose implementation complexity after profiling the current UI. Preserve working transports, routing, state, keyboard behavior, and security semantics. Refactors need parity gates before visual polish.

## Define a design thesis

Before styling, write a short internal brief identifying:

1. The primary user, their top three jobs, and the decisions visible on the first screen.
2. The main information hierarchy, primary action, read/write states, and recovery path.
3. Existing style constraints: typography, spacing, color semantics, density, responsive behavior, and light/dark support.
4. At least two credible, substantively different composition directions, with a reason to prefer one. For major redesigns, render small actual prototypes or representative layouts; prose-only mood boards do not prove visual quality.

References are input, not a template. Borrow the useful interaction principles from strong products without reproducing branding, arbitrarily copying patterns, or shipping generic SaaS chrome. Favor calm editorial hierarchy, purposeful whitespace, consistent alignment, restrained color, readable long-form content, and clear affordances. Treat empty space and information density as deliberate tradeoffs. Remove interface elements that do not help a real user decision.

## Work on complete journeys, not a pretty static frame

Choose representative real tasks and seeded states from the target product. At minimum cover its entry/empty state, busy everyday state, long or dense content, a consequential action, error or disconnected state, and recovery. Add loading, permission, search, keyboard, and touch variants when applicable.

- Keep context near the action it explains; don't bury essential provenance or failure behind a hover tooltip.
- Make control labels describe native capability, including pending, unavailable, uncertain, and failed outcomes. Never fabricate success or install placeholder controls to complete a layout.
- Preserve meaningful scroll position and focus across updates and navigation; do not auto-scroll when the reader is studying history. A responsive layout must retain actions instead of simply hiding them.
- Text must fit naturally: audit clipping, wrapping, line lengths, code blocks, long identifiers, locale variants, and unusual content. Never use ellipsis to conceal primary information; truncate only where progressive disclosure is intentional and a full-value path exists.
- Reserve color for state and emphasis. Avoid dashboard-shaped filler, decorative badges, over-boxing, gratuitous gradients/shadows, competing type scales, and unconstrained animations.
- Support keyboard operation, semantic labels, visible focus, usable touch targets, contrast, and reduced motion. Accessibility is part of this skill's scope regardless of the narrower scope of a standalone CSS refactor.

## Visual loop (mandatory for a substantial redesign)

1. **Baseline.** Run the existing local app using documented fixture commands; take before screenshots and record initial functional failures separately. Use agent-browser: read the installed agent-browser skill and then `agent-browser skills get core` before nontrivial commands. Do not pretend a code skim is a browser inspection.
2. **Design + implementation.** Build a coherent first pass with real content and real state transitions. Remove superseded CSS/markup rather than stacking overrides. Prefer small slices with a runnable browser check after each.
3. **Independent critique.** Capture actual rendered screenshots and pass them to a screenshot-capable reviewer in an isolated context that has not justified the implementation. Give it the design thesis, scenario, and screenshot; require observed evidence, severity, and a concrete suggested fix, not generic aesthetic adjectives. If no independent multimodal critic is available, say so; do your own image inspection but do not label it independent.
4. **Repair by cause.** Triage defects by user impact; fix hierarchy, layout ownership, interaction flow, and information structure before microstyling. Re-run the affected journey after each substantive change.
5. **Repeat.** Complete three substantive review/repair passes for a major redesign when the environment supports it, with at most five passes before reporting diminishing returns or blockers. Stop only when no S0/S1 defects remain, the same critical states have passed two successive reviews, and the relevant functional gates pass. A review with no changed evidence is not a new pass.

The visual reviewer should assess hierarchy, composition, consistency, density, text rhythm, color/contrast, affordance, interactive states, responsive reflow, and overall restraint. Classify S0 as unsafe or functionally impossible, S1 as conspicuous or high-friction daily-use defects, S2 as polish defects, and S3 as subjective preferences. Require screenshot location and reproduction for S0–S2.

## Evidence matrix

For the primary journeys capture 390, 768, 1024, and 1440 px widths (or more suitable project-specific breakpoints); add 320 px and 200% zoom for overflow/accessibility probes. Cover both themes only if supported, and any native reduced-motion setting. Use a deterministic viewport height and seeded content. Compare before and after at equivalent states, not different demo data.

Check the built product, not only isolated component previews:

- Browser console and network errors; failed, loading, and offline feedback.
- No unexpected horizontal overflow, clipped text, overlapping controls, or broken scroll containers.
- Real keyboard traversal, return focus, shortcuts that do not steal input, and readable screen-reader names.
- Navigation, dialogs, menus, search/filter, mobile back, form submit, errors and retries; no inert affordances.
- Layout stability with variable-length text and streaming/polling updates; selection, cursor, and draft preservation.
- Build, typecheck, tests, relevant end-to-end/browser tests, and performance/asset-size deltas. Do not trade correctness for appearance.
- Capture screenshot artifacts with scenario labels and a short defect ledger. An unviewed screenshot diff is not approval.

When a required environment is absent, preserve honest evidence from available checks and list the exact missing proof. Don't assert a visual pass from screenshots you did not inspect.

## Improve this skill from use

Treat each completed redesign as a field experiment. After every critique cycle, record: symptom, observed screenshot/state, root cause, fix, and the regression check that would detect recurrence. Apply product-specific fixes in the product repository.

Update this shared skill in usr only for a transferable rule supported by repeated evidence (the same failure twice in a product or once in two distinct products). Prefer improving a checker or fixture rather than expanding prose. Keep application-specific design choices out of the generic skill. Re-read the edited skill and apply the new rule to the ongoing product before calling the iteration complete. Commit skill updates separately from product code when possible, with a short evidence-based explanation.

After using it on a second product, compare outcomes and remove rules that were overfit to the first. This should become a smaller, sharper reusable method over time, not a diary or a growing pile of exceptions.

**The test:** the important real journeys pass in the browser, before/after evidence demonstrates a deliberate and coherent improvement at responsive sizes, independent screenshot critique finds no unresolved S0/S1 defects, and behavioral checks still pass. Any missing independent review or environment-specific proof stays explicitly open.

**Report:** chosen direction and rejected alternatives; screenshots/scenarios reviewed; S0–S2 findings and fixes; interaction, accessibility and performance evidence; removed UI/CSS; skill revisions made and their supporting evidence; exact commands and tests run or unavailable; remaining limitations and commit state.
