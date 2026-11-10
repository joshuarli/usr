---
name: refactor-dashboard-ui
description: "Apply when a dashboard or admin UI is overwhelming, hard to act on, or not yet built on @laputa-systems/ui-dashboard. Rebuild it around the reader's next action, using ~/d/stats as the conceptual benchmark. Skip single-component tweaks, chart-only work (use dataviz), and new dashboards with no existing UI to measure."
---

# Refactor Dashboard UI

A dashboard is working when a reader can say what to do next within seconds of opening it. Restyling leaves the overload in place, so change what the page says before how it looks; a wall of well-styled tables is still a wall.

## Requirements

- Build on `@laputa-systems/ui-dashboard`. Read the installed package's `README.md`, `dist/index.d.ts`, and `dist/styles.css` before writing markup. Never work from memory of its API.
- For a Solid app, use the components. For static or server-rendered HTML, use the CSS-only mode and emit the exact `ui-*` structure the README documents.
- When the project does not have the package yet, follow [installing the package](references/install.md).
- Write app CSS only for what the library lacks, and build it from `--ui-*` tokens. Add no second palette, type scale, or dark theme. Do not restyle `ui-*` internals.

## Learn from the benchmark

Read `~/d/stats/cloudflare/src/client/pages/` (start with `FleetPage.tsx` and `ProjectsPage.tsx`) and the screenshots in `~/d/stats/cloudflare/test/ui/*-snapshots/`. Copy the ideas, not its components, data, or table density: stats shows live metrics read across columns, not lists a reader works through.

- **Status strip first.** A few tiles carry one number, one label, and one line of context. Each tile links to its detail. Tint a tile only when it needs attention.
- **One panel, one question.** The panel title names the subject, and the panel meta states the basis in one line, such as the time window or what is excluded.
- **One entity per card or row.** Lead with the name. Show one strong value with at most one muted note beneath it.
- **Lists stay short.** Narrow with search and reveal the tail with "Show N more". Never print a long list inline. Show a count and put the list one click away.
- **Drill down for depth.** Summary rows link to a detail page or pane. Evidence, identifiers, and rarely used breakdowns live there.
- **Color means state.** Green, amber, and red appear only for state, always with a text label. Everything else stays in text tokens.
- **Empty states say what happens next.** Distinguish "nothing to do" from "not checked" and "could not read".

## Show only actionable signal

For each element, ask what the reader would change or decide after seeing it. If nothing, delete it. Collapsing it behind a disclosure is not a fix.

Counters are the exception: a number or small chart gives perspective at little visual cost.

- List only the entities that must change. Name the repositories off the preferred option, and count the compliant ones.
- Turn healthy, settled, accepted, and known-limit states into counts.
- Drop an item when acting on it would achieve nothing, such as a dependency whose removal drops no packages.
- Name who must act in visible text, not only in a tooltip.
- Remove full inventories and metadata from working pages. If a lookup is still needed, keep one surface for it behind search.
- Audit every page against this rule, not only the page someone complained about.

## Group and visualize

Tables are the last resort. Use one only on a lookup surface the reader searched for. If a working page is mostly a table, redo it.

Group first. Give each group a heading, a count, and a one-line note, and name it for the decision or outcome, such as "Fix now" or "Decide". Do not name groups after the analysis that produced them.

Then pick the form from the data's job. Follow the `dataviz` skill for marks, labels, and checks.

| The data | Use |
| --- | --- |
| A few headline numbers | Status strip of tiles |
| Things to act on | Cards in a grid: name, the change, where, next step |
| One task across many entities | One wide card with the command |
| Ranked impact or weight | Horizontal bars with the value at the tip |
| Parts of a whole across entities | Stacked bars on one shared scale, with one legend |
| Fleet health | Cards grouped into severity tiers, with healthy entities as a count |
| Adoption of competing options | One bar per option, then the names of only those who must move |
| Spread across an ordered scale, such as versions | Dots along a lane, sized by count, with the target marked |

Keep the page easy on the eyes:

- Put one or two facts on a card. Move identifiers such as advisory IDs and full repository lists to a tooltip or a disclosure.
- Set names in the sans face. Keep monospace for commands and hashes.
- Run the palette validator instead of trusting the library's series colors; where a series color fails, use status colors for severity and one hue or emphasis elsewhere.
- Print every charted value as text. Tooltips add detail but must not be the only way to read a value.

## Method

1. **Measure the overload.** Render real data and screenshot the main pages at 1440×900 and 390×844. Record page heights, table rows, and the number of items in each category. These numbers are the baseline for the final report.
2. **Name the reader's decisions.** List the few decisions the dashboard exists to support, then apply "Show only actionable signal" to every element against them.
3. **Fix accuracy before layout.** Find labels the data cannot support, such as "critical" with no severity field. Find exclusions the page claims but does not apply, and advice the data does not prove. Overload often hides these defects, and a cleaner page makes them more believable.
4. **Model actions as data.** In a pure, tested module separate from rendering, produce one record per action: what to do, why, where, and how. Merge duplicates so one change is one row. Rank by urgency, then by how much one change fixes. If the project has a command that performs the action, show that exact command.
5. **Organize by the reader's work.** Make the landing page the ranked action list under a status strip. Add an entity view ranked worst first, such as repositories or hosts. Group analysis pages under a quieter heading. Keep existing URLs when you can.
6. **Compose the pages.** Apply "Group and visualize" page by page. Isolate the `ui-*` markup and chart primitives in one small helper module so pages stay declarative and the vocabulary stays consistent. Escape every interpolated value in that module's callers. Keep client scripts to filtering, search, and reveal. Rows must stay visible when JavaScript fails.
7. **Delete what you replaced.** Remove dead renderers, old CSS, and charts that answer no decision. Tell the owner which recent additions you removed and why.
8. **Update tests and docs together.** Keep tests that pin behavior. Rewrite assertions that pin only the old markup vocabulary, and say which ones you rewrote. Add tests for action ranking, merging, and exclusions.

## Verify

Run the project's type, lint, and test commands, then rebuild the assets and confirm the staleness check passes. Open the real output in `agent-browser` at both viewports and confirm:

- The landing page's first screen shows the status strip and where the work is.
- Every listed item names a change or a decision, and healthy items appear only as counts.
- No working page is mostly tabular, and you have looked at every page as a full-page screenshot.
- The console has no errors, and the page does not overflow horizontally.
- Search, "Show N more", and deep links work, and the page also works from `file://` if the project promises that.
- Every tile count matches the rows it links to.

**Report:** the decisions the dashboard now supports, before and after measurements, accuracy defects fixed, what you removed, markup-coupled tests you rewrote, and what you did not verify.
