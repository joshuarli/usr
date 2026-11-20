---
name: bug-report
description: "Apply when writing a bug report, an issue, an `Upstream draft:` issue in a laputa-systems fork, or a bug-fix pull request description, for any repository. Produces a short, exact report with a pinned reproduction that fails on the base and passes on the fix. Skip internal TODO tickets (use todo) and chat summaries."
---

# Bug Report

A report is short, exact and reproducible. Every sentence is a verified fact. One defect per report.

## Shape

- **Title**: `area: defect` in the project's convention, lowercase, no trailing period.
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

## Wording

- No hedges or unexercised scope: no "some", "may", "probably", "older versions", or CPU, OS or configuration classes the reproduction did not run.
- A claim the reproduction cannot show needs a `path:line` at the pinned commit, or it is cut.
- No "What/Why/How" headings, background essays, thanks, or restating the title.

## Before filing

1. Run the reproduction exactly as pasted, from a clean build, against the base and the fix. Confirm the quoted output matches.
2. Check that every commit is 40 hex characters and every image is pinned by digest.
3. Post only where you are allowed to. Repositories outside `joshuarli` and `laputa-systems` need Joshua's explicit consent per post; otherwise file it as an `Upstream draft:` issue in the `laputa-systems` fork (see `~/.agents/instructions/owned-tools.md`).

**Report:** the report's URL or the draft text, the reproduction runs (base failing, fix passing) with their decisive lines, and anything cut for lack of evidence.
