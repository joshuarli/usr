---
name: bug-report
description: "Apply when writing a bug report, an issue, an `Upstream draft:` issue in a laputa-systems fork, or a bug-fix pull request description, for any repository. Produces a short, exact report with a pinned reproduction that fails on the base and passes on the fix. Skip internal TODO tickets (use todo) and chat summaries."
---

# Bug Report

A report is short, exact and reproducible. Every sentence is a verified fact. One defect per report.

**The reproduction is minimal.** It shows the crux of the defect and nothing else: the fewest files, lines, dependencies, build steps and inputs that still fail on the base and pass on the fix. Cut every step, flag, file and line whose removal keeps that result; if the defect needs one call, the program makes one call. A reader should see the defect at a glance.

**The reproduction is self-contained.** A stranger on a clean machine with only Docker (or QEMU) and network access must get the same result by pasting it. It must not depend on anything local to us: no checkouts, worktrees, `.work/` or `.out/` paths, locally built binaries or images, caches, registries or mirrors only we can reach, environment variables, credentials, dotfiles, or files the report does not inline or fetch by pinned URL and checksum. If it needs a file, inline it (heredoc) or fetch it by full commit or checksum.

## Shape

- **Title**: a Conventional Commits subject for both issues and pull requests, even where the project's own titles use another style: `type(scope): subject`, lowercase imperative or defect statement, at most 72 characters, no trailing period. An issue uses `fix(scope): <defect>` (`fix(vz): warm forks of running linux guests cannot reach their network`); a fix pull request uses `fix(scope): <change>` (`fix(vz): give each linux guest its own vmnet network`). Take the scope from the affected component.
- **Body**, in this order. Omit a section that has nothing verified to say.
  1. **Summary**: one paragraph naming the defect and its consequence, pinned to `OWNER/REPO@<40-hex commit>`, with `path:line` links at that commit. Name a release only alongside its commit.
  2. **Environment**: one line, listing only what bears on the defect, with exact versions: OS release and architecture, `uname -sr`, the relevant toolchain (`rustc 1.99.1 (<hash>)`, `clang 23.1.3`), and the CPU model or flags or the QEMU version, machine and `-cpu` when the defect depends on them.
  3. **Reproduction**: the commands, then the smallest self-contained, pinned environment that exercises the defect.
     - Default to a Dockerfile. Pin the base image by digest and fetch sources by full commit (`ADD https://codeload.github.com/OWNER/REPO/tar.gz/<sha>`).
     - When the defect depends on the CPU, kernel or devices, use QEMU (for example TCG with `-cpu Haswell,-bmi2`), with any guest image pinned by checksum. A Dockerfile that builds the QEMU run is fine.
     - The final step asserts the defect, so it fails on the base commit and passes on the fix.
     - Paste the decisive output lines verbatim.
  4. **Fix** (pull requests only): what changed and why, in at most three sentences, naming `laputa-systems/REPO@<40-hex commit>` when it is a fork candidate.
  5. **Tested**: that the shown reproduction ran unchanged against both commits, plus the project's own checks that passed. Add a benchmark table only when the change can affect performance, with method, sample count and spread.
  6. End with the line `Regression bisection available upon request.` Do not bisect for the report.

## Wording

- No hedges or unexercised scope: no "some", "may", "probably", "older versions", or CPU, OS or configuration classes the reproduction did not run.
- A claim the reproduction cannot show needs a `path:line` at the pinned commit, or it is cut.
- No "What/Why/How" headings, background essays, thanks, or restating the title.

## Before filing

1. Confirm it still fails on the tip of the upstream default branch: run the reproduction against that commit, and pin the report to it (cite the release commit too when the consumer pins a release).
2. Search the upstream tracker (open and closed issues and pull requests) for duplicates. A duplicate does not stop the report when ours adds a better reproduction or a fix; link it in the summary ("Same defect as #N; this adds a minimal reproduction and a fix.").
3. Minimize: remove each step, line and dependency in turn and keep only those whose removal changes the result.
4. Run the reproduction exactly as pasted, against the base and the fix, from an empty directory with `docker build --no-cache` (or a fresh QEMU scratch directory) and no local build context beyond the pasted files. Confirm the quoted output matches.
5. Check that every commit is 40 hex characters and every image is pinned by digest.
6. Post only where you are allowed to. Repositories outside `joshuarli` and `laputa-systems` need Joshua's explicit consent per post; otherwise file it as an `Upstream draft:` issue in the `laputa-systems` fork (see `~/.agents/instructions/owned-tools.md`).

**Report:** the report's URL or the draft text, the reproduction runs (base failing, fix passing) with their decisive lines, and anything cut for lack of evidence.
