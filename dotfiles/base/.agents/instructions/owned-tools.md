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

## Third-party defects

Repositories outside the `joshuarli` and `laputa-systems` namespaces are not ours to post in. Opening an issue, pull request, comment or review there needs Joshua's explicit consent for that post; a general grant such as "take your recommendations" or run-until-done authority is not consent. When a task finds a defect in a third-party project:

1. Fork it into `laputa-systems` with `gh repo fork OWNER/REPO --org laputa-systems --clone=false`, or reuse the existing fork. Enable its issues if they are off.
2. Fix it there from a worktree, on a branch based on the exact upstream revision the consumer uses, with a regression test, and run the project's own checks. Keep one branch per upstream candidate so each can be offered separately.
3. Switch the consumer to the fork at the fixed commit through its normal pin (a Cargo `git` + `rev` dependency, a vendored tree recorded with the fork URL and revision, a lockfile entry), and verify the consumer.
4. File an issue in the fork titled `Upstream draft: …` with the label `upstream-draft`. It holds the text that would go upstream: the defect, evidence against the upstream revision, the fix branch and commit, and whether an upstream issue or pull request is suggested. Link any related upstream issues instead of commenting on them.
5. Report the draft. Joshua decides whether and how it goes upstream.

### Draft format

A draft is short, exact and reproducible; every sentence is a verified fact. One defect per draft.

- **Title**: `area: defect` in the project's own convention, lowercase, no trailing period.
- **Body**, in this order, omitting any section with nothing verified to say:
  1. One paragraph: the defect and its consequence, pinned to `OWNER/REPO@<40-hex commit>` with `path:line` links at that commit. Name releases only alongside their commit.
  2. `Reproduction`: the commands, then the smallest self-contained, pinned environment that exercises the defect. Default to a Dockerfile: base image pinned by digest, sources fetched by full commit (`ADD https://codeload.github.com/OWNER/REPO/tar.gz/<sha>`). When the defect depends on the CPU, kernel or devices, run it under QEMU instead (for example TCG with `-cpu Haswell,-bmi2`), with the QEMU version, machine and CPU flags exact and any guest image pinned by checksum; a Dockerfile that builds that QEMU run is fine. Either way the final step asserts the defect, failing on the base commit and passing on the fix. Paste the decisive output lines verbatim.
  3. `Fix` (pull requests only): what changed and why, in at most three sentences, naming `laputa-systems/REPO@<40-hex commit>`.
  4. `Tested`: exact toolchain versions, host `uname -srvm`, and the statement that the shown reproduction was run unchanged against both commits. Add a benchmark table only when the change can affect performance.
- No hedges or unverified scope: no "some", "may", "probably", "older versions", or CPU, OS or configuration classes the reproduction did not exercise. A claim the reproduction cannot show needs a `path:line` at the pinned commit, or it is cut.
- Before filing, run the reproduction exactly as pasted on a clean build and confirm the outputs quoted.

## Releases

Release only when the blocked consumer cannot use the fix through a local build or the existing distribution path. Follow the repository's live release workflow and the consumer's pins; use `repomod release` where it applies. Verify the commit a dispatched workflow ran, wait for its real result, check artifact provenance and checksums, update only the relevant pins, install, and retry. A dispatch, tag, or asset name is not a successful release. Never publish to crates.io, npm, or PyPI because a manifest exists, and never mass-release the fleet.
