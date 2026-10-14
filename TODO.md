Prefix: USR
Next: 4

### USR-1 · P3 · The local DNS cache falls back to Cloudflare in the clear

- **Area:** Security
- **Where:** `macos/setup-macos:223`, `macos/setup-macos:246`, `macos/setup-macos:283`
- **Problem:** The system resolver list is `127.0.0.1 1.1.1.1`, so a stopped unbound sends queries to Cloudflare unencrypted. unbound also runs as root (`username: ""`, line 169). Both are deliberate and documented in the script, and neither has been revisited.
- **Recommendation:** Drop `1.1.1.1` from `dns_wanted` if a hard failure is preferable to a leak. Undo with `networksetup -setdnsservers SERVICE Empty`. The owner decides which failure mode to keep.
- **Fix with:** none
- **Effort:** S (hours)

### USR-2 · P3 · The auto-triggered skills have never been measured

- **Area:** Tests
- **Where:** `dotfiles/base/.agents/skills/` (the skills without `disable-model-invocation: true`)
- **Problem:** Their descriptions are reviewed for breadth, but nothing shows that they fire at the right times or change behavior. Several were switched from explicit-only to auto-triggered, and four were added or merged recently, without a measurement.
- **Recommendation:** Run `skill-eval` on the broadest few (`single-source-of-truth`, `make-invalid-states-unrepresentable`, `isolate-effects`, `comment-cleanup`) and demote any that does not move the result.
- **Fix with:** skill-eval
- **Effort:** M (days)

### USR-3 · P4 · `mdtool` reports false positives on this repo

- **Area:** Docs
- **Where:** `dotfiles/base/.local/bin/mdtool`, `AGENTS.md`, `macos/macos-lean.py`
- **Problem:** `R001` strips a leading dot, so `.claude/skills` is reported as the untracked `claude/skills`. `T002` counts a whole H1 as one oversized section. `P002` fires on parenthesised lists in `macos-lean.py` docstrings. `T000` says the repo has no AGENTS.md when it has one but no `docs/`.
- **Recommendation:** Keep a leading dot when extracting a path, measure `T002` per H2, require a section word for `P002`, and give `T000` its own message. Each fix gets a failing `mdtool selftest` case first.
- **Fix with:** none
- **Effort:** S (hours)
