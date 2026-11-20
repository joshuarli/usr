---
name: linux-capsule
description: "Use for /linux-capsule: prove a repository's development environment can be set up from scratch on a fresh Linux host by running its bootstrap and full checks in a pristine container from a clean clone, then fix what breaks until it passes. Skip release packaging, CI-only fixes (use green), and moving local work between machines (use settle)."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Linux capsule

Prove that a newcomer with a fresh Linux box, a clone and the repository's own docs reaches a passing build and test run. The capsule is a pristine distribution container. It is not the repository's CI image, which already contains the answers. Fix every gap in the repository so that the documented path works, then record that path.

## Establish the target

**Read what the repository already promises.** Read the README, contributor and development docs, agent instructions, `Makefile` or task runner, toolchain pins, `Dockerfile`s and CI workflows. The CI setup is evidence of what the build needs, not a substitute for a newcomer's path. List every external requirement: system packages, toolchains and pins, compiler wrappers and caches, linkers, assemblers, `pkg-config` libraries, Python or Node versions, and owner-specific tools on `PATH`. Grep build scripts (`build.rs`, `CMakeLists.txt`, `setup.py`, `package.json` scripts) and test code for `Command::new`, `which`, `pkg-config` and environment variables. Separate the requirements of the default build and test from optional workflows such as benchmarks, oracles, releases and cross builds.

**Pick the capsule.** Default to the current Ubuntu LTS image. Add the distributions the owner names, and the repository's own CI distribution as a second capsule when it differs. Run the host's native architecture so the run stays fast and faithful. Emulated runs prove that the build compiles and the tests pass, not performance. If the owner's target box has a different architecture, run that architecture as well, and say which runs were emulated.

## Run it

**Start from committed state only.** Commit your local changes first, without pushing. Mount the repository read-only, `git clone` it inside the container, and install only what the clone needs to fetch itself (`git`, `ca-certificates`). Use the repository's bootstrap script if it has one. Otherwise follow its docs literally. Run as root, and also as an unprivileged user when the docs assume `sudo` or the tests depend on file ownership.

**Keep evidence outside the container.** Mount a host directory under the repository's scratch area for logs. Do not wrap the run in `set -e` around the checks: record each step's exit code and keep its full log, so a failure leaves its cause behind. Run the repository's real gates, such as `make lint test`, not a hand-picked subset.

**Use caches only to iterate.** A build cache mounted from the host speeds up reruns while you diagnose. It also hides missing build-time dependencies, because cached build-script outputs skip the steps that need them. The final proof runs cold, from a fresh clone, with no mounted build cache.

## Fix forward

**Fix causes in the repository, not in the capsule.** Each failure is a defect in the newcomer path. Find its root cause before changing anything. Typical defects are host-specific configuration committed to the repository (cross-compile runners and linkers in `.cargo/config.toml`, macOS-only flags), mandatory owner tools such as a compiler wrapper that should be optional, undeclared system packages, version floors, and tests that assume a particular user or tool. Make owner conveniences optional rather than deleting them. Remove host-specific settings only after confirming that nothing else consumes them; CI often overrides them through environment variables. Never weaken or skip a correct test to make the capsule pass. If a test genuinely needs an external tool, gate it on that tool's presence the way the repository already does, and document the tool.

**Make the path one command.** Add or update a small idempotent bootstrap script, such as `scripts/setup-dev`. It installs the distribution packages for the verified families, the pinned toolchain, and the locked dependencies, and it fails clearly on an unverified distribution. Write a short development doc with the bootstrap command, a package table with each package's consumer, the measured cold-build cost, and the optional tools with how to obtain them. Link the doc from the README.

**Rerun until green, then once cold.** Each fix gets a new commit and a rerun of the failing step. When everything passes, run the final cold capsule from a fresh clone of the final commit.

## Verify and report

**The test:** a cold run in a pristine container, from a fresh clone of the pushed commit, follows only the documented commands and passes the repository's lint and test gates.

**Report:**

- the capsules run: distribution, architecture, native or emulated, and cold or cached;
- each defect found, its root cause and its fix commit;
- the bootstrap command and the docs that now describe it;
- final gate results with exit codes and the cold build time;
- requirements left optional or manual, such as credentials, owner tools and private corpora, and how to obtain each;
- what was not verified, such as performance on native hardware or untested distributions.
