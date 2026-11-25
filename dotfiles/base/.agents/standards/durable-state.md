+++
name = "durable-state"
summary = "Durable state has explicit contracts: transactions follow invariants, the datastore enforces durable truth, formats are versioned compatibility commitments, each fact is stored once, and jobs are durable state machines with leases and idempotency."

[[trigger]]
paths = ["migrations/", "migration/", "*.sql", "*.proto", "*.avsc", "schema.*", "!*.md"]

[[trigger]]
paths = ["*", "!*.md", "!*.txt", "!*.rst"]
content = ['(?i)\b(CREATE|ALTER|DROP)\s+(TABLE|INDEX|VIEW)\b', '(?i)\b(transaction|savepoint|begin\s+immediate)\b', '\b(Serialize|Deserialize)\b', '\b(sqlite3|rusqlite|sqlx|diesel|psycopg|sqlalchemy|prisma|drizzle)\b', '\b(lease|leased_at|idempoten\w*)\b', '\bschema_version\b']

[examples]
match = ["db/migrations/0003_add_jobs.sql", "proto/api.proto", { path = "src/store.rs", text = "#[derive(Serialize, Deserialize)]\n" }, { path = "app/db.py", text = "import sqlite3\n" }]
skip = [{ path = "src/math.rs", text = "fn add() {}\n" }, { path = "docs/schema.md", text = "CREATE TABLE jobs\n" }]
+++

# Durable State

Durable state outlives the code that wrote it, so its contracts must be explicit.

## Code

- **Transactions follow invariants.** One transaction covers changes that must succeed or fail together. Domain code decides; one persistence boundary executes.
- **The datastore guards durable truth.** Use NOT NULL, UNIQUE, CHECK, and foreign keys for facts every write path must respect. Concurrent writers get an atomic update, a version check, or a lock, never a read assumed to stay current. Check existing data before adding a constraint.
- **A format is a contract.** Field names, discriminants, defaults, and null meaning are compatibility commitments. Choose the versioning strategy on purpose (version field, additive defaults, tagged variants, migrate on read or write), not "try the old shape, then the new". Decide whether unknown fields are rejected, ignored, or preserved. Absent, null, empty, and default stay distinct. Parsing is not validating. Keep one canonical writer: old readers may stay, old writers go. Derived serialization must not expose secrets or internals.
- **Store each fact once.** Constrain cardinality and uniqueness. Null means one specific absence. Core facts do not live in blobs. Name timestamps for the event (`leased_at`, not `timestamp`). Tenant scope is visible in every query. Migrations converge on one schema, never two equal authorities.
- **A job is a durable state machine.** Name the delivery guarantee: at-most-once, at-least-once, or effectively-once through idempotency. Exactly-once exists only inside a transactional boundary. Use explicit states, not booleans. A lease has an owner and a compare-and-set, so an expired worker cannot complete the job. Walk the crash windows: side effect before ack, claim before execute, result before status. Dedupe with durable keys scoped by operation, lifetime, tenant, and payload, never an in-memory flag. Retries follow `lifecycle-concurrency`.
- **A cache is derived state.** Invalidate it next to the mutation that makes it stale.

**The test:** kill the process between any two writes. The next start must reach a valid state without a human.

Test the failure windows, old-format fixtures (oldest supported, current, unknown field, malformed), and constraint rejection. The happy path proves little. Save the full migration suite for the end.

**Report:** the contracts you set or tightened, and any format or data compatibility impact.
