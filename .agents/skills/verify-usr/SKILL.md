---
name: verify-usr
description: "Verify repository-facing behavior in usr through its tracked CLI tools and safe scratch fixtures."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Verify usr

Use this procedure for the `sym` command and repository-level Markdown and skill checks. `dotfiles-health` owns agent setup policy and structural invariants; this skill exercises behavior through tracked tools.

## Scope and prerequisites

The `sym` journey runs in a disposable Git fixture and scratch home under `.work/tmp`. It never uses the real home directory. The helper rejects `.work` or `.work/tmp` symlinks before creating scratch files. The Markdown checks read the repository and write nothing. You need `sh`, `git`, and Python 3.

This procedure does not exercise `dl`, home sync, platform setup, installed system services, or applications outside this repository.

## Launch and readiness

Run from the repository root. The helper checks that `.work` is ignored by `.git/info/exclude` before it creates scratch files.

```sh
./.agents/skills/verify-usr/scripts/sym-journey.sh
```

The helper creates no server or long-running process. A zero exit status means it observed a valid link, an idempotent repeat, and a conflict that left the existing destination intact.

## Doctor

If the result looks wrong, confirm that the command runs at the `usr` Git root and that `.work` is ignored:

```sh
git rev-parse --show-toplevel
git check-ignore -v .work/tmp/verify-marker
git status --short --branch
```

Check only the `verify-usr.*` fixture directory from this run if the helper is interrupted. Do not remove unrelated scratch directories.

## Repository checks

Use these read-only checks for skill and Markdown changes:

```sh
sh dotfiles/skills-check.sh dotfiles/base/.agents/skills
sh dotfiles/skills-check.sh .agents/skills
python3 -I dotfiles/base/.local/bin/mdtool check --untracked
```

`dotfiles-health` defines agent setup invariants. `mdtool` checks links, references, and repository documentation. Neither command proves tool behavior outside its own checks.

## Evidence and cleanup

The helper prints the path to a text record under `.work/tmp/verify-usr.*.log`. Read it to see the commands' output and the observed filesystem results. It contains no environment dump or credentials. A successful record proves only the exercised `sym` behavior on this platform.

On success, failure, or interruption after the cleanup trap is installed, the helper removes only the fixture directory it created and keeps the evidence file. If interrupted before its first observation, the evidence states that no journey observation was recorded. Run it again to create a fresh fixture; each run uses a unique name, so prior evidence cannot collide. Do not delete evidence as part of fixture cleanup.

Update this procedure if `sym` flags, its fixture assumptions, `.work` handling, or the repository check commands change.

**The test:** the helper demonstrates linking, repeat-run behavior, and preservation of a conflicting destination, removes its fixture after both outcomes, keeps evidence, and passes on a second run.

**Report:** the journey run, evidence path, observed outcomes, platform, and anything not covered.
