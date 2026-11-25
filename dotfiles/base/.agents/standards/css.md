+++
name = "css"
summary = "Plain CSS gives every layout fact one owner: tokens defined once, one file per component with its responsive rules, containers owning symmetric spacing, no overrides, and stable controls."

[[trigger]]
paths = ["*.css", "!*.min.css"]

[examples]
match = ["web/src/components/card.css", "styles/tokens.css"]
skip = ["dist/app.min.css", "web/src/App.tsx", "README.md"]
+++

# CSS

Refactor a frontend's plain CSS so every layout fact has one owner. Competing spacing systems, compensating paddings, override rules patching a base rule, duplicate selectors, repeated magic numbers, and append-order stylesheets are the defects; a lint or reformat alone does not finish actionable work. Preserve rendered output unless a visual change is authorized or is a deliberate snap to the scale. A justified no-op is valid; make no edits to look busy.

Keep these decisions: plain CSS with custom properties owns styling; Vite owns bundling; no preprocessor, CSS-in-JS, or utility framework is introduced. Tokens are defined once. Each component owns one file, with its responsive rules inline. Containers own spacing symmetrically.

Owner preferences override generic best practice. Accessibility is out of scope: do not add or audit ARIA, focus order, contrast, reduced-motion, or keyboard support, and do not spend effort on it; leave existing accessibility attributes intact (ARIA attributes already serving as state hooks may stay). There is no dark mode: no `prefers-color-scheme`, no theme switching, no dual token sets; `color-scheme` stays light.

## Code

### Tokens

Define each token once, in one file loaded first, as custom properties on `:root`. Components reference tokens; they never restate the value.

- Spacing: a 4px grid with a 2px half step (`2, 4, 8, 12, 16, 24, 32, ...`). Name by step, not by use.
- Control size: one height for buttons, inputs, and icon controls, so rows align.
- Inset and gutter: the padding inside a container and the gap between containers, each defined once.
- Radii, type scale (size and line-height together), and a z-index scale with named layers. No literal `z-index` in components.
- Breakpoints: one list. Custom properties cannot appear in `@media` conditions, so keep the list in one documented-by-name place (a single file or build-time substitution) and have every component use those exact values.

A value that appears three times is a missing token. A value that is off-scale by 1 to 2px is a snap, not a new token; record it for the report. Do not add a token nothing uses.

### Ownership

One owner per fact: one file per component, one definition per selector, one rule per property of that selector.

- The container owns its padding and the gap between its children, symmetrically. A header with `12px` above and `0` below plus a body with `6px` is two owners compensating; replace with one inset and one gap.
- No component compensates for another's padding. If a child needs a different edge, the container's contract is wrong; fix the container.
- Space siblings with `gap` or a stack (`> * + *` or a flex/grid column), not per-child `margin-bottom`. Last-child special cases are a sign of per-child margins.
- A trailing element (notice, footer) is spaced by its container's gap, not by a margin that depends on what precedes it.
- A flush child (table under a header) is handled by the container choosing its gap or inset once, not by a negative margin or a zeroed sibling.

### Selectors and state

- Delete overrides instead of adding specificity. A rule such as `.parent > .card .head { ... }` that patches `.head` is merged into `.head`, or the variation becomes a modifier on the component.
- No `!important`. No id selectors. One class per concept; do not give two classes the same meaning.
- Pick one state-hook style per project and use it everywhere: `data-` attributes, ARIA attributes already in use as state, or modifier classes. Do not mix them for the same state.
- Descendant selectors reach at most one level into a component's own markup. Do not style another component's internals; give it a modifier or a token.
- Never define one selector in two places. If a base and a variant both exist, the variant holds only the differing properties.

### Controls

- A control that can appear in a header or row reserves its space in every state. Never mount or unmount it; disable it, or hide it with `visibility: hidden` or `opacity: 0`, so siblings do not move.
- The rightmost control is the stable anchor: its right edge is identical across state changes and across sibling components that share the layout.
- Hover-only affordances live behind `@media (hover: hover)`. Without hover they are either always visible or absent, and they still reserve their space so nothing leaves a hole beside the anchor.

### Layout

- Grid for two-dimensional structure, flex for one-dimensional rows. Do not simulate a grid with nested flex and fixed widths.
- Prefer intrinsic sizing (`min-content`, `auto`, `minmax`, `aspect-ratio`) over fixed heights. A fixed height needs a stated reason in the name or token.
- Variable-height cards in columns: state the tradeoff and pick one.
  - Grid rows align cards but leave gaps under shorter cards.
  - CSS multi-column packs tightly but reflows cards between columns when any height changes.
  - Explicit column stacks (one flex column per column, items assigned in markup) are deterministic: a height change moves nothing sideways.
  Prefer explicit stacks when collapse or expand must not reshuffle neighbors; otherwise ask the owner if the choice is not evident.
- Constrain overflow at the container (`min-width: 0`, `overflow` on the scroller), not by shrinking content.

### Rhythm and context-specific overrides

Give the page container a column `gap` for vertical rhythm. A zero-height sentinel or observer node inside that container still receives a gap; cancel it with a negative margin equal to the gap on that node alone. Inside CSS multi-column layout, `gap` does not space vertically, so cards keep a per-card margin there and trailing margins at a column end are truncated; give a following full-span element its own top margin.

When an override applies in every real use of a component, such as a chart that only ever renders inside one card grid, fold it into the base rule instead of keeping a context selector. Delete components and classes that markup no longer references; the dead-selector sweep finds them from both sides.

### Responsive rules

A component's media queries sit inside its own file, next to the rules they change. Global media-query blocks that patch components are deleted and redistributed. Prefer fluid layout and container-owned reflow to adding a breakpoint; a breakpoint that only fixes one component's overflow belongs to that component.

### Ids

DOM ids are unique across the whole app, including repeated and conditionally rendered widgets. Anchors, `aria-controls`, and persisted UI state key off them; a duplicate makes two components share state. Prefer classes for styling; audit ids that feed persisted state and migrate stored keys if an id changes.

### Comments and tools

Write no CSS comments except a genuine external-platform quirk stated as the constraint. Do not install, configure, or run formatters. Do not touch CI.

### Verify

Run the affected builds, type checks, and tests. Add invariant geometry tests for the defects fixed, run the goldens against the baseline, and check the result in a real browser at the widths under Geometry invariants. Run the dead-selector sweep both ways with `rg`. Separate baseline failures from regressions.

Review the final diff and rescan for remaining overrides, duplicate selectors, magic numbers, and orphaned classes. Stale goldens, skipped viewports, and unrun browser checks are not passes; state any missing proof as a specific gap.

#### Baseline

Before editing, run the project's existing layout tests and screenshot goldens and record the results. Later failures are regressions only against this baseline.


#### Geometry invariants

Test the layout facts a user would notice, with Playwright and `getBoundingClientRect`, not pixel snapshots. Write the test for each symptom first, watch it fail on the old CSS, then fix.

- Control x-positions are identical before and after each state change (collapse, expand, fullscreen, loading, empty).
- A collapsed container has symmetric vertical padding: space above the title equals space below it.
- The last control in each header shares the same right edge across all components in a column or row.
- Spacing between siblings, and between the last card and a trailing element, equals the gap token.
- DOM ids are unique: collect `[id]` and assert no duplicates.
- No horizontal overflow at 320, 390, 768, and 1440 px: `document.documentElement.scrollWidth <= innerWidth`.

Compare against tokens by reading the computed custom property, not a hard-coded number, so the test survives a scale change. Keep these tests; they are the regression record.


#### Goldens

Run the existing screenshot goldens before (baseline) and after. A visually neutral refactor keeps them passing unchanged. When values were deliberately snapped to the scale, regenerate goldens only after viewing the new images, desktop and mobile, and confirm each difference is an intended snap. Report which goldens changed and why. Never regenerate to make a failure pass without looking.


#### Real browser

Open the built app in a real browser, not only the test runner. At each width above, exercise the affected states: collapse and expand, hover and no-hover, the trailing and flush cases, and any control that appears or disappears. Watch for controls shifting, holes beside the anchor, and clipped or doubled spacing.


#### Dead-selector sweep

Run it in both directions with `rg`.

- Every class removed from CSS has no remaining users in TSX, HTML, or JS, including dynamically built class names and string concatenation.
- Every class used in markup is defined in a stylesheet, or is deliberately a hook with no styles; list the latter.
- Every custom property referenced is defined, and every defined token is referenced.
- No `!important`, id selector, or duplicate selector definition remains: search for each.

An unmatched dynamic class name is a gap to inspect, not a pass.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

### Inventory

Read active instructions, working changes, every stylesheet and its import order, the bundler entry, the markup (TSX/HTML/JS) that uses each class, persisted UI state keyed by id, and existing screenshot and layout tests. Preserve unrelated edits.

Establish baseline results: run the existing goldens and layout tests before editing, or record them unavailable. For each batch, name the fact it consolidates, the invariant it preserves, and the smallest check that would show a regression.

Inventory first: repeated literal values, selectors defined more than once, rules that exist only to patch another rule, `!important`, id selectors, per-child margins, media queries living outside their component, and fixed heights. Map each visible symptom to the competing owners that cause it, not to the single rule that happens to win.

### Passes

1. Define tokens once: spacing scale, control size, inset and gutter, radii, type scale, z-index scale, breakpoints. Replace repeated literals with them; snap near-misses to the scale deliberately and list each.
2. Split by component: one file per component, its responsive rules inline, imported from one place. Move component fixes out of global media-query blocks and shared sheets.
3. Fix ownership: the container sets padding and gap symmetrically; children set none for each other. Replace per-child `margin-bottom` with `gap` or a stack. Remove every compensating padding.
4. Delete overrides: merge each patch back into its base rule, delete duplicate definitions, and drop `!important` and id selectors. Lower specificity; never raise it.
5. Stabilize controls: reserve their space, hide with `visibility` or `opacity` instead of unmounting, and keep the rightmost control as the anchor. Put hover-only affordances behind `@media (hover: hover)`.
6. Choose layout deliberately: grid for two-dimensional structure, flex for one-dimensional rows; prefer intrinsic sizing to fixed heights. Make DOM ids unique across the app and fix duplicates in markup and in persisted state.
7. Update markup, tests, and docs together. Complete the requested scope, not the first easy file.

**Report:** tokens added; files split; overrides deleted; selectors removed; intentional visual changes and which goldens changed and why.
