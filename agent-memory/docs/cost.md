# Where usr-memories spends money

The `usr-memories` Worker runs on the Workers Paid plan ($5 a month). Almost
everything it uses fits inside that plan's allowances. The exception is D1 rows
written, which `commitSnapshot` drives. This document explains why, using the
numbers measured on 2026-11-05.

## Usage against the plan

The figures come from the `stats` dashboard's collected history (about 73 hours,
from 2026-11-01) projected to 30 days. D1 rows written come straight from
`events.d1Queries`. Prices are Cloudflare's list prices on 2026-11-05.

| Component | Used (30-day rate) | Included | Cost over the plan |
| --- | --- | --- | --- |
| Worker requests | 1.5M | 10M | $0 |
| Worker CPU | 10.5M ms | 30M ms | $0 |
| D1 rows read | 1.7B | 25B | $0 |
| D1 storage | 0.91 GB | 5 GB | $0 |
| R2 storage | 6.1 GB, 95,457 objects | 10 GB-month | $0 |
| R2 operations | 1.25M | 1M Class A, 10M Class B | at most $1.13 |
| D1 rows written | see below | 50M | $1 per million |

R2 operations have no Class A and Class B split in the analytics. The bound
assumes every operation is a Class A `PUT /sync/objects`, which the backfill made
most of them.

## D1 rows written

D1 rows written in November, by UTC day:

| Day | Rows written | What happened |
| --- | --- | --- |
| Nov 1 | 4.2M | backfill |
| Nov 2 | 15.8M | backfill, 10 snapshots |
| Nov 3 | 6.3M | 16 snapshots |
| Nov 4 | 66.4M | every snapshot commit failed |
| Nov 5, to 01:30 | 4.1M | failing, then the mirror was paused |
| Month so far | 96.8M | 46.8M over the allowance |

### A successful snapshot rewrites every object row

`commitSnapshot` in `cloudflare/src/db.ts` inserts one `snapshot_object` row for
every object the snapshot references, 32 rows per statement. D1 bills an extra
written row for each index a write touches. `snapshot_object` has two: its
primary key and `snapshot_object_plaintext`. Each object therefore costs 3 rows
written, so a full `INSERT` statement costs 96. The commit also runs
`UPDATE remote_object SET last_referenced_at = ...` for every referenced digest.

On Nov 3, 16 snapshots of about 75,000 objects each wrote 6.3M rows, about
400,000 per snapshot. At that pace the mirror writes about 190M rows a month, or
about $140 over the allowance. The cost grows with both the object count and how
often sessions change, because each sync that changes a generation commits a
new snapshot of the whole list. The database itself stays small (it grew 13 MB on
Nov 4) because retention deletes old snapshots, so storage never shows the
churn.

### A failed commit is paid for on every retry

From 2026-11-03 22:22 UTC every `commitSnapshot` batch failed with an error the
Worker reports as `snapshots.commit` in `D1DatabaseSessionAlwaysPrimary._sendOrThrow`.
The batch rolls back, so no snapshot lands. D1 analytics still count every row
the batch wrote before it failed. `com.josh.agent-sessions-mirror` runs
`agent-sessions mirror sync` every 15 minutes and retries the commit each time,
so the whole object list was rewritten about three times per run. That is the
66.4M rows on Nov 4, a 30-day rate of about $2,000.

Cloudflare's pricing page does not say whether rolled-back rows are billed. If
the billing page's November D1 rows written is near 97M, they are. If it is
near 30M, they are not, and the Nov 4 failure cost nothing beyond the allowance.

## Pausing the mirror stops the spend

The mirror LaunchAgent was unloaded on 2026-11-05 at 01:24 UTC with
`launchctl bootout gui/$(id -u)/com.josh.agent-sessions-mirror`. The plist stays
in `~/Library/LaunchAgents`. While it is unloaded no recovery snapshot is taken,
and new sessions stay local-only. To resume, run
`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.josh.agent-sessions-mirror.plist`.
Resume only after USR-21 is fixed, or the failing commit starts rewriting rows
again on the first run.

## Watching it

The `stats` project page for `usr-memories` prices D1 rows written per
statement in its cost ledger, and its D1 widget charts rows written per bucket.
An `INSERT INTO snapshot_object` line that dominates the ledger is the signal
that snapshots are being rewritten faster than expected.
