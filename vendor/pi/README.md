# Pi source vendor (not yet a self-contained runtime)

This directory holds byte-for-byte **selected source** snapshots from the upstream Git commits in [upstreams.json](upstreams.json). The `files` maps store each upstream Git **blob SHA**, not merely a package version.

| Source | License | Purpose |
| --- | --- | --- |
| `pi-subagents` | MIT | Native subagent extension and RPC |
| `agent-intercom-pi` | AGPL-3.0-or-later | Pi intercom adapter |
| `agent-intercom-core` | AGPL-3.0-or-later | Intercom broker policy/protocol |
| `pi-muse-subscription` | MIT | Muse subscription adapter |

All upstream copyright notices remain in their respective directories. The intercom components are AGPL; keep notices and evaluate obligations before incorporating their code into a distributed combined work.

**Crucial limitation:** these are source snapshots. The Pi CLI, `@earendil-works/pi-coding-agent` SDK and transitive runtime dependencies, intercom's core build output and the other harness adapters have **not** been bundled into a complete offline runtime. Existing `sync` still uses npm for the Pi executable and bridge dependencies. The snapshots are **not activated**; do not switch `settings.json` to local paths until the complete module graph is available and tested. A source checkout alone does not meet the no-npm requirement.

`python3 -I tools/pi/vendor.py check` checks every tracked file against its upstream Git blob SHA and rejects unexpected additions. `python3 -I tools/pi/vendor.py plan` compares upstream heads without writing. `python3 -I tools/pi/vendor.py update` updates the selected source snapshots and provenance, but **does not** upgrade or activate the SDK/runtime automatically. See `/pi-update` for the full update gates.

The endpoint for this effort is a Pi runtime archive (or reproducible equivalent) **committed under `usr`**, including platform-specific assets and every transitive runtime dependency. Routine `sh sync`, `sh sync bridge`, and `sh sync doctor` must perform zero npm network accesses, and they must not invoke `pi install` or `pi update`. Build/fetch work belongs to the explicit `pi-update` workflow, never normal setup.

No separate intercom fleet/orchestrator package should be imported. `pi-subagent-bridge` remains the sole worker admission, lease, scope and verification authority; intercom is only a messaging capability.
