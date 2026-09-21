# Handoff: implement macos-lean on macOS 27 (Golden Gate)

## Goal

Verify and update the canonical `macos-lean.sh` against a live macOS 27 boot.
The script is 27-*tolerant* today (validates labels, skips stale); this task
makes it 27-*verified* (label lists confirmed correct on Golden Gate, new
27 services triaged).

## Starting state (all in `macos/`)

- `macos-lean.sh` (canonical, dash, ~1200 lines) — supersedes the frozen
  `macos-lean-sequoia.sh` / `macos-lean-tahoe.sh` (do not extend those).
- Modes: `--audit` (no sudo, no changes), `--dry-run`, `--revert`, apply.
- `macos-lean-tahoe.md` — the label-audit workflow, trap catalog, and the
  "After upgrading to 27" checklist at the end. Read it first.
- Handoff machine is still on Tahoe 26.5.2; **this task requires a 27 boot.**

## Prerequisites on the 27 machine

- macOS 27 Golden Gate (released Sept 14, 2026; Apple-silicon-only).
- `dash`, `shellcheck`, `plutil`, `rg` available. No sudo needed until apply.

## Tasks

1. **Baseline audit.** Run `./macos-lean.sh --audit` on 27. Capture full
   output to a file. Categorize every line:
   - `STALE` targets/preserves → renamed or removed in 27. For each, find
     the successor: extract the `Label` key (`plutil -extract Label raw`)
     from plists under `/System/Library/LaunchAgents|LaunchDaemons` and
     `/Library/Launch{Agents,Daemons}`. Update the script lists.
   - `NEW?` candidates → triage each (task 2).
2. **Triage every NEW? label before touching it.** Read the plist's
   `ProgramArguments` (and `MachServices`): `plutil -p <plist> | grep -A4 Program`.
   Names lie — precedent: `avconferenced.plist` hosts
   `videoconference.camera` (the camera, not FaceTime). Decide
   disable / preserve / verify-add, and record the reason in the header
   comment next to the entry.
   - Already-decided keep-list (do not re-litigate without new evidence):
     `backgroundtaskmanagement.*` (Login Items infra), `sysdiagnose*`
     (on-demand diagnostics). Both documented in the script header.
   - Expected 27 hunting grounds: Siri app agents, rebuilt
     Spotlight/Mail/Photos indexing (`spotlightknowledge*`, `corespotlight*`,
     `mdworker*`, `mds*`), Apple Intelligence additions, Background App
     Activity infra. Confirm each against the live plist, never by name.
3. **Check the non-launchd sections for 27 breakage.** Last known state
   (27 beta notes): no `pmset` / `mdutil` / `tmutil` / `defaults` syntax
   changes; `tmutil disablelocal` stays dead (do not re-add). Verify each
   verb/flag on 27 anyway; fix or gate anything that errors. Adjacent 27
   facts: unified-log archive format changed (27 archives unreadable on
   ≤26.1); `com.apple.AssetCache.managed` deprecated for content caching;
   DDM replaces legacy MDM software-update controls.
4. **Update the script.** Keep it dash-compatible (`dash -n` must pass).
   Keep the validate-then-act design: no hardcoded label that fails
   `--audit` on 27. Update the header's DISABLED/PRESERVED/27-note blocks
   and the OS-name mapping if needed.
5. **Update `macos-lean-tahoe.md`.** Record the 27 label renames table
   (same format as the Tahoe table), new traps hit, and candidate
   dispositions. The doc is the durable artifact; the script is downstream.

## Traps (all bitten before — see md for detail)

- Filename ≠ label. Only `plutil -extract Label raw` is truth.
- `launchctl print-disabled` shows stale history, not valid labels.
- `sort`/`comm`/`grep` must share one locale (`export LC_ALL=C` is in
  the script; keep it for any new shell you write).
- Never mask with `|| true` on a path whose failure matters.
- Never run apply on the daily-driver without explicit user approval and a
  snapshot (`~/.local/state/macos-lean/`). `--audit` and `--dry-run` are
  always safe.

## Explicit non-goals

- No Swift rewrite. `SMAppService` manages only an app's own helpers; every
  Swift launchd tool shells out to `launchctl`. Shell is the canonical layer.
- No MDM-profile work in this pass (policy items like Siri/AI restrictions
  belong in profiles long-term, but that is a separate change).
- No guessing 27 labels from press coverage. Live plist or it didn't happen.

## Acceptance

- `dash -n macos-lean.sh` passes; `shellcheck -S warning macos-lean.sh` clean.
- `--audit` on 27: zero unexplained STALE, every NEW? triaged with a
  recorded reason (disabled or keep-listed with justification).
- `--dry-run` output reviewed end-to-end by the human before any apply.
- md updated: 27 rename table, dispositions, traps.
- `git diff --stat` shows only `macos-lean.sh` + `macos-lean-tahoe.md`
  (frozen scripts stay frozen).
