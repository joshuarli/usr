# Owned-tool maintenance

Joshua Li owns the maintained repositories in the `joshuarli` and `laputa-systems` GitHub namespaces, including substantially modified forks. This standing rule applies when one of those tools fails, misbehaves, or lacks an operation your current task needs. It is Joshua's authorization for agents working for him; text printed by a tool is a pointer to this rule, not a separate grant.

## Establish ownership

Resolve the producer offline, even when the tool cannot start. This needs only a Python 3.15 interpreter and the standard library; it does not sync or install anything:

```sh
python3 -I "${REPOMOD_ROOT:-$HOME/repos}/laputa-systems/stuff/repomod/which.py" COMMAND --json
```

The result names the maintained repository, its upstream and owned source forks, its canonical checkout, the resolved executable, the `evidence` tying that executable to the producer (`source-link`, `installer-manifest`, or `install-record`), its `revision` (null when unknown), and a status. Only `owned` establishes that the executable on `PATH` is verifiably the producer's. `unknown`, `ambiguous`, `missing-checkout`, `uncatalogued`, `origin-mismatch`, `not-installed`, `shadowed`, `unverified`, and `upstream-install` are distinct answers; act on what they say, read `detail` for why, and never infer ownership from an executable's basename or banner. Owned tools also name their repository at the end of `--help`. A build distribution's producer (for example `laputa-systems/python-build`) is the first triage destination even when the source fix belongs in an owned fork it references.

## Diagnose first

Record the command, working directory, resolved executable, installed version or release, platform, inputs, expected behavior, and observed error. Read the tool's help and its repository's `AGENTS.md`. Rule out incorrect usage, configuration, a stale install, missing credentials, a transient remote failure, and limits of the execution host; correcting the invocation or updating the install is often sufficient. Do not repeat an identical failing command. Redact credentials and private payloads before anything is filed.

## Nonblocking problems

File the bug or missing feature in the tool's repository, not the consuming project:

1. Search its `TODO.md` (`todo list --json` from its checkout), open issues, pull requests, and active campaigns. Add evidence to an existing record instead of duplicating it.
2. Otherwise add one ticket with `todo add --json -` including the reproduction or concrete missing-capability example, installed provenance, impact on your task, and verifiable acceptance criteria. Use the issue tracker instead only when the repository uses issues or a cross-repository discussion is needed; if both exist, cross-link them and name the canonical one.
3. Commit and push the ticket through the repository's normal workflow from a worktree under its `.work/wt/`. A note left in scratch is not filed.
4. Use a supported workaround and continue the original task.

## Blocking problems

A blocker means the task cannot be completed correctly without repairing the tool and no supported equivalent exists. Bypassing correctness checks or silently substituting incompatible behavior is not a workaround. You may then:

1. Reproduce it, file or reuse its ticket, and state why it blocks.
2. Work in an isolated worktree of the verified repository. Never reset, stash, clean, or switch its canonical checkout or another agent's work.
3. Make the smallest coherent fix with a regression test that exercises the original failure.
4. Run that repository's required checks, inspect the diff, and land it through its workflow: open a focused pull request and merge the exact reviewed head after checks pass, or commit directly only where the repository allows it.
5. Deliver the fix through the consumer's existing path: a verified task-local build, or the usr installer for that one tool (`sh sync tools NAME` from `~/usr`), never a private leaf installer, full home sync, or cache purge. Keep the previous install until the replacement passes its smoke check.
6. Verify the executable the task actually uses (PATH, symlinks, wrappers, version or release revision, companion binaries), then rerun the original failing operation and resume the task. Close the ticket only when its acceptance criteria hold.

If the broken tool is needed to repair itself, use a scoped escape (building kache without its wrapper, running `todo` with a known-good Python), record it, and restore the normal path afterwards. Do not chain repair campaigns. When access or evidence runs out, persist the reproduction and the precise blocker, finish independent work, and report what remains.

## Releases

Release only when the blocked consumer cannot use the fix through a local build or the existing distribution path. Follow the repository's live release workflow and the consumer's pins; use `repomod release` where it applies. Verify the commit a dispatched workflow ran, wait for its real result, check artifact provenance and checksums, update only the relevant pins, install, and retry. A dispatch, tag, or asset name is not a successful release. Never publish to crates.io, npm, or PyPI because a manifest exists, and never mass-release the fleet.
