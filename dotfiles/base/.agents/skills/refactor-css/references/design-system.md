# Design system: tokens, ownership, layout

## Contents

- [Tokens](#tokens)
- [Ownership](#ownership)
- [Selectors and state](#selectors-and-state)
- [Controls](#controls)
- [Layout](#layout)
- [Responsive rules](#responsive-rules)
- [Ids](#ids)
- [Out of scope](#out-of-scope)

## Tokens

Define each token once, in one file loaded first, as custom properties on `:root`. Components reference tokens; they never restate the value.

- Spacing: a 4px grid with a 2px half step (`2, 4, 8, 12, 16, 24, 32, ...`). Name by step, not by use.
- Control size: one height for buttons, inputs, and icon controls, so rows align.
- Inset and gutter: the padding inside a container and the gap between containers, each defined once.
- Radii, type scale (size and line-height together), and a z-index scale with named layers. No literal `z-index` in components.
- Breakpoints: one list. Custom properties cannot appear in `@media` conditions, so keep the list in one documented-by-name place (a single file or build-time substitution) and have every component use those exact values.

A value that appears three times is a missing token. A value that is off-scale by 1 to 2px is a snap, not a new token; record it for the report. Do not add a token nothing uses.

## Ownership

One owner per fact: one file per component, one definition per selector, one rule per property of that selector.

- The container owns its padding and the gap between its children, symmetrically. A header with `12px` above and `0` below plus a body with `6px` is two owners compensating; replace with one inset and one gap.
- No component compensates for another's padding. If a child needs a different edge, the container's contract is wrong; fix the container.
- Space siblings with `gap` or a stack (`> * + *` or a flex/grid column), not per-child `margin-bottom`. Last-child special cases are a sign of per-child margins.
- A trailing element (notice, footer) is spaced by its container's gap, not by a margin that depends on what precedes it.
- A flush child (table under a header) is handled by the container choosing its gap or inset once, not by a negative margin or a zeroed sibling.

## Selectors and state

- Delete overrides instead of adding specificity. A rule such as `.parent > .card .head { ... }` that patches `.head` is merged into `.head`, or the variation becomes a modifier on the component.
- No `!important`. No id selectors. One class per concept; do not give two classes the same meaning.
- Pick one state-hook style per project and use it everywhere: `data-` attributes, ARIA attributes already in use as state, or modifier classes. Do not mix them for the same state.
- Descendant selectors reach at most one level into a component's own markup. Do not style another component's internals; give it a modifier or a token.
- Never define one selector in two places. If a base and a variant both exist, the variant holds only the differing properties.

## Controls

- A control that can appear in a header or row reserves its space in every state. Never mount or unmount it; disable it, or hide it with `visibility: hidden` or `opacity: 0`, so siblings do not move.
- The rightmost control is the stable anchor: its right edge is identical across state changes and across sibling components that share the layout.
- Hover-only affordances live behind `@media (hover: hover)`. Without hover they are either always visible or absent, and they still reserve their space so nothing leaves a hole beside the anchor.

## Layout

- Grid for two-dimensional structure, flex for one-dimensional rows. Do not simulate a grid with nested flex and fixed widths.
- Prefer intrinsic sizing (`min-content`, `auto`, `minmax`, `aspect-ratio`) over fixed heights. A fixed height needs a stated reason in the name or token.
- Variable-height cards in columns: state the tradeoff and pick one.
  - Grid rows align cards but leave gaps under shorter cards.
  - CSS multi-column packs tightly but reflows cards between columns when any height changes.
  - Explicit column stacks (one flex column per column, items assigned in markup) are deterministic: a height change moves nothing sideways.
  Prefer explicit stacks when collapse or expand must not reshuffle neighbors; otherwise ask the owner if the choice is not evident.
- Constrain overflow at the container (`min-width: 0`, `overflow` on the scroller), not by shrinking content.

## Responsive rules

A component's media queries sit inside its own file, next to the rules they change. Global media-query blocks that patch components are deleted and redistributed. Prefer fluid layout and container-owned reflow to adding a breakpoint; a breakpoint that only fixes one component's overflow belongs to that component.

## Ids

DOM ids are unique across the whole app, including repeated and conditionally rendered widgets. Anchors, `aria-controls`, and persisted UI state key off them; a duplicate makes two components share state. Prefer classes for styling; audit ids that feed persisted state and migrate stored keys if an id changes.

## Out of scope

Accessibility (ARIA, focus order, contrast, reduced-motion, keyboard support) and dark mode are excluded by the owner. Do not add, audit, or remove accessibility attributes, and do not introduce `prefers-color-scheme`, theme switching, or second token sets. `color-scheme` stays light.
