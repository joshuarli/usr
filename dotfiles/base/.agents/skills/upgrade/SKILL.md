---
name: upgrade
description: "Use for /upgrade to update repository dependencies and explicit pins to newest stable versions, then run focused checks. Investigate a bump only when an upgrade causes a check to fail."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Upgrade

Update every dependency and explicit version pin to its newest stable release. Run focused checks after updating. Investigate a bump only when an upgrade causes a check to fail.

## Rules

- **Whole repo, all ecosystems.** Find every manifest and lockfile, plus toolchain, runtime, action, container, and script pins. List pins that stay unchanged and why. Never change a pinned Rust nightly unless the user explicitly asks.
- **Newest means newest stable.** Use package-manager update commands or published version metadata to select the newest stable release. Do not stop at the range already allowed by a manifest.
- **Update before investigating.** Do not read release notes, migration guides, issues, or source code for a dependency bump before applying it. Do not audit call sites or launch scouts before the update. Let package managers resolve transitives, then review the lockfile diff as a group.
- **Investigate upgrade-caused failures only.** When a focused check fails, reproduce it. Determine whether an upgrade caused it. Inspect only changed dependencies that could explain the failure. Use upstream material to find the cause and fix. Do not research unrelated bumps.
- **Fix failures at the source.** Make the smallest change that resolves a reproduced failure. Do not add compatibility shims, suppressions, or fallback behavior to avoid understanding it. If a fix changes a public contract or cannot be made safely within the request, explain the blocker and ask the user.
- **Keep tool actions local.** Do not run workflows or commands that publish, deploy, or otherwise mutate external systems as upgrade verification. Use focused local checks and state what could not be exercised.
- **Stuck is a result.** Report a dependency that cannot be upgraded or a check that remains failing, with the observed blocker.

## Steps

1. **Inventory and baseline.** Find manifests, lockfiles, and explicit pins. Run the narrowest relevant checks and record existing failures.
2. **Update.** Apply newest stable releases through each ecosystem's package manager. Update explicit pins in every place that owns them. Leave pinned Rust nightlies unchanged.
3. **Check.** Run the narrowest relevant tests, builds, and type checks. If one fails, reproduce it before researching the changed dependency that could explain it.
4. **Verify.** Re-run checks after fixes. Confirm lockfiles are consistent and remove dependencies the project no longer uses. Follow any performance gate in AGENTS.md, including its readiness check.
5. **Docs.** Update version mentions, install instructions, and examples made stale by the upgrades.

Do not run formatters. Commit only when asked. Never push. Say which checks ran and which did not.

**Report:** Say what changed and which pins stayed fixed. Report check results against the baseline. List checks not run and why. Report performance measurements required by repository gates.
