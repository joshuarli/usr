# PTY Oracle

The old binary is the oracle. A real PTY gives it a terminal, so it exercises the
same raw mode, alternate screen, mouse reporting, resize handling, and output
diffing the user gets. An in-process test backend shares the framework's layout
and diff logic, so it cannot prove that the replacement matches the terminal.

Add the harness before touching the renderer and keep the framework installed
for this phase. Run the suite against the untouched app and keep it green before
replacing anything.

## Harness shape

Use `laputa-ptytest` (or the project's existing PTY harness) with:

- `CommandSpec` pointing at the compiled binary or a feature-gated fixture example.
- `TestEnv::hermetic()` plus isolated `HOME`, XDG, config, state, cache, and temp paths.
- A fixed locale, timezone, and terminal size per scenario.
- Fixture data at the app's session/API seam, not a live network.

Drive the app with keys and resizes, wait for a stable screen, then assert. Do not
sleep for a guessed interval; wait for the text or quiescence with a deadline.

## Scenario matrix

At minimum:

| Area | Cases |
| --- | --- |
| Lifecycle | start, quit, `Ctrl-C`, panic, terminal restored |
| Geometry | 80x24, 40x12, 200x60, one very short and one very narrow |
| Content | empty, loading, error, populated, very long names, Unicode and emoji |
| Navigation | every pane/tab, focus changes, paging, home/end, filter, command bar |
| Modals | every modal, including help, settings, chat, browse, room list, confirmation |
| Editing | ASCII, Unicode, backspace, delete, cursor movement, paste |
| Resize | grow, shrink, cross a layout breakpoint |
| Mouse | click, drag, wheel, coordinates at edges |

Capture after quiescence, and again after the next key if a redraw is part of
the behavior.

## Snapshots

Prefer semantic snapshots: size, cursor, modes, cell text, and style runs. They
survive a different diff strategy and still catch wrong cells. Include attributes
when styling matters, which is almost always.

- Commit the snapshots from the oracle run, before the replacement lands.
- Update only with an explicit environment variable such as
  `PTYTEST_UPDATE_SNAPSHOTS=1`, and review the diff.
- Normalize only genuine nondeterminism (spinner frame, elapsed time, random
  ids); do not normalize spacing, colors, or visible cursor position. A hidden
  cursor's reported position is not visible, so it can be replaced with a bare
  "hidden" line when the terminal reports one.
- Keep one raw lifecycle golden per terminal mode if needed. Do not require
  byte-identical frame output.

## Fixture mode

The fixture must run the real UI, not a parallel renderer:

- Use the existing session/API seam, such as `Arc<dyn SessionApi>`, with a
  deterministic fixture session. Add a small feature-gated fixture binary or
  example only when no existing seam can be driven from a binary.
- The example enters and restores the terminal exactly like the real binary.
- Keep fixture-only state out of release builds; use a Cargo feature or a
  separate example target.
- If the app cannot run without login, still capture the login screen from the
  real binary with no credentials; a fixture is only needed past that point.

## Hillclimb to parity

Run the oracle snapshots against the new binary after each slice, one behavior
area at a time. Fix differences in this order:

1. Content and placement.
2. Style and modifiers.
3. Cursor.
4. Lifecycle and restoration.
5. Raw output, if it matters.

Run only the failing scenario while developing; run the whole matrix at each
slice boundary, including cramped, ordinary, and wide sizes.

Compare semantic screens first. Only after they match compare normalized raw
output where it matters; a different diff strategy or cursor movement between
equal cells need not produce identical bytes. Never normalize away visible
content.

For a mismatch, fix the smallest rule that explains it: a layout split, border,
padding, column allocation, wrap point, clipping rule, or highlight column. Add a
unit test for that rule before moving on. Keep the oracle snapshots passing
while testing the new layer's edge cases: wide characters, zero-size areas,
one-cell terminals, and scrolling past the end.

The loop ends when every scenario matches, not when the code compiles.
