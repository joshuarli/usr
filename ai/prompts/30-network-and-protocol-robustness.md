# Network and Protocol Robustness

You are improving an existing codebase so network communication has explicit timeout, retry, framing, validation, compatibility, cancellation, and partial-failure semantics.

The goal is to treat networks as unreliable asynchronous boundaries rather than local function calls.

Preserve protocol compatibility unless explicitly changing it.

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

## 1. Define timeout semantics

Distinguish where relevant:

- connect timeout
- request deadline
- read timeout
- idle timeout
- overall operation deadline

Avoid infinite waits by accident.

## 2. Retry only safe operations

Retry policy must consider:

- idempotency
- whether bytes may already have been accepted
- server status
- transport failure phase
- deadline
- backoff and jitter

Do not retry every network error.

## 3. Bound message/body sizes

External peers can control resource consumption.

Define limits for:

- headers
- messages
- request/response bodies
- decompression expansion
- buffered streaming data

## 4. Validate framing and completeness

For stream protocols, handle:

- partial reads
- partial writes
- message boundaries
- EOF
- truncation
- malformed length fields

Never assume one read equals one message.

## 5. Preserve cancellation/deadlines

Propagate caller cancellation and deadlines through downstream network operations where supported.

## 6. Define connection lifecycle

For pools/reconnects:

- max lifetime
- idle behavior
- broken connection detection
- shutdown
- TLS/session behavior where relevant

## 7. Make protocol errors structured

Distinguish:

- transport failure
- timeout
- malformed peer response
- authentication failure
- application rejection
- rate limit
- server failure

## 8. Treat redirects and endpoint changes deliberately

For HTTP, define whether redirects are followed and what happens to credentials/method/body.

## 9. Test interoperability, not only mocks

For protocol behavior, use real local servers/peers or fixtures where practical.

Mocks should not be the only proof of protocol correctness.

## 10. Protect against retry storms

Use bounded backoff, jitter where appropriate, and deadlines.

Coordinate retries with concurrency/backpressure policy.

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
