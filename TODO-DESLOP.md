Prefix: DSLP
Next: 13

Deslop campaign backlog ([plan](https://github.com/laputa-systems/stuff/blob/main/docs/campaigns/deslop.md), tier C). One agent works this file with the `deslop` skill: take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work the open P1 and P2 findings, then fill in `## Report` below.

## Report

The tooling pass is incomplete. DSLP-3 and DSLP-5 remain open: the existing ty profile reports 175 first-party diagnostics after excluding vendored PyYAML, and Vulture and Knip findings remain untriaged. [Scanner observations](docs/verification/deslop-scans.md) record the candidates and scope. The [test inventory](docs/verification/deslop-test-inventory.md) records fixture boundaries and unverified live and platform cases.

- **Types:** no new strict settings adopted; Python and TypeScript matching escape-hatch lines are 75 and 201. The full bridge profile passed with pinned declarations supplied in scratch.
- **Tests:** the inventory is complete. No mutation lane was added. The pinned offline fixture changes have failing-first checks. Branch coverage and a repeat flake baseline were not measured.
- **Dead code:** eight lines of unreferenced private pinact helpers removed; no dependency removed. Scanner triage is incomplete.
- **Bench outcomes:** the existing FX fixture entrypoint passed its numeric edit and numeric-string correction workloads with Node 26.13.1. It uses a loopback provider and cannot establish live runtime performance. Gate checks exited 0, but reported a hot external process; timing conclusions are deferred. DSLP-9 tracks missing representative CLI workloads. The `bench-pyramid` tool is unavailable (DSLP-10).
- **Findings:** DSLP-6 and DSLP-7 fixed; DSLP-8 remains open; DSLP-12 records a null companion pin accepted by validation. The Intercom test inherited a worker role marker; its coordinator fixture now clears role markers. The bridge fixture now rejects a mismatched Node release.
- **Verification:** `make test` and `make lint` passed with isolated home and config, Python 3.15.1 and Node 26.13.1. Earlier runs exposed Python 3.9 and missing scratch Git identity; both environment prerequisites were corrected for the passing run. CI minutes, coverage, mutation counts, and live provider behavior are unmeasured.
- **Review:** cumulative diff reviewed. The stale SDK failure note in AGENTS.md was corrected. No other demonstrated regression was found. No shared-file change was made; unavailable audit tools are recorded in DSLP-10.

## Tickets

### DSLP-3 · P2 · Types: strict profile and typing findings

- **Area:** deslop · types
- **Where:** type checker and lint configuration; Python/TypeScript sources
- **Problem:** The strict-profile candidates in the deslop skill's tools reference have not been measured here.
- **Recommendation:** Run the deslop Types step. Accept: clean at the adopted profile, escape hatches not increased, witnesses recorded.
- **Fix with:** deslop
- **Effort:** M

### DSLP-5 · P2 · Dead code: tools and debloat

- **Area:** deslop · dead code
- **Where:** whole repository
- **Problem:** No dead-code scan has run.
- **Recommendation:** Run the deslop Dead code step. Accept: tools clean or allowlisted with reasons; walk-backs filed as Needs owner tickets.
- **Fix with:** deslop
- **Effort:** M

### DSLP-8 · P3 · Wake-on-LAN file input drops compact MAC addresses

- **Area:** Wake-on-LAN · file input
- **Where:** src/wol.py:18, src/wol.py:42
- **Problem:** The parser accepts compact twelve-digit and dotted MAC addresses, but file input silently skips every line shorter than 17 characters before parsing. Running python3 -I src/wol.py -f FILE with 001122334455 exits 1 with no valid addresses; the same address passed positionally succeeds against loopback. Mixed files silently omit those hosts.
- **Recommendation:** Pass each nonblank file line to the shared parser and cover compact, dotted, and separated addresses through the CLI.
- **Fix with:** root-cause
- **Effort:** S

### DSLP-9 · P3 · Measure representative tool workflows

- **Area:** Bench · repository workloads
- **Where:** Makefile, tools/pi-subagent-bridge/experiment/fx/spike.mjs
- **Problem:** The only declared performance workload compares a local FX bridge fixture; it does not measure representative sync, pinact, mdtool, or other shipped CLI workflows, leaving their performance regressions unmeasured.
- **Recommendation:** Define reproducible edit and change workloads around representative CLI journeys, with validated inputs and resource measurements.
- **Fix with:** refactor-benchmarks
- **Effort:** M

### DSLP-10 · P3 · Provide unavailable deslop audit tools

- **Area:** Needs environment · deslop tools
- **Where:** deslop Steps 4–6
- **Problem:** The test-pyramid, debloat, and bench-pyramid commands are unavailable in this worker environment, so their dedicated audits could not run. The inventory and direct scanner results are recorded under docs/verification.
- **Recommendation:** Make the audit tools available in an isolated environment and run them against this worktree without adding project dependencies.
- **Fix with:** deslop
- **Effort:** S

### DSLP-12 · P3 · Reject a null companion archive mapping

- **Area:** Pi release · pin validation
- **Where:** tools/sync/pi_release.py:76, tools/sync/pi_release.py:95
- **Problem:** A release pin with companions set to null passes _is_pin, but companions then raises TypeError rather than the missing-archives OfflinePiError. A local reproduction using the tracked pin with companions replaced by null printed validation True and TypeError.
- **Recommendation:** Define the supported absent and null pin states, validate them consistently, and cover loading and companion selection with a failing-first test.
- **Fix with:** root-cause
- **Effort:** S

