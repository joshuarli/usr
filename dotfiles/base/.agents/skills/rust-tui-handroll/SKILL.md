---
name: rust-tui-handroll
description: "Replace a Rust TUI framework (ratatui, tui-rs, crossterm, termion, cursive, tuirealm, or similar) with a hand-rolled terminal layer over rustix termios, using PTY screen captures as the oracle and hillclimbing to parity."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Hand-Roll a Rust TUI

Remove the framework by making the old binary the oracle. Capture what it actually draws and how it responds through a real PTY, then build the smallest terminal and widget layer the app uses and drive both until the screens match. Do not port the framework's full API or internals, and do not redesign the UI while replacing its renderer. Preserve keys, mouse behavior, layout, styles, cursor, startup, exit, and restoration; a deliberate visual or behavioral change is a separate decision.

## 1. Freeze the oracle first

Add a PTY harness such as `laputa-ptytest` before touching the renderer. Keep the framework installed for this phase.

- Run the real binary through a kernel PTY, not a test backend. The test backend shares the framework's own layout and diff logic, so it cannot prove the replacement matches the terminal.
- Make the app deterministic: hermetic environment, isolated home/config/state, fixed locale and timezone, fixed terminal sizes, and a fixture session instead of the network. Use the app's existing session/API seam; add a feature-gated fixture binary or example only when no seam can be driven from a binary.
- Capture start-up, every pane and modal, empty/loading/error states, long and wide text, narrow and short terminals, navigation, typed Unicode, resize, mouse, quit, and terminal restoration. Use at least one ordinary size, one cramped size, and one wide size.
- Store semantic snapshots (text, attributes, cursor, modes) and commit them. Raw byte goldens are for lifecycle sequences only; a replacement may legitimately diff or batch output differently.
- Run the suite against the untouched app and keep it green before replacing anything.

## 2. Inventory the real surface

List every framework item the app touches: terminal lifecycle, input decoding, layout constraints, text and width handling, blocks, paragraphs, tables, lists, scrolling, styles, cursor placement, and test-only backend calls. Read the framework version's source for the behaviors the snapshots depend on, especially layout distribution, wrapping, borders, table column allocation, and highlight spacing. Classify each item as required behavior or incidental API. Build only the required set.

Prefer a narrow in-repo module with the same concepts the app already uses (`Screen`, `Rect`, `Style`, `Line`, `Block`, `Table`, `Terminal`) over editing every call site at once. Keep the module framework-free; the app must compile with the dependency removed.

## 3. Build the terminal layer

See [the terminal contract](references/terminal-layer.md) for rustix details.

- Save and restore termios on every exit path, including errors, panic, and signals. Raw mode, alternate screen, cursor visibility, mouse reporting, and bracketed paste are one lifecycle contract.
- Read the size with `tcgetwinsize`; treat a changed size as a resize event. Read input with `select`/`poll` plus an escape-sequence timeout so a lone Esc is not mistaken for a sequence prefix.
- Decode the keys and mouse events the app uses, including modifiers, SGR mouse coordinates, paste, and fragmented reads.
- Keep a cell buffer with symbol, foreground, background, and modifiers. Measure display width with `unicode-width`; handle wide glyphs, wide continuations, combining marks, and the right edge. Diff against the previous frame, or repaint deliberately, but never leave stale cells.
- Serialize SGR with a reset before each run; do not rely on the terminal inheriting state.

## 4. Hillclimb to parity

Run the oracle snapshots against the new binary after each slice, one behavior area at a time.

1. Fix content and placement first, then colors and modifiers, then cursor position and visibility, then lifecycle bytes.
2. Compare semantic screens; only when they match compare normalized raw output. Normalize only real nondeterminism (timing, diff strategy, cursor movement between equal cells), never visible content.
3. When a screen differs, solve the smallest rule that explains it: a layout split, border cell, padding, column allocation, wrap point, clipping rule, or highlight column. Add a unit test for that rule before moving on.
4. Keep the oracle snapshots passing while adding tests for the new layer's own edge cases (wide chars, zero-size areas, one-cell terminals, scrolling past the end).
5. Do not tune to one terminal. Run the matrix at cramped, ordinary, and wide sizes; text that fits one size often wraps or clips differently at another.

The loop ends when every scenario matches, not when the code compiles.

## 5. Cut over

- Remove the framework, its re-exported backend/event crates, and test-only framework backends from `Cargo.toml` and the lockfile.
- Keep the PTY fixtures, snapshots, and focused tests; delete throwaway comparison scripts and any fixture hook that is not needed by the retained suite.
- Verify startup without a TTY, quit, `Ctrl-C`, panic, resize, tiny sizes, and restoration. Run the repository's normal checks on the affected packages.
- Update docs and any architecture notes that name the old framework.

**The test:** the dependency is gone, the same PTY scenario matrix produces the same semantic screens and lifecycle state, and a deliberately broken layout or key binding makes a committed test fail.

**Report:** framework and version removed, module that replaced it, scenario matrix and sizes, snapshot command, checks run and not run, deliberate differences, and any remaining lifecycle or platform limitation.
