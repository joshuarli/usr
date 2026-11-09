---
name: stats-improve
description: "Use for /stats-improve: find a performance or cost win in a Cloudflare project that ~/d/stats observes (stuff, stats itself, stats-observe, nanoshop-storied, usr-memories, ...) from its production metrics, prove it locally, deploy it, and confirm the effect in the same metrics. Extend ~/d/stats when the evidence it collects is not enough."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Stats Improve

Production metrics choose the work, a local reproduction proves the change, and the same production metrics confirm it after deploy. This skill applies to one named project at a time. With no project named, ask which one; `statsctl projects` lists them.

The skill grants deploy authority for the target project's Worker and for `~/d/stats` when the request asks for this workflow. It does not cover publishes, data deletion, or settings outside those Workers. Engineering method stays with [make-it-fast](../make-it-fast/SKILL.md) and [benchmark-checklist](../benchmark-checklist/SKILL.md); this skill owns the evidence loop around them.

## 1. Orient

Run commands from `~/d/stats` and read its `AGENTS.md`. `pnpm --dir cloudflare -s statsctl help workflow` is authoritative for `statsctl`.

```sh
pnpm --dir cloudflare -s statsctl projects
pnpm --dir cloudflare -s statsctl health --project P
pnpm --dir cloudflare -s statsctl cost --project P --window 24h --json > .work/tmp/P-cost.json
pnpm --dir cloudflare -s statsctl observe routes --project P --window 24h   # only for observed services
```

Find the project's repository: the one whose `cloudflare.config.ts` (or Wrangler file) names the Worker. Read its instructions, deploy target, and tests before editing. When P is `stats`, the repository is `~/d/stats`, the Worker deploys with `make stats-deploy`, and the tail consumer deploys with `make observe-deploy`.

Read the cost ledger before choosing a target. Split each line into its requests, CPU, and storage parts. A project billed mostly by request count gets nothing from CPU work, and a CPU line can still hide a latency problem. If health is not healthy, fix collection first; every later number depends on it.

## 2. Drill into raw events

`statsctl` aggregates. To ask a new question, query the same datasets directly. The account tag comes from `cf accounts list`.

```sh
A=$(cf -q accounts list | jaq -r '.[0].id'); S=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)
cf sql query --scope-account "$A" "SELECT attributes['\$workers.entrypoint'] AS ep,
  attributes['\$workers.event.request.headers.host'] AS host, invocationLabel AS label, httpStatus,
  COUNT(*) AS n, SUM(cpuTimeMs) AS cpu, SUM(wallTimeMs) AS wall
  FROM logs.workersLogs WHERE scriptName = 'WORKER' AND logType = 'cf-worker-event' AND timestamp >= '$S'
  GROUP BY ep, host, label, httpStatus ORDER BY n DESC LIMIT 10000 FORMAT JSON" > .work/tmp/q.json
```

Group the labels into route classes with `jaq`, then rank them by total CPU and total wall time, with per-request averages. The shape of the costs points to the cause:

- High wall time with low CPU means serial I/O.
- High CPU per request on a rare route means repeated computation worth caching.
- A large share of top-level requests means the requests are reaching the Worker at all.

Facts about this SQL surface, all of them verified:

- `logs.workersLogs`, R2, and D1 rows are unweighted: use `COUNT(*)` and plain `SUM`. Their `sampleInterval` is a stamp equal to `1/headSamplingRate`, not a weight. Weighting by it inflated counts by 4 to 10 (stats commit `84a6fe5`).
- Durable Object invocations are the exception and use `SUM(sampleInterval)`.
- A named stateless entrypoint (`$workers.entrypoint` set and not `default`) is a loopback `ctx.exports` or service binding call. It is not billed as a request, but its CPU is billed.
- No entrypoint means a top-level fetch. `default` means a cron invocation.
- `ORDER BY` needs a `LIMIT`.
- `quantile` and `splitByChar` are unsupported; use `APPROX_MAX` and post-process locally.
- Escape `$` in shell strings, and pipe the results through `jaq`.

For where the wall time goes inside one request, read a trace's spans:

```sh
T=$(date +%s000); F=$((T-3600000))
cf o11y telemetry query --query-id adhoc --view traces --timeframe-from $F --timeframe-to $T --limit 3 \
  --parameters-filters '[{"key":"$metadata.service","operation":"eq","type":"string","value":"WORKER"}]'
cf o11y telemetry query --query-id adhoc --view events --timeframe-from $F --timeframe-to $T --limit 20 \
  --parameters-filters '[{"key":"$metadata.traceId","operation":"eq","type":"string","value":"TRACE"}]' \
  | jaq -c '.. | objects | select(has("$metadata")) | .["$metadata"] | {spanName, startTime, endTime}'
```

Before treating a number as a finding, cross-check any total against a second source, such as `events.workersInvocations`, the stats history, or a known request count. Retract a claim the moment a second source contradicts it.

## 3. Choose, reproduce, change

Pick the line with the largest attainable effect and name its mechanism, for example "two serial R2 GETs, ~55 ms each" or "a 2.4 MB render at 188 ms CPU per miss". Reproduce it locally on production inputs: pull the real objects (`cf r2 objects get --bucket-name B KEY --text`) into `.work/tmp`, and time the built artifact with CPU time (`process.cpuUsage`), warm and cold.

Keep the reproduction as a durable benchmark in the repository's harness, not a scratch script. Use the production inputs as a committed fixture, run them at small, production, and heavy (about ten times production) scale, and track allocations; follow [refactor-benchmarks](../refactor-benchmarks/SKILL.md). The heavy tier is how superlinear work shows up before production grows into it.

Write the failing test first in the repository's own harness. A cache or memo must state its authority and its invalidation. Key it on immutable inputs (generation ids, the Worker version via `bindings.versionMetadata()`) instead of on time, and keep every documented freshness promise. A speculative read is used only when the authoritative read confirms it.

## 4. Validate locally, then deploy

Before deploying, all of these must pass:

- the repository's focused tests;
- its typecheck and lint;
- a deploy dry run (`cf deploy --prebuilt --dry-run`, or the repository's check target).

Record the baseline numbers and the live version id. Commit, deploy through the repository's target, run its deployed smoke check, and push.

## 5. Confirm in production

Compare per-request metrics by version on the same route class:

```sh
... SELECT attributes['\$workers.scriptVersion.id'] AS v, COUNT(*) AS n, SUM(cpuTimeMs) AS cpu, SUM(wallTimeMs) AS wall
    FROM logs.workersLogs WHERE ... AND <route class filter> GROUP BY v LIMIT 20 FORMAT JSON
```

Check the mechanism first in a few traces of the new version, for example two spans that now start together. Averages taken at different times move with upstream latency, so they need this check before you trust them.

For an aggregate cost claim, use `statsctl compare` or `statsctl verify` with a committed policy. Space deploys of the same project more than the comparison window plus one five-minute bucket apart. Otherwise the before window contains the previous deploy and the verdict is `confounded`. A lower monthly estimate is not a win (`statsctl help workflow`). Wait until the candidate side has enough events for the claim, and report its sample size. A change within noise is reported as unchanged.

## 6. Extend stats when the evidence is missing

If a question needed raw SQL that `statsctl` should answer, or a stats number turned out wrong, change `~/d/stats`:

- the fixed queries in `cloudflare/src/projects/queries.ts`;
- the parsers in `cloudflare/src/cloudflare/projects/parse.ts`;
- tests in `cloudflare/test/projects-*.test.ts`;
- `docs/architecture.md`.

Check it live with `node --experimental-strip-types cloudflare/scripts/check-analytics-sql.mjs` and `cloudflare/scripts/check-parity.mjs`. Deploy with `make stats-deploy`. A change to what a stored metric means is a contract change: use `!` and say how old history reads.

**The test:** a production metric named the problem, a local reproduction proved the fix, and the same metric moved after deploy by more than its noise.

**Report:**

- the metric and window that chose the work;
- the mechanism;
- the change;
- local evidence;
- the deployed version;
- before and after numbers with sample sizes, or "pending" with the command that settles them;
- any stats changes and contract changes.
