# PTY Oracle

The old binary is the oracle. A real PTY gives it a terminal, so it exercises the
same raw mode, alternate screen, mouse reporting, resize handling, and output
diffing the user gets. An in-process test backend does not.

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
| Modals | help, settings, chat, browse, room list, confirmation |
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
  ids); do not normalize spacing, colors, or cursor position.
- Keep one raw lifecycle golden per terminal mode if needed. Do not require
  byte-identical frame output.

## Fixture mode

The fixture must run the real UI, not a parallel renderer:

- If the app already takes an `Arc<dyn SessionApi>` (or equivalent), implement a
  deterministic fixture session and add a small feature-gated example binary.
- The example enters and restores the terminal exactly like the real binary.
- Keep fixture-only state out of release builds; use a Cargo feature or a
  separate example target.
- If the app cannot run without login, still capture the login screen from the
  real binary with no credentials; a fixture is only needed past that point.

## Hillclimb order

1. Content and placement.
2. Style and modifiers.
3. Cursor.
4. Lifecycle and restoration.
5. Raw output, if it matters.

Run only the failing scenario while developing; run the whole matrix at each
slice boundary.
