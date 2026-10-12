# Review: usr (dotfiles)

Scope: `sym`, the layers, `dl`, `macos/`, the scripts under `dotfiles/*/.local/bin`, the Claude, Codex, and pi configuration, and the skills library. Checks run: `make check` (passes, with known length warnings); the sym suite under `sh` and `dash` on macOS and on Debian; `make plan` and `make` into a scratch Linux home. Not covered: running `dl` for the mactop app, running `setup-macos` for real, and the Linux-only scripts beyond syntax.

## Summary

The installer is small and its failure modes are now pinned by tests. What remains is mostly enforcement that depends on the agent cooperating, and machine state that tools rewrite inside tracked files.

## Findings

### R1 · P2 · Codex has no guard against `git push` forms its prefix rules cannot see

- **Area:** Security
- **Where:** `dotfiles/base/.codex/rules/default.rules:1`, `dotfiles/base/.codex/config.toml:8`
- **Problem:** Codex runs with `approval_policy = "never"` and full access. Its prefix rules match only leading tokens, so `git -C dir push`, `git -c k=v push`, and `sh -c 'git push'` are not caught. The Claude deny list covers those forms; Codex has nothing behind its rules. Proven with `codex execpolicy check` for the forms the rules do and do not match.
- **Recommendation:** Add a global `pre-push` hook that refuses when stderr is not a terminal. Agents run without a tty and you push from one. Check first that none of your scripts push without a tty.
- **Fix with:** none
- **Effort:** S

### R2 · P3 · Codex and Claude rewrite tracked config in place

- **Area:** Config
- **Where:** `dotfiles/base/.codex/config.toml:66`, `dotfiles/base/.claude/settings.json`
- **Problem:** Codex appends a `[projects."..."]` trust entry for every directory it runs in, and Claude rewrites `settings.json` (for example on `/effort`). Both write through the symlink into the repo, so the working tree is dirty after ordinary use and machine-specific paths land in shared config. This happened twice during this review.
- **Recommendation:** Accept it and review `git diff` on those two files before committing, or stop tracking the trust entries by keeping them in `~/.codex/config.toml.local` if Codex ever supports an include. There is no include today.
- **Fix with:** none
- **Effort:** S

### R3 · P3 · `macos-lean.py --revert` restores fixed defaults, not what was there before

- **Area:** Operability
- **Where:** `macos/macos-lean.py` (`PMSET_REVERT`, `USER_DEFAULTS_REVERT`)
- **Problem:** Apply then revert resets power and preference settings to the script's constants, so any custom value you had before is lost.
- **Recommendation:** Keep it. Note it in the `--revert` help so it is not a surprise. Recording prior values would add the bookkeeping this repo avoids.
- **Fix with:** none
- **Effort:** S

### R4 · P3 · The local DNS cache runs as root and falls back to Cloudflare in the clear

- **Area:** Security
- **Where:** `macos/setup-macos` (`unbound_conf`, `dns_wanted`)
- **Problem:** `username: ""` keeps unbound running as root, and the system resolver list includes `1.1.1.1` after `127.0.0.1`, so a stopped unbound sends queries out unencrypted. Both are deliberate and documented in the script.
- **Recommendation:** Drop the `1.1.1.1` fallback if a hard failure is preferable to a leak. Undo with `networksetup -setdnsservers SERVICE Empty`.
- **Fix with:** none
- **Effort:** S

### R5 · P3 · The auto-triggered skills have never been measured

- **Area:** Tests
- **Where:** `dotfiles/base/.agents/skills/` (17 auto-triggered skills)
- **Problem:** Their descriptions are reviewed for breadth, but nothing shows they fire at the right times or change behavior. Six were switched from explicit-only to auto-triggered without a measurement.
- **Recommendation:** Run `skill-eval` on the broadest few (`single-source-of-truth`, `make-invalid-states-unrepresentable`, `isolate-effects`) and demote any that does not move the result.
- **Fix with:** skill-eval
- **Effort:** M

## Open decisions

- Whether to add the `pre-push` hook in R1. It changes how any scripted push behaves.

## Strengths to keep

- `sym` aborts on every conflict before writing, and refuses to follow a symlinked directory in either direction.
- Layers are plain directories, and a path in two of them fails `make` before anything is applied.
- Harness state lives in the real `~/.claude`, `~/.codex`, and `~/.pi/agent`, with allowlist ignores on the two directories linked into the repo.
- `setup-macos` previews with `-n`, checks before every change, and keeps its Touch ID module out of the user-writable Homebrew tree.
