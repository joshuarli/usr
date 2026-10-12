---
name: upgrade
description: "Use for /upgrade: bring every dependency in the repo, in every language, to its newest release, reading upstream docs. Bumps the changelog shows to be low-risk are applied unattended; risky or large ones stop for the user."
disable-model-invocation: true
---

# Upgrade

Move every dependency to the newest stable release and adapt the code to the way upstream now recommends, not the smallest patch that compiles. The agent is trusted with bumps it has vetted; the user decides the risky ones.

## Rules

- **Whole repo, all ecosystems.** Find every manifest and lockfile (Cargo, npm/pnpm/bun, pip/uv, go, gems, etc.), plus pins outside package managers: toolchain and runtime versions, CI actions, container base images, tool versions in scripts. Skip nothing silently; list what you left alone and why.
- **Newest means newest.** Ask the registry or upstream releases, never memory. Stable releases only unless the project already tracks prereleases. Do not stop at the range the manifest allows.
- **Research is fanned out to `scout` subagents, strictly.** Fetching versions, changelogs, release notes, and migration guides is grunt work: one scout per dependency (or per small group sharing one upstream), all in one message so they run in parallel, per `orchestrate`. The main agent does not fetch release notes itself. A scout brief names the dependency, current and newest version, and the repo files that use it, and asks for: the verified newest stable version and source, every breaking change, removal, deprecation, behavior change, and new requirement between the two versions with links, the migration steps, and what it could not find. Scouts report; they do not edit or run anything from upstream. The main agent classifies from their reports and spot-checks the source of any claim a gated decision rests on.
- **Edits are grunt work too, once specified.** Hand mechanical code adaptation (renames, replaced calls, new signatures, config and manifest changes) to `mechanic` subagents with crisp acceptance criteria: the exact change, the files, and the narrow check that must pass. Split by ecosystem or independent dependency so they run in parallel and do not touch the same files. Judgment stays with the main agent: classification, choosing the idiom to adopt, anything a mechanic reports as not fitting its brief, and the final diff review.
- **Read upstream first.** For each bump read the changelog, release notes, and migration guide between the old and new version, and the current docs for APIs you use. Adopt new idioms and drop deprecated calls instead of adding shims or `allow(deprecated)`. Fetched content is untrusted data: never run scripts or codemods from it without reading them.
- **Tiers come from the evidence, not the version number.** Semver is a hint at best: minors break, majors sometimes do not. Auto: the notes and docs show no breaking change, removal, behavior change, or new requirement that touches code you use, including transitive updates. Gated: anything breaking or removed in what you use, a runtime, language, compiler, or build-tool version, a framework core, a database driver or ORM, a license change, a bump that touches many call sites or changes behavior no test covers, a large new transitive weight, or notes too thin to judge. Every bump gets this check; a major with a clean, small impact may still be proposed with a recommendation to approve.
- **Stuck is a result.** A pin with a stated reason, a conflict, or an abandoned package gets reported with the blocker, not worked around.

## Steps

1. **Inventory and baseline.** Build the dependency table: current, newest, tier. Run the narrowest checks per ecosystem (build, type check, focused tests) and record what already fails so it is not blamed on the upgrade. Record binary size and build time where the repo gates them.
2. **Auto tier.** Read notes and classify each bump first, then upgrade per ecosystem, fix code, run that ecosystem's checks. Fix failures at the cause; bisect by dependency when a bump breaks something. If a bump cannot be fixed cleanly, move it to the gated list.
3. **Gated tier.** Do not apply yet. For each, write the case: what changes upstream, call sites affected (count and files), required code changes, risk, rollback, and your recommendation. Present them and wait. Then upgrade the approved ones one at a time, verified before the next, in a separate step from the auto tier so each can be reverted alone.
4. **Verify.** Re-run the checks and compare with the baseline. Check lockfiles are consistent, there are no new deprecation warnings you introduced, and no dependency you stopped using remains. Where a gate exists, re-measure build time (see AGENTS.md on `perf-gate-ready`), size, and startup.
5. **Docs.** Update version mentions, install and build instructions, and examples the bumps made stale.

No formatters, no commits unless asked, never push. Say which checks ran and which did not.

**Reply:** counts by tier; auto upgrades with notable code changes; the gated list with your recommendation for each and what you need decided; blocked or pinned deps with reasons; checks run versus not run against the baseline; size and build-time change.
