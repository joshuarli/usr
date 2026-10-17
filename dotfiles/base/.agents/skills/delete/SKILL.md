---
name: delete
description: "Use when the user directs complete removal of a feature, subsystem, API, command, dependency, or format and expects the retired path gone. Skip dead-code discovery, routine artifact cleanup, and deleting user data."
---

# Delete

Deletion is complete when the retired capability and its support paths are gone. A direct request for complete removal authorizes the stated breaking change; it does not authorize unrelated data loss, deployment, or external effects.

## Rules

- **Bound the target.** Name what is being removed and what remains. Read repository instructions and follow them. Ask only if the target or a consequential side effect cannot be resolved from the request and repository.
- **Trace before cutting.** Inspect definitions, direct and indirect callers, public exports, runtime wiring, configuration, generated inputs, manifests, tests, fixtures, docs, persisted data, and wire formats. Search the retired name and inspect dynamic or cross-language boundaries that text search cannot prove.
- **Remove the whole path.** Delete the implementation and its exports, callers owned by the target, flags, fallbacks, aliases, adapters, old readers and writers, stale tests and fixtures, dead docs, configuration, and dependencies. Update remaining in-scope callers to the surviving canonical behavior. Do not leave commented-out code, tombstones, deprecation periods, dual paths, or old behavior for comparison.
- **Do not preserve compatibility.** Read [dead-code-archaeology](../dead-code-archaeology/SKILL.md) to classify consumers and persisted data. Its quarantine exception does not override an explicit request for complete removal: remove the old surface and report the break. Do not add aliases, shims, old-format readers, or fallback behavior to ease the transition.
- **Preserve data deliberately.** If in-scope persisted data must survive, convert it once to the surviving canonical format and remove the old runtime path. Do not silently discard user data or keep a recurring dual-format reader. If safe removal requires data loss or an external migration not authorized by the request, stop at that boundary and ask.
- **Prove the cut.** Search the live tree for retired names, symbols, keys, and formats after editing. Classify every remaining hit as unrelated or historical; inspect generated output and manifests where applicable. Keep tests for surviving behavior, remove tests that only assert the deleted contract, and run the narrowest verification required by repository instructions.

**The test:** no live execution path or supported surface implements the retired behavior, no compatibility path accepts or emits its old form, and every remaining match has a clear non-live owner.

**Reply:** what was removed, remaining historical or unrelated matches, verification run and not run, and any breaking contract or data migration.
