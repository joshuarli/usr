+++
name = "github-actions"
summary = "GitHub Actions steps put logic in github-script modules or stdlib Python, pin every action with pinact, and pass pinact lint with least privilege."

[[trigger]]
paths = ["/.github/workflows/**", "/.github/actions/**", "action.yml", "action.yaml"]

[examples]
match = [".github/workflows/ci.yml", ".github/actions/setup/action.yml", "actions/release/action.yaml"]
skip = ["docs/github-actions.md", "svc/.github/workflows/ci.yml", ".github/dependabot.yml"]
+++

# GitHub Actions

Apply this when a change adds or changes a step in `.github/workflows/` or `.github/actions/`, or a script that a step runs. Every item here is must-fix for the steps the change touches. A repo's own guide, such as `docs/github-actions.md`, wins where it is more specific.

## Code

### Where step logic goes

| Logic | Goes in |
|---|---|
| One command with literal arguments, such as `make test` or `pnpm check` | inline `run:` |
| Anything that calls the GitHub API: commits, refs, PRs, comments, labels, checks, releases | `actions/github-script`, importing a module from the repo |
| Logic that `github-script` cannot do well, such as reading a Python tool's output | a Python 3 script on disk, standard library only |
| Anything else | not shell; pick one of the rows above |

- Prefer `actions/github-script` over Python. Use Python only when the step really needs it.
- Add no dependencies for step logic. `github-script` already provides Octokit (`github`), the event `context`, and `core`. Python imports only the standard library.
- Do not add new `.sh` scripts or multi-line `run:` shell to a workflow. When the change touches a step that already runs shell, move that step's logic in the same change. Report other shell steps in the file instead of rewriting them. This is a fix-forward rule, not a reason to sweep a repo.
- Shell that has to stay, such as a composite action that wraps a CLI, follows [shell](shell.md).

### Pinning

- Write the version tag in `uses:` and run `pinact`. It resolves every external action to a full commit SHA with a version comment, without a token or the GitHub API. Do not hand-write SHAs.
- Rerun `pinact` after changing any `uses:`, and commit the pinned workflow. `pinact --refresh` re-resolves existing pins from their version comments; choosing a newer version is an explicit edit.
- Branch refs fail unless you pass `--allow-branches`. Do not pass it for a workflow you are adding; pin a tag.
- A pin proves a SHA shape, not provenance. Where the repo keeps an approved catalog, also run `pinact lint --catalog CATALOG` and pin with `pinact fix --catalog CATALOG`.

### `actions/github-script`

- Keep `script:` to an import and one call. Put the logic in a module next to the other workflow scripts, such as `.github/workflows/scripts/<name>.ts`, and export one function that takes `{github, context, core, ...inputs}`.
- Write the module in TypeScript when the repo's Node can strip types: Node 22.18+ or 23.6+, which `github-script` v8 and later run on. Use only erasable syntax: no `enum`, `namespace`, or constructor parameter properties, and import with the `.ts` extension. Otherwise use ESM `.js`.
- Type the Octokit calls the module uses in a local interface, so the repo needs no `@actions/github` dependency.
- Pass inputs through `env:` and read them from `process.env`. Never put `${{ }}` expressions in `script:`, because they are templated into the code before it runs, which allows injection.
- Use Octokit, not `gh`, `curl`, or `git push`. To commit to a bot branch, use the Git Data API (`git.getCommit`, `git.createTree`, `git.createCommit`, then `git.updateRef` with `force` only for the bot's own branch). That needs no git identity, and GitHub signs the commit as the app.
- Let API errors throw. Catch only the status the step expects, such as `422` from `updateRef` on a branch that does not exist yet, and rethrow everything else. Report failure with a thrown error or `core.setFailed`, and log with `core.info`.

Anti-pattern:

```yaml
- run: |
    gh auth setup-git
    git switch -C bot/update
    git commit -am "chore: update"
    git push -f origin bot/update
    PR=$(gh pr list --head bot/update --json number --jq '.[0].number // empty')
    [ -n "$PR" ] || gh pr create --head bot/update --title "chore: update" --body "..."
```

Fix (`pinact` then replaces the tag with its SHA and a version comment):

```yaml
- uses: actions/github-script@v9.0.0
  env:
    NEW_FILE: ${{ runner.temp }}/artifact/file.json
  with:
    github-token: ${{ steps.bot.outputs.token }}
    script: |
      const {publish} = await import(`${process.env.GITHUB_WORKSPACE}/.github/workflows/scripts/publish.ts`);
      await publish({github, context, core, newFilePath: process.env.NEW_FILE});
```

### Python scripts

- Use `#!/usr/bin/env python3` and only the standard library, such as `json`, `argparse`, `subprocess`, and `urllib.request`.
- Take inputs as arguments or env vars, exit non-zero on failure, and run as one command per step.
- Do not feed Python to an interpreter inline (`python -c`, heredocs). Put it in a file.

### Tests

- Add a test next to each new or changed module. For TypeScript or JS, use `node:test` with `node:assert/strict`. For Python, use the repo's existing test runner for workflow scripts.
- Mock `github` with plain objects that record their calls. Assert on the API calls for each path: the no-op, the first run, an existing branch or PR, and invalid input.
- Check that a workflow the repo already runs picks up the test. If none does, add the test command to one, and say so in the PR.

### Least privilege

Every touched workflow and action passes `pinact lint` (the `default` profile) with no findings. Fix a finding in the change instead of working around it. Also run `--profile=strict` on touched files and resolve its permission findings for the jobs you touched.

| Rule | Source | Requirement |
|---|---|---|
| Explicit permissions | `pinact` `excessive-permissions`, `missing-permissions` (strict) | Set `permissions: contents: read` (or `{}`) at the top of the workflow, and give each job its own `permissions:` block with only the scopes that job uses |
| Checkout credentials | `pinact` `checkout-credentials` | Check out with `persist-credentials: false`, unless the job pushes, fetches, or calls an action that needs the token on disk |
| No template injection | `pinact` `template-injection` | Never put `${{ }}` in `run:` or `script:`. Pass it through `env:` |
| Safe triggers | `pinact` `dangerous-trigger` | A `pull_request_target`, `workflow_run`, or `issue_comment` workflow never checks out or runs PR code |
| No secret leaks | `pinact` `credential-exposure` | A secret or token never reaches logs, outputs, artifacts, or untrusted steps |
| Pinned actions | `pinact` `unpinned-uses` | Every external action is pinned, as above |
| Scoped app tokens | review | Scope every `actions/create-github-app-token` with `permission-*` inputs, so the token does not get every permission the app has |
| Named secrets | review | Name each secret. A computed lookup such as `secrets[matrix.name]` loads every repository secret into the runner |

- Give a write token only to the job that writes. Scan or build in a separate read-only job, and hand the result over as an artifact. Validate the artifact before acting on it with the write token.
- Run a `pull_request` trigger only for jobs that need no secrets. Gate write jobs on the event and ref, such as `github.event_name != 'pull_request' && github.ref == format('refs/heads/{0}', github.event.repository.default_branch)`.
- `pinact` has no suppression mechanism. When an intentional design trips a rule, state the reason in the PR body. When the rule is wrong, file the false positive in the `pinact` repository and keep the finding visible.
- A permission change in a job that runs only after merge, such as on schedule, release, or `pull_request_target`, is not exercised by the PR's CI. Name those jobs in the PR body. When narrowing permissions across many workflows, use one PR per workflow so each can be reverted alone.

### Verify

- Run the module's tests with `node --test` or the repo's Python test runner.
- Run `pinact --check` (offline) and `pinact lint` on every touched workflow and action, plus any other workflow linters the repo has, such as actionlint.
- Import the module the way `script:` does, with the same Node major version, to catch syntax that cannot be stripped.

## Adoption

Apply these only when bringing a whole repository up to this standard, not at the completion gate.

- Run `pinact` over every workflow and action, and add `pinact --check` and `pinact lint` to a workflow the repository already runs.
- Move each shell step's logic into `actions/github-script` modules or stdlib Python scripts, one workflow per change.
- Narrow permissions one workflow per PR, so each can be reverted alone.
