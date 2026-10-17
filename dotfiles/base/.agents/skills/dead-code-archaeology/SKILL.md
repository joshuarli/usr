---
name: dead-code-archaeology
description: "Apply when investigating whether code is dead or a compatibility path still has consumers, or when adding a compatibility path, deprecated alias, or feature flag for old consumers. Skip owner-directed complete removals without compatibility; use delete."
---

# Dead Code Archaeology

Historical complexity must justify its continued existence.

Owner-directed complete removals without compatibility belong to `delete`. Use this skill to establish liveness and consumer evidence; an explicit no-compatibility request rules out quarantining the old path.

- **Classify each suspect with evidence:** actively used, consumed externally, present in persisted data, needed for compatibility, needed for a migration, or dead. Check callers, tests, docs, scripts, config, and generated inputs. A compiler warning is a lead, not a verdict.
- **Delete dead code completely:** the implementation, its tests, config, docs, exports, feature gates, and compatibility glue. Leave no tombstone and no commented-out copy. Version control is the archive.
- **Migrate callers and delete the old API in the same change** rather than keeping both.
- **Quarantine compatibility only when a consumer is proven or the user asks,** the one exception to deleting rather than deprecating. Mark it deprecated, name the canonical replacement, route it through the canonical implementation, and keep new code off it.
- **A fallback is suspect once its trigger is gone.** Verify the condition that justified it before removing it.
- **A completed rollout gets its final behavior and loses the flag,** the dual path, and the tests for the dead side.
- **Legacy readers may stay for old data. Old writers do not.** New writes use the canonical format.
- **Docs describe the live system, and no comment mentions what was removed.** Remove references to deleted flags, APIs, and paths. Quarantined compatibility is marked by its name, a language deprecation attribute, and its removal condition in the reply or a failing check, not a comment.

**The test:** for each survivor, name who calls it or which data needs it. If you cannot, it goes.

Do not delete compatibility code before checking external and persisted consumers. When unsure, report it as unproven rather than removing it.

**Reply:** what you deleted, what you quarantined and why, and what you could not prove either way.
