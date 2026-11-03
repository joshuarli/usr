# Widget Parity

Frameworks encode layout and rendering rules that are easy to approximate and
hard to match. Read the pinned framework source for the rules the snapshots
depend on, then implement only those.

## Layout

- A split distributes an area along one axis. `Length` is fixed, `Fill` shares
  the remainder by weight, `Percentage` is proportional, `Min`/`Max` clamp.
- Modern ratatui uses a Cassowary solver, not a waterfill. Constraints have
  strengths: spacing and explicit lengths dominate `Fill`, and a short area can
  shrink any fixed segment while keeping the others. Do not infer a rule from a
  few widths; probe the real solver at cramped, ordinary, and wide sizes.
- For exact parity, port the framework's solver setup against the same solver
  crate. `kasuari` is the crate under ratatui 0.30; using it directly keeps the
  priority behavior without porting the solver itself.
- Spacing is subtracted between items before distribution.
- Flex controls leftover space: `Center`, `End`, `SpaceBetween`. Implement the
  variants the app uses. Ratatui's default flex is `Start`, not `Legacy`.
- `Rect` arithmetic must saturate. A zero-size area is valid and must render
  nothing, not panic.
- Nested blocks: the inner area is the outer area minus borders and padding.

## Blocks

- Borders: plain `┌┐└┘─│`, rounded `╭╮╰╯─│`, and single-side variants. Corners
  only appear where two adjacent borders meet.
- Padding is inside the border and shrinks the inner area.
- A title is rendered into the top border, left-aligned by default; the app's
  title string usually carries its own spaces. Titles must be clipped to the
  inner width without overwriting the corners.
- Multiple title lines occupy successive top rows; the inner area starts below
  them.

## Paragraph and text

- Text is a sequence of lines; a line is a sequence of styled spans.
- Without wrapping, each line is clipped to the area width. With wrapping,
  word-wrap at spaces and fall back to breaking a word wider than the line.
  Hold whitespace until the next word fits; whitespace at a wrap point is
  dropped, while whitespace at the end of a logical line is kept. Blank input
  lines still produce a row. `trim` drops leading whitespace, not trailing.
- Alignment applies within the area after wrapping.
- Scroll offset is applied after wrapping.
- Width is display width, not byte or char count.

## Tables

- The block, if any, is rendered first; the table uses its inner area.
- A header row is fixed at the top; the body starts below it. Body rows are
  clipped to the remaining height.
- Column widths come from the same layout solver as splits. Ratatui subtracts
  the highlight symbol width and spacing before laying out columns.
- `HighlightSpacing::Always` reserves the symbol column even when no row is
  selected; `WhenSelected` reserves it only with a selection. Render spaces in
  the reserved cells for unselected rows.
- The selected row gets the row highlight style across the full row, then the
  highlight symbol, then the cells. Cell styles are patched over the row style.
- A table's own state (`selected`, `offset`) may be moved by rendering; the app
  often pre-computes a page and renders a state whose selection is relative to
  that page. Match that contract or the app's paging tests will fail.

## Lists and logs

- A list renders from its offset, not from its selection, and clamps the offset
  to the last page.
- A selected item gets the highlight style and symbol; non-selected items still
  reserve the symbol column when the app asks for it.
- Log views usually pre-wrap lines; do not wrap them twice.

## Styles

- A style is foreground, background, and a modifier set. `patch` overlays a
  style onto another without clearing unspecified parts.
- Row/cell styles compose: block style, row style, cell style, then selection.
  Order matters.
- Reset before each SGR run; do not emit a bare color change that inherits a
  previous modifier.
- RGB, indexed, and named colors need distinct SGR encodings. Test at least one
  of each if the app uses them.

## Parity traps

- Off-by-one on right/bottom edges (`x + width` is exclusive).
- Border corners overwritten by a title or a wide glyph.
- Table highlight column included in width calculations twice.
- Wrapping by char count instead of display width.
- Truncating at a byte boundary, splitting a UTF-8 sequence.
- Keeping whitespace at a wrap point, which leaves a styled blank cell the
  original did not have.
- Setting the terminal cursor before the diff: the diff's last write overrides
  it. Set it after drawing, before flushing.
- Comparing a time-driven spinner phase across runs; snapshot a fixed phase.
- Differences only at 40 columns or 12 rows; always run the cramped size.
