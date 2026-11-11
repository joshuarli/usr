# Agent Intercom Core

The shared security policy kernel and protocol primitives for the [Agent Intercom](https://github.com/dataforxyz/agent-intercom-pi) adapter family.

This package is intentionally narrow. It contains pure, versioned authorization rules and policy state transitions used by every broker and remote gateway. Transport, worker lifecycle, queues, and harness integrations remain in their adapter repositories.

## Current policy semantics

Version 2 provides ownership-tree routing:

- Existing local sessions retain public local behavior.
- Communication is symmetric along one ancestor chain: root ↔ manager ↔ lead ↔ worker.
- Remote siblings, cousins, unrelated local sessions, and unrelated trees remain denied.
- Administrative subtree actions are directional: ancestors may inspect, revoke, or adopt descendants, while descendants cannot control ancestors.
- A principal may request attenuated child delegation only under itself.
- Revoked principals and stale generations are denied.

Gateways negotiate the exact semantic version and golden-vector hash rather than checking a boolean feature flag.

## Dormant Boss-run contracts

The additive `@dataforxyz/agent-intercom-core/boss` surface defines the `boss-run-v1` feature, a separate run-scoped authorization policy and vector hash, authenticated participant/authority/control contracts, canonical worker identity/state migration, and durable lifecycle delivery and supervision records.

Publishing these constants does not advertise or activate the feature. A Boss participant must explicitly negotiate and echo-verify the exact feature version/hash with a protected broker; unknown Boss metadata and old brokers fail closed. The legacy `remote-access-v1` version 2 vectors/hash and ordinary non-Boss local-public behavior remain unchanged.

Public package entry points are intentionally explicit:

- `@dataforxyz/agent-intercom-core` remains a legacy-only root export of the policy kernel and frozen corpus; it does not aggregate canonical or Boss contracts.
- `/policy` and `/vectors` provide the corresponding explicit legacy entry points.
- `/canonical` exposes the shared canonical encoder, branded counters, and fail-closed store result contract.
- `/boss` exposes all additive Boss feature, broker trust, restricted-client, participant-state, delivery, migration, and supervision contracts.
- `/boss/policy` and `/boss/vectors` provide the separate Boss policy kernel and golden-vector surfaces.

## Verify

```bash
npm install
npm run verify
```

The golden policy-vector corpus is hashed and asserted in tests. Any semantic change requires a deliberate version/hash update.

## Security boundary

The policy kernel limits broker visibility and routing. It does not isolate hostile processes sharing one Unix account or host. Remote deployments should still use SSH/TLS transport, private credential files, dedicated users or containers where needed, and a physically separate authenticated remote gateway endpoint rather than forwarding the raw local broker socket.

## License

`AGPL-3.0-or-later`.
