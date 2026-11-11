import {
  assertExactKeys,
  assertRecord,
  ContractValidationError,
  readBoolean,
  readEnum,
  readInteger,
  readOptionalString,
  readString,
  readStringArray,
  readTimestamp,
  participantBindingEpoch,
  validateVersionedStoreRecord,
  type ParticipantBindingEpoch,
  type StoreValidationResult,
  workerGeneration as readWorkerGeneration,
  type WorkerGeneration,
} from "./canonical.ts";
import {
  LEGACY_WORKER_STATES,
  migrateLegacyWorkerRecordV1,
  parseLegacyWorkerMigrationInputV1,
  parseMigratedWorkerRecordV2,
  type LegacyWorkerMigrationInputV1,
  type LegacyWorkerState,
  type MigratedWorkerRecordV2,
  type ParticipantState,
} from "./boss-participant-state.ts";

export const FULL_WORKER_STORE_MIGRATION_VERSION = 1 as const;
export const FULL_WORKER_STORE_V2_RECORD_VERSION = "orc.worker-store-record.v2" as const;
export const WORKER_STORE_MANAGER_RECIPIENT_CONTEXTS = ["pi", "opencode", "headless_cli"] as const;

export type WorkerStoreManagerRecipientContext = (typeof WORKER_STORE_MANAGER_RECIPIENT_CONTEXTS)[number];

export interface InteractiveOwningManagerRecipientV1 {
  recipientPrincipalId: string;
  recipientBindingEpoch: ParticipantBindingEpoch;
  recipientContext: "pi" | "opencode";
  recipientSessionId: string;
  recipientTargetSessionId?: string;
}

export interface HeadlessOwningManagerRecipientV1 {
  recipientPrincipalId: string;
  recipientBindingEpoch: ParticipantBindingEpoch;
  recipientContext: "headless_cli";
}

export type OwningManagerRecipientV1 = InteractiveOwningManagerRecipientV1 | HeadlessOwningManagerRecipientV1;

export interface LegacyWorkerCompatibilityFieldsV1 {
  environment: {
    AGENT_INTERCOM_WORKER_ID: string;
    AGENT_INTERCOM_RUN_ID: string;
    workspacePath?: string;
  };
  health: {
    observedLegacyState: LegacyWorkerState;
    lastConfirmedAt?: string;
    failureCode?: string;
  };
  runtime: {
    runtimeId: string;
    processId?: number;
    leaseExpiresAt?: string;
    maxRuntimeAt?: string;
  };
  adapter: {
    adapterId: string;
    adapterVersion: string;
    sessionId?: string;
    readinessReported: boolean;
  };
  systemd: {
    unitName: string;
    activeState: string;
    subState: string;
    observedAt: string;
  };
  notice: {
    pendingNoticeIds: string[];
    lastDeliveredNoticeId?: string;
    owningManagerRecipient: OwningManagerRecipientV1;
  };
  controller: {
    projectionId?: string;
    revision: number;
  };
}

export interface FullWorkerStoreMigrationInputV1 extends LegacyWorkerCompatibilityFieldsV1 {
  version: typeof FULL_WORKER_STORE_MIGRATION_VERSION;
  worker: LegacyWorkerMigrationInputV1;
}

export interface WorkerStoreSurfaceIdentityV2 {
  workerIncarnationId: string;
  workerGeneration: WorkerGeneration;
}

export interface WorkerStoreRecordV2 {
  version: typeof FULL_WORKER_STORE_V2_RECORD_VERSION;
  worker: MigratedWorkerRecordV2;
  environment: {
    AGENT_INTERCOM_WORKER_ID: string;
    AGENT_INTERCOM_WORKER_INCARNATION_ID: string;
    AGENT_INTERCOM_WORKER_GENERATION: string;
    /** Deprecated incarnation alias retained only for the v2 rollout. */
    AGENT_INTERCOM_RUN_ID: string;
    workspacePath?: string;
  };
  health: WorkerStoreSurfaceIdentityV2 & {
    originalLegacyState: LegacyWorkerState;
    canonicalState: ParticipantState | null;
    lastConfirmedAt?: string;
    failureCode?: string;
  };
  runtime: WorkerStoreSurfaceIdentityV2 & LegacyWorkerCompatibilityFieldsV1["runtime"];
  adapter: WorkerStoreSurfaceIdentityV2 & LegacyWorkerCompatibilityFieldsV1["adapter"];
  systemd: WorkerStoreSurfaceIdentityV2 & LegacyWorkerCompatibilityFieldsV1["systemd"];
  notice: WorkerStoreSurfaceIdentityV2 & LegacyWorkerCompatibilityFieldsV1["notice"];
  controller: WorkerStoreSurfaceIdentityV2 & LegacyWorkerCompatibilityFieldsV1["controller"];
  compatibilityAudit: {
    sourceEnvironmentIncarnationField: "AGENT_INTERCOM_RUN_ID";
    targetEnvironmentIncarnationField: "AGENT_INTERCOM_WORKER_INCARNATION_ID";
    deprecatedEnvironmentAliasLastSupportedVersion: typeof FULL_WORKER_STORE_V2_RECORD_VERSION;
    bossRunIdDerived: false;
    preservedFieldGroups: ["environment", "health", "runtime", "adapter", "systemd", "notice", "controller"];
  };
}

function parseOwningManagerRecipient(value: unknown, path: string): OwningManagerRecipientV1 {
  assertRecord(value, path);
  const recipientContext = readEnum(value.recipientContext, WORKER_STORE_MANAGER_RECIPIENT_CONTEXTS, `${path}.recipientContext`);
  const recipientPrincipalId = readString(value.recipientPrincipalId, `${path}.recipientPrincipalId`);
  const recipientBindingEpoch = participantBindingEpoch(value.recipientBindingEpoch, `${path}.recipientBindingEpoch`);
  if (recipientContext === "headless_cli") {
    assertExactKeys(value, ["recipientPrincipalId", "recipientBindingEpoch", "recipientContext"], [], path);
    return { recipientPrincipalId, recipientBindingEpoch, recipientContext };
  }
  assertExactKeys(
    value,
    ["recipientPrincipalId", "recipientBindingEpoch", "recipientContext", "recipientSessionId"],
    ["recipientTargetSessionId"],
    path,
  );
  return {
    recipientPrincipalId,
    recipientBindingEpoch,
    recipientContext,
    recipientSessionId: readString(value.recipientSessionId, `${path}.recipientSessionId`),
    ...(value.recipientTargetSessionId === undefined
      ? {}
      : { recipientTargetSessionId: readString(value.recipientTargetSessionId, `${path}.recipientTargetSessionId`) }),
  };
}

function parseCompatibilityFields(value: Record<string, unknown>, path: string): LegacyWorkerCompatibilityFieldsV1 {
  assertRecord(value.environment, `${path}.environment`);
  assertExactKeys(value.environment, ["AGENT_INTERCOM_WORKER_ID", "AGENT_INTERCOM_RUN_ID"], ["workspacePath"], `${path}.environment`);
  const environment = {
    AGENT_INTERCOM_WORKER_ID: readString(value.environment.AGENT_INTERCOM_WORKER_ID, `${path}.environment.AGENT_INTERCOM_WORKER_ID`),
    AGENT_INTERCOM_RUN_ID: readString(value.environment.AGENT_INTERCOM_RUN_ID, `${path}.environment.AGENT_INTERCOM_RUN_ID`),
    ...(value.environment.workspacePath === undefined ? {} : { workspacePath: readString(value.environment.workspacePath, `${path}.environment.workspacePath`) }),
  };

  assertRecord(value.health, `${path}.health`);
  assertExactKeys(value.health, ["observedLegacyState"], ["lastConfirmedAt", "failureCode"], `${path}.health`);
  const health = {
    observedLegacyState: readEnum(value.health.observedLegacyState, LEGACY_WORKER_STATES, `${path}.health.observedLegacyState`),
    ...(value.health.lastConfirmedAt === undefined ? {} : { lastConfirmedAt: readTimestamp(value.health.lastConfirmedAt, `${path}.health.lastConfirmedAt`) }),
    ...(value.health.failureCode === undefined ? {} : { failureCode: readString(value.health.failureCode, `${path}.health.failureCode`) }),
  };

  assertRecord(value.runtime, `${path}.runtime`);
  assertExactKeys(value.runtime, ["runtimeId"], ["processId", "leaseExpiresAt", "maxRuntimeAt"], `${path}.runtime`);
  const runtime = {
    runtimeId: readString(value.runtime.runtimeId, `${path}.runtime.runtimeId`),
    ...(value.runtime.processId === undefined ? {} : { processId: readInteger(value.runtime.processId, `${path}.runtime.processId`, 1) }),
    ...(value.runtime.leaseExpiresAt === undefined ? {} : { leaseExpiresAt: readTimestamp(value.runtime.leaseExpiresAt, `${path}.runtime.leaseExpiresAt`) }),
    ...(value.runtime.maxRuntimeAt === undefined ? {} : { maxRuntimeAt: readTimestamp(value.runtime.maxRuntimeAt, `${path}.runtime.maxRuntimeAt`) }),
  };

  assertRecord(value.adapter, `${path}.adapter`);
  assertExactKeys(value.adapter, ["adapterId", "adapterVersion", "readinessReported"], ["sessionId"], `${path}.adapter`);
  const adapter = {
    adapterId: readString(value.adapter.adapterId, `${path}.adapter.adapterId`),
    adapterVersion: readString(value.adapter.adapterVersion, `${path}.adapter.adapterVersion`),
    ...(value.adapter.sessionId === undefined ? {} : { sessionId: readString(value.adapter.sessionId, `${path}.adapter.sessionId`) }),
    readinessReported: readBoolean(value.adapter.readinessReported, `${path}.adapter.readinessReported`),
  };

  assertRecord(value.systemd, `${path}.systemd`);
  assertExactKeys(value.systemd, ["unitName", "activeState", "subState", "observedAt"], [], `${path}.systemd`);
  const systemd = {
    unitName: readString(value.systemd.unitName, `${path}.systemd.unitName`),
    activeState: readString(value.systemd.activeState, `${path}.systemd.activeState`),
    subState: readString(value.systemd.subState, `${path}.systemd.subState`),
    observedAt: readTimestamp(value.systemd.observedAt, `${path}.systemd.observedAt`),
  };

  assertRecord(value.notice, `${path}.notice`);
  assertExactKeys(value.notice, ["pendingNoticeIds", "owningManagerRecipient"], ["lastDeliveredNoticeId"], `${path}.notice`);
  const pendingNoticeIds = readStringArray(value.notice.pendingNoticeIds, `${path}.notice.pendingNoticeIds`);
  if (new Set(pendingNoticeIds).size !== pendingNoticeIds.length) throw new ContractValidationError(`${path}.notice.pendingNoticeIds`, "must not contain duplicates");
  const notice = {
    pendingNoticeIds,
    ...(value.notice.lastDeliveredNoticeId === undefined ? {} : { lastDeliveredNoticeId: readString(value.notice.lastDeliveredNoticeId, `${path}.notice.lastDeliveredNoticeId`) }),
    owningManagerRecipient: parseOwningManagerRecipient(value.notice.owningManagerRecipient, `${path}.notice.owningManagerRecipient`),
  };

  assertRecord(value.controller, `${path}.controller`);
  assertExactKeys(value.controller, ["revision"], ["projectionId"], `${path}.controller`);
  const controller = {
    ...(value.controller.projectionId === undefined ? {} : { projectionId: readString(value.controller.projectionId, `${path}.controller.projectionId`) }),
    revision: readInteger(value.controller.revision, `${path}.controller.revision`),
  };
  return { environment, health, runtime, adapter, systemd, notice, controller };
}

export function parseFullWorkerStoreMigrationInputV1(value: unknown): FullWorkerStoreMigrationInputV1 {
  assertRecord(value);
  assertExactKeys(value, ["version", "worker", "environment", "health", "runtime", "adapter", "systemd", "notice", "controller"]);
  if (value.version !== FULL_WORKER_STORE_MIGRATION_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  const worker = parseLegacyWorkerMigrationInputV1(value.worker, "$.worker");
  const fields = parseCompatibilityFields(value, "$");
  if (fields.environment.AGENT_INTERCOM_WORKER_ID !== worker.workerId) throw new ContractValidationError("$.environment.AGENT_INTERCOM_WORKER_ID", "must match workerId");
  if (fields.environment.AGENT_INTERCOM_RUN_ID !== worker.legacyRunId) throw new ContractValidationError("$.environment.AGENT_INTERCOM_RUN_ID", "must match the legacy incarnation byte-for-byte");
  if (fields.health.observedLegacyState !== worker.legacyState) throw new ContractValidationError("$.health.observedLegacyState", "must match the legacy worker state");
  return { version: FULL_WORKER_STORE_MIGRATION_VERSION, worker, ...fields };
}

function bindWorkerSurface<T extends object>(surface: T, worker: MigratedWorkerRecordV2): T & WorkerStoreSurfaceIdentityV2 {
  return {
    ...surface,
    workerIncarnationId: worker.workerIncarnationId,
    workerGeneration: worker.workerGeneration,
  };
}

function stripWorkerSurfaceIdentity(
  value: unknown,
  path: string,
  required: readonly string[],
  optional: readonly string[],
  worker: MigratedWorkerRecordV2,
): Record<string, unknown> {
  assertRecord(value, path);
  assertExactKeys(value, [...required, "workerIncarnationId", "workerGeneration"], optional, path);
  const workerIncarnationId = readString(value.workerIncarnationId, `${path}.workerIncarnationId`);
  const workerGeneration = readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`);
  if (workerIncarnationId !== worker.workerIncarnationId || workerGeneration !== worker.workerGeneration) {
    throw new ContractValidationError(path, "must bind the migrated worker incarnation and generation");
  }
  const result: Record<string, unknown> = {};
  for (const key of [...required, ...optional]) {
    if (value[key] !== undefined) result[key] = value[key];
  }
  return result;
}

export function migrateFullWorkerStoreV1(value: unknown): WorkerStoreRecordV2 {
  const input = parseFullWorkerStoreMigrationInputV1(value);
  const worker = migrateLegacyWorkerRecordV1(input.worker);
  return {
    version: FULL_WORKER_STORE_V2_RECORD_VERSION,
    worker,
    environment: {
      AGENT_INTERCOM_WORKER_ID: worker.workerId,
      AGENT_INTERCOM_WORKER_INCARNATION_ID: worker.workerIncarnationId,
      AGENT_INTERCOM_WORKER_GENERATION: String(worker.workerGeneration),
      AGENT_INTERCOM_RUN_ID: worker.workerIncarnationId,
      ...(input.environment.workspacePath === undefined ? {} : { workspacePath: input.environment.workspacePath }),
    },
    health: bindWorkerSurface({
      originalLegacyState: input.health.observedLegacyState,
      canonicalState: worker.state,
      ...(input.health.lastConfirmedAt === undefined ? {} : { lastConfirmedAt: input.health.lastConfirmedAt }),
      ...(input.health.failureCode === undefined ? {} : { failureCode: input.health.failureCode }),
    }, worker),
    runtime: bindWorkerSurface(input.runtime, worker),
    adapter: bindWorkerSurface(input.adapter, worker),
    systemd: bindWorkerSurface(input.systemd, worker),
    notice: bindWorkerSurface(input.notice, worker),
    controller: bindWorkerSurface(input.controller, worker),
    compatibilityAudit: {
      sourceEnvironmentIncarnationField: "AGENT_INTERCOM_RUN_ID",
      targetEnvironmentIncarnationField: "AGENT_INTERCOM_WORKER_INCARNATION_ID",
      deprecatedEnvironmentAliasLastSupportedVersion: FULL_WORKER_STORE_V2_RECORD_VERSION,
      bossRunIdDerived: false,
      preservedFieldGroups: ["environment", "health", "runtime", "adapter", "systemd", "notice", "controller"],
    },
  };
}

export function parseWorkerStoreRecordV2(value: unknown): WorkerStoreRecordV2 {
  assertRecord(value);
  assertExactKeys(value, ["version", "worker", "environment", "health", "runtime", "adapter", "systemd", "notice", "controller", "compatibilityAudit"]);
  if (value.version !== FULL_WORKER_STORE_V2_RECORD_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  const worker = parseMigratedWorkerRecordV2(value.worker, "$.worker");

  assertRecord(value.environment, "$.environment");
  assertExactKeys(
    value.environment,
    ["AGENT_INTERCOM_WORKER_ID", "AGENT_INTERCOM_WORKER_INCARNATION_ID", "AGENT_INTERCOM_WORKER_GENERATION", "AGENT_INTERCOM_RUN_ID"],
    ["workspacePath"],
    "$.environment",
  );
  const environmentWorkerId = readString(value.environment.AGENT_INTERCOM_WORKER_ID, "$.environment.AGENT_INTERCOM_WORKER_ID");
  const environmentIncarnationId = readString(value.environment.AGENT_INTERCOM_WORKER_INCARNATION_ID, "$.environment.AGENT_INTERCOM_WORKER_INCARNATION_ID");
  const environmentGeneration = readString(value.environment.AGENT_INTERCOM_WORKER_GENERATION, "$.environment.AGENT_INTERCOM_WORKER_GENERATION");
  const deprecatedEnvironmentIncarnationId = readString(value.environment.AGENT_INTERCOM_RUN_ID, "$.environment.AGENT_INTERCOM_RUN_ID");
  const workspacePath = readOptionalString(value.environment.workspacePath, "$.environment.workspacePath");
  if (
    environmentWorkerId !== worker.workerId
    || environmentIncarnationId !== worker.workerIncarnationId
    || environmentGeneration !== String(worker.workerGeneration)
  ) throw new ContractValidationError("$.environment", "must match the migrated worker identity without Boss metadata");
  if (deprecatedEnvironmentIncarnationId !== worker.workerIncarnationId) {
    throw new ContractValidationError("$.environment.AGENT_INTERCOM_RUN_ID", "must remain a byte-for-byte alias of workerIncarnationId during the v2 rollout");
  }

  const health = stripWorkerSurfaceIdentity(value.health, "$.health", ["originalLegacyState", "canonicalState"], ["lastConfirmedAt", "failureCode"], worker);
  if (health.originalLegacyState !== worker.migrationAudit.originalState || health.canonicalState !== worker.state) {
    throw new ContractValidationError("$.health", "must retain the original state and project the canonical state");
  }
  const runtime = stripWorkerSurfaceIdentity(value.runtime, "$.runtime", ["runtimeId"], ["processId", "leaseExpiresAt", "maxRuntimeAt"], worker);
  const adapter = stripWorkerSurfaceIdentity(value.adapter, "$.adapter", ["adapterId", "adapterVersion", "readinessReported"], ["sessionId"], worker);
  const systemd = stripWorkerSurfaceIdentity(value.systemd, "$.systemd", ["unitName", "activeState", "subState", "observedAt"], [], worker);
  const notice = stripWorkerSurfaceIdentity(value.notice, "$.notice", ["pendingNoticeIds", "owningManagerRecipient"], ["lastDeliveredNoticeId"], worker);
  const controller = stripWorkerSurfaceIdentity(value.controller, "$.controller", ["revision"], ["projectionId"], worker);

  const compatibilitySource = {
    environment: { AGENT_INTERCOM_WORKER_ID: worker.workerId, AGENT_INTERCOM_RUN_ID: worker.workerIncarnationId, ...(workspacePath === undefined ? {} : { workspacePath }) },
    health: {
      observedLegacyState: health.originalLegacyState,
      ...(health.lastConfirmedAt === undefined ? {} : { lastConfirmedAt: health.lastConfirmedAt }),
      ...(health.failureCode === undefined ? {} : { failureCode: health.failureCode }),
    },
    runtime,
    adapter,
    systemd,
    notice,
    controller,
  };
  const fields = parseCompatibilityFields(compatibilitySource, "$compatibility");

  assertRecord(value.compatibilityAudit, "$.compatibilityAudit");
  assertExactKeys(
    value.compatibilityAudit,
    ["sourceEnvironmentIncarnationField", "targetEnvironmentIncarnationField", "deprecatedEnvironmentAliasLastSupportedVersion", "bossRunIdDerived", "preservedFieldGroups"],
    [],
    "$.compatibilityAudit",
  );
  if (
    value.compatibilityAudit.sourceEnvironmentIncarnationField !== "AGENT_INTERCOM_RUN_ID"
    || value.compatibilityAudit.targetEnvironmentIncarnationField !== "AGENT_INTERCOM_WORKER_INCARNATION_ID"
    || value.compatibilityAudit.deprecatedEnvironmentAliasLastSupportedVersion !== FULL_WORKER_STORE_V2_RECORD_VERSION
    || value.compatibilityAudit.bossRunIdDerived !== false
  ) throw new ContractValidationError("$.compatibilityAudit", "must forbid deriving Boss authority from legacy identity");
  const preservedFieldGroups = readStringArray(value.compatibilityAudit.preservedFieldGroups, "$.compatibilityAudit.preservedFieldGroups");
  if (preservedFieldGroups.join(",") !== "environment,health,runtime,adapter,systemd,notice,controller") {
    throw new ContractValidationError("$.compatibilityAudit.preservedFieldGroups", "must enumerate every preserved compatibility field group");
  }
  return {
    version: FULL_WORKER_STORE_V2_RECORD_VERSION,
    worker,
    environment: {
      AGENT_INTERCOM_WORKER_ID: environmentWorkerId,
      AGENT_INTERCOM_WORKER_INCARNATION_ID: environmentIncarnationId,
      AGENT_INTERCOM_WORKER_GENERATION: environmentGeneration,
      AGENT_INTERCOM_RUN_ID: deprecatedEnvironmentIncarnationId,
      ...(workspacePath === undefined ? {} : { workspacePath }),
    },
    health: bindWorkerSurface({
      originalLegacyState: fields.health.observedLegacyState,
      canonicalState: worker.state,
      ...(fields.health.lastConfirmedAt === undefined ? {} : { lastConfirmedAt: fields.health.lastConfirmedAt }),
      ...(fields.health.failureCode === undefined ? {} : { failureCode: fields.health.failureCode }),
    }, worker),
    runtime: bindWorkerSurface(fields.runtime, worker),
    adapter: bindWorkerSurface(fields.adapter, worker),
    systemd: bindWorkerSurface(fields.systemd, worker),
    notice: bindWorkerSurface(fields.notice, worker),
    controller: bindWorkerSurface(fields.controller, worker),
    compatibilityAudit: {
      sourceEnvironmentIncarnationField: "AGENT_INTERCOM_RUN_ID",
      targetEnvironmentIncarnationField: "AGENT_INTERCOM_WORKER_INCARNATION_ID",
      deprecatedEnvironmentAliasLastSupportedVersion: FULL_WORKER_STORE_V2_RECORD_VERSION,
      bossRunIdDerived: false,
      preservedFieldGroups: ["environment", "health", "runtime", "adapter", "systemd", "notice", "controller"],
    },
  };
}

export const validateFullWorkerStoreMigrationInputV1 = (value: unknown): StoreValidationResult<FullWorkerStoreMigrationInputV1> =>
  validateVersionedStoreRecord(value, FULL_WORKER_STORE_MIGRATION_VERSION, parseFullWorkerStoreMigrationInputV1);
export const validateWorkerStoreRecordV2 = (value: unknown): StoreValidationResult<WorkerStoreRecordV2> =>
  validateVersionedStoreRecord(value, FULL_WORKER_STORE_V2_RECORD_VERSION, parseWorkerStoreRecordV2);
