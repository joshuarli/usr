# Workers observability SQL: verified facts

- `logs.workersLogs`, R2, and D1 rows are unweighted: use `COUNT(*)` and plain `SUM`. Their `sampleInterval` is a stamp equal to `1/headSamplingRate`, not a weight. Weighting by it inflated counts by 4 to 10 (stats commit `84a6fe5`).
- Durable Object invocations are the exception and use `SUM(sampleInterval)`.
- A named stateless entrypoint (`$workers.entrypoint` set and not `default`) is a loopback `ctx.exports` or service binding call. It is not billed as a request, but its CPU is billed.
- No entrypoint means a top-level fetch. `default` means a cron invocation.
- `ORDER BY` needs a `LIMIT`.
- `quantile` and `splitByChar` are unsupported; use `APPROX_MAX` and post-process locally.
- Escape `$` in shell strings, and pipe the results through `jaq`.
