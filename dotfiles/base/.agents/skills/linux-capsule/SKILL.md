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

**Trace the branches a fresh host takes.** Build files often pick a target, toolchain or wrapper from the host: a `Makefile` that turns a glibc host into a musl target, or that uses a wrapper only when one is on `PATH`. Note which branch the capsule's distribution takes, and whether CI ever runs that branch. A default path that CI never runs is the likeliest to be broken. Check that dependency sources, including registry mirrors and source replacements, are reachable without credentials, or that the docs say how to get them. Follow the links on the newcomer path, such as the README's contributing link, and confirm each one resolves.

**Pick the capsule.** Default to `ubuntu:24.04`, the base most AI cloud environments run, even after a newer LTS ships. Add the distributions the owner names, and the repository's own CI distribution as a second capsule when it differs. Run the host's native architecture so the run stays fast and faithful. Emulated runs prove that the build compiles and the tests pass, not performance. If the owner's target box has a different architecture, run that architecture as well, and say which runs were emulated.

**Give the capsule Docker.** Assume AI cloud environments provide a Docker daemon, so a repository's Docker-based builds and tests belong on the default path and are not optional extras. Run the capsule `--privileged`, have the bootstrap install the distribution's Docker engine, and start `dockerd` inside it. Do not mount the host's Docker socket instead: the host daemon resolves bind mounts against host paths, so a nested `docker run -v` of the clone inside the capsule mounts the wrong directory or nothing. Images the repository pulls or builds count toward the cold cost.

## Run it

**Start from committed state only.** Commit your local changes first, without pushing. Mount the repository read-only, `git clone` it inside the container, and install only what the clone needs to fetch itself (`git`, `ca-certificates`). Use the repository's bootstrap script if it has one. Otherwise follow its docs literally. Run as root, and also as an unprivileged user when the docs assume `sudo` or the tests depend on file ownership. Git refuses a bind-mounted repository owned by another user ("dubious ownership"), so clone it with `safe.directory` set for that one path. A toolchain manager may not install a pinned toolchain implicitly; `rustup show` no longer does, so run `rustup toolchain install`, which reads `rust-toolchain.toml`. Leave `TMPDIR` at the distribution default. Tests that build throwaway projects often assume their temporary directories sit outside the workspace.

**Keep evidence outside the container.** Mount a host directory under the repository's scratch area for logs. Do not wrap the run in `set -e` around the checks: record each step's exit code and keep its full log, so a failure leaves its cause behind. Run the repository's real gates, such as `make lint test`, not a hand-picked subset. Create the unprivileged user before the run and make the log directory writable for it. Use a new log directory for each run instead of clearing the previous one. After the gates, `git status --porcelain` in the clone must print nothing. Any output is generated files that `.gitignore` does not cover, which a local `.git/info/exclude` hid on the owner's machine.

**Expect a slow host.** A cold capsule installs packages and builds everything, and a shared host makes it slower. Run it in the background and watch its logs. Do not time it as a benchmark.

**Use caches only to iterate.** A build cache mounted from the host speeds up reruns while you diagnose. It also hides missing build-time dependencies, because cached build-script outputs skip the steps that need them. The final proof runs cold, from a fresh clone, with no mounted build cache.

## Fix forward

**Fix causes in the repository, not in the capsule.** Each failure is a defect in the newcomer path. Find its root cause before changing anything. Typical defects are host-specific configuration committed to the repository (cross-compile runners and linkers in `.cargo/config.toml`, macOS-only flags), mandatory owner tools such as a compiler wrapper that should be optional, undeclared system packages, version floors, and tests that assume a particular user or tool. Make owner conveniences optional rather than deleting them. Remove host-specific settings only after confirming that nothing else consumes them; CI often overrides them through environment variables. Never weaken or skip a correct test to make the capsule pass. If a test genuinely needs an external tool, gate it on that tool's presence the way the repository already does, and document the tool.

**Make the path one command.** Add or update a small idempotent bootstrap script, such as `scripts/setup-dev`. It installs the distribution packages for the verified families, the pinned toolchain, and the locked dependencies, and it fails clearly on an unverified distribution. Write a short development doc with the bootstrap command, a package table with each package's consumer, the measured cold-build cost, and the optional tools with how to obtain them. Link the doc from the README.

**Bootstrap Python through buildlib.** When the build needs Python newer than the distribution ships, or the repository uses [laputa-systems/buildlib](https://github.com/laputa-systems/buildlib), do not depend on the distribution's Python, uv or pip. Vendor buildlib's `bootstrap/` shell shim. It downloads the owner's pinned [python-build](https://github.com/laputa-systems/python-build) CPython, verifies its size and SHA-256 before extracting, and runs buildlib's wheel from `PYTHONPATH`. python-build's Linux archive is linked against musl. On a glibc host, setup must install the distribution's `musl` package, and that package must be musl 1.2.5 or newer: Debian 13 and Ubuntu 26.04 ship it, Ubuntu 24.04 does not ([python-build#19](https://github.com/laputa-systems/python-build/issues/19)). Run the capsule on a distribution that meets that floor until the issue closes, and record the gap.

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

Capsule logs carry host paths and environment. Keep them in scratch, and redact them before committing any to a public repository.
