---
name: refactor-css
description: "Refactor plain CSS in a web frontend into design tokens, one file per component, and symmetric container-owned spacing. Use only when explicitly requested by name or for fixing layout jank, spacing drift, or override-patched stylesheets."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Refactor CSS

Refactor a frontend's plain CSS so every layout fact has one owner. Competing spacing systems, compensating paddings, override rules patching a base rule, duplicate selectors, repeated magic numbers, and append-order stylesheets are the defects; a lint or reformat alone does not finish actionable work. Preserve rendered output unless a visual change is authorized or is a deliberate snap to the scale. A justified no-op is valid; make no edits to look busy.

Use the requested paths; an unqualified invocation covers the repository's first-party stylesheets and the markup that uses them. Exclude vendored and generated CSS. A refactor instruction does not authorize deploying.

## Chosen decisions

Keep these decisions: plain CSS with custom properties owns styling; Vite owns bundling; no preprocessor, CSS-in-JS, or utility framework is introduced. Tokens are defined once. Each component owns one file, with its responsive rules inline. Containers own spacing symmetrically.

Owner preferences override generic best practice. Accessibility is out of scope: do not add or audit ARIA, focus order, contrast, reduced-motion, or keyboard support, and do not spend effort on it; leave existing accessibility attributes intact (ARIA attributes already serving as state hooks may stay). There is no dark mode: no `prefers-color-scheme`, no theme switching, no dual token sets; `color-scheme` stays light.

Read the references before editing:

- [Design system](references/design-system.md): always; tokens, ownership, components, layout, controls, and state hooks.
- [Verification](references/verification.md): always; geometry tests, goldens, real-browser checks, and the dead-selector sweep.

## Inspect and decide

Read active instructions, working changes, every stylesheet and its import order, the bundler entry, the markup (TSX/HTML/JS) that uses each class, persisted UI state keyed by id, and existing screenshot and layout tests. Preserve unrelated edits.

Inventory first: repeated literal values, selectors defined more than once, rules that exist only to patch another rule, `!important`, id selectors, per-child margins, media queries living outside their component, and fixed heights. Map each visible symptom to the competing owners that cause it, not to the single rule that happens to win.

Establish baseline results: run the existing goldens and layout tests before editing, or record them unavailable. For each batch, name the fact it consolidates, the invariant it preserves, and the smallest check that would show a regression.

## Refactor in coherent passes

1. Define tokens once: spacing scale, control size, inset and gutter, radii, type scale, z-index scale, breakpoints. Replace repeated literals with them; snap near-misses to the scale deliberately and list each.
2. Split by component: one file per component, its responsive rules inline, imported from one place. Move component fixes out of global media-query blocks and shared sheets.
3. Fix ownership: the container sets padding and gap symmetrically; children set none for each other. Replace per-child `margin-bottom` with `gap` or a stack. Remove every compensating padding.
4. Delete overrides: merge each patch back into its base rule, delete duplicate definitions, and drop `!important` and id selectors. Lower specificity; never raise it.
5. Stabilize controls: reserve their space, hide with `visibility` or `opacity` instead of unmounting, and keep the rightmost control as the anchor. Put hover-only affordances behind `@media (hover: hover)`.
6. Choose layout deliberately: grid for two-dimensional structure, flex for one-dimensional rows; prefer intrinsic sizing to fixed heights. Make DOM ids unique across the app and fix duplicates in markup and in persisted state.
7. Update markup, tests, and docs together. Complete the requested scope, not the first easy file.

Write no CSS comments except a genuine external-platform quirk stated as the constraint. Do not install, configure, or run formatters. Do not touch CI.

## Verify and finish

Run the affected builds, type checks, and tests. Add invariant geometry tests for the defects fixed, run the goldens against the baseline, and check the result in a real browser at the widths in the verification reference. Run the dead-selector sweep both ways with `rg`. Separate baseline failures from regressions.

Review the final diff and rescan for remaining overrides, duplicate selectors, magic numbers, and orphaned classes. Stale goldens, skipped viewports, and unrun browser checks are not passes; state any missing proof as a specific gap.

**The test:** the build and tests pass on the final diff, geometry invariants hold at every width, goldens pass or were regenerated only after viewing the new images, and no override, duplicate selector, or unowned magic number remains.

**Report:** tokens added; files split; overrides deleted; selectors removed; intentional visual changes and which goldens changed and why; checks run and not run.
