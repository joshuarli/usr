---
name: durable-state
description: "Apply when changing schemas, migrations, persisted or wire formats, transactions, concurrent writes to shared durable state, or retried and leased background jobs. Skip in-memory-only state."
---

# Durable State

Durable state outlives the code that wrote it, so its contracts must be explicit.

- **Transactions follow invariants.** One transaction covers changes that must succeed or fail together. Domain code decides; one persistence boundary executes.
- **The datastore guards durable truth.** Use NOT NULL, UNIQUE, CHECK, and foreign keys for facts every write path must respect. Concurrent writers get an atomic update, a version check, or a lock, never a read assumed to stay current. Check existing data before adding a constraint.
- **A format is a contract.** Field names, discriminants, defaults, and null meaning are compatibility commitments. Choose the versioning strategy on purpose (version field, additive defaults, tagged variants, migrate on read or write), not "try the old shape, then the new". Decide whether unknown fields are rejected, ignored, or preserved. Absent, null, empty, and default stay distinct. Parsing is not validating. Keep one canonical writer: old readers may stay, old writers go. Derived serialization must not expose secrets or internals.
- **Store each fact once.** Constrain cardinality and uniqueness. Null means one specific absence. Core facts do not live in blobs. Name timestamps for the event (`leased_at`, not `timestamp`). Tenant scope is visible in every query. Migrations converge on one schema, never two equal authorities.
- **A job is a durable state machine.** Name the delivery guarantee: at-most-once, at-least-once, or effectively-once through idempotency. Exactly-once exists only inside a transactional boundary. Use explicit states, not booleans. A lease has an owner and a compare-and-set, so an expired worker cannot complete the job. Walk the crash windows: side effect before ack, claim before execute, result before status. Dedupe with durable keys scoped by operation, lifetime, tenant, and payload, never an in-memory flag. Retries are bounded.
- **A cache is derived state.** Invalidate it next to the mutation that makes it stale.

**The test:** kill the process between any two writes. The next start must reach a valid state without a human.

Test the failure windows, old-format fixtures (oldest supported, current, unknown field, malformed), and constraint rejection. The happy path proves little. Run them by name, and save the full migration suite for the end.

**Reply:** the contracts you set or tightened, and any format or data compatibility impact.
