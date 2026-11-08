---
name: refactor-dashboard-ui
description: "Apply when a dashboard or admin UI is overwhelming, hard to act on, or not yet built on @laputa-systems/ui-dashboard. Rebuild it around the reader's next action, using ~/d/stats as the conceptual benchmark. Skip single-component tweaks, chart-only work (use dataviz), and new dashboards with no existing UI to measure."
---

# Refactor Dashboard UI

A dashboard is working when a reader can say what to do next within seconds of opening it. An exhaustive report is not a dashboard, however clean it looks. Restyling alone leaves the overload in place, so change what the page says before you change how it looks.

## Requirements

- Build on `@laputa-systems/ui-dashboard`. Read the installed package's `README.md`, `dist/index.d.ts`, and `dist/styles.css` before writing markup. Never work from memory of its API.
- For a Solid app, use the components. For static or server-rendered HTML, use the CSS-only mode and emit the exact `ui-*` structure the README documents.
- If the render path cannot run Node, add the package as a pinned dev dependency, copy `dist/styles.css` and `dist/tokens.css` into the source tree at build time, and make the existing asset staleness check cover them. `styles.css` imports `./tokens.css`, so keep both in one directory.
- Route the scope in `.npmrc`: `@laputa-systems:registry=https://npm.17166969.xyz/current/`.
- Write app CSS only for what the library lacks, and build it from `--ui-*` tokens. Add no second palette, type scale, or dark theme. Do not restyle `ui-*` internals.

## Learn from the benchmark

Read `~/d/stats/cloudflare/src/client/pages/` (start with `FleetPage.tsx` and `ProjectsPage.tsx`) and the screenshots in `~/d/stats/cloudflare/test/ui/*-snapshots/`. Copy these ideas, not its components or data:

- **Status strip first.** A few tiles carry one number, one label, and one line of context. Each tile links to its detail. Tint a tile only when it needs attention.
- **One panel, one question.** The panel title names the subject, and the panel meta states the basis in one line, such as the time window or what is excluded.
- **One entity per row.** The first cell holds a status dot, the name, and a muted identifier. Other cells hold one strong value with at most one muted note beneath it.
- **Lists stay short.** Filter with chips that show counts, narrow with search, and reveal the tail with "Show N more". Never print a long list inline. Show a count and put the list one click away.
- **Drill down for depth.** Summary rows link to a detail page or pane. Evidence, identifiers, and rarely used breakdowns live there.
- **Color means state.** Green, amber, and red appear only for state, always with a text label. Everything else stays in text tokens.
- **Empty states say what happens next.** Distinguish "nothing to do" from "not checked" and "could not read".

## Method

1. **Measure the overload.** Render real data and screenshot the main pages at 1440×900 and 390×844. Record page heights, table rows, and the number of items in each category. These numbers are the baseline for the final report.
2. **Name the reader's decisions.** List the few decisions the dashboard exists to support. For each element, name the decision it changes. Delete it or move it behind a drill-down if it changes none.
3. **Fix accuracy before layout.** Find labels the data cannot support, such as "critical" with no severity field. Find exclusions the page claims but does not apply, and advice the data does not prove. Overload often hides these defects, and a cleaner page makes them more believable.
4. **Model actions as data.** In a pure, tested module separate from rendering, produce one record per action: what to do, why, where, and how. Merge duplicates so one change is one row. Rank by urgency, then by how much one change fixes. If the project has a command that performs the action, show that exact command.
5. **Organize by the reader's work.** Make the landing page the ranked action list under a status strip. Add an entity view ranked worst first, such as repositories or hosts. Group analysis pages under a quieter heading. Keep existing URLs when you can.
6. **Compose the pages.** Isolate the `ui-*` markup in one small helper module so pages stay declarative and the vocabulary stays consistent. Escape every interpolated value in that module's callers. Keep client scripts to filtering, search, and reveal. Rows must stay visible when JavaScript fails.
7. **Delete what you replaced.** Remove dead renderers, old CSS, and charts that answer no decision. Tell the owner which recent additions you removed and why.
8. **Update tests and docs together.** Keep tests that pin behavior. Rewrite assertions that pin only the old markup vocabulary, and say which ones you rewrote. Add tests for action ranking, merging, and exclusions.

## Verify

Run the project's type, lint, and test commands, then rebuild the assets and confirm the staleness check passes. Open the real output in `agent-browser` at both viewports and confirm:

- The landing page's first screen shows the status strip and the top actions.
- The console has no errors, and the page does not overflow horizontally.
- Filters, search, "Show N more", and deep links work, and the page also works from `file://` if the project promises that.
- Every tile count matches the rows it links to.

**Report:** the decisions the dashboard now supports, before and after measurements, accuracy defects fixed, what you removed, markup-coupled tests you rewrote, and what you did not verify.
