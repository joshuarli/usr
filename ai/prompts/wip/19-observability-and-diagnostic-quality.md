# Observability and Diagnostic Quality

You are improving this codebase so failures, state transitions, external operations, and performance-relevant behavior are diagnosable without reading source code or attaching a debugger.

The goal is **high-signal observability**: the right information, at the right boundary, with stable semantics and low noise.

Scope: logging, tracing, metrics, diagnostics, debug modes, status surfaces, error reporting, and operational state transitions.

Applicability: Apply this prompt only when the system has non-trivial runtime behavior that users/operators must diagnose without source-level debugging. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory logging, tracing, metrics, diagnostics, stderr output, structured events, debug modes, health/status commands, telemetry, and crash/error reporting
- identify duplicated messages and logs that restate the same event at multiple layers
- identify important state transitions with no visibility
- identify logs that omit relevant resource identifiers or operation context
- identify logs that include secrets, tokens, large payloads, or unstable/debug-only structure
- identify arbitrary `println!`, `eprintln!`, console logging, and ad hoc debug output
- identify operations whose failure cannot be attributed to a resource, phase, or dependency
- inspect test coverage for diagnostics where text/structure is part of the contract
- run the narrowest useful baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Define observability around operational questions and semantic boundaries

#### Define observability by question


For each important operation, ensure the system can answer questions such as:

- what operation failed?
- on what resource?
- during which phase?
- what external dependency was involved?
- was the failure retryable?
- how long did it take?
- what state transition occurred?
- what correlation/job/request identity ties related events together?

Do not emit data merely because it is available.

#### Log at semantic boundaries


Prefer logging where mechanism becomes application meaning.

Good:

```text
job lease acquired
configuration rejected
artifact upload failed
database migration completed
worker shutting down after cancellation
```

Avoid logging every internal helper call.

#### Avoid duplicate error reporting


If an error is logged at a lower layer and then propagated to a boundary that logs it again, determine which layer owns presentation.

Prefer:

```text
lower layers: return structured error
boundary: render/log once
```

Add lower-level logs only when they capture information that would otherwise be lost.

### 2. Use structured context, deliberate severity, and meaningful correlation

#### Make context structured


Use structured fields where supported:

```text
job_id
project_id
path
attempt
duration_ms
status
dependency
```

Prefer stable semantic fields over embedding everything in prose.

Do not over-structure tiny tools when simple diagnostics are clearer.

#### Distinguish severity deliberately


Define consistent semantics for:

- trace/debug
- informational lifecycle events
- warnings
- user/actionable errors
- invariant/critical failures

Do not label ordinary expected conditions as warnings or errors merely to make them visible.

#### Make identifiers useful


Use stable, meaningful correlation identifiers for operations that span:

- tasks
- retries
- child processes
- network calls
- database operations
- asynchronous stages

Do not generate IDs when the domain already has an appropriate identifier.

### 3. Measure actionable behavior while preserving causal context

#### Measure meaningful latency and counts


Metrics should answer operational questions.

Good candidates include:

- request/job duration
- queue depth
- retries
- failures by category
- work completed
- cache hit rate
- external dependency latency

Avoid vanity metrics with no operational decision attached.

#### Make diagnostics actionable


A diagnostic should tell the operator/user what failed and, where appropriate, what they can do next.

Prefer:

```text
failed to open project config `/x/y.toml`: permission denied
```

over:

```text
IO error
```

Avoid giant stack traces for ordinary user mistakes.

#### Preserve causal chains


Do not lose the underlying cause while adding application context.

Operator-facing diagnostics should be concise while debug/trace modes may expose deeper chains according to project conventions.

### 4. Keep secrets out and make debug behavior intentional

#### Keep secrets and payloads out of observability


Audit:

- authorization headers
- cookies
- environment variables
- tokens
- private keys
- request/response bodies
- user content

Redact or omit sensitive data by default.

#### Make debug modes intentional


If verbose/debug logging exists:

- define what additional information it reveals
- keep it deterministic where possible
- avoid changing program semantics
- prevent accidental secret disclosure

### 5. Test stable user/operator diagnostic contracts


Where diagnostics are a user-facing API, test:

- error category
- key context
- output stream
- exit/status
- stable structure

Avoid overspecifying incidental punctuation unless exact text is intentionally stable.


## Explicit anti-patterns

Do not:

- add logs to every function
- log the same propagated error at every layer
- dump raw structs or payloads indiscriminately
- use severity levels inconsistently
- emit secrets
- create metrics with no operational use
- rely on free-form strings when structured context is already available
- hide useful causal context behind a generic failure message
- make debug mode alter correctness semantics


## Verification

After editing:

- run representative success and failure flows
- inspect logs/diagnostics for duplication and missing context
- verify secrets are absent
- verify key state transitions are visible
- verify metrics/log fields have stable names
- verify error presentation happens at deliberate boundaries
- run focused diagnostic tests


- Distinguish failures that predate the work from regressions introduced by this change.

## Acceptance criteria

The work is complete only when:

- important operations and state transitions are diagnosable
- errors identify operation and relevant resource
- duplicate reporting is minimized
- structured context is used where it adds value
- severity semantics are consistent
- correlation identifiers exist where multi-stage work needs them
- useful causal chains are preserved
- secrets and large payloads are not leaked
- diagnostics remain concise and actionable
- observable output is tested where it forms part of the user contract

The architectural principle is: **observability should explain what the system did and why it failed, not narrate every line it executed.**
