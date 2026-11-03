# Verification: invariants, goldens, real browser

## Contents

- [Baseline](#baseline)
- [Geometry invariants](#geometry-invariants)
- [Goldens](#goldens)
- [Real browser](#real-browser)
- [Dead-selector sweep](#dead-selector-sweep)

## Baseline

Before editing, run the project's existing layout tests and screenshot goldens and record the results. Later failures are regressions only against this baseline.

## Geometry invariants

Test the layout facts a user would notice, with Playwright and `getBoundingClientRect`, not pixel snapshots. Write the test for each symptom first, watch it fail on the old CSS, then fix.

- Control x-positions are identical before and after each state change (collapse, expand, fullscreen, loading, empty).
- A collapsed container has symmetric vertical padding: space above the title equals space below it.
- The last control in each header shares the same right edge across all components in a column or row.
- Spacing between siblings, and between the last card and a trailing element, equals the gap token.
- DOM ids are unique: collect `[id]` and assert no duplicates.
- No horizontal overflow at 320, 390, 768, and 1440 px: `document.documentElement.scrollWidth <= innerWidth`.

Compare against tokens by reading the computed custom property, not a hard-coded number, so the test survives a scale change. Keep these tests; they are the regression record.

## Goldens

Run the existing screenshot goldens before (baseline) and after. A visually neutral refactor keeps them passing unchanged. When values were deliberately snapped to the scale, regenerate goldens only after viewing the new images, desktop and mobile, and confirm each difference is an intended snap. Report which goldens changed and why. Never regenerate to make a failure pass without looking.

## Real browser

Open the built app in a real browser, not only the test runner. At each width above, exercise the affected states: collapse and expand, hover and no-hover, the trailing and flush cases, and any control that appears or disappears. Watch for controls shifting, holes beside the anchor, and clipped or doubled spacing.

## Dead-selector sweep

Run it in both directions with `rg`.

- Every class removed from CSS has no remaining users in TSX, HTML, or JS, including dynamically built class names and string concatenation.
- Every class used in markup is defined in a stylesheet, or is deliberately a hook with no styles; list the latter.
- Every custom property referenced is defined, and every defined token is referenced.
- No `!important`, id selector, or duplicate selector definition remains: search for each.

An unmatched dynamic class name is a gap to inspect, not a pass.
