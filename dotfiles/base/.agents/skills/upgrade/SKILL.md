---
name: upgrade
description: "Use for /upgrade to update repository dependencies and explicit pins to newest stable versions, then run focused checks. Investigate a bump only when an upgrade causes a check to fail."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Upgrade

Update every dependency and explicit version pin to its newest stable release, then run focused checks.

## Rules

- **Whole repo, all ecosystems.** Find every manifest and lockfile, plus toolchain, runtime, action, container, and script pins. List pins that stay unchanged and why. A pin a skill marks intentional (Solid 2's release candidate in `refactor-ts`) stays. Never change a pinned Rust nightly unless the user explicitly asks.
- **Newest means newest stable.** Use package-manager update commands or published version metadata to select the newest stable release. Do not stop at the range already allowed by a manifest.
- **Update before investigating.** Do not read release notes, migration guides, issues, or source for a bump before applying it, and do not audit call sites or launch scouts first. Let package managers resolve transitives, then review the lockfile diff as a group.
- **Investigate upgrade-caused failures only.** When a focused check fails, reproduce it and decide whether an upgrade caused it. Inspect only the changed dependencies that could explain it, and use upstream material to find the cause. Do not research unrelated bumps.
- **Fix failures at the source** with the smallest change that resolves the reproduced failure. If a fix changes a public contract or cannot be made safely within the request, explain the blocker and ask the user.
- **Keep tool actions local.** Do not run workflows or commands that publish, deploy, or otherwise mutate external systems as upgrade verification. Use focused local checks and state what could not be exercised.
- **Stuck is a result.** Report a dependency that cannot be upgraded or a check that remains failing, with the observed blocker.

## Steps

1. **Inventory and baseline.** Find manifests, lockfiles, and explicit pins. Run the narrowest relevant checks and record existing failures.
2. **Update.** Apply newest stable releases through each ecosystem's package manager. Update explicit pins in every place that owns them.
3. **Check.** Run the narrowest relevant tests, builds, and type checks.
4. **Verify.** Re-run checks after fixes. Confirm lockfiles are consistent and remove dependencies the project no longer uses. Follow any performance gate in AGENTS.md, including its readiness check.
5. **Docs.** Update version mentions, install instructions, and examples made stale by the upgrades.

Never push.

**The test:** every dependency and pin is at its newest stable release or listed with the reason it stayed, and the focused checks match the baseline.

**Report:** Say what changed and which pins stayed fixed. Report check results against the baseline. List checks not run and why. Report performance measurements required by repository gates.
