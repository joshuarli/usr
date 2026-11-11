import { participantBindingEpoch } from "./canonical.ts";
import { PARTICIPANT_STATE_MIGRATION_VECTORS } from "./boss-participant-state-vectors.ts";
import {
  FULL_WORKER_STORE_MIGRATION_VECTOR_VERSION,
  FULL_WORKER_STORE_MIGRATION_VECTORS_HASH,
} from "./boss-semantic-binding-constants.ts";
import {
  migrateFullWorkerStoreV1,
  type FullWorkerStoreMigrationInputV1,
  type OwningManagerRecipientV1,
} from "./worker-store-migration.ts";

export {
  FULL_WORKER_STORE_MIGRATION_VECTOR_VERSION,
  FULL_WORKER_STORE_MIGRATION_VECTORS_HASH,
};
export const FULL_WORKER_STORE_MIGRATION_VECTOR_HASH_DOMAIN =
  "agent-intercom-core/worker-store-v1-v2-full-v2" as const;

export const FULL_WORKER_STORE_MIGRATION_VECTORS = PARTICIPANT_STATE_MIGRATION_VECTORS.map((vector, index) => {
  const recipientContext = (["pi", "opencode", "headless_cli"] as const)[index % 3]!;
  const owningManagerRecipient: OwningManagerRecipientV1 = recipientContext === "headless_cli"
    ? {
        recipientPrincipalId: `manager-${index}`,
        recipientBindingEpoch: participantBindingEpoch(index + 1),
        recipientContext,
      }
    : {
        recipientPrincipalId: `manager-${index}`,
        recipientBindingEpoch: participantBindingEpoch(index + 1),
        recipientContext,
        recipientSessionId: `manager-session-${index}`,
        ...(index % 2 === 0 ? { recipientTargetSessionId: `manager-target-session-${index}` } : {}),
      };
  const input: FullWorkerStoreMigrationInputV1 = {
    version: 1,
    worker: vector.input,
    environment: {
      AGENT_INTERCOM_WORKER_ID: vector.input.workerId,
      AGENT_INTERCOM_RUN_ID: vector.input.legacyRunId,
      workspacePath: `/workspace/${index}`,
    },
    health: {
      observedLegacyState: vector.input.legacyState,
      lastConfirmedAt: "2026-07-28T11:59:00.000Z",
      ...(vector.input.legacyState === "failed" ? { failureCode: "legacy_adapter_failure" } : {}),
    },
    runtime: { runtimeId: `runtime-${index}`, processId: 10_000 + index, leaseExpiresAt: "2026-07-28T14:00:00.000Z", maxRuntimeAt: "2026-07-28T16:00:00.000Z" },
    adapter: { adapterId: "codex", adapterVersion: "1.0.0", sessionId: `session-${index}`, readinessReported: vector.input.legacyState === "running" },
    systemd: { unitName: `agent-worker-${index}.service`, activeState: vector.input.legacyState === "stopped" ? "inactive" : "active", subState: vector.input.legacyState, observedAt: "2026-07-28T12:00:00.000Z" },
    notice: {
      pendingNoticeIds: [`notice-${index}`],
      ...(index === 0 ? { lastDeliveredNoticeId: "notice-prior" } : {}),
      owningManagerRecipient,
    },
    controller: { projectionId: `projection-${index}`, revision: index + 1 },
  };
  return { name: `full compatibility mapping: ${vector.input.legacyState}`, input, expected: migrateFullWorkerStoreV1(input) };
});

const STRICT_VECTOR_BASE = FULL_WORKER_STORE_MIGRATION_VECTORS[0]!.expected;
const IDENTITY_BOUND_SURFACES = ["health", "runtime", "adapter", "systemd", "notice", "controller"] as const;

export const FULL_WORKER_STORE_V2_STRICT_REJECTION_VECTORS = [
  ...IDENTITY_BOUND_SURFACES.flatMap((surface) => [
    {
      name: `${surface} rejects a substituted worker incarnation`,
      value: {
        ...STRICT_VECTOR_BASE,
        [surface]: { ...STRICT_VECTOR_BASE[surface], workerIncarnationId: "substituted-incarnation" },
      },
    },
    {
      name: `${surface} rejects a substituted worker generation`,
      value: {
        ...STRICT_VECTOR_BASE,
        [surface]: { ...STRICT_VECTOR_BASE[surface], workerGeneration: STRICT_VECTOR_BASE.worker.workerGeneration + 1 },
      },
    },
  ]),
  {
    name: "environment requires the deprecated alias to equal the canonical incarnation",
    value: {
      ...STRICT_VECTOR_BASE,
      environment: { ...STRICT_VECTOR_BASE.environment, AGENT_INTERCOM_RUN_ID: "substituted-incarnation" },
    },
  },
  {
    name: "notice rejects an invalid owning Manager recipient binding",
    value: {
      ...STRICT_VECTOR_BASE,
      notice: {
        ...STRICT_VECTOR_BASE.notice,
        owningManagerRecipient: { ...STRICT_VECTOR_BASE.notice.owningManagerRecipient, recipientBindingEpoch: 0 },
      },
    },
  },
  {
    name: "interactive owning Manager recipient requires an authenticated session",
    value: {
      ...STRICT_VECTOR_BASE,
      notice: {
        ...STRICT_VECTOR_BASE.notice,
        owningManagerRecipient: {
          recipientPrincipalId: "manager-interactive",
          recipientBindingEpoch: participantBindingEpoch(1),
          recipientContext: "pi",
        },
      },
    },
  },
  {
    name: "headless owning Manager recipient forbids an interactive session",
    value: {
      ...STRICT_VECTOR_BASE,
      notice: {
        ...STRICT_VECTOR_BASE.notice,
        owningManagerRecipient: {
          recipientPrincipalId: "manager-headless",
          recipientBindingEpoch: participantBindingEpoch(1),
          recipientContext: "headless_cli",
          recipientSessionId: "forbidden-headless-session",
        },
      },
    },
  },
  {
    name: "ordinary migrated workers reject legacy bossRunId authority",
    value: {
      ...STRICT_VECTOR_BASE,
      worker: { ...STRICT_VECTOR_BASE.worker, bossRunId: "forbidden-legacy-authority" },
    },
  },
] as const;

export const FULL_WORKER_STORE_MIGRATION_VECTOR_CORPUS = {
  version: FULL_WORKER_STORE_MIGRATION_VECTOR_VERSION,
  vectors: FULL_WORKER_STORE_MIGRATION_VECTORS,
  strictRejectionVectors: FULL_WORKER_STORE_V2_STRICT_REJECTION_VECTORS,
} as const;
