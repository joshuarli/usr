import {
  ContractValidationError,
  assertExactKeys,
  assertRecord,
  readBoolean,
  readEnum,
  readInteger,
  readString,
  readTimestamp,
  type StringEnum,
  participantBindingEpoch,
  type ParticipantBindingEpoch,
  validateVersionedStoreRecord,
  type StoreValidationResult,
  workerGeneration as readWorkerGeneration,
  type WorkerGeneration,
} from "./canonical.ts";

/** Revision 17, section 22.5 canonical vocabulary. Order is contract-significant. */
export const PARTICIPANT_STATES = [
  "provisioning",
  "registering",
  "ready",
  "working",
  "waiting",
  "paused",
  "stalled",
  "blocked",
  "failed",
  "lost",
  "unreachable",
  "stopped",
] as const;

export type ParticipantState = StringEnum<typeof PARTICIPANT_STATES>;

export const TERMINAL_PARTICIPANT_STATES = ["failed", "lost", "stopped"] as const satisfies readonly ParticipantState[];
export type TerminalParticipantState = StringEnum<typeof TERMINAL_PARTICIPANT_STATES>;

export const LEGACY_WORKER_STATES = [
  "provisioning",
  "running",
  "idle",
  "needs_attention",
  "completed",
  "failed",
  "stopped",
  "lost",
  "stopping",
] as const;

export type LegacyWorkerState = StringEnum<typeof LEGACY_WORKER_STATES>;

export const PARTICIPANT_HEALTH_EVENT_VERSION = 1 as const;
export const WORKER_STATE_MIGRATION_CONTRACT_VERSION = 1 as const;
export const LEGACY_WORKER_STORE_SCHEMA_VERSION = 1 as const;
export const CANONICAL_WORKER_STORE_SCHEMA_VERSION = 2 as const;

export const PARTICIPANT_HEALTH_SEVERITIES = ["info", "warning", "error", "critical"] as const;
export type ParticipantHealthSeverity = StringEnum<typeof PARTICIPANT_HEALTH_SEVERITIES>;

export interface ParticipantHealthEventV1 {
  version: typeof PARTICIPANT_HEALTH_EVENT_VERSION;
  eventId: string;
  bossRunId: string;
  participantId: string;
  bindingEpoch: ParticipantBindingEpoch;
  previousState: ParticipantState;
  state: ParticipantState;
  severity: ParticipantHealthSeverity;
  failureCode: string | null;
  reason: string | null;
  suggestedRecovery: string | null;
  occurredAt: string;
  acknowledgedAt?: string;
}

export interface LegacyWorkerMigrationInputV1 {
  version: typeof WORKER_STATE_MIGRATION_CONTRACT_VERSION;
  sourceStoreVersion: typeof LEGACY_WORKER_STORE_SCHEMA_VERSION;
  targetStoreVersion: typeof CANONICAL_WORKER_STORE_SCHEMA_VERSION;
  workerId: string;
  /** The legacy WorkerStore `runId`; it is an incarnation ID, never Boss authority. */
  legacyRunId: string;
  /** Preserved for audit only; this deprecated environment value never becomes `bossRunId`. */
  deprecatedAgentIntercomRunId: string | null;
  legacyState: LegacyWorkerState;
  legacyOutcome: string | null;
  /** Highest already-persisted generation for this stable worker ID, or zero for its first generation. */
  workerGenerationFloor: number;
  assignedWorkerGeneration: WorkerGeneration;
  migratedAt: string;
}

export type WorkerMigrationStatus = "complete" | "pending_stopping_reconciliation";

export interface WorkerStateMigrationAuditV1 {
  version: typeof WORKER_STATE_MIGRATION_CONTRACT_VERSION;
  sourceStoreVersion: typeof LEGACY_WORKER_STORE_SCHEMA_VERSION;
  targetStoreVersion: typeof CANONICAL_WORKER_STORE_SCHEMA_VERSION;
  sourceIncarnationField: "runId";
  originalRunId: string;
  originalDeprecatedAgentIntercomRunId: string | null;
  originalState: LegacyWorkerState;
  originalOutcome: string | null;
  workerGenerationFloor: number;
  migratedAt: string;
}

export const STOPPING_RECONCILIATION_OUTCOMES = ["stopped", "failed", "lost", "unresolved_after_settle"] as const;
export type StoppingReconciliationOutcome = StringEnum<typeof STOPPING_RECONCILIATION_OUTCOMES>;

export const STOPPING_EVIDENCE_SOURCES = ["systemd", "cgroup", "systemd_and_cgroup"] as const;
export type StoppingEvidenceSource = StringEnum<typeof STOPPING_EVIDENCE_SOURCES>;

export interface LegacyStoppingReconciliationV1 {
  version: typeof WORKER_STATE_MIGRATION_CONTRACT_VERSION;
  workerId: string;
  workerIncarnationId: string;
  workerGeneration: WorkerGeneration;
  observationId: string;
  evidenceSource: StoppingEvidenceSource;
  outcome: StoppingReconciliationOutcome;
  boundedSettleWindowExpired: boolean;
  observedAt: string;
}

export interface MigratedWorkerRecordV2 {
  schemaVersion: typeof CANONICAL_WORKER_STORE_SCHEMA_VERSION;
  workerId: string;
  workerIncarnationId: string;
  workerGeneration: WorkerGeneration;
  /** Null only while legacy `stopping` is fenced pending direct process reconciliation. */
  state: ParticipantState | null;
  /** Persisted recovery target; non-null exactly while the canonical state is `blocked`. */
  resumeState: BlockedResumeState | null;
  reason: string | null;
  terminalOutcome: string | null;
  requiresReadinessReconciliation: boolean;
  legacyIdleHint: boolean;
  migrationStatus: WorkerMigrationStatus;
  readOnly: boolean;
  dispatchAllowed: false;
  migrationAudit: WorkerStateMigrationAuditV1;
  stoppingReconciliation: LegacyStoppingReconciliationV1 | null;
  /** Deliberately no `bossRunId`: legacy workers remain ordinary workers. */
}

const EXPLICIT_REASON_STATES = ["blocked", "failed", "lost", "unreachable"] as const satisfies readonly ParticipantState[];

function readNullableString(value: unknown, path: string): string | null {
  if (value === null) return null;
  return readString(value, path);
}

function readLiteralInteger<const T extends number>(value: unknown, expected: T, path: string): T {
  const parsed = readInteger(value, path, 0);
  if (parsed !== expected) throw new ContractValidationError(path, `unsupported version ${parsed}; expected ${expected}`);
  return expected;
}

function readLiteralString<const T extends string>(value: unknown, expected: T, path: string): T {
  if (value !== expected) throw new ContractValidationError(path, `must be ${JSON.stringify(expected)}`);
  return expected;
}

export function parseParticipantState(value: unknown, path = "$.state"): ParticipantState {
  return readEnum(value, PARTICIPANT_STATES, path);
}

export function isTerminalParticipantState(state: ParticipantState): state is TerminalParticipantState {
  return (TERMINAL_PARTICIPANT_STATES as readonly ParticipantState[]).includes(state);
}

export function parseParticipantHealthEventV1(value: unknown, path = "$"): ParticipantHealthEventV1 {
  assertRecord(value, path);
  assertExactKeys(
    value,
    [
      "version",
      "eventId",
      "bossRunId",
      "participantId",
      "bindingEpoch",
      "previousState",
      "state",
      "severity",
      "failureCode",
      "reason",
      "suggestedRecovery",
      "occurredAt",
    ],
    ["acknowledgedAt"],
    path,
  );
  const event: ParticipantHealthEventV1 = {
    version: readLiteralInteger(value.version, PARTICIPANT_HEALTH_EVENT_VERSION, `${path}.version`),
    eventId: readString(value.eventId, `${path}.eventId`),
    bossRunId: readString(value.bossRunId, `${path}.bossRunId`),
    participantId: readString(value.participantId, `${path}.participantId`),
    bindingEpoch: participantBindingEpoch(value.bindingEpoch, `${path}.bindingEpoch`),
    previousState: parseParticipantState(value.previousState, `${path}.previousState`),
    state: parseParticipantState(value.state, `${path}.state`),
    severity: readEnum(value.severity, PARTICIPANT_HEALTH_SEVERITIES, `${path}.severity`),
    failureCode: readNullableString(value.failureCode, `${path}.failureCode`),
    reason: readNullableString(value.reason, `${path}.reason`),
    suggestedRecovery: readNullableString(value.suggestedRecovery, `${path}.suggestedRecovery`),
    occurredAt: readTimestamp(value.occurredAt, `${path}.occurredAt`),
    ...(value.acknowledgedAt === undefined
      ? {}
      : { acknowledgedAt: readTimestamp(value.acknowledgedAt, `${path}.acknowledgedAt`) }),
  };
  if ((EXPLICIT_REASON_STATES as readonly ParticipantState[]).includes(event.state) && event.reason === null) {
    throw new ContractValidationError(`${path}.reason`, `${event.state} requires an explicit reason`);
  }
  if (event.state === "failed" && event.failureCode === null) {
    throw new ContractValidationError(`${path}.failureCode`, "failed requires an explicit failure code");
  }
  if (event.acknowledgedAt !== undefined && Date.parse(event.acknowledgedAt) < Date.parse(event.occurredAt)) {
    throw new ContractValidationError(`${path}.acknowledgedAt`, "must not precede occurredAt");
  }
  return event;
}

export function parseLegacyWorkerMigrationInputV1(value: unknown, path = "$"): LegacyWorkerMigrationInputV1 {
  assertRecord(value, path);
  assertExactKeys(
    value,
    [
      "version",
      "sourceStoreVersion",
      "targetStoreVersion",
      "workerId",
      "legacyRunId",
      "deprecatedAgentIntercomRunId",
      "legacyState",
      "legacyOutcome",
      "workerGenerationFloor",
      "assignedWorkerGeneration",
      "migratedAt",
    ],
    [],
    path,
  );
  const workerGenerationFloor = readInteger(value.workerGenerationFloor, `${path}.workerGenerationFloor`, 0);
  const assignedWorkerGeneration = readWorkerGeneration(value.assignedWorkerGeneration, `${path}.assignedWorkerGeneration`);
  if (assignedWorkerGeneration <= workerGenerationFloor) {
    throw new ContractValidationError(
      `${path}.assignedWorkerGeneration`,
      "must be greater than the persisted workerGenerationFloor",
    );
  }
  return {
    version: readLiteralInteger(value.version, WORKER_STATE_MIGRATION_CONTRACT_VERSION, `${path}.version`),
    sourceStoreVersion: readLiteralInteger(value.sourceStoreVersion, LEGACY_WORKER_STORE_SCHEMA_VERSION, `${path}.sourceStoreVersion`),
    targetStoreVersion: readLiteralInteger(value.targetStoreVersion, CANONICAL_WORKER_STORE_SCHEMA_VERSION, `${path}.targetStoreVersion`),
    workerId: readString(value.workerId, `${path}.workerId`),
    legacyRunId: readString(value.legacyRunId, `${path}.legacyRunId`),
    deprecatedAgentIntercomRunId: readNullableString(
      value.deprecatedAgentIntercomRunId,
      `${path}.deprecatedAgentIntercomRunId`,
    ),
    legacyState: readEnum(value.legacyState, LEGACY_WORKER_STATES, `${path}.legacyState`),
    legacyOutcome: readNullableString(value.legacyOutcome, `${path}.legacyOutcome`),
    workerGenerationFloor,
    assignedWorkerGeneration,
    migratedAt: readTimestamp(value.migratedAt, `${path}.migratedAt`),
  };
}

function auditFor(input: LegacyWorkerMigrationInputV1): WorkerStateMigrationAuditV1 {
  return {
    version: WORKER_STATE_MIGRATION_CONTRACT_VERSION,
    sourceStoreVersion: LEGACY_WORKER_STORE_SCHEMA_VERSION,
    targetStoreVersion: CANONICAL_WORKER_STORE_SCHEMA_VERSION,
    sourceIncarnationField: "runId",
    originalRunId: input.legacyRunId,
    originalDeprecatedAgentIntercomRunId: input.deprecatedAgentIntercomRunId,
    originalState: input.legacyState,
    originalOutcome: input.legacyOutcome,
    workerGenerationFloor: input.workerGenerationFloor,
    migratedAt: input.migratedAt,
  };
}

interface LegacyStateMapping {
  state: ParticipantState | null;
  resumeState: BlockedResumeState | null;
  reason: string | null;
  terminalOutcome: string | null;
  requiresReadinessReconciliation: boolean;
  legacyIdleHint: boolean;
  migrationStatus: WorkerMigrationStatus;
  readOnly: boolean;
}

function mapLegacyState(input: LegacyWorkerMigrationInputV1): LegacyStateMapping {
  switch (input.legacyState) {
    case "provisioning":
      return completeMapping("provisioning");
    case "running":
      return { ...completeMapping("registering"), requiresReadinessReconciliation: true };
    case "idle":
      return { ...completeMapping("registering"), requiresReadinessReconciliation: true, legacyIdleHint: true };
    case "needs_attention":
      return { ...completeMapping("blocked"), resumeState: "registering", reason: "legacy_needs_attention" };
    case "completed":
      return { ...completeMapping("stopped"), terminalOutcome: "completed" };
    case "failed":
      return { ...completeMapping("failed"), reason: input.legacyOutcome ?? "legacy_failed" };
    case "stopped":
      return completeMapping("stopped");
    case "lost":
      return { ...completeMapping("lost"), reason: input.legacyOutcome ?? "legacy_lost" };
    case "stopping":
      return {
        state: null,
        resumeState: null,
        reason: null,
        terminalOutcome: null,
        requiresReadinessReconciliation: false,
        legacyIdleHint: false,
        migrationStatus: "pending_stopping_reconciliation",
        readOnly: true,
      };
  }
}

function completeMapping(state: ParticipantState): LegacyStateMapping {
  return {
    state,
    resumeState: null,
    reason: null,
    terminalOutcome: null,
    requiresReadinessReconciliation: false,
    legacyIdleHint: false,
    migrationStatus: "complete",
    readOnly: false,
  };
}

/**
 * Applies only the frozen v1 projection contract. Store readers must validate their own complete
 * source record before projecting it here; unknown/corrupt store versions are never normalized.
 */
export function migrateLegacyWorkerRecordV1(value: unknown): MigratedWorkerRecordV2 {
  const input = parseLegacyWorkerMigrationInputV1(value);
  const mapping = mapLegacyState(input);
  return {
    schemaVersion: CANONICAL_WORKER_STORE_SCHEMA_VERSION,
    workerId: input.workerId,
    workerIncarnationId: input.legacyRunId,
    workerGeneration: input.assignedWorkerGeneration,
    ...mapping,
    dispatchAllowed: false,
    migrationAudit: auditFor(input),
    stoppingReconciliation: null,
  };
}

export function parseLegacyStoppingReconciliationV1(value: unknown, path = "$"): LegacyStoppingReconciliationV1 {
  assertRecord(value, path);
  assertExactKeys(
    value,
    [
      "version",
      "workerId",
      "workerIncarnationId",
      "workerGeneration",
      "observationId",
      "evidenceSource",
      "outcome",
      "boundedSettleWindowExpired",
      "observedAt",
    ],
    [],
    path,
  );
  const evidence: LegacyStoppingReconciliationV1 = {
    version: readLiteralInteger(value.version, WORKER_STATE_MIGRATION_CONTRACT_VERSION, `${path}.version`),
    workerId: readString(value.workerId, `${path}.workerId`),
    workerIncarnationId: readString(value.workerIncarnationId, `${path}.workerIncarnationId`),
    workerGeneration: readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`),
    observationId: readString(value.observationId, `${path}.observationId`),
    evidenceSource: readEnum(value.evidenceSource, STOPPING_EVIDENCE_SOURCES, `${path}.evidenceSource`),
    outcome: readEnum(value.outcome, STOPPING_RECONCILIATION_OUTCOMES, `${path}.outcome`),
    boundedSettleWindowExpired: readBoolean(value.boundedSettleWindowExpired, `${path}.boundedSettleWindowExpired`),
    observedAt: readTimestamp(value.observedAt, `${path}.observedAt`),
  };
  if (evidence.outcome === "unresolved_after_settle" && !evidence.boundedSettleWindowExpired) {
    throw new ContractValidationError(
      `${path}.boundedSettleWindowExpired`,
      "must be true for unresolved_after_settle",
    );
  }
  if (evidence.outcome !== "unresolved_after_settle" && evidence.boundedSettleWindowExpired) {
    throw new ContractValidationError(
      `${path}.boundedSettleWindowExpired`,
      "must be false when direct evidence establishes a terminal outcome",
    );
  }
  return evidence;
}

export function reconcileLegacyStoppingWorker(
  pendingValue: unknown,
  evidenceValue: unknown,
): MigratedWorkerRecordV2 {
  const pending = parseMigratedWorkerRecordV2(pendingValue);
  const evidence = parseLegacyStoppingReconciliationV1(evidenceValue);
  if (pending.migrationStatus !== "pending_stopping_reconciliation" || pending.migrationAudit.originalState !== "stopping") {
    throw new ContractValidationError("$.migrationStatus", "worker is not pending legacy stopping reconciliation");
  }
  if (
    evidence.workerId !== pending.workerId
    || evidence.workerIncarnationId !== pending.workerIncarnationId
    || evidence.workerGeneration !== pending.workerGeneration
  ) {
    throw new ContractValidationError("$.evidence", "worker identity or generation does not match the pending record");
  }
  if (Date.parse(evidence.observedAt) < Date.parse(pending.migrationAudit.migratedAt)) {
    throw new ContractValidationError("$.evidence.observedAt", "must not precede the pending migration");
  }
  const state: ParticipantState = evidence.outcome === "unresolved_after_settle" ? "unreachable" : evidence.outcome;
  return parseMigratedWorkerRecordV2({
    ...pending,
    state,
    reason: evidence.outcome === "unresolved_after_settle" ? "legacy_stopping_unresolved" : null,
    migrationStatus: "complete",
    readOnly: false,
    stoppingReconciliation: evidence,
  });
}

function parseWorkerStateMigrationAuditV1(value: unknown, path: string): WorkerStateMigrationAuditV1 {
  assertRecord(value, path);
  assertExactKeys(
    value,
    [
      "version",
      "sourceStoreVersion",
      "targetStoreVersion",
      "sourceIncarnationField",
      "originalRunId",
      "originalDeprecatedAgentIntercomRunId",
      "originalState",
      "originalOutcome",
      "workerGenerationFloor",
      "migratedAt",
    ],
    [],
    path,
  );
  return {
    version: readLiteralInteger(value.version, WORKER_STATE_MIGRATION_CONTRACT_VERSION, `${path}.version`),
    sourceStoreVersion: readLiteralInteger(value.sourceStoreVersion, LEGACY_WORKER_STORE_SCHEMA_VERSION, `${path}.sourceStoreVersion`),
    targetStoreVersion: readLiteralInteger(value.targetStoreVersion, CANONICAL_WORKER_STORE_SCHEMA_VERSION, `${path}.targetStoreVersion`),
    sourceIncarnationField: readLiteralString(value.sourceIncarnationField, "runId", `${path}.sourceIncarnationField`),
    originalRunId: readString(value.originalRunId, `${path}.originalRunId`),
    originalDeprecatedAgentIntercomRunId: readNullableString(
      value.originalDeprecatedAgentIntercomRunId,
      `${path}.originalDeprecatedAgentIntercomRunId`,
    ),
    originalState: readEnum(value.originalState, LEGACY_WORKER_STATES, `${path}.originalState`),
    originalOutcome: readNullableString(value.originalOutcome, `${path}.originalOutcome`),
    workerGenerationFloor: readInteger(value.workerGenerationFloor, `${path}.workerGenerationFloor`, 0),
    migratedAt: readTimestamp(value.migratedAt, `${path}.migratedAt`),
  };
}

export function parseMigratedWorkerRecordV2(value: unknown, path = "$"): MigratedWorkerRecordV2 {
  assertRecord(value, path);
  assertExactKeys(
    value,
    [
      "schemaVersion",
      "workerId",
      "workerIncarnationId",
      "workerGeneration",
      "state",
      "resumeState",
      "reason",
      "terminalOutcome",
      "requiresReadinessReconciliation",
      "legacyIdleHint",
      "migrationStatus",
      "readOnly",
      "dispatchAllowed",
      "migrationAudit",
      "stoppingReconciliation",
    ],
    [],
    path,
  );
  const migrationStatus = readEnum(
    value.migrationStatus,
    ["complete", "pending_stopping_reconciliation"] as const,
    `${path}.migrationStatus`,
  );
  const state = value.state === null ? null : parseParticipantState(value.state, `${path}.state`);
  const resumeState = value.resumeState === null
    ? null
    : readEnum(value.resumeState, BLOCKED_RESUME_STATES, `${path}.resumeState`);
  const migrationAudit = parseWorkerStateMigrationAuditV1(value.migrationAudit, `${path}.migrationAudit`);
  const stoppingReconciliation = value.stoppingReconciliation === null
    ? null
    : parseLegacyStoppingReconciliationV1(value.stoppingReconciliation, `${path}.stoppingReconciliation`);
  const record: MigratedWorkerRecordV2 = {
    schemaVersion: readLiteralInteger(value.schemaVersion, CANONICAL_WORKER_STORE_SCHEMA_VERSION, `${path}.schemaVersion`),
    workerId: readString(value.workerId, `${path}.workerId`),
    workerIncarnationId: readString(value.workerIncarnationId, `${path}.workerIncarnationId`),
    workerGeneration: readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`),
    state,
    resumeState,
    reason: readNullableString(value.reason, `${path}.reason`),
    terminalOutcome: readNullableString(value.terminalOutcome, `${path}.terminalOutcome`),
    requiresReadinessReconciliation: readBoolean(
      value.requiresReadinessReconciliation,
      `${path}.requiresReadinessReconciliation`,
    ),
    legacyIdleHint: readBoolean(value.legacyIdleHint, `${path}.legacyIdleHint`),
    migrationStatus,
    readOnly: readBoolean(value.readOnly, `${path}.readOnly`),
    dispatchAllowed: value.dispatchAllowed === false
      ? false
      : (() => { throw new ContractValidationError(`${path}.dispatchAllowed`, "must be false during legacy migration"); })(),
    migrationAudit,
    stoppingReconciliation,
  };
  validateMigratedWorkerRecordSemantics(record, path);
  return record;
}

function validateMigratedWorkerRecordSemantics(record: MigratedWorkerRecordV2, path: string): void {
  if (record.workerIncarnationId !== record.migrationAudit.originalRunId) {
    throw new ContractValidationError(`${path}.workerIncarnationId`, "must preserve legacy runId byte-for-byte");
  }
  if (record.workerGeneration <= record.migrationAudit.workerGenerationFloor) {
    throw new ContractValidationError(`${path}.workerGeneration`, "must be monotonic above the persisted generation floor");
  }
  if (record.migrationStatus === "pending_stopping_reconciliation") {
    if (record.migrationAudit.originalState !== "stopping") {
      throw new ContractValidationError(`${path}.migrationAudit.originalState`, "pending migration requires legacy stopping");
    }
    if (
      record.state !== null
      || record.resumeState !== null
      || record.reason !== null
      || record.terminalOutcome !== null
      || record.requiresReadinessReconciliation
      || record.legacyIdleHint
      || !record.readOnly
      || record.stoppingReconciliation !== null
    ) {
      throw new ContractValidationError(
        path,
        "pending legacy stopping must be state-null, detail-free, read-only, and unreconciled",
      );
    }
    return;
  }
  if (record.state === null || record.readOnly) {
    throw new ContractValidationError(path, "completed migration requires a canonical state and must not remain read-only");
  }
  if (record.state === "blocked") {
    if (record.resumeState === null) {
      throw new ContractValidationError(`${path}.resumeState`, "blocked requires a persisted resumable state");
    }
  } else if (record.resumeState !== null) {
    throw new ContractValidationError(`${path}.resumeState`, "is only valid while state is blocked");
  }
  if (record.migrationAudit.originalState === "stopping" && record.stoppingReconciliation === null) {
    throw new ContractValidationError(`${path}.stoppingReconciliation`, "completed legacy stopping requires evidence");
  }
  if (record.migrationAudit.originalState !== "stopping" && record.stoppingReconciliation !== null) {
    throw new ContractValidationError(`${path}.stoppingReconciliation`, "is only valid for legacy stopping");
  }
  if (record.stoppingReconciliation !== null) {
    if (
      record.stoppingReconciliation.workerId !== record.workerId
      || record.stoppingReconciliation.workerIncarnationId !== record.workerIncarnationId
      || record.stoppingReconciliation.workerGeneration !== record.workerGeneration
    ) {
      throw new ContractValidationError(`${path}.stoppingReconciliation`, "must match worker identity and generation");
    }
    if (Date.parse(record.stoppingReconciliation.observedAt) < Date.parse(record.migrationAudit.migratedAt)) {
      throw new ContractValidationError(`${path}.stoppingReconciliation.observedAt`, "must not precede migration");
    }
  }
  const expected = expectedCompletedMigrationMapping(record);
  const fields = [
    "state",
    "resumeState",
    "reason",
    "terminalOutcome",
    "requiresReadinessReconciliation",
    "legacyIdleHint",
  ] as const;
  for (const field of fields) {
    if (record[field] !== expected[field]) {
      throw new ContractValidationError(`${path}.${field}`, `does not match legacy ${record.migrationAudit.originalState} mapping`);
    }
  }
}

function expectedCompletedMigrationMapping(record: MigratedWorkerRecordV2): LegacyStateMapping {
  switch (record.migrationAudit.originalState) {
    case "provisioning":
      return completeMapping("provisioning");
    case "running":
      return { ...completeMapping("registering"), requiresReadinessReconciliation: true };
    case "idle":
      return { ...completeMapping("registering"), requiresReadinessReconciliation: true, legacyIdleHint: true };
    case "needs_attention":
      return { ...completeMapping("blocked"), resumeState: "registering", reason: "legacy_needs_attention" };
    case "completed":
      return { ...completeMapping("stopped"), terminalOutcome: "completed" };
    case "failed":
      return { ...completeMapping("failed"), reason: record.migrationAudit.originalOutcome ?? "legacy_failed" };
    case "stopped":
      return completeMapping("stopped");
    case "lost":
      return { ...completeMapping("lost"), reason: record.migrationAudit.originalOutcome ?? "legacy_lost" };
    case "stopping": {
      const evidence = record.stoppingReconciliation;
      if (evidence === null) {
        throw new ContractValidationError("$.stoppingReconciliation", "completed legacy stopping requires evidence");
      }
      return {
        ...completeMapping(evidence.outcome === "unresolved_after_settle" ? "unreachable" : evidence.outcome),
        reason: evidence.outcome === "unresolved_after_settle" ? "legacy_stopping_unresolved" : null,
      };
    }
  }
}

export const PARTICIPANT_STATE_TRANSITION_CONTRACT_VERSION = 1 as const;

export const BLOCKED_RESUME_STATES = ["registering", "ready", "working", "waiting", "paused"] as const;
export type BlockedResumeState = StringEnum<typeof BLOCKED_RESUME_STATES>;

export const STALLED_RESUME_STATES = ["registering", "ready", "working", "waiting"] as const;
export type StalledResumeState = StringEnum<typeof STALLED_RESUME_STATES>;

export const PARTICIPANT_STATE_TRANSITION_EVIDENCE_KINDS = [
  "state_confirmation",
  "registration_started",
  "readiness_reconciled",
  "legacy_idle_reconciled",
  "turn_started",
  "turn_settled",
  "intentional_pause",
  "parked_resume",
  "blocker_detected",
  "blocked_reaffirmed",
  "blocker_cleared",
  "controller_liveness_stalled",
  "controller_liveness_recovered",
  "connectivity_recovered",
  "failure_observed",
  "stop_observed",
  "new_generation_provisioned",
] as const;

export type ParticipantStateTransitionEvidenceKind = StringEnum<
  typeof PARTICIPANT_STATE_TRANSITION_EVIDENCE_KINDS
>;

interface TransitionEvidenceBase<K extends ParticipantStateTransitionEvidenceKind> {
  kind: K;
  evidenceId: string;
}

interface ReadinessAssertions {
  adapterStartupReady: true;
  brokerRegistrationReady: true;
  bindingAttested: true;
  capabilityProfileAttested: true;
  assignmentControlSupported: true;
}

export type ParticipantStateTransitionEvidence =
  | TransitionEvidenceBase<"state_confirmation">
  | TransitionEvidenceBase<"registration_started">
  | (TransitionEvidenceBase<"readiness_reconciled"> & ReadinessAssertions)
  | (TransitionEvidenceBase<"legacy_idle_reconciled"> & ReadinessAssertions & {
    legacyIdleHint: true;
    noActiveTurn: true;
  })
  | (TransitionEvidenceBase<"turn_started"> & { turnId: string })
  | (TransitionEvidenceBase<"turn_settled"> & { turnId: string; noActiveTurn: true })
  | (TransitionEvidenceBase<"intentional_pause"> & { checkpointId: string })
  | (TransitionEvidenceBase<"parked_resume"> & ReadinessAssertions & {
    resumableState: "ready" | "waiting";
    parkedProcessConfirmed: true;
    noActiveTurn: true;
  })
  | (TransitionEvidenceBase<"blocker_detected"> & { resumeState: BlockedResumeState; reason: string })
  | (TransitionEvidenceBase<"blocked_reaffirmed"> & { storedResumeState: BlockedResumeState; reason: string })
  | (TransitionEvidenceBase<"blocker_cleared"> & {
    storedResumeState: BlockedResumeState;
    blockerClearConfirmed: true;
  })
  | (TransitionEvidenceBase<"controller_liveness_stalled"> & {
    controllerParticipantId: string;
    livenessDeadlineExceeded: true;
  })
  | (TransitionEvidenceBase<"controller_liveness_recovered"> & {
    controllerParticipantId: string;
    resumableState: StalledResumeState;
    positiveStateEvidenceId: string;
  })
  | (TransitionEvidenceBase<"connectivity_recovered"> & {
    freshReadinessReconciliationRequired: true;
  })
  | (TransitionEvidenceBase<"failure_observed"> & { outcome: "failed" | "lost" | "unreachable" })
  | TransitionEvidenceBase<"stop_observed">
  | TransitionEvidenceBase<"new_generation_provisioned">;

export interface ParticipantStateTransitionContextV1 {
  version: typeof PARTICIPANT_STATE_TRANSITION_CONTRACT_VERSION;
  previousState: ParticipantState;
  previousResumeState?: BlockedResumeState;
  state: ParticipantState;
  previousWorkerGeneration: WorkerGeneration;
  workerGeneration: WorkerGeneration;
  evidence: ParticipantStateTransitionEvidence;
}

/** Backwards-compatible type name for the v1 transition contract. */
export type ParticipantStateTransitionContext = ParticipantStateTransitionContextV1;

type SameGenerationTransitionRule = ParticipantStateTransitionEvidenceKind | null;
type SameGenerationTransitionRow = Readonly<Record<ParticipantState, SameGenerationTransitionRule>>;

/**
 * Every same-generation pair is explicit. `null` is a denial; no exceptional-target fallback exists.
 * In particular, terminal states have no exits, paused cannot stall, and unreachable can only
 * re-enter readiness through registering.
 */
export const PARTICIPANT_STATE_TRANSITION_TABLE = {
  provisioning: {
    provisioning: "state_confirmation",
    registering: "registration_started",
    ready: null,
    working: null,
    waiting: null,
    paused: null,
    stalled: null,
    blocked: null,
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  registering: {
    provisioning: null,
    registering: "state_confirmation",
    ready: "readiness_reconciled",
    working: null,
    waiting: "legacy_idle_reconciled",
    paused: null,
    stalled: "controller_liveness_stalled",
    blocked: "blocker_detected",
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  ready: {
    provisioning: null,
    registering: null,
    ready: "state_confirmation",
    working: "turn_started",
    waiting: null,
    paused: null,
    stalled: "controller_liveness_stalled",
    blocked: "blocker_detected",
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  working: {
    provisioning: null,
    registering: null,
    ready: null,
    working: "state_confirmation",
    waiting: "turn_settled",
    paused: "intentional_pause",
    stalled: "controller_liveness_stalled",
    blocked: "blocker_detected",
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  waiting: {
    provisioning: null,
    registering: null,
    ready: null,
    working: "turn_started",
    waiting: "state_confirmation",
    paused: "intentional_pause",
    stalled: "controller_liveness_stalled",
    blocked: "blocker_detected",
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  paused: {
    provisioning: null,
    registering: null,
    ready: "parked_resume",
    working: null,
    waiting: "parked_resume",
    paused: "state_confirmation",
    stalled: null,
    blocked: null,
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  stalled: {
    provisioning: null,
    registering: "controller_liveness_recovered",
    ready: "controller_liveness_recovered",
    working: "controller_liveness_recovered",
    waiting: "controller_liveness_recovered",
    paused: null,
    stalled: "controller_liveness_stalled",
    blocked: null,
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  blocked: {
    provisioning: null,
    registering: "blocker_cleared",
    ready: "blocker_cleared",
    working: "blocker_cleared",
    waiting: "blocker_cleared",
    paused: "blocker_cleared",
    stalled: null,
    blocked: "blocked_reaffirmed",
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  failed: {
    provisioning: null,
    registering: null,
    ready: null,
    working: null,
    waiting: null,
    paused: null,
    stalled: null,
    blocked: null,
    failed: "state_confirmation",
    lost: null,
    unreachable: null,
    stopped: null,
  },
  lost: {
    provisioning: null,
    registering: null,
    ready: null,
    working: null,
    waiting: null,
    paused: null,
    stalled: null,
    blocked: null,
    failed: null,
    lost: "state_confirmation",
    unreachable: null,
    stopped: null,
  },
  unreachable: {
    provisioning: null,
    registering: "connectivity_recovered",
    ready: null,
    working: null,
    waiting: null,
    paused: null,
    stalled: null,
    blocked: null,
    failed: "failure_observed",
    lost: "failure_observed",
    unreachable: "failure_observed",
    stopped: "stop_observed",
  },
  stopped: {
    provisioning: null,
    registering: null,
    ready: null,
    working: null,
    waiting: null,
    paused: null,
    stalled: null,
    blocked: null,
    failed: null,
    lost: null,
    unreachable: null,
    stopped: "state_confirmation",
  },
} as const satisfies Readonly<Record<ParticipantState, SameGenerationTransitionRow>>;

/** The only transitions that may cross exactly one worker-generation boundary. */
export const PARTICIPANT_NEW_GENERATION_TRANSITIONS = {
  provisioning: [] as const,
  registering: [] as const,
  ready: [] as const,
  working: [] as const,
  waiting: [] as const,
  paused: ["ready", "waiting"] as const,
  stalled: [] as const,
  blocked: [] as const,
  failed: ["provisioning"] as const,
  lost: ["provisioning"] as const,
  unreachable: [] as const,
  stopped: ["provisioning"] as const,
} as const satisfies Readonly<Record<ParticipantState, readonly ParticipantState[]>>;

function readTrue(value: unknown, path: string): true {
  if (readBoolean(value, path) !== true) throw new ContractValidationError(path, "must be true");
  return true;
}

function parseReadinessAssertions(
  value: Record<string, unknown>,
  path: string,
): ReadinessAssertions {
  return {
    adapterStartupReady: readTrue(value.adapterStartupReady, `${path}.adapterStartupReady`),
    brokerRegistrationReady: readTrue(value.brokerRegistrationReady, `${path}.brokerRegistrationReady`),
    bindingAttested: readTrue(value.bindingAttested, `${path}.bindingAttested`),
    capabilityProfileAttested: readTrue(value.capabilityProfileAttested, `${path}.capabilityProfileAttested`),
    assignmentControlSupported: readTrue(value.assignmentControlSupported, `${path}.assignmentControlSupported`),
  };
}

const READINESS_EVIDENCE_KEYS = [
  "adapterStartupReady",
  "brokerRegistrationReady",
  "bindingAttested",
  "capabilityProfileAttested",
  "assignmentControlSupported",
] as const;

export function parseParticipantStateTransitionEvidence(
  value: unknown,
  path = "$.evidence",
): ParticipantStateTransitionEvidence {
  assertRecord(value, path);
  const kind = readEnum(value.kind, PARTICIPANT_STATE_TRANSITION_EVIDENCE_KINDS, `${path}.kind`);
  const evidenceId = readString(value.evidenceId, `${path}.evidenceId`);
  switch (kind) {
    case "state_confirmation":
    case "registration_started":
    case "stop_observed":
    case "new_generation_provisioned":
      assertExactKeys(value, ["kind", "evidenceId"], [], path);
      return { kind, evidenceId };
    case "readiness_reconciled":
      assertExactKeys(value, ["kind", "evidenceId", ...READINESS_EVIDENCE_KEYS], [], path);
      return { kind, evidenceId, ...parseReadinessAssertions(value, path) };
    case "legacy_idle_reconciled":
      assertExactKeys(
        value,
        ["kind", "evidenceId", ...READINESS_EVIDENCE_KEYS, "legacyIdleHint", "noActiveTurn"],
        [],
        path,
      );
      return {
        kind,
        evidenceId,
        ...parseReadinessAssertions(value, path),
        legacyIdleHint: readTrue(value.legacyIdleHint, `${path}.legacyIdleHint`),
        noActiveTurn: readTrue(value.noActiveTurn, `${path}.noActiveTurn`),
      };
    case "turn_started":
      assertExactKeys(value, ["kind", "evidenceId", "turnId"], [], path);
      return { kind, evidenceId, turnId: readString(value.turnId, `${path}.turnId`) };
    case "turn_settled":
      assertExactKeys(value, ["kind", "evidenceId", "turnId", "noActiveTurn"], [], path);
      return {
        kind,
        evidenceId,
        turnId: readString(value.turnId, `${path}.turnId`),
        noActiveTurn: readTrue(value.noActiveTurn, `${path}.noActiveTurn`),
      };
    case "intentional_pause":
      assertExactKeys(value, ["kind", "evidenceId", "checkpointId"], [], path);
      return { kind, evidenceId, checkpointId: readString(value.checkpointId, `${path}.checkpointId`) };
    case "parked_resume":
      assertExactKeys(
        value,
        [
          "kind",
          "evidenceId",
          ...READINESS_EVIDENCE_KEYS,
          "resumableState",
          "parkedProcessConfirmed",
          "noActiveTurn",
        ],
        [],
        path,
      );
      return {
        kind,
        evidenceId,
        ...parseReadinessAssertions(value, path),
        resumableState: readEnum(value.resumableState, ["ready", "waiting"] as const, `${path}.resumableState`),
        parkedProcessConfirmed: readTrue(value.parkedProcessConfirmed, `${path}.parkedProcessConfirmed`),
        noActiveTurn: readTrue(value.noActiveTurn, `${path}.noActiveTurn`),
      };
    case "blocker_detected":
      assertExactKeys(value, ["kind", "evidenceId", "resumeState", "reason"], [], path);
      return {
        kind,
        evidenceId,
        resumeState: readEnum(value.resumeState, BLOCKED_RESUME_STATES, `${path}.resumeState`),
        reason: readString(value.reason, `${path}.reason`),
      };
    case "blocked_reaffirmed":
      assertExactKeys(value, ["kind", "evidenceId", "storedResumeState", "reason"], [], path);
      return {
        kind,
        evidenceId,
        storedResumeState: readEnum(value.storedResumeState, BLOCKED_RESUME_STATES, `${path}.storedResumeState`),
        reason: readString(value.reason, `${path}.reason`),
      };
    case "blocker_cleared":
      assertExactKeys(value, ["kind", "evidenceId", "storedResumeState", "blockerClearConfirmed"], [], path);
      return {
        kind,
        evidenceId,
        storedResumeState: readEnum(value.storedResumeState, BLOCKED_RESUME_STATES, `${path}.storedResumeState`),
        blockerClearConfirmed: readTrue(value.blockerClearConfirmed, `${path}.blockerClearConfirmed`),
      };
    case "controller_liveness_stalled":
      assertExactKeys(
        value,
        ["kind", "evidenceId", "controllerParticipantId", "livenessDeadlineExceeded"],
        [],
        path,
      );
      return {
        kind,
        evidenceId,
        controllerParticipantId: readString(value.controllerParticipantId, `${path}.controllerParticipantId`),
        livenessDeadlineExceeded: readTrue(value.livenessDeadlineExceeded, `${path}.livenessDeadlineExceeded`),
      };
    case "controller_liveness_recovered":
      assertExactKeys(
        value,
        ["kind", "evidenceId", "controllerParticipantId", "resumableState", "positiveStateEvidenceId"],
        [],
        path,
      );
      return {
        kind,
        evidenceId,
        controllerParticipantId: readString(value.controllerParticipantId, `${path}.controllerParticipantId`),
        resumableState: readEnum(value.resumableState, STALLED_RESUME_STATES, `${path}.resumableState`),
        positiveStateEvidenceId: readString(value.positiveStateEvidenceId, `${path}.positiveStateEvidenceId`),
      };
    case "connectivity_recovered":
      assertExactKeys(value, ["kind", "evidenceId", "freshReadinessReconciliationRequired"], [], path);
      return {
        kind,
        evidenceId,
        freshReadinessReconciliationRequired: readTrue(
          value.freshReadinessReconciliationRequired,
          `${path}.freshReadinessReconciliationRequired`,
        ),
      };
    case "failure_observed":
      assertExactKeys(value, ["kind", "evidenceId", "outcome"], [], path);
      return {
        kind,
        evidenceId,
        outcome: readEnum(value.outcome, ["failed", "lost", "unreachable"] as const, `${path}.outcome`),
      };
  }
}

export function parseParticipantStateTransitionContextV1(
  value: unknown,
  path = "$",
): ParticipantStateTransitionContextV1 {
  assertRecord(value, path);
  assertExactKeys(
    value,
    ["version", "previousState", "state", "previousWorkerGeneration", "workerGeneration", "evidence"],
    ["previousResumeState"],
    path,
  );
  const previousState = parseParticipantState(value.previousState, `${path}.previousState`);
  const previousResumeState = value.previousResumeState === undefined
    ? undefined
    : readEnum(value.previousResumeState, BLOCKED_RESUME_STATES, `${path}.previousResumeState`);
  if (previousState === "blocked" && previousResumeState === undefined) {
    throw new ContractValidationError(`${path}.previousResumeState`, "is required for a persisted blocked state");
  }
  if (previousState !== "blocked" && previousResumeState !== undefined) {
    throw new ContractValidationError(`${path}.previousResumeState`, "is valid only for a persisted blocked state");
  }
  return {
    version: readLiteralInteger(
      value.version,
      PARTICIPANT_STATE_TRANSITION_CONTRACT_VERSION,
      `${path}.version`,
    ),
    previousState,
    ...(previousResumeState === undefined ? {} : { previousResumeState }),
    state: parseParticipantState(value.state, `${path}.state`),
    previousWorkerGeneration: readWorkerGeneration(value.previousWorkerGeneration, `${path}.previousWorkerGeneration`),
    workerGeneration: readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`),
    evidence: parseParticipantStateTransitionEvidence(value.evidence, `${path}.evidence`),
  };
}

function validateTransitionEvidenceTarget(context: ParticipantStateTransitionContextV1): void {
  const { evidence, previousState, previousResumeState, state } = context;
  switch (evidence.kind) {
    case "failure_observed":
      if (evidence.outcome !== state) {
        throw new ContractValidationError("$.evidence.outcome", "must match the failure target state");
      }
      break;
    case "parked_resume":
      if (evidence.resumableState !== state) {
        throw new ContractValidationError("$.evidence.resumableState", "must match the resumed target state");
      }
      break;
    case "blocker_detected":
      if (evidence.resumeState !== previousState) {
        throw new ContractValidationError("$.evidence.resumeState", "must preserve the state interrupted by the blocker");
      }
      break;
    case "blocked_reaffirmed":
      if (evidence.storedResumeState !== previousResumeState) {
        throw new ContractValidationError(
          "$.evidence.storedResumeState",
          "must preserve the persisted blocked resume state",
        );
      }
      break;
    case "blocker_cleared":
      if (evidence.storedResumeState !== previousResumeState) {
        throw new ContractValidationError(
          "$.evidence.storedResumeState",
          "must match the persisted blocked resume state",
        );
      }
      if (evidence.storedResumeState !== state) {
        throw new ContractValidationError("$.evidence.storedResumeState", "must match the recovered target state");
      }
      break;
    case "controller_liveness_recovered":
      if (evidence.resumableState !== state) {
        throw new ContractValidationError("$.evidence.resumableState", "must match the positively evidenced target state");
      }
      break;
    default:
      break;
  }
}

/** Enforces the complete evidence-guarded §22.5 transition and generation tables. */
export function validateParticipantStateTransition(value: unknown): void {
  const context = parseParticipantStateTransitionContextV1(value);
  const generationDelta = context.workerGeneration - context.previousWorkerGeneration;
  if (generationDelta < 0) {
    throw new ContractValidationError("$.workerGeneration", "must not regress");
  }
  if (generationDelta > 1) {
    throw new ContractValidationError("$.workerGeneration", "must increase by exactly one generation");
  }
  if (generationDelta === 1) {
    const allowedTargets = PARTICIPANT_NEW_GENERATION_TRANSITIONS[context.previousState];
    if (!(allowedTargets as readonly ParticipantState[]).includes(context.state)) {
      throw new ContractValidationError(
        "$.state",
        `transition ${context.previousState} -> ${context.state} is not canonical for a new generation`,
      );
    }
    const expectedEvidence: ParticipantStateTransitionEvidenceKind = context.previousState === "paused"
      ? "parked_resume"
      : "new_generation_provisioned";
    if (context.evidence.kind !== expectedEvidence) {
      throw new ContractValidationError(
        "$.evidence.kind",
        `transition requires ${expectedEvidence} evidence`,
      );
    }
    validateTransitionEvidenceTarget(context);
    return;
  }
  const rule = PARTICIPANT_STATE_TRANSITION_TABLE[context.previousState][context.state];
  if (rule === null) {
    throw new ContractValidationError(
      "$.state",
      `transition ${context.previousState} -> ${context.state} is not canonical for the current generation`,
    );
  }
  if (context.evidence.kind !== rule) {
    throw new ContractValidationError("$.evidence.kind", `transition requires ${rule} evidence`);
  }
  validateTransitionEvidenceTarget(context);
}

export const PARTICIPANT_DISPATCHABLE_STATES = ["ready", "waiting"] as const satisfies readonly ParticipantState[];
export const PARTICIPANT_READ_ONLY_STATES = ["unreachable"] as const satisfies readonly ParticipantState[];

/** Dispatch is positive-state gated; transition, failure, park, block, stall, and connectivity states fail closed. */
export function canDispatchParticipantState(value: unknown): boolean {
  const state = parseParticipantState(value);
  return (PARTICIPANT_DISPATCHABLE_STATES as readonly ParticipantState[]).includes(state);
}

/** Unreachable remains a nonterminal observation state, but is read-only until registration recovery. */
export function isParticipantStateReadOnly(value: unknown): boolean {
  const state = parseParticipantState(value);
  return (PARTICIPANT_READ_ONLY_STATES as readonly ParticipantState[]).includes(state);
}

/** Compatibility helpers must consult direct systemd/cgroup evidence before process cleanup. */
export function requiresDirectProcessEvidenceForCleanup(_state: ParticipantState): true {
  return true;
}

/** Dispatch requires positive v2 readiness proof; no legacy-migrated record is immediately dispatchable. */
export function canDispatchMigratedWorker(record: MigratedWorkerRecordV2): false {
  parseMigratedWorkerRecordV2(record);
  return false;
}

export const validateParticipantHealthEventStore = (value: unknown): StoreValidationResult<ParticipantHealthEventV1> =>
  validateVersionedStoreRecord(value, PARTICIPANT_HEALTH_EVENT_VERSION, parseParticipantHealthEventV1);
export const validateLegacyWorkerMigrationInputStore = (value: unknown): StoreValidationResult<LegacyWorkerMigrationInputV1> =>
  validateVersionedStoreRecord(value, WORKER_STATE_MIGRATION_CONTRACT_VERSION, parseLegacyWorkerMigrationInputV1);
export const validateLegacyStoppingReconciliationStore = (value: unknown): StoreValidationResult<LegacyStoppingReconciliationV1> =>
  validateVersionedStoreRecord(value, WORKER_STATE_MIGRATION_CONTRACT_VERSION, parseLegacyStoppingReconciliationV1);
