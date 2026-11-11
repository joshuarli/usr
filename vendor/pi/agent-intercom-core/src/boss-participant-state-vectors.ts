import type {
  LegacyStoppingReconciliationV1,
  LegacyWorkerMigrationInputV1,
  LegacyWorkerState,
  MigratedWorkerRecordV2,
  ParticipantHealthEventV1,
  ParticipantStateTransitionContextV1,
} from "./boss-participant-state.ts";
import { participantBindingEpoch, workerGeneration } from "./canonical.ts";
import {
  PARTICIPANT_NEW_GENERATION_TRANSITIONS,
  PARTICIPANT_STATE_TRANSITION_TABLE,
} from "./boss-participant-state.ts";
import {
  PARTICIPANT_STATE_TRANSITION_VECTOR_SCHEMA_VERSION,
  PARTICIPANT_STATE_TRANSITION_VECTORS_HASH,
  PARTICIPANT_STATE_VECTOR_SCHEMA_VERSION,
  PARTICIPANT_STATE_VECTORS_HASH,
} from "./boss-semantic-binding-constants.ts";

export {
  PARTICIPANT_STATE_TRANSITION_VECTOR_SCHEMA_VERSION,
  PARTICIPANT_STATE_TRANSITION_VECTORS_HASH,
  PARTICIPANT_STATE_VECTOR_SCHEMA_VERSION,
  PARTICIPANT_STATE_VECTORS_HASH,
};

export const PARTICIPANT_STATE_VECTOR_HASH_DOMAIN = "agent-intercom-core/boss-participant-state-v1" as const;
export const PARTICIPANT_STATE_TRANSITION_VECTOR_HASH_DOMAIN =
  "agent-intercom-core/boss-participant-state-transition-v1" as const;

const MIGRATED_AT = "2026-07-28T12:00:00.000Z";

function source(
  legacyState: LegacyWorkerState,
  generation: number,
  options: {
    legacyOutcome?: string | null;
    deprecatedAgentIntercomRunId?: string | null;
    legacyRunId?: string;
  } = {},
): LegacyWorkerMigrationInputV1 {
  return {
    version: 1,
    sourceStoreVersion: 1,
    targetStoreVersion: 2,
    workerId: `worker-${legacyState}`,
    legacyRunId: options.legacyRunId ?? `incarnation/${legacyState}/\u00e9`,
    deprecatedAgentIntercomRunId: options.deprecatedAgentIntercomRunId ?? `deprecated-env/${legacyState}`,
    legacyState,
    legacyOutcome: options.legacyOutcome ?? null,
    workerGenerationFloor: generation - 1,
    assignedWorkerGeneration: workerGeneration(generation),
    migratedAt: MIGRATED_AT,
  };
}

function expected(
  input: LegacyWorkerMigrationInputV1,
  mapping: Pick<
    MigratedWorkerRecordV2,
    | "state"
    | "resumeState"
    | "reason"
    | "terminalOutcome"
    | "requiresReadinessReconciliation"
    | "legacyIdleHint"
    | "migrationStatus"
    | "readOnly"
  >,
): MigratedWorkerRecordV2 {
  return {
    schemaVersion: 2,
    workerId: input.workerId,
    workerIncarnationId: input.legacyRunId,
    workerGeneration: input.assignedWorkerGeneration,
    ...mapping,
    dispatchAllowed: false,
    migrationAudit: {
      version: 1,
      sourceStoreVersion: 1,
      targetStoreVersion: 2,
      sourceIncarnationField: "runId",
      originalRunId: input.legacyRunId,
      originalDeprecatedAgentIntercomRunId: input.deprecatedAgentIntercomRunId,
      originalState: input.legacyState,
      originalOutcome: input.legacyOutcome,
      workerGenerationFloor: input.workerGenerationFloor,
      migratedAt: input.migratedAt,
    },
    stoppingReconciliation: null,
  };
}

const provisioning = source("provisioning", 1, {
  legacyRunId: "legacy-incarnation-byte-for-byte/\ud83d\udee0\ufe0f",
  deprecatedAgentIntercomRunId: "looks-like-boss-run-but-is-not-authority",
});
const running = source("running", 2);
const idle = source("idle", 3);
const needsAttention = source("needs_attention", 4);
const completed = source("completed", 5, { legacyOutcome: "legacy-completion-detail" });
const failed = source("failed", 6, { legacyOutcome: "adapter_crash" });
const stopped = source("stopped", 7, { legacyOutcome: "cancelled-by-owner" });
const lost = source("lost", 8);
const stopping = source("stopping", 9, { legacyOutcome: "shutdown-requested" });

export interface ParticipantStateMigrationVector {
  name: string;
  input: LegacyWorkerMigrationInputV1;
  expected: MigratedWorkerRecordV2;
}

/** One and only one golden vector for every WorkerStore v1 state in Revision 17 section 22.5. */
export const PARTICIPANT_STATE_MIGRATION_VECTORS: readonly ParticipantStateMigrationVector[] = [
  {
    name: "provisioning remains provisioning and legacy runId remains the incarnation",
    input: provisioning,
    expected: expected(provisioning, {
      state: "provisioning",
      resumeState: null,
      reason: null,
      terminalOutcome: null,
      requiresReadinessReconciliation: false,
      legacyIdleHint: false,
      migrationStatus: "complete",
      readOnly: false,
    }),
  },
  {
    name: "running becomes registering and cannot bypass readiness reconciliation",
    input: running,
    expected: expected(running, {
      state: "registering",
      resumeState: null,
      reason: null,
      terminalOutcome: null,
      requiresReadinessReconciliation: true,
      legacyIdleHint: false,
      migrationStatus: "complete",
      readOnly: false,
    }),
  },
  {
    name: "idle becomes registering with an audit-only idle hint",
    input: idle,
    expected: expected(idle, {
      state: "registering",
      resumeState: null,
      reason: null,
      terminalOutcome: null,
      requiresReadinessReconciliation: true,
      legacyIdleHint: true,
      migrationStatus: "complete",
      readOnly: false,
    }),
  },
  {
    name: "needs_attention becomes recoverable blocked with the frozen reason",
    input: needsAttention,
    expected: expected(needsAttention, {
      state: "blocked",
      resumeState: "registering",
      reason: "legacy_needs_attention",
      terminalOutcome: null,
      requiresReadinessReconciliation: false,
      legacyIdleHint: false,
      migrationStatus: "complete",
      readOnly: false,
    }),
  },
  {
    name: "completed becomes stopped with completed terminal outcome",
    input: completed,
    expected: expected(completed, {
      state: "stopped",
      resumeState: null,
      reason: null,
      terminalOutcome: "completed",
      requiresReadinessReconciliation: false,
      legacyIdleHint: false,
      migrationStatus: "complete",
      readOnly: false,
    }),
  },
  {
    name: "failed remains failed and preserves the original outcome in audit and reason",
    input: failed,
    expected: expected(failed, {
      state: "failed",
      resumeState: null,
      reason: "adapter_crash",
      terminalOutcome: null,
      requiresReadinessReconciliation: false,
      legacyIdleHint: false,
      migrationStatus: "complete",
      readOnly: false,
    }),
  },
  {
    name: "stopped remains stopped while the original outcome remains audit metadata",
    input: stopped,
    expected: expected(stopped, {
      state: "stopped",
      resumeState: null,
      reason: null,
      terminalOutcome: null,
      requiresReadinessReconciliation: false,
      legacyIdleHint: false,
      migrationStatus: "complete",
      readOnly: false,
    }),
  },
  {
    name: "lost remains lost with an explicit compatibility reason",
    input: lost,
    expected: expected(lost, {
      state: "lost",
      resumeState: null,
      reason: "legacy_lost",
      terminalOutcome: null,
      requiresReadinessReconciliation: false,
      legacyIdleHint: false,
      migrationStatus: "complete",
      readOnly: false,
    }),
  },
  {
    name: "stopping remains read-only and state-null pending direct process evidence",
    input: stopping,
    expected: expected(stopping, {
      state: null,
      resumeState: null,
      reason: null,
      terminalOutcome: null,
      requiresReadinessReconciliation: false,
      legacyIdleHint: false,
      migrationStatus: "pending_stopping_reconciliation",
      readOnly: true,
    }),
  },
] as const;

const stoppingPending = PARTICIPANT_STATE_MIGRATION_VECTORS[8].expected;

function evidence(
  outcome: LegacyStoppingReconciliationV1["outcome"],
  generation = stoppingPending.workerGeneration,
): LegacyStoppingReconciliationV1 {
  return {
    version: 1,
    workerId: stoppingPending.workerId,
    workerIncarnationId: stoppingPending.workerIncarnationId,
    workerGeneration: generation,
    observationId: `observation-${outcome}`,
    evidenceSource: "systemd_and_cgroup",
    outcome,
    boundedSettleWindowExpired: outcome === "unresolved_after_settle",
    observedAt: "2026-07-28T12:00:30.000Z",
  };
}

export interface StoppingReconciliationVector {
  name: string;
  pending: MigratedWorkerRecordV2;
  evidence: LegacyStoppingReconciliationV1;
  expectedState: "stopped" | "failed" | "lost" | "unreachable";
  expectedReason: string | null;
}

export const STOPPING_RECONCILIATION_VECTORS: readonly StoppingReconciliationVector[] = [
  {
    name: "direct stopped evidence settles stopped",
    pending: stoppingPending,
    evidence: evidence("stopped"),
    expectedState: "stopped",
    expectedReason: null,
  },
  {
    name: "direct failed evidence settles failed",
    pending: stoppingPending,
    evidence: evidence("failed"),
    expectedState: "failed",
    expectedReason: null,
  },
  {
    name: "direct lost evidence settles lost",
    pending: stoppingPending,
    evidence: evidence("lost"),
    expectedState: "lost",
    expectedReason: null,
  },
  {
    name: "unresolved after the bounded settle window becomes unreachable",
    pending: stoppingPending,
    evidence: evidence("unresolved_after_settle"),
    expectedState: "unreachable",
    expectedReason: "legacy_stopping_unresolved",
  },
] as const;

export const PARTICIPANT_HEALTH_EVENT_VECTOR: ParticipantHealthEventV1 = {
  version: 1,
  eventId: "event-01JSTATEVECTOR",
  bossRunId: "boss-run-vector",
  participantId: "participant-worker-1",
  bindingEpoch: participantBindingEpoch(4),
  previousState: "working",
  state: "blocked",
  severity: "warning",
  failureCode: null,
  reason: "permission_denied",
  suggestedRecovery: "request_manager_review",
  occurredAt: "2026-07-28T12:01:00.000Z",
  acknowledgedAt: "2026-07-28T12:02:00.000Z",
};

const READINESS_ASSERTIONS = {
  adapterStartupReady: true,
  brokerRegistrationReady: true,
  bindingAttested: true,
  capabilityProfileAttested: true,
  assignmentControlSupported: true,
} as const;

export interface ParticipantStateTransitionVector {
  name: string;
  input: ParticipantStateTransitionContextV1;
}

/** Golden positive cases for every guarded recovery path added by the B6 ruling. */
export const PARTICIPANT_STATE_TRANSITION_VECTORS: readonly ParticipantStateTransitionVector[] = [
  {
    name: "registration reaches ready only with the complete readiness proof",
    input: {
      version: 1,
      previousState: "registering",
      state: "ready",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: { kind: "readiness_reconciled", evidenceId: "readiness-7", ...READINESS_ASSERTIONS },
    },
  },
  {
    name: "legacy idle reaches waiting only with readiness and no-active-turn proof",
    input: {
      version: 1,
      previousState: "registering",
      state: "waiting",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: {
        kind: "legacy_idle_reconciled",
        evidenceId: "legacy-idle-7",
        ...READINESS_ASSERTIONS,
        legacyIdleHint: true,
        noActiveTurn: true,
      },
    },
  },
  {
    name: "block entry persists the interrupted resumable state",
    input: {
      version: 1,
      previousState: "working",
      state: "blocked",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: {
        kind: "blocker_detected",
        evidenceId: "block-7",
        resumeState: "working",
        reason: "permission_denied",
      },
    },
  },
  {
    name: "blocked recovery matches the stored resume state and clear evidence",
    input: {
      version: 1,
      previousState: "blocked",
      previousResumeState: "working",
      state: "working",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: {
        kind: "blocker_cleared",
        evidenceId: "block-clear-7",
        storedResumeState: "working",
        blockerClearConfirmed: true,
      },
    },
  },
  {
    name: "Controller liveness evidence alone enters stalled",
    input: {
      version: 1,
      previousState: "working",
      state: "stalled",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: {
        kind: "controller_liveness_stalled",
        evidenceId: "liveness-timeout-7",
        controllerParticipantId: "participant-controller",
        livenessDeadlineExceeded: true,
      },
    },
  },
  {
    name: "stalled recovers to the positively evidenced resumable state",
    input: {
      version: 1,
      previousState: "stalled",
      state: "waiting",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: {
        kind: "controller_liveness_recovered",
        evidenceId: "liveness-recovery-7",
        controllerParticipantId: "participant-controller",
        resumableState: "waiting",
        positiveStateEvidenceId: "session-observation-7",
      },
    },
  },
  {
    name: "parked paused participant resumes ready with positive readiness evidence",
    input: {
      version: 1,
      previousState: "paused",
      state: "ready",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: {
        kind: "parked_resume",
        evidenceId: "parked-resume-7",
        ...READINESS_ASSERTIONS,
        resumableState: "ready",
        parkedProcessConfirmed: true,
        noActiveTurn: true,
      },
    },
  },
  {
    name: "unreachable recovers only to registering with fresh readiness still required",
    input: {
      version: 1,
      previousState: "unreachable",
      state: "registering",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: {
        kind: "connectivity_recovered",
        evidenceId: "connectivity-recovery-7",
        freshReadinessReconciliationRequired: true,
      },
    },
  },
  {
    name: "unreachable may converge to a terminal failure outcome",
    input: {
      version: 1,
      previousState: "unreachable",
      state: "lost",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: { kind: "failure_observed", evidenceId: "loss-7", outcome: "lost" },
    },
  },
  {
    name: "terminal restart provisions exactly one fresh generation",
    input: {
      version: 1,
      previousState: "stopped",
      state: "provisioning",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(8),
      evidence: { kind: "new_generation_provisioned", evidenceId: "generation-8" },
    },
  },
  {
    name: "parked resume may cross exactly one fresh generation",
    input: {
      version: 1,
      previousState: "paused",
      state: "waiting",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(8),
      evidence: {
        kind: "parked_resume",
        evidenceId: "parked-resume-8",
        ...READINESS_ASSERTIONS,
        resumableState: "waiting",
        parkedProcessConfirmed: true,
        noActiveTurn: true,
      },
    },
  },
  {
    name: "blocked reaffirmation preserves the persisted resume state",
    input: {
      version: 1,
      previousState: "blocked",
      previousResumeState: "ready",
      state: "blocked",
      previousWorkerGeneration: workerGeneration(7),
      workerGeneration: workerGeneration(7),
      evidence: {
        kind: "blocked_reaffirmed",
        evidenceId: "block-reaffirmed-7",
        storedResumeState: "ready",
        reason: "permission_denied",
      },
    },
  },
] as const;

export const PARTICIPANT_STATE_TRANSITION_VECTOR_CORPUS = {
  version: PARTICIPANT_STATE_TRANSITION_VECTOR_SCHEMA_VERSION,
  sameGenerationTransitionTable: PARTICIPANT_STATE_TRANSITION_TABLE,
  newGenerationTransitionTable: PARTICIPANT_NEW_GENERATION_TRANSITIONS,
  transitionVectors: PARTICIPANT_STATE_TRANSITION_VECTORS,
} as const;

export const PARTICIPANT_STATE_VECTOR_CORPUS = {
  version: PARTICIPANT_STATE_VECTOR_SCHEMA_VERSION,
  migrationVectors: PARTICIPANT_STATE_MIGRATION_VECTORS,
  stoppingReconciliationVectors: STOPPING_RECONCILIATION_VECTORS,
  healthEvent: PARTICIPANT_HEALTH_EVENT_VECTOR,
} as const;
