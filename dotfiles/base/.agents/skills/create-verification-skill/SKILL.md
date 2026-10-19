---
name: create-verification-skill
description: "Create or update a repository-local skill that verifies a project's real user-facing behavior with safe, repeatable evidence."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Create verification skill

Create or maintain a compact repository-local procedure for exercising a project's actual interface. Change verifier instructions and narrowly needed helpers only when they are within the user's requested scope. This workflow does not authorize product fixes, dependencies, home installation, or external writes.

## Rules

- **Discover before writing.** Read the target's agent instructions, documented commands, build and test entrypoints, local skills, fixtures, runtime boundaries, and available drivers. Follow an explicit verifier pointer first. Identify the interface users exercise: CLI, TUI, web, desktop, API, mobile, or library.
- **Reuse the owner.** Extend a relevant local verification skill when one exists. Otherwise create `.agents/skills/verify-<project>/SKILL.md` using the repository's current link and allowlist conventions. Preserve hand-written instructions.
- **Ground every step.** Reuse the current harness. Include exact commands and expected output. State broken baselines and unavailable tools without repairing unrelated code or inventing launch instructions.
- **Cover the whole journey.** Document scope and prerequisites, safe fixture boundaries, launch and readiness, a focused doctor, actions through the real public surface, expected results and persisted side effects, evidence and its limits, and cleanup of only resources created by this run.
- **Keep it small.** Do not add smoke tests or CI steps; the procedure is for an agent exercising the real interface by hand. Put a few useful journeys inline. Add a helper only when repeated work benefits from it. Make helpers executable, document their actual invocation, and exercise them. Do not create a generic test framework or exhaustive feature catalog.
- **Control effects.** Prefer explicit-only metadata when the verifier starts processes or mutates fixtures. Preserve project-specific metadata. A referenced skill provides a procedure, not permission for effects outside the request.
- **Prove and maintain.** Run one meaningful success path and one failure or negative path. Exercise cleanup after both, confirm evidence remains, then repeat a run to check for stale-state collisions. Update the skill when code changes its commands, fixtures, selectors, or assumptions.

**The test:** a fresh run can follow exact instructions through the public surface, observe the stated success and failure, clean up its own resources, retain useful evidence, and run again without collision.

**Report:** the skill and helpers changed, the journeys and evidence exercised, the surface and platform covered, what remains unverified, and any blocker.
