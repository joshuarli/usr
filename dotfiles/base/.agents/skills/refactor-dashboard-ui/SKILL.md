---
name: refactor-dashboard-ui
description: "Apply when a dashboard or admin UI is overwhelming, hard to act on, or not yet built on @laputa-systems/ui-dashboard. Rebuild it around the reader's next action, using ~/d/stats as the conceptual benchmark. Skip single-component tweaks, chart-only work (use dataviz), and new dashboards with no existing UI to measure."
---

# Refactor Dashboard UI

A dashboard is working when a reader can say within seconds what to do next, how things are trending, and where they are heading. Change what the page says before how it looks: a wall of well-styled tables is still a wall, and point-in-time numbers without history are boring even when tidy.

## Requirements

- Build on `@laputa-systems/ui-dashboard`. Read the installed `README.md`, `dist/index.d.ts`, and `dist/styles.css` first, never memory. Solid apps use the components; static HTML emits the documented `ui-*` structure.
- When the project does not have the package yet, follow [installing the package](references/install.md).
- Write app CSS only for what the library lacks, and build it from `--ui-*` tokens. Add no second palette, type scale, or dark theme. Do not restyle `ui-*` internals; set documented input tokens instead, such as `--ui-side-width`.
- Draw charts as small app SVG primitives; add no chart library for a few static series.

## Learn from the benchmark

Read `~/d/stats/cloudflare/src/client/pages/` (start with `FleetPage.tsx` and `ProjectsPage.tsx`) and the screenshots in `~/d/stats/cloudflare/test/ui/*-snapshots/` (`.webp`: use `sips`). Copy the ideas, not its components, data, or table density: stats shows live metrics read across columns, not lists a reader works through.

- **Status strip first.** Tiles with an uppercase label, a status dot and word when state matters, one value, one line of context, and a sparkline. Each links to its detail.
- **Trends and a time window.** Chart every quantity with history, project forward when the data supports it, and drive all history charts from one stats-style time window. Details: [owner preferences](references/owner-preferences.md#trends-and-time).
- **One panel, one question.** The title names the subject; the meta states the basis in a few words.
- **One entity per card or row.** Lead with the name. Show one strong value with at most one muted note beneath it.
- **Lists stay short.** Narrow with search, reveal the tail with "Show N more", and never print a long list inline.
- **Drill down for depth.** Evidence, identifiers, and rare breakdowns live on a linked detail page or pane.
- **Color means state.** Green, amber, and red appear only for state, always with a text label. Everything else stays in text tokens.
- **Empty states say what happens next:** "nothing to do", "not checked", or "could not read".

## Show only actionable signal

For each element, ask what the reader would change or decide after seeing it. If nothing, delete it. Collapsing it behind a disclosure is not a fix.

Counters are the exception: a number or small chart adds perspective cheaply.

- List only the entities that must change; turn healthy, settled, and known-limit states into counts.
- Drop items whose fix would achieve nothing.
- Name who must act in visible text, not only in a tooltip.
- Remove full inventories and metadata from working pages; keep any needed lookup behind search.
- Audit every page, not just the reported one.

## Group and visualize

Tables are the last resort. Use one only on a lookup surface the reader searched for. If a working page is mostly a table, redo it.

Group first. Give each group a heading, a count, and a one-line note, named for the decision or outcome ("Fix now", "Decide"), not the analysis behind it.

Then pick the form from the data's job. Follow the `dataviz` skill for marks, labels, and checks.

| The data | Use |
| --- | --- |
| A few headline numbers | Status strip of tiles, each with a sparkline when history exists |
| Values over time | Line or area chart under the shared time window |
| Composition over time | Stacked areas, with a dashed reference line such as money put in |
| Where a value is heading | Actual line, then dashed scenario lines past a "now" divider, endpoint values in the legend |
| Things to act on | Ranked hairline rows: status dot and name, the change, the amount, when |
| Ranked impact or weight | Horizontal bars with the value at the tip |
| Parts of a whole across entities | Stacked bars on one shared scale, with one legend |
| Adoption of competing options | One bar per option, then the names of only those who must move |
| Spread across an ordered scale, such as versions | Dots along a lane, sized by count, with the target marked |

Keep the page quiet: the owner wants minimal and tasteful ([visual restraint](references/owner-preferences.md#visual-restraint)). Clipped or awkwardly wrapped text is a defect ([text must fit](references/owner-preferences.md#text-must-fit)).

- One or two facts per row; identifiers go in a tooltip or disclosure.
- Run the `dataviz` palette validator rather than trusting the library's series colors.
- Print every charted value as text. Tooltips add detail but must not be the only way to read a value.

## Method

1. **Measure the overload.** Screenshot the main pages with real data at 1440×900 and 390×844, and record page heights, table rows, and item counts as the baseline.
2. **Name the reader's decisions.** List the few decisions the dashboard exists to support, including "how is this trending" and "where is it heading", then apply "Show only actionable signal" to every element against them. Find the dated series in the project that can answer the trend questions before designing the page.
3. **Fix accuracy before layout.** Find labels the data cannot support, exclusions claimed but not applied, and advice the data does not prove. A cleaner page makes these defects more believable.
4. **Model actions and series as data.** In pure, tested modules separate from rendering, produce one record per action: what to do, why, where, and how. Merge duplicates so one change is one row. Rank by urgency, then by how much one change fixes. If the project has a command that performs the action, show that exact command. Derive time series and time-window logic the same way ([details](references/owner-preferences.md#modules-and-checks)).
5. **Organize by the reader's work.** Land on the status strip and ranked actions, then trends. Add an entity view ranked worst first. Keep existing URLs when you can.
6. **Compose the pages.** Apply "Group and visualize" page by page. Isolate the `ui-*` markup and chart primitives in one small helper module so pages stay declarative and the vocabulary stays consistent. Escape every interpolated value in that module's callers. Keep client scripts to filtering, search, reveal, and the time window.
7. **Delete what you replaced:** dead renderers, old CSS, and charts that answer no decision. Tell the owner what you removed and why.
8. **Update tests and docs together.** Keep behavior tests, rewrite assertions that pin only old markup (and say which), and test ranking, merging, and exclusions.

## Verify

Run the project's checks and rebuild. In `agent-browser` at both viewports, confirm:

- The landing page's first screen shows the status strip and where the work is.
- Every listed item names a change or a decision, and healthy items appear only as counts.
- No working page is mostly tabular; you viewed every page as a full-page screenshot.
- No console errors and no horizontal overflow.
- Search, "Show N more", and deep links work, and the page also works from `file://` if the project promises that.
- The time window and text-fit checks in [owner preferences](references/owner-preferences.md#modules-and-checks) pass.
- Every tile count matches the rows it links to.

**Report:** decisions supported, before/after measurements, accuracy fixes, removals, rewritten markup tests, and what you did not verify.
