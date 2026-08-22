# Network and Protocol Robustness

You are improving this codebase so network communication has explicit timeout, retry, framing, validation, compatibility, cancellation, and partial-failure semantics.

The goal is to treat networks as unreliable asynchronous boundaries rather than local function calls.

Scope: HTTP/RPC/socket clients or servers, timeout/deadline policy, retries, framing, limits, connection lifecycle, authentication, and interoperability.

Applicability: Apply this prompt only when the subsystem communicates over a network or stream protocol whose failure and partial-I/O semantics matter. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory HTTP/RPC/socket clients and servers
- identify timeout configuration
- identify retry loops
- identify connection pooling
- identify body/message size limits
- identify streaming behavior
- identify protocol framing
- identify redirect behavior
- identify authentication
- identify status-code/error mapping
- identify cancellation
- identify idempotency
- identify reconnect logic
- identify partial reads/writes
- inspect interoperability tests
- run baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Define deadlines and idempotency-aware retry policy

#### Define timeout semantics


Distinguish where relevant:

- connect timeout
- request deadline
- read timeout
- idle timeout
- overall operation deadline

Avoid infinite waits by accident.

#### Retry only safe operations


Retry policy must consider:

- idempotency
- whether bytes may already have been accepted
- server status
- transport failure phase
- deadline
- backoff and jitter

Do not retry every network error.

### 2. Bound peer-controlled data and handle framing/partial I/O

#### Bound message/body sizes


External peers can control resource consumption.

Define limits for:

- headers
- messages
- request/response bodies
- decompression expansion
- buffered streaming data

#### Validate framing and completeness


For stream protocols, handle:

- partial reads
- partial writes
- message boundaries
- EOF
- truncation
- malformed length fields

Never assume one read equals one message.

### 3. Propagate cancellation and own connection lifecycle

#### Preserve cancellation/deadlines


Propagate caller cancellation and deadlines through downstream network operations where supported.

#### Define connection lifecycle


For pools/reconnects:

- max lifetime
- idle behavior
- broken connection detection
- shutdown
- TLS/session behavior where relevant

### 4. Keep protocol failures and redirect/auth behavior structured

#### Make protocol errors structured


Distinguish:

- transport failure
- timeout
- malformed peer response
- authentication failure
- application rejection
- rate limit
- server failure

#### Treat redirects and endpoint changes deliberately


For HTTP, define whether redirects are followed and what happens to credentials/method/body.

### 5. Test real interoperability and prevent retry storms

#### Test interoperability, not only mocks


For protocol behavior, use real local servers/peers or fixtures where practical.

Mocks should not be the only proof of protocol correctness.

#### Protect against retry storms


Use bounded backoff, jitter where appropriate, and deadlines.

Coordinate retries with concurrency/backpressure policy.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- treat network calls like infallible local calls
- retry non-idempotent operations blindly
- omit timeouts
- buffer unbounded bodies
- assume reads/writes are complete
- collapse all failures into "network error"
- ignore cancellation
- test only against mocks


## Verification

After editing:

- Run the nearest hard judge for HTTP/RPC/socket clients or servers, timeout/deadline policy, retries, framing, limits, connection lifecycle, authentication, and interoperability: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit timeouts, idempotent retries, body/message limits, partial I/O/framing, cancellation, connections, structured protocol errors, redirects/auth, and real interoperability tests; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- timeout/deadline semantics are explicit
- retries are bounded and idempotency-aware
- message/body sizes are bounded where necessary
- partial I/O and framing are handled correctly
- cancellation propagates
- connection lifecycle is deliberate
- protocol errors preserve meaningful categories
- redirect/auth behavior is defined where relevant
- real interoperability tests protect important protocol contracts

The architectural principle is: **a network boundary must assume delay, duplication, truncation, reordering, and failure—not local-call semantics.**
