---
name: jank-audit
description: Audit a software product for concrete user-facing rough edges, confusing flows, weak feedback, and inconsistent behavior. Use for broad UX or product-polish audits. Skip ordinary code review, subjective visual critique, and single-flow bug reports.
---

# Jank Audit

Find user-visible friction that materially slows, confuses, blocks, or surprises people using the product. Treat this as an audit, not an implementation request.

## Audit

1. Read repository instructions and the product's entry points, stated workflows, and relevant code. Set a practical scope from the request; do not turn a product audit into an unrelated architecture or style review.
2. Trace important user journeys from their visible affordance through input handling and state changes to the resulting screen, feedback, and persistence. Include relevant input modes and failure or recovery paths.
3. Use the cheapest available observation that can establish behavior. Run the product or inspect existing captures only when the project supports it safely and the observation adds evidence. Distinguish observed behavior from conclusions inferred from code.
4. Keep a finding only when you can show the triggering situation, the user-visible consequence, and the code or observation that supports it. Prefer defects, dead ends, missing feedback, misleading instructions, inconsistent controls, and unnecessarily difficult workflows over personal taste.
5. Rank findings by user impact and likelihood. Merge findings with the same root cause. Give each finding a stable number, a short title, priority, evidence with file and line references, and a concrete recommendation.
6. State scope and meaningful limits, such as untested input devices or code-only conclusions. Do not invent findings to fill a quota.

## Stop for selection

Do not edit code, docs, configuration, or tests during the audit. Return the numbered findings and wait for the owner to select which items to fix or skip. A request to audit does not authorize implementation. After the owner selects items, implement only those items and follow the repository's instructions for the changes.

**Reply:** report the audit scope, numbered findings from highest impact down, what you observed versus inferred, and what you did not inspect or run. End by asking which finding numbers the owner wants fixed or skipped. Do not start fixes in the same turn.
