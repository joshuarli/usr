# Terminal Contract

The replacement needs a small, correct terminal layer. Implement it once; do
not spread escape sequences through widgets.

## Lifecycle

Use `rustix::termios` and `rustix::event` (or the project's established OS
layer) rather than a terminal crate.

- Save the original `Termios` with `tcgetattr` before changing anything.
- Clone it, call `make_raw()`, and install with `tcsetattr(..., Now, ...)`.
- Restore the saved attributes on normal exit, error, panic, and signal paths.
  A panic hook is the last line of defense; `Drop` alone is not enough because
  `abort` skips it.
- Enter the alternate screen with `ESC[?1049h`, hide the cursor, clear, and home.
  Leave with reset SGR, show cursor, and `ESC[?1049l`.
- Enable only the input modes the app uses: SGR mouse (`?1006h` plus the button
  mode), bracketed paste (`?2004h`), and application cursor/keypad only if the
  key decoder requires it. Disable each on the way out.
- If the app spawns or forks, restore before exec and re-enter in the child.

## Size and resize

`tcgetwinsize(stdout)` gives columns and rows. Poll it before each frame or use
`SIGWINCH`; either way a size change must become a render at the new size. A
zero dimension is possible during teardown; skip drawing rather than panic.

## Input

- Wait for readable input with `select` or `poll`. On macOS, `select` is the
  portable choice for terminal descriptors.
- Read into a byte buffer, append to a decoder, and consume complete events.
- Esc is ambiguous: a lone `ESC` is a key, `ESC [` starts CSI, and `ESC O`
  starts SS3. Hold a partial sequence for a short escape timeout, then emit Esc.
- Handle fragmented UTF-8 and fragmented escape sequences; never assume one
  read is one key.
- Decode at least: printable UTF-8, Enter, Tab, BackTab, Backspace, Delete, Esc,
  arrows, Home/End, PageUp/PageDown, Insert, and Ctrl/Alt-modified characters.
- SGR mouse is `ESC [ < b ; x ; y M` (press/motion) and `m` (release), with
  one-based coordinates and modifier bits in `b`. X10 mouse is a fallback only
  if the app requests it.
- Bracketed paste is `ESC[200~ ... ESC[201~`; keep pasted text as text, not keys.

## Screen model

Keep a full cell buffer:

```text
Cell { symbol, width, fg, bg, modifiers }
```

- Width comes from `unicode-width` per grapheme, not per `char`.
- A wide glyph owns its first cell and leaves continuation cells with zero
  width. Writing either half must erase the whole glyph in the model.
- Combining marks and zero-width characters attach to the preceding cell and
  must not advance the cursor.
- Clip at the right edge; a wide glyph that does not fit becomes a blank (or
  the terminal's replacement behavior), never a half glyph.
- Reset the buffer to spaces with the default style for every frame, or clear
  the changed regions; stale cells are the most common parity failure.

## Output

- Emit runs of equal style, not one escape per cell.
- Start each run with `ESC[0m` and then the active SGR codes. This keeps the
  output independent of prior terminal state.
- Move the cursor only when the next cell is not at the current output
  position. Track the actual output position through wide glyphs.
- A simple diff against the previous frame is enough; full repaints are also
  correct but can flicker on slow terminals.
- Flush once per frame, not per row.

## Common failures

- Restoring termios but not the alternate screen (or the reverse).
- Leaving mouse reporting on after quit.
- Treating Esc as the start of a sequence forever.
- One-column-wide terminals and zero-height areas panicking in arithmetic.
- Wide glyph at the last column shifting a border.
- Writing a cell twice in one frame and losing the style of the second write.
- Using `char` count as display width.
