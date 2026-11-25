---
name: shell
summary: Shell scripts, Makefile recipes, Dockerfile RUN lines, and pipeline shell are strict POSIX sh on disk, shellcheck-clean, and never hide a failed pipeline stage.
paths:
  - "*.sh"
  - "*.bash"
  - "*.dash"
  - "Makefile"
  - "GNUmakefile"
  - "*.mk"
  - "Dockerfile"
  - "*.Dockerfile"
  - "Containerfile"
shebang:
  - '^#!\s*\S*/(env\s+(-S\s+)?)?(sh|bash|dash|ash|ksh|zsh)\b'
---

# Shell

Apply this to shell the change adds or touches anywhere: script files, `script` or `command` tasks in pipeline YAML, Dockerfile `RUN`, and Makefile recipes. Every item here is must-fix for the shell the change touches. GitHub Actions steps follow [github-actions](github-actions.md) first.

## Inline shell goes on disk

- Do not leave shell inline in pipeline or workflow YAML. Move it to a script file and have the step call that script, one command per step. This covers one-liners that capture values, such as `-var="sha=$(git rev-parse HEAD)"`.
- When the change touches a step that already has inline shell, break that step out too. Report any other inline shell in the same file instead of rewriting it.
- Pass values to the script as arguments or env vars. Do not template them into the shell text.
- Plain single commands with literal arguments (`make test`, `pnpm check`) can stay inline.
- Do not feed code to another interpreter as a string (`python -c`, `node -e`, heredoc-fed scripts) when a script file or a direct call would do.

## Strict POSIX

- New and extracted scripts use `#!/bin/sh` and POSIX syntax only. Debian and Ubuntu run `/bin/sh` as dash, so bashisms break there: `[[ ]]`, arrays, `<(...)`, `echo -e`, `function`, `source`, `$'...'`, and hyphens in function names. Use `printf` instead of `echo -e`.
- If you change an existing bash or zsh script, port it to POSIX `sh` when the port is contained to that script. If the port would spread, report it instead.
- Every touched script passes `shellcheck --shell=sh --enable=check-extra-masked-returns` with no disables added. SC2312 flags masked `$(...)` statuses.
- If the repo runs pre-commit or prek and has no shellcheck hook, add one with those flags. Type detection skips sourced, non-executable `.sh` files, so add a path-based entry for them too.
- To pass arguments through `env` in a shebang, use `#!/usr/bin/env -S cmd args`. Plain `env` treats the whole string as one program name on Linux.
- Do not add support for fish, zsh, or other non-POSIX output modes.

## Pipefail vigilance

POSIX `sh` has no reliable `pipefail`, so a pipeline returns only its last stage's status. Treat every `|` as a possible hidden failure.

| Pattern | Problem | Fix |
|---|---|---|
| `a \| b \| c` | `a` or `b` fails and `c` succeeds, often on empty input | capture `out=$(a)`, then feed the next stage with a here-document |
| `cmd "$(sub)"`, `export X=$(sub)`, `local X=$(sub)` | the substitution's status is lost | assign first, `x=$(sub)`, then use `"$x"` |
| `curl URL` | an HTTP 4xx or 5xx exits 0 | `curl --fail-with-body` (or `--fail`) |
| `jq -r .field` | a missing field prints `null` and exits 0 | `jq -e` (or `jaq -e`); pass values with `--arg`, never by building the filter string |
| `grep` | exit 1 means "no match", exit 2 means error | handle the two codes separately |
| bash script given `set -o pipefail` | a correct no-match `grep` or empty `xargs -r` now aborts the script | review each pipe; do not add `pipefail` as a blanket fix |
| helper ends with `set +x`, `echo`, or cleanup | the function always returns 0 | save `rc=$?` after the real command and `return "$rc"` |
| function called from `if`, `&&`, or `\|\|` | `set -e` is off inside it | check each command's status explicitly |
| loop body runs a command that reads stdin | it consumes the rest of the loop input, so only the first item runs | give that command `</dev/null` |
| stream that must stay a pipe, such as a log tail | the stage failures are lost | write each stage's failure to a temp file and check them after the pipe |

Anti-pattern:

```sh
# If grep fails, git mktree reads nothing, prints the empty-tree hash, and exits 0.
tree=$(git ls-tree HEAD | grep -v scripts | git mktree)
```

Fix:

```sh
listing=$(git ls-tree HEAD)
filtered=$(printf '%s\n' "$listing" | grep -v scripts)
tree=$(git mktree <<TREE
$filtered
TREE
)
```

In the fix, `printf` cannot fail on its own, so the `grep` status decides the result. Use a here-document whenever the producer is a real command.

## Control flow

- Start scripts with `set -eu`.
- Output that is piped to `sh` or passed to `eval` prints all or nothing. Collect it into a variable, check every producer, and only then print. A partial list makes a partial cleanup look complete.
- A required cleanup step, such as ending a downtime or releasing a lock, still runs when the main step fails. The script then exits with the main step's code, not the cleanup's.
- `trap cleanup EXIT` alone is not enough, because dash skips the EXIT trap on a signal. Also trap `INT TERM` and exit from that handler.
- Wrap network calls on startup and deploy paths in `timeout`. A timeout takes the same fallback as any other failure.

## Verify

- Run shellcheck with the flags above on every touched script.
- Run the script under dash, not bash in POSIX mode. Put stub commands on `PATH` and make each one fail in turn. Check that the script exits non-zero and prints nothing partial. Where the old script worked, compare its output with the new one's.
- Check `git diff --summary` for lost exec bits, because file-writing tools can drop them.
