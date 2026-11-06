---
name: audit-implicit-state-machine
description: "Apply when asked to audit, find, or inventory implicit, hidden, or latent state machines in an application or codebase, or when boolean flags and option soups suggest unmodeled lifecycle transitions. Skip implementing fixes (use make-invalid-states-unrepresentable or lifecycle-concurrency), single-type reviews, and routine bug investigations."
---

# Audit Implicit State Machines

Discover, classify, and document implicit state machines across a codebase. An implicit state machine coordinates lifecycle phases, modes, or protocols through boolean flags, optional fields, magic strings, ad-hoc closure state, or distributed collections rather than explicit sum types (enums or discriminated unions).

Treat this as an audit and inventory skill. Do not refactor code or implement fixes during the audit unless explicitly instructed.

## The Five Archetypes

Search for these five structural patterns:

1. **Boolean Soup:** Two or more boolean flags representing mutually exclusive lifecycle phases or modes (e.g., `is_loading`, `is_saving`, `has_error`, `is_dirty`, `is_conflict`). $N$ booleans permit $2^N$ states for what is usually a linear or small set of domain phases.
2. **Option Soup & Nullable Bundles:** Interdependent nullable fields where the presence or absence of one field depends on the value of another (e.g., `status?: string`, `result?: T`, `error?: E`, `started_at?: number`, `completed_at?: number`).
3. **Magic Strings in Persisted or Wire Contracts:** Lifecycle status stored as untyped or loose strings in databases, files, or message payloads (e.g., `"prepared"`, `"pending"`, `"accepted"`, `"conflict"` in SQLite or JSON) without exhaustive compile-time verification.
4. **Distributed Concurrency & Timer State:** Asynchronous lifecycle state split across collections, timeouts, and cancellation handles (e.g., a pending map, a timer map, and an in-flight promise map coordinated through manual callbacks).
5. **Closure-Bound Interaction State:** UI controls, widgets, or event handlers tracking multi-step user interactions via local closure variables (e.g., `titleAtFocus`, `canceled`, `submitOnEnter`) alongside DOM events.

## Where to Look

Audit these architectural boundaries in order:

- **Application & Workspace Lifecycles:** App bootstrapping, authentication gates, active tenant/vault/project switching, shutdown, and disposal.
- **Entity & Document Mutation Lifecycles:** Unloaded, loading, clean, dirty, saving, pending materialization, conflict, and tombstoned states.
- **UI View Modes & Modals:** Overlay hosts, command palettes, search dialogs, find-in-page, side panels, inspector diffs, and context menus.
- **In-Place Editing & Drag Workflows:** Inline renaming, slash menus, block dragging, drop targets, and settle animations.
- **Media & Asset Pipelines:** Pasted media encoding, optimistic local preview widgets, background upload, retry, revocation, and cleanup.
- **Tooltip & Hover Cards:** Debounced hover timers, in-flight abortable fetches, active display, and leave grace periods.
- **Reconciliation & Synchronization:** Filesystem reconciliation pipelines, change classification (matched, moved, edited, deleted, collided), and two-phase commits.
- **Network & Protocol Streams:** Server-sent events (SSE), WebSocket connections, replay backlogs, reconnection backoffs, and stream lease revocations.
- **Handshakes & Import Protocols:** Multi-step browser extension messaging, challenge-response ceremonies, and ticket consumption.

## Analysis Formula

For every discovered candidate, document:

1. **Location:** File path and exact line range of the fields and transitions.
2. **Current Representation:** The struct, type, closure variables, or database columns currently storing the state.
3. **Latent States & Transitions:** The real domain states and the events or triggers that move between them.
4. **Permitted Invalid States:** Count the state space ($2^N \times \text{nullables}$). Identify specific impossible or contradictory combinations the current types allow (e.g., `saving: true` when `document == null`, or `tombstoned = 1` with an `unresolved` error).
5. **Concrete Failure Modes:** Trace observable runtime consequences: memory leaks (unrevoked blob URLs), UI glitches (duplicate backdrops or overlapping modals), race conditions, data loss, or permanent lockout (stuck pending flags).

## Output & Action

1. **Catalog:** Present findings grouped by subsystem (Frontend Workspace, Editor & UI, Backend Storage, Network Protocols).
2. **Prioritize:** Rank candidates by impact times likelihood:
   - **P1:** Reachable data corruption, security exposure, or permanent crash/lockout.
   - **P2:** Real defect, race condition, or architectural tax where invalid states cause incidents or complicate every change.
   - **P3:** Latent inconsistency, memory leak, or cleanup gap with clear payoff at scale.
   - **P4:** Minor type cleanup or localized optimization.
3. **Ticketing (when requested):** Convert findings directly into structured tickets using `todo` skill conventions in `TODO.md`. Link design RFCs for items requiring architectural consensus.
4. **Remediation Routing:**
   - For type-level fixes: route to `make-invalid-states-unrepresentable`.
   - For async/concurrency/timer coordination: route to `lifecycle-concurrency`.
   - For database/persisted schemas: route to `durable-state`.

**Report:** the audit scope, the implicit state machines found grouped by archetype and subsystem, their permitted invalid states and concrete failure modes, prioritized recommendations, and any tickets filed in `TODO.md`.
