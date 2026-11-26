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

Follow the [PTY oracle procedure](references/pty-oracle.md) to capture and verify the untouched binary before replacing the renderer. It owns the harness, fixture boundaries, scenario matrix, and snapshots.

## 2. Inventory the real surface

List every framework item the app touches: terminal lifecycle, input decoding, layout constraints, text and width handling, blocks, paragraphs, tables, lists, scrolling, styles, cursor placement, and test-only backend calls. Read the framework version's source for the behaviors the snapshots depend on, using [widget parity](references/widget-parity.md) for the layout and rendering rules to inspect. Classify each item as required behavior or incidental API. Build only the required set.

Prefer a narrow in-repo module with the same concepts the app already uses (`Screen`, `Rect`, `Style`, `Line`, `Block`, `Table`, `Terminal`) over editing every call site at once. Keep the module framework-free; the app must compile with the dependency removed.

## 3. Build the terminal layer

Implement [the terminal contract](references/terminal-layer.md): lifecycle, resize, input, cell model, and output. Keep these operations below the widgets, with one owner for terminal state.

## 4. Hillclimb to parity

Follow the [oracle comparison loop](references/pty-oracle.md#hillclimb-to-parity) after each slice. Use the [widget parity traps](references/widget-parity.md#parity-traps) to locate mismatches. Continue until every scenario matches.

## 5. Cut over

Remove the framework only after the complete PTY scenario matrix matches.

- Remove the framework, its re-exported backend/event crates, and test-only framework backends from `Cargo.toml` and the lockfile.
- Keep the PTY fixtures, snapshots, and focused tests; delete throwaway comparison scripts and any fixture hook that is not needed by the retained suite.
- Verify startup without a TTY, quit, `Ctrl-C`, panic, resize, tiny sizes, and restoration. Run the repository's normal checks on the affected packages.
- Update docs and any architecture notes that name the old framework.

**The test:** the dependency is gone, the same PTY scenario matrix produces the same semantic screens and lifecycle state, and a deliberately broken layout or key binding makes a committed test fail.

**Report:** framework and version removed, module that replaced it, scenario matrix and sizes, snapshot command, checks run and not run, deliberate differences, and any remaining lifecycle or platform limitation.
