---
name: dead-code-archaeology
description: "Use when hunting dead code, stale fallbacks, completed feature flags, or legacy compatibility paths. Prove what is live, delete the rest, and quarantine what must stay."
disable-model-invocation: true
---

# Dead Code Archaeology

Historical complexity must justify its continued existence. Work on the scope named; sweep the whole repo only when asked.

- **Classify each suspect with evidence:** actively used, consumed externally, present in persisted data, needed for compatibility, needed for a migration, or dead. Check callers, tests, docs, scripts, config, and generated inputs. A compiler warning is a lead, not a verdict.
- **Delete dead code completely:** the implementation, its tests, config, docs, exports, feature gates, and compatibility glue. Leave no tombstone and no commented-out copy. Version control is the archive.
- **Migrate callers and delete the old API in the same change** rather than keeping both.
- **Quarantine compatibility only when a consumer is proven.** Mark it deprecated, name the canonical replacement, route it through the canonical implementation, and keep new code off it.
- **A fallback is suspect once its trigger is gone.** Verify the condition that justified it before removing it.
- **A completed rollout gets its final behavior and loses the flag,** the dual path, and the tests for the dead side.
- **Legacy readers may stay for old data. Old writers do not.** New writes use the canonical format.
- **Docs and comments describe the live system.** Remove references to deleted flags, APIs, and paths.

**The test:** for each survivor, name who calls it or which data needs it. If you cannot, it goes.

Do not delete compatibility code before checking external and persisted consumers. When unsure, report it as unproven rather than removing it.

**Reply:** what you deleted, what you quarantined and why, and what you could not prove either way.
