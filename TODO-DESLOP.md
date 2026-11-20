Prefix: DSLP
Next: 9

Deslop campaign backlog ([plan](https://github.com/laputa-systems/stuff/blob/main/docs/campaigns/deslop.md), tier C). One agent works this file with the `deslop` skill: take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work the open P1 and P2 findings, then fill in `## Report` below.

## Report

Not started.

## Tickets

### DSLP-3 · P2 · Types: strict profile and typing findings

- **Area:** deslop · types
- **Where:** type checker and lint configuration; Python/TypeScript sources
- **Problem:** The strict-profile candidates in the deslop skill's tools reference have not been measured here.
- **Recommendation:** Run the deslop Types step. Accept: clean at the adopted profile, escape hatches not increased, witnesses recorded.
- **Fix with:** deslop
- **Effort:** M

### DSLP-4 · P2 · Tests: coverage, boundary gaps, mutation

- **Area:** deslop · tests
- **Where:** test suites and CI
- **Problem:** Coverage and mutation results are unmeasured; no deslop mutation lane exists.
- **Recommendation:** Run the deslop Tests step. Accept: no undispositioned survivor in critical code, the test cost budget holds, and the lane is green where the tools are mirrored.
- **Fix with:** deslop
- **Effort:** L

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

