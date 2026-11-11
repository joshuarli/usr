import { types as nodeUtilTypes } from "node:util";
import {
  assertExactKeys,
  assertRecord,
  canonicalHash,
  ContractValidationError,
  readBoolean,
  readEnum,
  readHexDigest,
  readInteger,
  readOptionalInteger,
  readOptionalString,
  readOptionalTimestamp,
  readString,
  readStringArray,
  readTimestamp,
  subscriberBindingEpoch,
  subscriberBindingGeneration,
  validateVersionedStoreRecord,
  type StoreValidationResult,
  type SubscriberBindingEpoch,
  type SubscriberBindingGeneration,
  type ParticipantBindingEpoch,
  workerGeneration as readWorkerGeneration,
  type WorkerGeneration,
  triggerGeneration as readTriggerGeneration,
  recipientTransferGeneration as readRecipientTransferGeneration,
  deliveryClaimGeneration as readDeliveryClaimGeneration,
  type TriggerGeneration,
  type RecipientTransferGeneration,
  type DeliveryClaimGeneration,
  participantBindingEpoch,
} from "./canonical.ts";
import {
  DELIVERY_INTENTS,
  deliveryGroupId,
  effectiveDeliveryIntent,
  parseDeliveryClaimRecord,
  parseDeliveryGroupRecord,
  type DeliveryClaimRecord,
  type DeliveryEquivalenceKey,
  type DeliveryGroupRecord,
  type DeliveryIntent,
} from "./boss-wire.ts";
import { PARTICIPANT_STATES, type ParticipantState } from "./boss-participant-state.ts";

export const LIFECYCLE_SUBSCRIPTION_VERSION = "orc.lifecycle-subscription.v1" as const;
export const ACTIVITY_RECORD_VERSION = "orc.activity-record.v1" as const;
export const ACTIVE_OPERATION_LEASE_VERSION = "orc.active-operation-lease.v1" as const;
export const EXTERNAL_WAIT_LEASE_VERSION = "orc.external-wait-lease.v1" as const;
export const SUBSCRIBER_REBIND_MIGRATION_VERSION = "orc.subscriber-rebind-migration.v1" as const;
export const LIFECYCLE_TRIGGER_SCHEMA_VERSION = 1 as const;
export const LIFECYCLE_TRIGGER_VERSION = "orc.lifecycle-trigger.v1" as const;
export const MAX_EXTERNAL_WAIT_LEASE_MS_DEFAULT = 2 * 60 * 60 * 1_000;

export const SUBSCRIPTION_STATES = ["armed", "triggered", "suspended", "cancelled", "expired"] as const;
export type SubscriptionState = (typeof SUBSCRIPTION_STATES)[number];
export const INACTIVITY_MODES = ["smart", "raw"] as const;
export type InactivityMode = (typeof INACTIVITY_MODES)[number];
export const ACTIVITY_BASES = ["meaningful", "liveness"] as const;
export type ActivityBasis = (typeof ACTIVITY_BASES)[number];
export const SUPERVISED_ROLES = ["boss", "manager", "adversary", "scout", "worker", "council"] as const;
export type SupervisedRole = (typeof SUPERVISED_ROLES)[number];

function assertUnproxied(value: unknown, path: string): void {
  if (nodeUtilTypes.isProxy(value)) {
    throw new ContractValidationError(path, "Proxy values are not supported");
  }
}

function readOwnDenseArray(value: unknown, path: string): unknown[] {
  assertUnproxied(value, path);
  if (!Array.isArray(value)) throw new ContractValidationError(path, "must be an array");

  const lengthDescriptor = Object.getOwnPropertyDescriptor(value, "length");
  if (lengthDescriptor === undefined || !Object.hasOwn(lengthDescriptor, "value")) {
    throw new ContractValidationError(path, "must be an array");
  }
  const length = lengthDescriptor.value as number;
  const descriptors = new Map<number, PropertyDescriptor>();
  for (const key of Reflect.ownKeys(value)) {
    if (key === "length") continue;
    if (typeof key !== "string") {
      throw new ContractValidationError(path, "array must not have symbol or non-index properties");
    }
    const index = Number(key);
    if (!Number.isInteger(index) || index < 0 || index >= length || String(index) !== key) {
      throw new ContractValidationError(path, "array must not have symbol or non-index properties");
    }
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor === undefined || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) {
      throw new ContractValidationError(`${path}[${index}]`, "must be an enumerable data property");
    }
    descriptors.set(index, descriptor);
  }

  if (descriptors.size !== length) {
    const indices = [...descriptors.keys()].sort((left, right) => left - right);
    let missingIndex = 0;
    while (indices[missingIndex] === missingIndex) missingIndex += 1;
    throw new ContractValidationError(`${path}[${missingIndex}]`, "sparse array holes are not supported");
  }

  const result: unknown[] = [];
  for (let index = 0; index < length; index += 1) result.push(descriptors.get(index)!.value);
  return result;
}

export type LifecycleTarget =
  | { kind: "worker"; workerId: string; workerGeneration: WorkerGeneration }
  | { kind: "role"; bossRunId: string; role: SupervisedRole };

export type LifecyclePredicate =
  | { kind: "state_changed" }
  | { kind: "state_in"; states: ParticipantState[] }
  | { kind: "failed" }
  | { kind: "stopped" }
  | { kind: "turn_settled" }
  | { kind: "inactive_for" };

export interface LifecycleSubscriptionRecord {
  version: typeof LIFECYCLE_SUBSCRIPTION_VERSION;
  subscriptionId: string;
  subscriberPrincipalId: string;
  subscriberBindingEpoch: SubscriberBindingEpoch;
  subscriberBindingGeneration: SubscriberBindingGeneration;
  lastSubscriberAuthorityTransitionId?: string;
  bossRunId?: string;
  target: LifecycleTarget;
  followReplacement: boolean;
  predicates: LifecyclePredicate[];
  inactivityMode?: InactivityMode;
  inactiveAfterMs?: number;
  activityBasis?: ActivityBasis;
  cooldownMs: number;
  maxFires?: number;
  expiresAt?: string;
  delivery: DeliveryIntent;
  state: SubscriptionState;
  triggerGeneration: TriggerGeneration;
  lastActivityAt?: string;
  dueAt?: string;
  lastSourceEventId?: string;
  createdAt: string;
  updatedAt: string;
}

export function parseLifecycleTarget(value: unknown, path = "$"): LifecycleTarget {
  assertUnproxied(value, path);
  assertRecord(value, path);
  const kind = readEnum(value.kind, ["worker", "role"] as const, `${path}.kind`);
  if (kind === "worker") {
    assertExactKeys(value, ["kind", "workerId", "workerGeneration"], [], path);
    return {
      kind,
      workerId: readString(value.workerId, `${path}.workerId`),
      workerGeneration: readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`),
    };
  }
  assertExactKeys(value, ["kind", "bossRunId", "role"], [], path);
  return {
    kind,
    bossRunId: readString(value.bossRunId, `${path}.bossRunId`),
    role: readEnum(value.role, SUPERVISED_ROLES, `${path}.role`),
  };
}

function parsePredicates(value: unknown, path: string): LifecyclePredicate[] {
  const entries = readOwnDenseArray(value, path);
  if (entries.length === 0) {
    throw new ContractValidationError(path, "must be a non-empty array");
  }
  const result = entries.map((entry, index): LifecyclePredicate => {
    const itemPath = `${path}[${index}]`;
    assertUnproxied(entry, itemPath);
    assertRecord(entry, itemPath);
    const kind = readEnum(
      entry.kind,
      ["state_changed", "state_in", "failed", "stopped", "turn_settled", "inactive_for"] as const,
      `${itemPath}.kind`,
    );
    if (kind === "state_in") {
      assertExactKeys(entry, ["kind", "states"], [], itemPath);
      const stateValues = readOwnDenseArray(entry.states, `${itemPath}.states`);
      const states = stateValues.map((state, stateIndex) => readEnum(state, PARTICIPANT_STATES, `${itemPath}.states[${stateIndex}]`));
      if (states.length === 0 || new Set(states).size !== states.length) {
        throw new ContractValidationError(`${itemPath}.states`, "must be non-empty and unique");
      }
      return { kind, states };
    }
    assertExactKeys(entry, ["kind"], [], itemPath);
    return { kind };
  });
  const keys = result.map((predicate) => predicate.kind);
  if (new Set(keys).size !== keys.length) throw new ContractValidationError(path, "predicate kinds must be unique");
  return result;
}

export function parseLifecycleSubscription(value: unknown): LifecycleSubscriptionRecord {
  const path = "$";
  assertUnproxied(value, path);
  assertRecord(value, path);
  assertExactKeys(
    value,
    [
      "version", "subscriptionId", "subscriberPrincipalId", "subscriberBindingEpoch", "subscriberBindingGeneration",
      "target", "followReplacement", "predicates", "cooldownMs", "delivery", "state", "triggerGeneration", "createdAt", "updatedAt",
    ],
    [
      "lastSubscriberAuthorityTransitionId", "bossRunId", "inactivityMode", "inactiveAfterMs", "activityBasis", "maxFires", "expiresAt",
      "lastActivityAt", "dueAt", "lastSourceEventId",
    ],
    path,
  );
  const version = readString(value.version, "$.version");
  if (version !== LIFECYCLE_SUBSCRIPTION_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${version}`);
  const predicates = parsePredicates(value.predicates, "$.predicates");
  const hasInactivity = predicates.some((predicate) => predicate.kind === "inactive_for");
  const inactivityMode = value.inactivityMode === undefined
    ? undefined
    : readEnum(value.inactivityMode, INACTIVITY_MODES, "$.inactivityMode");
  const inactiveAfterMs = readOptionalInteger(value.inactiveAfterMs, "$.inactiveAfterMs", 1);
  const activityBasis = value.activityBasis === undefined
    ? undefined
    : readEnum(value.activityBasis, ACTIVITY_BASES, "$.activityBasis");
  const hasAnyInactivityConfig = inactivityMode !== undefined || inactiveAfterMs !== undefined || activityBasis !== undefined;
  const hasCompleteInactivityConfig = inactivityMode !== undefined && inactiveAfterMs !== undefined && activityBasis !== undefined;
  if ((hasInactivity && !hasCompleteInactivityConfig) || (!hasInactivity && hasAnyInactivityConfig)) {
    throw new ContractValidationError("$.predicates", "inactive_for requires inactivityMode, inactiveAfterMs, and activityBasis, which are forbidden otherwise");
  }
  const target = parseLifecycleTarget(value.target, "$.target");
  const followReplacement = readBoolean(value.followReplacement, "$.followReplacement");
  if (followReplacement && target.kind !== "role") {
    throw new ContractValidationError("$.followReplacement", "requires an authorized role target");
  }
  const bossRunId = readOptionalString(value.bossRunId, "$.bossRunId");
  if (bossRunId !== undefined && target.kind === "role" && bossRunId !== target.bossRunId) {
    throw new ContractValidationError("$.bossRunId", "must match the role target Boss run");
  }
  const createdAt = readTimestamp(value.createdAt, "$.createdAt");
  const updatedAt = readTimestamp(value.updatedAt, "$.updatedAt");
  if (Date.parse(updatedAt) < Date.parse(createdAt)) throw new ContractValidationError("$.updatedAt", "must not precede createdAt");
  const expiresAt = readOptionalTimestamp(value.expiresAt, "$.expiresAt");
  if (expiresAt !== undefined && Date.parse(expiresAt) < Date.parse(createdAt)) {
    throw new ContractValidationError("$.expiresAt", "must not precede createdAt");
  }
  const lastActivityAt = readOptionalTimestamp(value.lastActivityAt, "$.lastActivityAt");
  const dueAt = readOptionalTimestamp(value.dueAt, "$.dueAt");
  const lastSubscriberAuthorityTransitionId = readOptionalString(value.lastSubscriberAuthorityTransitionId, "$.lastSubscriberAuthorityTransitionId");
  const maxFires = readOptionalInteger(value.maxFires, "$.maxFires", 1);
  const lastSourceEventId = readOptionalString(value.lastSourceEventId, "$.lastSourceEventId");
  const triggerGeneration = readTriggerGeneration(value.triggerGeneration, "$.triggerGeneration");
  if (!hasInactivity && dueAt !== undefined) {
    throw new ContractValidationError("$.dueAt", "is supported only for inactive_for subscriptions");
  }
  if (lastActivityAt !== undefined && dueAt !== undefined && inactiveAfterMs !== undefined) {
    const lastActivityEpochMs = Date.parse(lastActivityAt);
    const dueEpochMs = Date.parse(dueAt);
    if (!Number.isSafeInteger(lastActivityEpochMs) || !Number.isSafeInteger(dueEpochMs)) {
      throw new ContractValidationError("$.dueAt", "timestamp relation must use finite safe-integer milliseconds");
    }
    const earliestDueEpochMs = lastActivityEpochMs + inactiveAfterMs;
    if (!Number.isSafeInteger(earliestDueEpochMs)) {
      throw new ContractValidationError("$.dueAt", "lastActivityAt + inactiveAfterMs must be a finite safe-integer timestamp");
    }
    if (dueEpochMs < earliestDueEpochMs) {
      throw new ContractValidationError("$.dueAt", "must be at or after lastActivityAt + inactiveAfterMs");
    }
  }
  if (maxFires !== undefined && triggerGeneration > maxFires) {
    throw new ContractValidationError("$.triggerGeneration", "must not exceed maxFires");
  }
  return {
    version: LIFECYCLE_SUBSCRIPTION_VERSION,
    subscriptionId: readString(value.subscriptionId, "$.subscriptionId"),
    subscriberPrincipalId: readString(value.subscriberPrincipalId, "$.subscriberPrincipalId"),
    subscriberBindingEpoch: subscriberBindingEpoch(value.subscriberBindingEpoch, "$.subscriberBindingEpoch"),
    subscriberBindingGeneration: subscriberBindingGeneration(value.subscriberBindingGeneration, "$.subscriberBindingGeneration"),
    ...(lastSubscriberAuthorityTransitionId === undefined ? {} : { lastSubscriberAuthorityTransitionId }),
    ...(bossRunId === undefined ? {} : { bossRunId }),
    target,
    followReplacement,
    predicates,
    ...(inactivityMode === undefined ? {} : { inactivityMode }),
    ...(inactiveAfterMs === undefined ? {} : { inactiveAfterMs }),
    ...(activityBasis === undefined ? {} : { activityBasis }),
    cooldownMs: readInteger(value.cooldownMs, "$.cooldownMs"),
    ...(maxFires === undefined ? {} : { maxFires }),
    ...(expiresAt === undefined ? {} : { expiresAt }),
    delivery: readEnum(value.delivery, DELIVERY_INTENTS, "$.delivery"),
    state: readEnum(value.state, SUBSCRIPTION_STATES, "$.state"),
    triggerGeneration,
    ...(lastActivityAt === undefined ? {} : { lastActivityAt }),
    ...(dueAt === undefined ? {} : { dueAt }),
    ...(lastSourceEventId === undefined ? {} : { lastSourceEventId }),
    createdAt,
    updatedAt,
  };
}

export const ACTIVITY_KINDS = ["meaningful", "liveness"] as const;
export type ActivityKind = (typeof ACTIVITY_KINDS)[number];
export const ACTIVITY_TYPES = ["turn", "tool", "progress", "checkpoint", "assignment", "state_transition", "heartbeat", "health_confirmation"] as const;
export type ActivityType = (typeof ACTIVITY_TYPES)[number];

export interface AuthenticatedActivityRecord {
  version: typeof ACTIVITY_RECORD_VERSION;
  activityId: string;
  workerId: string;
  workerGeneration: WorkerGeneration;
  sourceEventId: string;
  participantId: string;
  bindingEpoch: ParticipantBindingEpoch;
  kind: ActivityKind;
  activityType: ActivityType;
  occurredAt: string;
}

export function parseAuthenticatedActivity(value: unknown): AuthenticatedActivityRecord {
  assertRecord(value);
  assertExactKeys(value, ["version", "activityId", "workerId", "workerGeneration", "sourceEventId", "participantId", "bindingEpoch", "kind", "activityType", "occurredAt"]);
  const version = readString(value.version, "$.version");
  if (version !== ACTIVITY_RECORD_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${version}`);
  const kind = readEnum(value.kind, ACTIVITY_KINDS, "$.kind");
  const activityType = readEnum(value.activityType, ACTIVITY_TYPES, "$.activityType");
  const meaningful = new Set<ActivityType>(["turn", "tool", "progress", "checkpoint", "assignment", "state_transition"]);
  if ((kind === "meaningful") !== meaningful.has(activityType)) {
    throw new ContractValidationError("$.activityType", `is not ${kind} activity`);
  }
  return {
    version: ACTIVITY_RECORD_VERSION,
    activityId: readString(value.activityId, "$.activityId"),
    workerId: readString(value.workerId, "$.workerId"),
    workerGeneration: readWorkerGeneration(value.workerGeneration, "$.workerGeneration"),
    sourceEventId: readString(value.sourceEventId, "$.sourceEventId"),
    participantId: readString(value.participantId, "$.participantId"),
    bindingEpoch: participantBindingEpoch(value.bindingEpoch, "$.bindingEpoch"),
    kind,
    activityType,
    occurredAt: readTimestamp(value.occurredAt, "$.occurredAt"),
  };
}

export const OPERATION_LEASE_STATES = ["active", "settled", "cancelled", "expired"] as const;
export type OperationLeaseState = (typeof OPERATION_LEASE_STATES)[number];

export interface ActiveOperationLease {
  version: typeof ACTIVE_OPERATION_LEASE_VERSION;
  leaseId: string;
  workerId: string;
  workerGeneration: WorkerGeneration;
  invocationId: string;
  processId: number;
  cgroupIdentity: string;
  startedAt: string;
  renewBy: string;
  maxUntil: string;
  hardWorkerLeaseExpiresAt: string;
  maxRuntimeAt: string;
  state: OperationLeaseState;
}

export function parseActiveOperationLease(value: unknown): ActiveOperationLease {
  assertRecord(value);
  assertExactKeys(value, [
    "version", "leaseId", "workerId", "workerGeneration", "invocationId", "processId", "cgroupIdentity", "startedAt", "renewBy", "maxUntil",
    "hardWorkerLeaseExpiresAt", "maxRuntimeAt", "state",
  ]);
  const version = readString(value.version, "$.version");
  if (version !== ACTIVE_OPERATION_LEASE_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${version}`);
  const startedAt = readTimestamp(value.startedAt, "$.startedAt");
  const renewBy = readTimestamp(value.renewBy, "$.renewBy");
  const maxUntil = readTimestamp(value.maxUntil, "$.maxUntil");
  const hardWorkerLeaseExpiresAt = readTimestamp(value.hardWorkerLeaseExpiresAt, "$.hardWorkerLeaseExpiresAt");
  const maxRuntimeAt = readTimestamp(value.maxRuntimeAt, "$.maxRuntimeAt");
  const hardBound = Math.min(Date.parse(hardWorkerLeaseExpiresAt), Date.parse(maxRuntimeAt));
  if (Date.parse(startedAt) > Date.parse(renewBy) || Date.parse(renewBy) > Date.parse(maxUntil) || Date.parse(maxUntil) > hardBound) {
    throw new ContractValidationError("$.maxUntil", "must satisfy startedAt <= renewBy <= maxUntil <= min(hard worker lease, MaxRuntime)");
  }
  return {
    version: ACTIVE_OPERATION_LEASE_VERSION,
    leaseId: readString(value.leaseId, "$.leaseId"),
    workerId: readString(value.workerId, "$.workerId"),
    workerGeneration: readWorkerGeneration(value.workerGeneration, "$.workerGeneration"),
    invocationId: readString(value.invocationId, "$.invocationId"),
    processId: readInteger(value.processId, "$.processId", 1),
    cgroupIdentity: readString(value.cgroupIdentity, "$.cgroupIdentity"),
    startedAt,
    renewBy,
    maxUntil,
    hardWorkerLeaseExpiresAt,
    maxRuntimeAt,
    state: readEnum(value.state, OPERATION_LEASE_STATES, "$.state"),
  };
}

export const WAIT_SOURCE_KINDS = ["process", "timer", "file", "port", "url", "webhook", "async_tool", "other"] as const;
export type WaitSourceKind = (typeof WAIT_SOURCE_KINDS)[number];
export const WAIT_LEASE_STATES = ["active", "fired", "cancelled", "expired"] as const;
export type WaitLeaseState = (typeof WAIT_LEASE_STATES)[number];

export interface ExternalWaitLease {
  version: typeof EXTERNAL_WAIT_LEASE_VERSION;
  leaseId: string;
  workerId: string;
  workerGeneration: WorkerGeneration;
  sourceKind: WaitSourceKind;
  sourceRefHash: string;
  processIdentity?: string;
  startedAt: string;
  renewBy: string;
  maxUntil: string;
  expectedWakeAt?: string;
  hardWorkerLeaseExpiresAt: string;
  maxRuntimeAt: string;
  state: WaitLeaseState;
}

export function parseExternalWaitLease(value: unknown, maxExternalWaitLeaseMs = MAX_EXTERNAL_WAIT_LEASE_MS_DEFAULT): ExternalWaitLease {
  if (!Number.isSafeInteger(maxExternalWaitLeaseMs) || maxExternalWaitLeaseMs < 1) {
    throw new ContractValidationError("maxExternalWaitLeaseMs", "must be a positive safe integer");
  }
  assertRecord(value);
  assertExactKeys(
    value,
    ["version", "leaseId", "workerId", "workerGeneration", "sourceKind", "sourceRefHash", "startedAt", "renewBy", "maxUntil", "hardWorkerLeaseExpiresAt", "maxRuntimeAt", "state"],
    ["processIdentity", "expectedWakeAt"],
  );
  const version = readString(value.version, "$.version");
  if (version !== EXTERNAL_WAIT_LEASE_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${version}`);
  const startedAt = readTimestamp(value.startedAt, "$.startedAt");
  const renewBy = readTimestamp(value.renewBy, "$.renewBy");
  const maxUntil = readTimestamp(value.maxUntil, "$.maxUntil");
  const hardWorkerLeaseExpiresAt = readTimestamp(value.hardWorkerLeaseExpiresAt, "$.hardWorkerLeaseExpiresAt");
  const maxRuntimeAt = readTimestamp(value.maxRuntimeAt, "$.maxRuntimeAt");
  const bound = Math.min(Date.parse(startedAt) + maxExternalWaitLeaseMs, Date.parse(hardWorkerLeaseExpiresAt), Date.parse(maxRuntimeAt));
  if (Date.parse(startedAt) > Date.parse(renewBy) || Date.parse(renewBy) > Date.parse(maxUntil) || Date.parse(maxUntil) > bound) {
    throw new ContractValidationError("$.maxUntil", "must satisfy startedAt <= renewBy <= maxUntil <= min(configured ceiling, hard worker lease, MaxRuntime)");
  }
  const expectedWakeAt = readOptionalTimestamp(value.expectedWakeAt, "$.expectedWakeAt");
  if (
    expectedWakeAt !== undefined
    && (Date.parse(expectedWakeAt) < Date.parse(startedAt) || Date.parse(expectedWakeAt) > Date.parse(maxUntil))
  ) {
    throw new ContractValidationError("$.expectedWakeAt", "must be between startedAt and maxUntil");
  }
  const sourceKind = readEnum(value.sourceKind, WAIT_SOURCE_KINDS, "$.sourceKind");
  const processIdentity = readOptionalString(value.processIdentity, "$.processIdentity");
  if (sourceKind === "process" && processIdentity === undefined) {
    throw new ContractValidationError("$.processIdentity", "is required for process waits");
  }
  return {
    version: EXTERNAL_WAIT_LEASE_VERSION,
    leaseId: readString(value.leaseId, "$.leaseId"),
    workerId: readString(value.workerId, "$.workerId"),
    workerGeneration: readWorkerGeneration(value.workerGeneration, "$.workerGeneration"),
    sourceKind,
    sourceRefHash: readHexDigest(value.sourceRefHash, "$.sourceRefHash"),
    ...(processIdentity === undefined ? {} : { processIdentity }),
    startedAt,
    renewBy,
    maxUntil,
    ...(expectedWakeAt === undefined ? {} : { expectedWakeAt }),
    hardWorkerLeaseExpiresAt,
    maxRuntimeAt,
    state: readEnum(value.state, WAIT_LEASE_STATES, "$.state"),
  };
}

function assertSameLeaseField(
  previous: Record<string, unknown>,
  next: Record<string, unknown>,
  field: string,
): void {
  if (previous[field] !== next[field]) throw new ContractValidationError(`$.${field}`, "cannot change during renewal");
}

function assertLeaseStateTransition(
  previous: OperationLeaseState | WaitLeaseState,
  next: OperationLeaseState | WaitLeaseState,
): void {
  if (previous !== "active" && next !== previous) {
    throw new ContractValidationError("$.state", `terminal lease state ${previous} cannot transition to ${next}`);
  }
}

/** Validates an operation progress/settlement update without allowing identity, generation, or hard-bound drift. */
export function validateActiveOperationLeaseRenewal(previousValue: unknown, nextValue: unknown): ActiveOperationLease {
  const previous = parseActiveOperationLease(previousValue);
  const next = parseActiveOperationLease(nextValue);
  const previousRecord = previous as unknown as Record<string, unknown>;
  const nextRecord = next as unknown as Record<string, unknown>;
  for (const field of [
    "version", "leaseId", "workerId", "workerGeneration", "invocationId", "processId", "cgroupIdentity", "startedAt", "maxUntil",
    "hardWorkerLeaseExpiresAt", "maxRuntimeAt",
  ]) assertSameLeaseField(previousRecord, nextRecord, field);
  if (Date.parse(next.renewBy) < Date.parse(previous.renewBy)) {
    throw new ContractValidationError("$.renewBy", "cannot move backwards during renewal");
  }
  assertLeaseStateTransition(previous.state, next.state);
  return next;
}

/** Validates wait renewal/fire/cancellation while keeping the original bounded maximum immutable. */
export function validateExternalWaitLeaseRenewal(
  previousValue: unknown,
  nextValue: unknown,
  maxExternalWaitLeaseMs = MAX_EXTERNAL_WAIT_LEASE_MS_DEFAULT,
): ExternalWaitLease {
  const previous = parseExternalWaitLease(previousValue, maxExternalWaitLeaseMs);
  const next = parseExternalWaitLease(nextValue, maxExternalWaitLeaseMs);
  const previousRecord = previous as unknown as Record<string, unknown>;
  const nextRecord = next as unknown as Record<string, unknown>;
  for (const field of [
    "version", "leaseId", "workerId", "workerGeneration", "sourceKind", "sourceRefHash", "processIdentity", "startedAt", "maxUntil",
    "hardWorkerLeaseExpiresAt", "maxRuntimeAt",
  ]) assertSameLeaseField(previousRecord, nextRecord, field);
  if (Date.parse(next.renewBy) < Date.parse(previous.renewBy)) {
    throw new ContractValidationError("$.renewBy", "cannot move backwards during renewal");
  }
  assertLeaseStateTransition(previous.state, next.state);
  return next;
}

export interface SmartInactivityEvidence {
  workerId: string;
  workerGeneration: WorkerGeneration;
  now: string;
  currentOperation?: {
    invocationId: string;
    processId: number;
    cgroupIdentity: string;
    live: boolean;
  };
  activeOperation?: ActiveOperationLease;
  externalWait?: ExternalWaitLease;
  externalWaitSourceTerminal?: boolean;
}

export function isSmartInactivitySuppressed(evidence: SmartInactivityEvidence): boolean {
  const now = Date.parse(readTimestamp(evidence.now, "$.now"));
  const operation = evidence.activeOperation === undefined ? undefined : parseActiveOperationLease(evidence.activeOperation);
  const observedOperation = evidence.currentOperation;
  if (
    operation?.state === "active"
    && operation.workerId === evidence.workerId
    && operation.workerGeneration === evidence.workerGeneration
    && observedOperation?.live === true
    && observedOperation.invocationId === operation.invocationId
    && observedOperation.processId === operation.processId
    && observedOperation.cgroupIdentity === operation.cgroupIdentity
    && now >= Date.parse(operation.startedAt)
    && now <= Date.parse(operation.renewBy)
    && now <= Date.parse(operation.maxUntil)
  ) return true;
  const wait = evidence.externalWait === undefined ? undefined : parseExternalWaitLease(evidence.externalWait);
  return wait?.state === "active"
    && wait.workerId === evidence.workerId
    && wait.workerGeneration === evidence.workerGeneration
    && evidence.externalWaitSourceTerminal !== true
    && now >= Date.parse(wait.startedAt)
    && now <= Date.parse(wait.renewBy)
    && now <= Date.parse(wait.maxUntil);
}

export interface LifecycleTriggerRecord {
  version: typeof LIFECYCLE_TRIGGER_VERSION;
  triggerId: string;
  subscriptionId: string;
  triggerGeneration: TriggerGeneration;
  targetWorkerId: string;
  targetWorkerGeneration: WorkerGeneration;
  predicateEdge: string;
  sourceEventId: string;
  transitionId: string;
  subscriberBindingEpoch: SubscriberBindingEpoch;
  subscriberBindingGeneration: SubscriberBindingGeneration;
  deliveryGroupId: string;
  deliveryGroupMembershipRevision: number;
  noticeId?: string;
  satisfiedByNoticeId?: string;
  successorDeliveryGroupId?: string;
  recipientTransferGeneration: RecipientTransferGeneration;
  createdAt: string;
  acknowledgedAt?: string;
}

export function parseLifecycleTrigger(value: unknown): LifecycleTriggerRecord {
  assertRecord(value);
  assertExactKeys(
    value,
    [
      "version", "triggerId", "subscriptionId", "triggerGeneration", "targetWorkerId", "targetWorkerGeneration", "predicateEdge", "sourceEventId", "transitionId",
      "subscriberBindingEpoch", "subscriberBindingGeneration", "deliveryGroupId", "deliveryGroupMembershipRevision", "recipientTransferGeneration", "createdAt",
    ],
    ["noticeId", "satisfiedByNoticeId", "successorDeliveryGroupId", "acknowledgedAt"],
  );
  if (value.version !== LIFECYCLE_TRIGGER_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  const deliveryGroupId = readString(value.deliveryGroupId, "$.deliveryGroupId");
  const successorDeliveryGroupId = readOptionalString(value.successorDeliveryGroupId, "$.successorDeliveryGroupId");
  const recipientTransferGeneration = readRecipientTransferGeneration(value.recipientTransferGeneration, "$.recipientTransferGeneration");
  if (successorDeliveryGroupId === deliveryGroupId) {
    throw new ContractValidationError("$.successorDeliveryGroupId", "must differ from deliveryGroupId");
  }
  if (successorDeliveryGroupId !== undefined && recipientTransferGeneration < 1) {
    throw new ContractValidationError("$.recipientTransferGeneration", "must be at least 1 when a successor group exists");
  }
  const createdAt = readTimestamp(value.createdAt, "$.createdAt");
  const acknowledgedAt = readOptionalTimestamp(value.acknowledgedAt, "$.acknowledgedAt");
  if (acknowledgedAt !== undefined && Date.parse(acknowledgedAt) < Date.parse(createdAt)) {
    throw new ContractValidationError("$.acknowledgedAt", "must not precede createdAt");
  }
  return {
    version: LIFECYCLE_TRIGGER_VERSION,
    triggerId: readString(value.triggerId, "$.triggerId"),
    subscriptionId: readString(value.subscriptionId, "$.subscriptionId"),
    triggerGeneration: readTriggerGeneration(value.triggerGeneration, "$.triggerGeneration", 1),
    targetWorkerId: readString(value.targetWorkerId, "$.targetWorkerId"),
    targetWorkerGeneration: readWorkerGeneration(value.targetWorkerGeneration, "$.targetWorkerGeneration"),
    predicateEdge: readString(value.predicateEdge, "$.predicateEdge"),
    sourceEventId: readString(value.sourceEventId, "$.sourceEventId"),
    transitionId: readString(value.transitionId, "$.transitionId"),
    subscriberBindingEpoch: subscriberBindingEpoch(value.subscriberBindingEpoch, "$.subscriberBindingEpoch"),
    subscriberBindingGeneration: subscriberBindingGeneration(value.subscriberBindingGeneration, "$.subscriberBindingGeneration"),
    deliveryGroupId,
    deliveryGroupMembershipRevision: readInteger(value.deliveryGroupMembershipRevision, "$.deliveryGroupMembershipRevision", 1),
    ...(value.noticeId === undefined ? {} : { noticeId: readString(value.noticeId, "$.noticeId") }),
    ...(value.satisfiedByNoticeId === undefined ? {} : { satisfiedByNoticeId: readString(value.satisfiedByNoticeId, "$.satisfiedByNoticeId") }),
    ...(successorDeliveryGroupId === undefined ? {} : { successorDeliveryGroupId }),
    recipientTransferGeneration,
    createdAt,
    ...(acknowledgedAt === undefined ? {} : { acknowledgedAt }),
  };
}

export interface InactivityEdgeKey {
  workerId: string;
  workerGeneration: WorkerGeneration;
  inactivityEpochId: string;
  inactivityMode: InactivityMode;
  activityBasis: ActivityBasis;
  inactiveAfterMs: number;
  dueAt: string;
}

export function parseInactivityEdgeKey(value: unknown): InactivityEdgeKey {
  assertRecord(value);
  assertExactKeys(value, [
    "workerId", "workerGeneration", "inactivityEpochId", "inactivityMode", "activityBasis", "inactiveAfterMs", "dueAt",
  ]);
  return {
    workerId: readString(value.workerId, "$.workerId"),
    workerGeneration: readWorkerGeneration(value.workerGeneration, "$.workerGeneration"),
    inactivityEpochId: readString(value.inactivityEpochId, "$.inactivityEpochId"),
    inactivityMode: readEnum(value.inactivityMode, INACTIVITY_MODES, "$.inactivityMode"),
    activityBasis: readEnum(value.activityBasis, ACTIVITY_BASES, "$.activityBasis"),
    inactiveAfterMs: readInteger(value.inactiveAfterMs, "$.inactiveAfterMs", 1),
    dueAt: readTimestamp(value.dueAt, "$.dueAt"),
  };
}

export function inactivityTransitionId(key: InactivityEdgeKey): string {
  return canonicalHash("orc-inactivity-edge-v1", parseInactivityEdgeKey(key));
}

export const REBIND_MIGRATION_STATES = ["prepared", "projected", "committed", "aborted", "blocked"] as const;
export type RebindMigrationState = (typeof REBIND_MIGRATION_STATES)[number];

export interface RebindCurrentClaimEvidence {
  status: "unclaimed" | "claimed";
  observedAt: string;
  claim?: DeliveryClaimRecord;
}

export interface RebindTargetLedgerEvidence {
  deliveryGroupId: string;
  membershipRevision: number;
  recipientPrincipalId: string;
  recipientBindingEpoch: SubscriberBindingEpoch;
  recipientTransferGeneration: RecipientTransferGeneration;
  state: "absent" | "inserting" | "inserted" | "ambiguous";
  checkedAt: string;
  targetLedgerEntryId?: string;
  insertedAt?: string;
}

export interface RebindDeliveryReceiptEvidence {
  deliveryClaimId: string;
  claimGeneration: DeliveryClaimGeneration;
  deliveryGroupId: string;
  membershipRevision: number;
  recipientPrincipalId: string;
  recipientBindingEpoch: SubscriberBindingEpoch;
  recipientTransferGeneration: RecipientTransferGeneration;
  deliveryReceiptId: string;
  targetLedgerEntryId: string;
  insertedAt: string;
  deliveredAt: string;
}

export interface RebindDrainBarrierEvidence {
  deliveryGroupId: string;
  membershipRevision: number;
  recipientPrincipalId: string;
  recipientBindingEpoch: SubscriberBindingEpoch;
  recipientTransferGeneration: RecipientTransferGeneration;
  barrierId: string;
  noSessionEntry: true;
  noAdapterQueue: true;
  noInflightInvocation: true;
  operativePathsDrained: true;
  establishedAt: string;
}

export interface RebindAcknowledgmentEvidence {
  deliveryGroupId: string;
  noticeIds: string[];
  recipientPrincipalId: string;
  recipientBindingEpoch: SubscriberBindingEpoch;
  acknowledgedAt: string;
}

/** One authenticated authority-socket projection binds every fact used to classify an old group. */
export interface RebindMigrationLinkEvidence {
  authorityPrincipalId: string;
  authoritySessionId: string;
  authenticatedAt: string;
  evidenceDigest: string;
  oldGroup: DeliveryGroupRecord;
  currentClaim: RebindCurrentClaimEvidence;
  targetLedger: RebindTargetLedgerEvidence;
  receipt?: RebindDeliveryReceiptEvidence;
  drainBarrier?: RebindDrainBarrierEvidence;
  acknowledgment?: RebindAcknowledgmentEvidence;
}

export function rebindMigrationEvidenceDigest(
  evidence: Omit<RebindMigrationLinkEvidence, "evidenceDigest">,
): string {
  return canonicalHash("orc-subscriber-rebind-authoritative-evidence-v1", evidence);
}

export interface DeliveryGroupMigrationLink {
  oldDeliveryGroupId: string;
  oldEquivalenceKey: DeliveryEquivalenceKey;
  successorDeliveryGroupId?: string;
  successorEquivalenceKey?: DeliveryEquivalenceKey;
  disposition: "migrated" | "delivered_old_epoch" | "blocked_ambiguous" | "not_replayed";
  previousRecipientTransferGeneration: RecipientTransferGeneration;
  recipientTransferGeneration: RecipientTransferGeneration;
  evidence: RebindMigrationLinkEvidence;
}

export interface SubscriberRebindMigrationRecord {
  version: typeof SUBSCRIBER_REBIND_MIGRATION_VERSION;
  authorityTransitionId: string;
  subscriptionId: string;
  stableSubscriberPrincipalId: string;
  oldSubscriberBindingEpoch: SubscriberBindingEpoch;
  newSubscriberBindingEpoch: SubscriberBindingEpoch;
  oldSubscriberBindingGeneration: SubscriberBindingGeneration;
  newSubscriberBindingGeneration: SubscriberBindingGeneration;
  reauthorized: boolean;
  resultingSubscriptionState: SubscriptionState;
  deliveryGroups: DeliveryGroupMigrationLink[];
  state: RebindMigrationState;
  createdAt: string;
  committedAt?: string;
}

function parseRebindMigrationLinkEvidence(value: unknown, path: string): RebindMigrationLinkEvidence {
  assertRecord(value, path);
  assertExactKeys(
    value,
    ["authorityPrincipalId", "authoritySessionId", "authenticatedAt", "evidenceDigest", "oldGroup", "currentClaim", "targetLedger"],
    ["receipt", "drainBarrier", "acknowledgment"],
    path,
  );
  const oldGroup = parseDeliveryGroupRecord(value.oldGroup);

  assertRecord(value.currentClaim, `${path}.currentClaim`);
  assertExactKeys(value.currentClaim, ["status", "observedAt"], ["claim"], `${path}.currentClaim`);
  const claimStatus = readEnum(value.currentClaim.status, ["unclaimed", "claimed"] as const, `${path}.currentClaim.status`);
  const observedAt = readTimestamp(value.currentClaim.observedAt, `${path}.currentClaim.observedAt`);
  const claim = value.currentClaim.claim === undefined ? undefined : parseDeliveryClaimRecord(value.currentClaim.claim);
  if ((claimStatus === "claimed") !== (claim !== undefined)) {
    throw new ContractValidationError(`${path}.currentClaim.claim`, "is required exactly when the authoritative observation is claimed");
  }
  const claimEvidenceTimes = claim === undefined ? [] : [
    claim.deliveryAttemptedAt,
    claim.insertedAt,
    claim.deliveredAt,
    claim.releasedAt,
    claim.releaseProof?.establishedAt,
  ].flatMap((timestamp) => timestamp === undefined ? [] : [Date.parse(timestamp)]);
  const latestClaimEvidenceAt = claimEvidenceTimes.length === 0 ? undefined : Math.max(...claimEvidenceTimes);
  if (latestClaimEvidenceAt !== undefined && Date.parse(observedAt) < latestClaimEvidenceAt) {
    throw new ContractValidationError(`${path}.currentClaim.observedAt`, "must not precede the claim evidence it observes");
  }
  const currentClaim: RebindCurrentClaimEvidence = {
    status: claimStatus,
    observedAt,
    ...(claim === undefined ? {} : { claim }),
  };

  assertRecord(value.targetLedger, `${path}.targetLedger`);
  assertExactKeys(
    value.targetLedger,
    [
      "deliveryGroupId", "membershipRevision", "recipientPrincipalId", "recipientBindingEpoch", "recipientTransferGeneration", "state", "checkedAt",
    ],
    ["targetLedgerEntryId", "insertedAt"],
    `${path}.targetLedger`,
  );
  const ledgerState = readEnum(value.targetLedger.state, ["absent", "inserting", "inserted", "ambiguous"] as const, `${path}.targetLedger.state`);
  const targetLedgerEntryId = readOptionalString(value.targetLedger.targetLedgerEntryId, `${path}.targetLedger.targetLedgerEntryId`);
  const insertedAt = readOptionalTimestamp(value.targetLedger.insertedAt, `${path}.targetLedger.insertedAt`);
  if ((ledgerState === "inserted") !== (targetLedgerEntryId !== undefined && insertedAt !== undefined)) {
    throw new ContractValidationError(`${path}.targetLedger`, "target ledger entry and insertion time are required exactly for inserted evidence");
  }
  const targetLedger: RebindTargetLedgerEvidence = {
    deliveryGroupId: readString(value.targetLedger.deliveryGroupId, `${path}.targetLedger.deliveryGroupId`),
    membershipRevision: readInteger(value.targetLedger.membershipRevision, `${path}.targetLedger.membershipRevision`, 1),
    recipientPrincipalId: readString(value.targetLedger.recipientPrincipalId, `${path}.targetLedger.recipientPrincipalId`),
    recipientBindingEpoch: subscriberBindingEpoch(value.targetLedger.recipientBindingEpoch, `${path}.targetLedger.recipientBindingEpoch`),
    recipientTransferGeneration: readRecipientTransferGeneration(value.targetLedger.recipientTransferGeneration, `${path}.targetLedger.recipientTransferGeneration`),
    state: ledgerState,
    checkedAt: readTimestamp(value.targetLedger.checkedAt, `${path}.targetLedger.checkedAt`),
    ...(targetLedgerEntryId === undefined ? {} : { targetLedgerEntryId }),
    ...(insertedAt === undefined ? {} : { insertedAt }),
  };
  if (insertedAt !== undefined && Date.parse(targetLedger.checkedAt) < Date.parse(insertedAt)) {
    throw new ContractValidationError(`${path}.targetLedger.checkedAt`, "must not precede the proved insertion");
  }

  let receipt: RebindDeliveryReceiptEvidence | undefined;
  if (value.receipt !== undefined) {
    assertRecord(value.receipt, `${path}.receipt`);
    assertExactKeys(value.receipt, [
      "deliveryClaimId", "claimGeneration", "deliveryGroupId", "membershipRevision", "recipientPrincipalId", "recipientBindingEpoch",
      "recipientTransferGeneration", "deliveryReceiptId", "targetLedgerEntryId", "insertedAt", "deliveredAt",
    ], [], `${path}.receipt`);
    receipt = {
      deliveryClaimId: readString(value.receipt.deliveryClaimId, `${path}.receipt.deliveryClaimId`),
      claimGeneration: readDeliveryClaimGeneration(value.receipt.claimGeneration, `${path}.receipt.claimGeneration`),
      deliveryGroupId: readString(value.receipt.deliveryGroupId, `${path}.receipt.deliveryGroupId`),
      membershipRevision: readInteger(value.receipt.membershipRevision, `${path}.receipt.membershipRevision`, 1),
      recipientPrincipalId: readString(value.receipt.recipientPrincipalId, `${path}.receipt.recipientPrincipalId`),
      recipientBindingEpoch: subscriberBindingEpoch(value.receipt.recipientBindingEpoch, `${path}.receipt.recipientBindingEpoch`),
      recipientTransferGeneration: readRecipientTransferGeneration(value.receipt.recipientTransferGeneration, `${path}.receipt.recipientTransferGeneration`),
      deliveryReceiptId: readString(value.receipt.deliveryReceiptId, `${path}.receipt.deliveryReceiptId`),
      targetLedgerEntryId: readString(value.receipt.targetLedgerEntryId, `${path}.receipt.targetLedgerEntryId`),
      insertedAt: readTimestamp(value.receipt.insertedAt, `${path}.receipt.insertedAt`),
      deliveredAt: readTimestamp(value.receipt.deliveredAt, `${path}.receipt.deliveredAt`),
    };
    if (Date.parse(receipt.deliveredAt) < Date.parse(receipt.insertedAt)) {
      throw new ContractValidationError(`${path}.receipt.deliveredAt`, "must not precede insertedAt");
    }
  }

  let drainBarrier: RebindDrainBarrierEvidence | undefined;
  if (value.drainBarrier !== undefined) {
    assertRecord(value.drainBarrier, `${path}.drainBarrier`);
    assertExactKeys(value.drainBarrier, [
      "deliveryGroupId", "membershipRevision", "recipientPrincipalId", "recipientBindingEpoch", "recipientTransferGeneration", "barrierId",
      "noSessionEntry", "noAdapterQueue", "noInflightInvocation", "operativePathsDrained", "establishedAt",
    ], [], `${path}.drainBarrier`);
    for (const key of ["noSessionEntry", "noAdapterQueue", "noInflightInvocation", "operativePathsDrained"] as const) {
      if (!readBoolean(value.drainBarrier[key], `${path}.drainBarrier.${key}`)) {
        throw new ContractValidationError(`${path}.drainBarrier.${key}`, "must be true to prove absence");
      }
    }
    drainBarrier = {
      deliveryGroupId: readString(value.drainBarrier.deliveryGroupId, `${path}.drainBarrier.deliveryGroupId`),
      membershipRevision: readInteger(value.drainBarrier.membershipRevision, `${path}.drainBarrier.membershipRevision`, 1),
      recipientPrincipalId: readString(value.drainBarrier.recipientPrincipalId, `${path}.drainBarrier.recipientPrincipalId`),
      recipientBindingEpoch: subscriberBindingEpoch(value.drainBarrier.recipientBindingEpoch, `${path}.drainBarrier.recipientBindingEpoch`),
      recipientTransferGeneration: readRecipientTransferGeneration(value.drainBarrier.recipientTransferGeneration, `${path}.drainBarrier.recipientTransferGeneration`),
      barrierId: readString(value.drainBarrier.barrierId, `${path}.drainBarrier.barrierId`),
      noSessionEntry: true,
      noAdapterQueue: true,
      noInflightInvocation: true,
      operativePathsDrained: true,
      establishedAt: readTimestamp(value.drainBarrier.establishedAt, `${path}.drainBarrier.establishedAt`),
    };
  }

  let acknowledgment: RebindAcknowledgmentEvidence | undefined;
  if (value.acknowledgment !== undefined) {
    assertRecord(value.acknowledgment, `${path}.acknowledgment`);
    assertExactKeys(value.acknowledgment, ["deliveryGroupId", "noticeIds", "recipientPrincipalId", "recipientBindingEpoch", "acknowledgedAt"], [], `${path}.acknowledgment`);
    const noticeIds = readStringArray(value.acknowledgment.noticeIds, `${path}.acknowledgment.noticeIds`);
    if (noticeIds.length === 0 || new Set(noticeIds).size !== noticeIds.length) {
      throw new ContractValidationError(`${path}.acknowledgment.noticeIds`, "must be non-empty and unique");
    }
    acknowledgment = {
      deliveryGroupId: readString(value.acknowledgment.deliveryGroupId, `${path}.acknowledgment.deliveryGroupId`),
      noticeIds,
      recipientPrincipalId: readString(value.acknowledgment.recipientPrincipalId, `${path}.acknowledgment.recipientPrincipalId`),
      recipientBindingEpoch: subscriberBindingEpoch(value.acknowledgment.recipientBindingEpoch, `${path}.acknowledgment.recipientBindingEpoch`),
      acknowledgedAt: readTimestamp(value.acknowledgment.acknowledgedAt, `${path}.acknowledgment.acknowledgedAt`),
    };
  }

  const authenticatedAt = readTimestamp(value.authenticatedAt, `${path}.authenticatedAt`);
  const evidence: RebindMigrationLinkEvidence = {
    authorityPrincipalId: readString(value.authorityPrincipalId, `${path}.authorityPrincipalId`),
    authoritySessionId: readString(value.authoritySessionId, `${path}.authoritySessionId`),
    authenticatedAt,
    evidenceDigest: readHexDigest(value.evidenceDigest, `${path}.evidenceDigest`),
    oldGroup,
    currentClaim,
    targetLedger,
    ...(receipt === undefined ? {} : { receipt }),
    ...(drainBarrier === undefined ? {} : { drainBarrier }),
    ...(acknowledgment === undefined ? {} : { acknowledgment }),
  };
  const evidenceTimes = [observedAt, targetLedger.checkedAt, receipt?.deliveredAt, drainBarrier?.establishedAt, acknowledgment?.acknowledgedAt]
    .filter((entry): entry is string => entry !== undefined);
  if (evidenceTimes.some((entry) => Date.parse(authenticatedAt) < Date.parse(entry))) {
    throw new ContractValidationError(`${path}.authenticatedAt`, "must not precede any authenticated observation");
  }
  const { evidenceDigest, ...digestInput } = evidence;
  if (evidenceDigest !== rebindMigrationEvidenceDigest(digestInput)) {
    throw new ContractValidationError(`${path}.evidenceDigest`, "does not bind the authoritative migration evidence");
  }
  return evidence;
}

export function parseSubscriberRebindMigration(value: unknown): SubscriberRebindMigrationRecord {
  assertRecord(value);
  assertExactKeys(
    value,
    [
      "version", "authorityTransitionId", "subscriptionId", "stableSubscriberPrincipalId", "oldSubscriberBindingEpoch", "newSubscriberBindingEpoch",
      "oldSubscriberBindingGeneration", "newSubscriberBindingGeneration", "reauthorized", "resultingSubscriptionState", "deliveryGroups", "state", "createdAt",
    ],
    ["committedAt"],
  );
  const version = readString(value.version, "$.version");
  if (version !== SUBSCRIBER_REBIND_MIGRATION_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${version}`);
  const oldEpoch = subscriberBindingEpoch(value.oldSubscriberBindingEpoch, "$.oldSubscriberBindingEpoch");
  const newEpoch = subscriberBindingEpoch(value.newSubscriberBindingEpoch, "$.newSubscriberBindingEpoch");
  const oldGeneration = subscriberBindingGeneration(value.oldSubscriberBindingGeneration, "$.oldSubscriberBindingGeneration");
  const newGeneration = subscriberBindingGeneration(value.newSubscriberBindingGeneration, "$.newSubscriberBindingGeneration");
  const stableSubscriberPrincipalId = readString(value.stableSubscriberPrincipalId, "$.stableSubscriberPrincipalId");
  if (newEpoch <= oldEpoch) throw new ContractValidationError("$.newSubscriberBindingEpoch", "must increase");
  if (newGeneration !== oldGeneration + 1) throw new ContractValidationError("$.newSubscriberBindingGeneration", "must increment exactly once");
  const deliveryGroupEntries = readOwnDenseArray(value.deliveryGroups, "$.deliveryGroups");
  const deliveryGroups = deliveryGroupEntries.map((entry, index): DeliveryGroupMigrationLink => {
    const path = `$.deliveryGroups[${index}]`;
    assertRecord(entry, path);
    assertExactKeys(
      entry,
      ["oldDeliveryGroupId", "oldEquivalenceKey", "disposition", "previousRecipientTransferGeneration", "recipientTransferGeneration", "evidence"],
      ["successorDeliveryGroupId", "successorEquivalenceKey"],
      path,
    );
    const disposition = readEnum(entry.disposition, ["migrated", "delivered_old_epoch", "blocked_ambiguous", "not_replayed"] as const, `${path}.disposition`);
    const successorDeliveryGroupId = readOptionalString(entry.successorDeliveryGroupId, `${path}.successorDeliveryGroupId`);
    const successorEquivalenceKey = entry.successorEquivalenceKey as DeliveryEquivalenceKey | undefined;
    if (
      (disposition === "migrated") !== (successorDeliveryGroupId !== undefined)
      || (disposition === "migrated") !== (successorEquivalenceKey !== undefined)
    ) {
      throw new ContractValidationError(`${path}.successorDeliveryGroupId`, "successor ID and equivalence key are required only for migrated groups");
    }
    const oldDeliveryGroupId = readString(entry.oldDeliveryGroupId, `${path}.oldDeliveryGroupId`);
    const oldEquivalenceKey = entry.oldEquivalenceKey as DeliveryEquivalenceKey;
    if (oldDeliveryGroupId !== deliveryGroupId(oldEquivalenceKey)) {
      throw new ContractValidationError(`${path}.oldDeliveryGroupId`, "does not match oldEquivalenceKey");
    }
    if (oldEquivalenceKey.recipientPrincipalId !== stableSubscriberPrincipalId || oldEquivalenceKey.recipientBindingEpoch !== oldEpoch) {
      throw new ContractValidationError(`${path}.oldEquivalenceKey`, "must bind the stable subscriber at the old epoch");
    }
    if (successorDeliveryGroupId === oldDeliveryGroupId) {
      throw new ContractValidationError(`${path}.successorDeliveryGroupId`, "must differ from the old group");
    }
    const previousRecipientTransferGeneration = readRecipientTransferGeneration(entry.previousRecipientTransferGeneration, `${path}.previousRecipientTransferGeneration`);
    const recipientTransferGeneration = readRecipientTransferGeneration(entry.recipientTransferGeneration, `${path}.recipientTransferGeneration`);
    const evidence = parseRebindMigrationLinkEvidence(entry.evidence, `${path}.evidence`);
    const oldGroup = evidence.oldGroup;
    if (oldGroup.membershipState !== "sealed") {
      throw new ContractValidationError(`${path}.evidence.oldGroup.membershipState`, "the old delivery group must be sealed");
    }
    if (oldGroup.state === "migrated") {
      throw new ContractValidationError(`${path}.evidence.oldGroup.state`, "evidence must describe the authoritative pre-migration state");
    }
    if (
      oldGroup.deliveryGroupId !== oldDeliveryGroupId
      || canonicalHash("orc-supervision-equivalence-compare-v1", oldGroup.equivalenceKey) !== canonicalHash("orc-supervision-equivalence-compare-v1", oldEquivalenceKey)
    ) {
      throw new ContractValidationError(`${path}.evidence.oldGroup`, "must be the old delivery group named by this link");
    }
    if (oldGroup.recipientTransferGeneration !== previousRecipientTransferGeneration) {
      throw new ContractValidationError(`${path}.evidence.oldGroup.recipientTransferGeneration`, "must match the link's previous transfer generation");
    }
    const ledger = evidence.targetLedger;
    if (
      ledger.deliveryGroupId !== oldDeliveryGroupId
      || ledger.membershipRevision !== oldGroup.membershipRevision
      || ledger.recipientPrincipalId !== stableSubscriberPrincipalId
      || ledger.recipientBindingEpoch !== oldEpoch
      || ledger.recipientTransferGeneration !== previousRecipientTransferGeneration
    ) {
      throw new ContractValidationError(`${path}.evidence.targetLedger`, "must bind the old group revision, recipient epoch, and transfer generation");
    }
    if (evidence.authorityPrincipalId !== stableSubscriberPrincipalId) {
      throw new ContractValidationError(`${path}.evidence.authorityPrincipalId`, "must authenticate the old recipient's target ledger");
    }
    const currentClaim = evidence.currentClaim.claim;
    if (currentClaim !== undefined && (
      currentClaim.deliveryGroupId !== oldDeliveryGroupId
      || currentClaim.membershipRevision !== oldGroup.membershipRevision
      || currentClaim.recipientPrincipalId !== stableSubscriberPrincipalId
      || currentClaim.recipientBindingEpoch !== oldEpoch
      || currentClaim.recipientTransferGeneration !== previousRecipientTransferGeneration
    )) {
      throw new ContractValidationError(`${path}.evidence.currentClaim`, "must bind the current claim for the old group revision and recipient epoch");
    }
    const receipt = evidence.receipt;
    const matchingReceipt = receipt !== undefined && currentClaim !== undefined && currentClaim.state === "delivered" && (
      receipt.deliveryClaimId === currentClaim.deliveryClaimId
      && receipt.claimGeneration === currentClaim.claimGeneration
      && receipt.deliveryGroupId === oldDeliveryGroupId
      && receipt.membershipRevision === oldGroup.membershipRevision
      && receipt.recipientPrincipalId === stableSubscriberPrincipalId
      && receipt.recipientBindingEpoch === oldEpoch
      && receipt.recipientTransferGeneration === previousRecipientTransferGeneration
      && receipt.deliveryReceiptId === currentClaim.deliveryReceiptId
      && receipt.targetLedgerEntryId === currentClaim.targetLedgerEntryId
      && receipt.insertedAt === currentClaim.insertedAt
      && receipt.deliveredAt === currentClaim.deliveredAt
      && ledger.state === "inserted"
      && receipt.targetLedgerEntryId === ledger.targetLedgerEntryId
      && receipt.insertedAt === ledger.insertedAt
    );
    if (receipt !== undefined && !matchingReceipt) {
      throw new ContractValidationError(`${path}.evidence.receipt`, "must exactly match the delivered current claim and authenticated inserted-ledger evidence");
    }
    const barrier = evidence.drainBarrier;
    const matchingBarrier = barrier !== undefined && (
      barrier.deliveryGroupId === oldDeliveryGroupId
      && barrier.membershipRevision === oldGroup.membershipRevision
      && barrier.recipientPrincipalId === stableSubscriberPrincipalId
      && barrier.recipientBindingEpoch === oldEpoch
      && barrier.recipientTransferGeneration === previousRecipientTransferGeneration
      && Date.parse(barrier.establishedAt) >= Date.parse(evidence.currentClaim.observedAt)
      && Date.parse(barrier.establishedAt) >= Date.parse(ledger.checkedAt)
    );
    if (barrier !== undefined && !matchingBarrier) {
      throw new ContractValidationError(`${path}.evidence.drainBarrier`, "must postdate and bind the unclaimed old group and absent-ledger observations");
    }
    const acknowledgment = evidence.acknowledgment;
    const matchingAcknowledgment = acknowledgment !== undefined && (
      acknowledgment.deliveryGroupId === oldDeliveryGroupId
      && acknowledgment.recipientPrincipalId === stableSubscriberPrincipalId
      && acknowledgment.recipientBindingEpoch === oldEpoch
      && acknowledgment.noticeIds.length === oldGroup.memberNoticeIds.length
      && acknowledgment.noticeIds.every((noticeId) => oldGroup.memberNoticeIds.includes(noticeId))
      && (receipt === undefined || Date.parse(acknowledgment.acknowledgedAt) >= Date.parse(receipt.deliveredAt))
    );
    if (acknowledgment !== undefined && !matchingAcknowledgment) {
      throw new ContractValidationError(`${path}.evidence.acknowledgment`, "must acknowledge every notice in the old sealed group at the old recipient epoch");
    }
    const provedAbsent = oldGroup.state === "pending"
      && evidence.currentClaim.status === "unclaimed"
      && ledger.state === "absent"
      && matchingBarrier;
    const provedDelivered = oldGroup.state === "delivered" && matchingReceipt;
    const provedNotReplayed = provedDelivered || matchingAcknowledgment;
    const hasAmbiguousEvidence = ledger.state === "inserting"
      || ledger.state === "ambiguous"
      || (evidence.currentClaim.status === "claimed" && currentClaim?.state !== "delivered")
      || (!provedAbsent && !provedDelivered && !matchingAcknowledgment);
    if (disposition === "migrated") {
      if (!provedAbsent || receipt !== undefined || acknowledgment !== undefined) {
        throw new ContractValidationError(`${path}.evidence`, "migration requires an unclaimed pending group, authenticated absent ledger, and a matching fully drained barrier");
      }
      if (successorDeliveryGroupId !== deliveryGroupId(successorEquivalenceKey!)) {
        throw new ContractValidationError(`${path}.successorDeliveryGroupId`, "does not match successorEquivalenceKey");
      }
      const expectedSuccessor = { ...oldEquivalenceKey, recipientBindingEpoch: newEpoch };
      if (canonicalHash("orc-supervision-equivalence-compare-v1", successorEquivalenceKey) !== canonicalHash("orc-supervision-equivalence-compare-v1", expectedSuccessor)) {
        throw new ContractValidationError(`${path}.successorEquivalenceKey`, "must differ from the old key only by the new recipient epoch");
      }
      if (recipientTransferGeneration !== previousRecipientTransferGeneration + 1) {
        throw new ContractValidationError(`${path}.recipientTransferGeneration`, "must increment exactly once for migration");
      }
    } else if (recipientTransferGeneration !== previousRecipientTransferGeneration) {
      throw new ContractValidationError(`${path}.recipientTransferGeneration`, "must not increment without a successor group");
    }
    if (disposition === "delivered_old_epoch" && !provedDelivered) {
      throw new ContractValidationError(`${path}.evidence.receipt`, "delivered_old_epoch requires a receipt matching the delivered old-epoch claim");
    }
    if (disposition === "not_replayed" && !provedNotReplayed) {
      throw new ContractValidationError(`${path}.evidence`, "not_replayed requires matching delivered or acknowledged evidence");
    }
    if (disposition === "blocked_ambiguous" && !hasAmbiguousEvidence) {
      throw new ContractValidationError(`${path}.evidence`, "blocked_ambiguous requires unresolved claim or ledger evidence");
    }
    if (disposition !== "blocked_ambiguous" && hasAmbiguousEvidence) {
      throw new ContractValidationError(`${path}.disposition`, "ambiguous evidence must block the migration");
    }
    return {
      oldDeliveryGroupId,
      oldEquivalenceKey,
      ...(successorDeliveryGroupId === undefined ? {} : { successorDeliveryGroupId }),
      ...(successorEquivalenceKey === undefined ? {} : { successorEquivalenceKey }),
      disposition,
      previousRecipientTransferGeneration,
      recipientTransferGeneration,
      evidence,
    };
  });
  if (new Set(deliveryGroups.map((entry) => entry.oldDeliveryGroupId)).size !== deliveryGroups.length) {
    throw new ContractValidationError("$.deliveryGroups", "old delivery group IDs must be unique");
  }
  const successorIds = deliveryGroups.flatMap((entry) => entry.successorDeliveryGroupId === undefined ? [] : [entry.successorDeliveryGroupId]);
  if (new Set(successorIds).size !== successorIds.length) {
    throw new ContractValidationError("$.deliveryGroups", "successor delivery group IDs must be unique");
  }
  const reauthorized = readBoolean(value.reauthorized, "$.reauthorized");
  const resultingSubscriptionState = readEnum(value.resultingSubscriptionState, SUBSCRIPTION_STATES, "$.resultingSubscriptionState");
  if (!reauthorized && resultingSubscriptionState !== "suspended") {
    throw new ContractValidationError("$.resultingSubscriptionState", "must be suspended when reauthorization fails");
  }
  if (!reauthorized && deliveryGroups.some((entry) => entry.disposition === "migrated")) {
    throw new ContractValidationError("$.deliveryGroups", "unauthorized subscriptions cannot migrate delivery to the new binding");
  }
  const state = readEnum(value.state, REBIND_MIGRATION_STATES, "$.state");
  const committedAt = readOptionalTimestamp(value.committedAt, "$.committedAt");
  if ((state === "committed") !== (committedAt !== undefined)) {
    throw new ContractValidationError("$.committedAt", "is required exactly when state is committed");
  }
  const createdAt = readTimestamp(value.createdAt, "$.createdAt");
  if (committedAt !== undefined && Date.parse(committedAt) < Date.parse(createdAt)) {
    throw new ContractValidationError("$.committedAt", "must not precede createdAt");
  }
  if (deliveryGroups.some((entry) => Date.parse(entry.evidence.authenticatedAt) > Date.parse(createdAt))) {
    throw new ContractValidationError("$.deliveryGroups", "authoritative link evidence must be authenticated before the migration record is created");
  }
  const hasAmbiguousGroup = deliveryGroups.some((entry) => entry.disposition === "blocked_ambiguous");
  if (state === "blocked" && !hasAmbiguousGroup) {
    throw new ContractValidationError("$.deliveryGroups", "a blocked migration requires an ambiguous old-epoch group");
  }
  if (state !== "blocked" && hasAmbiguousGroup) {
    throw new ContractValidationError("$.deliveryGroups", "ambiguous old-epoch evidence blocks projection and commit");
  }
  return {
    version: SUBSCRIBER_REBIND_MIGRATION_VERSION,
    authorityTransitionId: readString(value.authorityTransitionId, "$.authorityTransitionId"),
    subscriptionId: readString(value.subscriptionId, "$.subscriptionId"),
    stableSubscriberPrincipalId,
    oldSubscriberBindingEpoch: oldEpoch,
    newSubscriberBindingEpoch: newEpoch,
    oldSubscriberBindingGeneration: oldGeneration,
    newSubscriberBindingGeneration: newGeneration,
    reauthorized,
    resultingSubscriptionState,
    deliveryGroups,
    state,
    createdAt,
    ...(committedAt === undefined ? {} : { committedAt }),
  };
}

export const SUPERVISOR_PRINCIPAL_KINDS = ["ordinary_owner", "boss", "manager", "controller", "worker", "scout", "adversary", "council"] as const;
export type SupervisorPrincipalKind = (typeof SUPERVISOR_PRINCIPAL_KINDS)[number];
export interface SupervisorPrincipal {
  principalId: string;
  kind: SupervisorPrincipalKind;
  state: "active" | "revoked";
  bindingEpoch: SubscriberBindingEpoch;
  bindingGeneration: SubscriberBindingGeneration;
  participantId?: string;
  bossRunId?: string;
  ownedWorkerIds?: string[];
  assignedParticipantIds?: string[];
}

export interface SupervisionWorker {
  workerId: string;
  workerGeneration: WorkerGeneration;
  participantId?: string;
  role?: SupervisedRole;
  bossRunId?: string;
  active: boolean;
}

export interface SupervisorAclState {
  principals: Record<string, SupervisorPrincipal>;
  workers: Record<string, SupervisionWorker>;
  currentManagerByRun: Record<string, string>;
}

export interface SupervisorAuthorizationRequest {
  actorPrincipalId: string;
  actorBindingEpoch: SubscriberBindingEpoch;
  actorBindingGeneration: SubscriberBindingGeneration;
  target: LifecycleTarget;
  followReplacement: boolean;
}

export type SupervisorDenialCode =
  | "UNKNOWN_SUBSCRIBER"
  | "REVOKED_SUBSCRIBER"
  | "STALE_SUBSCRIBER_BINDING"
  | "UNKNOWN_TARGET"
  | "STALE_TARGET_GENERATION"
  | "CROSS_RUN_DENIED"
  | "ROLE_SELECTOR_DENIED"
  | "FOLLOW_REPLACEMENT_DENIED"
  | "SUPERVISION_EDGE_DENIED";
export type SupervisorAuthorizationDecision =
  | { allowed: true; reason: "owner_to_worker" | "manager_to_assignment" | "boss_to_manager" | "controller_to_participant" }
  | { allowed: false; code: SupervisorDenialCode };

interface AuthoritativeSupervisorAclMaps {
  principals: Record<string, SupervisorPrincipal> | undefined;
  workers: Record<string, SupervisionWorker> | undefined;
  roleWorkerSetComplete: boolean;
  currentManagerByRun: Record<string, string> | undefined;
}

type OwnDataSnapshot = Record<string, unknown>;

const SUPERVISOR_PRINCIPAL_BASE_FIELDS = [
  "principalId",
  "kind",
  "state",
  "bindingEpoch",
  "bindingGeneration",
] as const;
const SUPERVISION_WORKER_BASE_FIELDS = ["workerId", "workerGeneration", "active"] as const;
const SUPERVISION_WORKER_ROLES = SUPERVISED_ROLES;

function isUnproxiedObject(value: unknown): value is object {
  return typeof value === "object" && value !== null && !nodeUtilTypes.isProxy(value);
}

/** Copy an untrusted record only through own enumerable data descriptors. */
function snapshotOwnDataRecord(
  value: unknown,
  allowedFields?: ReadonlySet<string>,
  requirePlainPrototype = true,
): OwnDataSnapshot | undefined {
  if (
    !isUnproxiedObject(value)
    || Array.isArray(value)
    || (requirePlainPrototype && Object.getPrototypeOf(value) !== Object.prototype)
  ) return undefined;

  const snapshot = Object.create(null) as OwnDataSnapshot;
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string" || (allowedFields !== undefined && !allowedFields.has(key))) return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor === undefined || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) return undefined;
    Object.defineProperty(snapshot, key, {
      configurable: true,
      enumerable: true,
      value: descriptor.value,
      writable: true,
    });
  }
  return snapshot;
}

function hasExactSnapshotFields(
  snapshot: OwnDataSnapshot,
  requiredFields: readonly string[],
  optionalFields: readonly string[] = [],
): boolean {
  const keys = Reflect.ownKeys(snapshot);
  const permitted = new Set<string>([...requiredFields, ...optionalFields]);
  return requiredFields.every((field) => Object.hasOwn(snapshot, field))
    && keys.every((key) => typeof key === "string" && permitted.has(key));
}

function snapshotExactOwnDataRecord(
  value: unknown,
  requiredFields: readonly string[],
  optionalFields: readonly string[] = [],
): OwnDataSnapshot | undefined {
  const snapshot = snapshotOwnDataRecord(value, new Set([...requiredFields, ...optionalFields]));
  return snapshot !== undefined && hasExactSnapshotFields(snapshot, requiredFields, optionalFields)
    ? snapshot
    : undefined;
}

function supervisorString(value: unknown, path: string): string | undefined {
  try {
    return readString(value, path);
  } catch (error) {
    if (error instanceof ContractValidationError) return undefined;
    throw error;
  }
}

function supervisorBindingEpochValue(value: unknown): SubscriberBindingEpoch | undefined {
  try {
    return subscriberBindingEpoch(value, "$.bindingEpoch");
  } catch (error) {
    if (error instanceof ContractValidationError) return undefined;
    throw error;
  }
}

function supervisorBindingGenerationValue(value: unknown): SubscriberBindingGeneration | undefined {
  try {
    return subscriberBindingGeneration(value, "$.bindingGeneration");
  } catch (error) {
    if (error instanceof ContractValidationError) return undefined;
    throw error;
  }
}

function supervisionWorkerGenerationValue(value: unknown): WorkerGeneration | undefined {
  try {
    return readWorkerGeneration(value, "$.workerGeneration");
  } catch (error) {
    if (error instanceof ContractValidationError) return undefined;
    throw error;
  }
}

function snapshotSupervisorStringArray(value: unknown): string[] | undefined {
  if (
    !isUnproxiedObject(value)
    || !Array.isArray(value)
    || Object.getPrototypeOf(value) !== Array.prototype
  ) return undefined;

  const lengthDescriptor = Object.getOwnPropertyDescriptor(value, "length");
  if (lengthDescriptor === undefined || !Object.hasOwn(lengthDescriptor, "value")) return undefined;
  const length = lengthDescriptor.value;
  if (!Number.isSafeInteger(length) || (length as number) < 0) return undefined;

  const descriptors = new Map<number, PropertyDescriptor>();
  for (const key of Reflect.ownKeys(value)) {
    if (key === "length") continue;
    if (typeof key !== "string") return undefined;
    const index = Number(key);
    if (!Number.isInteger(index) || index < 0 || index >= length || String(index) !== key) return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor === undefined || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) return undefined;
    descriptors.set(index, descriptor);
  }
  if (descriptors.size !== length) return undefined;

  const snapshot: string[] = [];
  const seen = new Set<string>();
  for (let index = 0; index < length; index += 1) {
    const entry = supervisorString(descriptors.get(index)?.value, `$[${index}]`);
    if (entry === undefined || seen.has(entry)) return undefined;
    seen.add(entry);
    snapshot.push(entry);
  }
  return snapshot;
}

function snapshotSupervisorPrincipal(value: unknown, mapPrincipalId: string): SupervisorPrincipal | undefined {
  const allFields = new Set<string>([
    ...SUPERVISOR_PRINCIPAL_BASE_FIELDS,
    "participantId",
    "bossRunId",
    "ownedWorkerIds",
    "assignedParticipantIds",
  ]);
  const raw = snapshotOwnDataRecord(value, allFields);
  if (raw === undefined) return undefined;

  const kind = typeof raw.kind === "string" && SUPERVISOR_PRINCIPAL_KINDS.includes(raw.kind as SupervisorPrincipalKind)
    ? raw.kind as SupervisorPrincipalKind
    : undefined;
  if (kind === undefined) return undefined;
  const requiredFields = kind === "ordinary_owner"
    ? [...SUPERVISOR_PRINCIPAL_BASE_FIELDS, "ownedWorkerIds"]
    : kind === "manager"
      ? [...SUPERVISOR_PRINCIPAL_BASE_FIELDS, "participantId", "bossRunId", "assignedParticipantIds"]
      : [...SUPERVISOR_PRINCIPAL_BASE_FIELDS, "bossRunId"];
  if (!hasExactSnapshotFields(raw, requiredFields)) return undefined;

  const principalId = supervisorString(raw.principalId, "$.principalId");
  const state = raw.state === "active" || raw.state === "revoked" ? raw.state : undefined;
  const bindingEpoch = supervisorBindingEpochValue(raw.bindingEpoch);
  const bindingGeneration = supervisorBindingGenerationValue(raw.bindingGeneration);
  if (
    principalId === undefined
    || principalId !== mapPrincipalId
    || state === undefined
    || bindingEpoch === undefined
    || bindingGeneration === undefined
  ) return undefined;

  if (kind === "ordinary_owner") {
    const ownedWorkerIds = snapshotSupervisorStringArray(raw.ownedWorkerIds);
    return ownedWorkerIds === undefined
      ? undefined
      : { principalId, kind, state, bindingEpoch, bindingGeneration, ownedWorkerIds };
  }

  const bossRunId = supervisorString(raw.bossRunId, "$.bossRunId");
  if (bossRunId === undefined) return undefined;
  if (kind === "manager") {
    const participantId = supervisorString(raw.participantId, "$.participantId");
    const assignedParticipantIds = snapshotSupervisorStringArray(raw.assignedParticipantIds);
    return participantId === undefined || assignedParticipantIds === undefined
      ? undefined
      : { principalId, kind, state, bindingEpoch, bindingGeneration, participantId, bossRunId, assignedParticipantIds };
  }
  return { principalId, kind, state, bindingEpoch, bindingGeneration, bossRunId };
}

function snapshotSupervisionWorker(value: unknown, mapWorkerId: string): SupervisionWorker | undefined {
  const allFields = new Set<string>([
    ...SUPERVISION_WORKER_BASE_FIELDS,
    "participantId",
    "role",
    "bossRunId",
  ]);
  const raw = snapshotOwnDataRecord(value, allFields);
  if (raw === undefined) return undefined;

  const ordinaryWorker = hasExactSnapshotFields(raw, SUPERVISION_WORKER_BASE_FIELDS);
  const runWorker = hasExactSnapshotFields(
    raw,
    [...SUPERVISION_WORKER_BASE_FIELDS, "role", "bossRunId"],
    ["participantId"],
  );
  if (!ordinaryWorker && !runWorker) return undefined;

  const workerId = supervisorString(raw.workerId, "$.workerId");
  const workerGeneration = supervisionWorkerGenerationValue(raw.workerGeneration);
  const active = typeof raw.active === "boolean" ? raw.active : undefined;
  if (workerId === undefined || workerId !== mapWorkerId || workerGeneration === undefined || active === undefined) {
    return undefined;
  }
  if (ordinaryWorker) return { workerId, workerGeneration, active };

  const role = typeof raw.role === "string" && SUPERVISION_WORKER_ROLES.includes(raw.role as SupervisionWorker["role"] & string)
    ? raw.role as NonNullable<SupervisionWorker["role"]>
    : undefined;
  const bossRunId = supervisorString(raw.bossRunId, "$.bossRunId");
  const participantId = raw.participantId === undefined
    ? undefined
    : supervisorString(raw.participantId, "$.participantId");
  if (role === undefined || bossRunId === undefined || (Object.hasOwn(raw, "participantId") && participantId === undefined)) {
    return undefined;
  }
  return {
    workerId,
    workerGeneration,
    ...(participantId === undefined ? {} : { participantId }),
    role,
    bossRunId,
    active,
  };
}

function snapshotSupervisorMap(value: unknown): OwnDataSnapshot | undefined {
  return snapshotOwnDataRecord(value);
}

function snapshotSupervisorPrincipalMap(value: unknown): Record<string, SupervisorPrincipal> | undefined {
  const raw = snapshotSupervisorMap(value);
  if (raw === undefined) return undefined;
  const principals = Object.create(null) as Record<string, SupervisorPrincipal>;
  for (const principalId of Reflect.ownKeys(raw)) {
    if (typeof principalId !== "string" || supervisorString(principalId, "$.[key]") === undefined) continue;
    const principal = snapshotSupervisorPrincipal(raw[principalId], principalId);
    if (principal !== undefined) principals[principalId] = principal;
  }
  return principals;
}

function snapshotSupervisionWorkerMap(value: unknown): {
  workers: Record<string, SupervisionWorker>;
  complete: boolean;
} | undefined {
  const raw = snapshotSupervisorMap(value);
  if (raw === undefined) return undefined;
  const workers = Object.create(null) as Record<string, SupervisionWorker>;
  let complete = true;
  for (const workerId of Reflect.ownKeys(raw)) {
    if (typeof workerId !== "string" || supervisorString(workerId, "$.[key]") === undefined) continue;
    const worker = snapshotSupervisionWorker(raw[workerId], workerId);
    if (worker === undefined) complete = false;
    else workers[workerId] = worker;
  }
  return { workers, complete };
}

function snapshotCurrentManagerMap(value: unknown): Record<string, string> | undefined {
  const raw = snapshotSupervisorMap(value);
  if (raw === undefined) return undefined;
  const managers = Object.create(null) as Record<string, string>;
  for (const bossRunId of Reflect.ownKeys(raw)) {
    if (typeof bossRunId !== "string" || supervisorString(bossRunId, "$.[key]") === undefined) continue;
    const principalId = supervisorString(raw[bossRunId], `$[${bossRunId}]`);
    if (principalId !== undefined) managers[bossRunId] = principalId;
  }
  return managers;
}

function authoritativeSupervisorAclMaps(state: unknown): AuthoritativeSupervisorAclMaps {
  if (!isUnproxiedObject(state) || Array.isArray(state)) {
    return { principals: undefined, workers: undefined, roleWorkerSetComplete: false, currentManagerByRun: undefined };
  }
  const allowedFields = new Set<string>(["principals", "workers", "currentManagerByRun"]);
  for (const key of Reflect.ownKeys(state)) {
    if (typeof key !== "string" || !allowedFields.has(key)) {
      return { principals: undefined, workers: undefined, roleWorkerSetComplete: false, currentManagerByRun: undefined };
    }
  }
  const mapValue = (field: string): unknown => {
    const descriptor = Object.getOwnPropertyDescriptor(state, field);
    return descriptor !== undefined && descriptor.enumerable && Object.hasOwn(descriptor, "value")
      ? descriptor.value
      : undefined;
  };
  const workerSnapshot = snapshotSupervisionWorkerMap(mapValue("workers"));
  return {
    principals: snapshotSupervisorPrincipalMap(mapValue("principals")),
    workers: workerSnapshot?.workers,
    roleWorkerSetComplete: workerSnapshot?.complete ?? false,
    currentManagerByRun: snapshotCurrentManagerMap(mapValue("currentManagerByRun")),
  };
}

function principalForId(principals: Record<string, SupervisorPrincipal>, principalId: string): SupervisorPrincipal | undefined {
  return Object.getOwnPropertyDescriptor(principals, principalId)?.value as SupervisorPrincipal | undefined;
}

function workerForId(workers: Record<string, SupervisionWorker>, workerId: string): SupervisionWorker | undefined {
  return Object.getOwnPropertyDescriptor(workers, workerId)?.value as SupervisionWorker | undefined;
}

function ownWorkers(workers: Record<string, SupervisionWorker>): SupervisionWorker[] {
  return Object.keys(workers).flatMap((workerId) => {
    const worker = workerForId(workers, workerId);
    return worker === undefined ? [] : [worker];
  });
}

function currentManagerPrincipal(
  maps: AuthoritativeSupervisorAclMaps,
  bossRunId: string,
): SupervisorPrincipal | undefined {
  if (maps.currentManagerByRun === undefined || maps.principals === undefined) return undefined;
  const principalId = Object.getOwnPropertyDescriptor(maps.currentManagerByRun, bossRunId)?.value as string | undefined;
  if (principalId === undefined) return undefined;
  const principal = principalForId(maps.principals, principalId);
  return principal?.kind === "manager"
    && principal.state === "active"
    && principal.bossRunId === bossRunId
    && principal.participantId !== undefined
    ? principal
    : undefined;
}

function isCurrentManagerPrincipal(
  maps: AuthoritativeSupervisorAclMaps,
  principal: SupervisorPrincipal,
): boolean {
  if (principal.kind !== "manager" || principal.bossRunId === undefined || principal.participantId === undefined) {
    return false;
  }
  const currentManager = currentManagerPrincipal(maps, principal.bossRunId);
  return currentManager?.principalId === principal.principalId
    && currentManager.participantId === principal.participantId;
}

function workersForRole(
  maps: AuthoritativeSupervisorAclMaps,
  bossRunId: string,
  role: SupervisedRole,
): SupervisionWorker[] | undefined {
  if (maps.workers === undefined || !maps.roleWorkerSetComplete) return undefined;
  if (role === "manager") {
    const manager = currentManagerPrincipal(maps, bossRunId);
    if (manager === undefined) return undefined;
    const matches = ownWorkers(maps.workers).filter((worker) =>
      worker.bossRunId === bossRunId
      && worker.participantId === manager.participantId
      && worker.role === "manager"
      && worker.active);
    return matches.length === 1 ? matches : undefined;
  }
  const matches = ownWorkers(maps.workers).filter((worker) => worker.bossRunId === bossRunId && worker.role === role && worker.active);
  return matches.length === 0 ? undefined : matches;
}

interface SupervisorAuthorizationRequestSnapshot {
  actorPrincipalId: string;
  actorBindingEpoch: SubscriberBindingEpoch;
  actorBindingGeneration: SubscriberBindingGeneration;
  target: unknown;
  followReplacement: boolean;
}

function snapshotSupervisorAuthorizationRequest(value: unknown): SupervisorAuthorizationRequestSnapshot | undefined {
  const raw = snapshotExactOwnDataRecord(
    value,
    ["actorPrincipalId", "actorBindingEpoch", "actorBindingGeneration", "target", "followReplacement"],
  );
  if (raw === undefined) return undefined;
  const actorPrincipalId = supervisorString(raw.actorPrincipalId, "$.actorPrincipalId");
  const actorBindingEpoch = supervisorBindingEpochValue(raw.actorBindingEpoch);
  const actorBindingGeneration = supervisorBindingGenerationValue(raw.actorBindingGeneration);
  if (
    actorPrincipalId === undefined
    || actorBindingEpoch === undefined
    || actorBindingGeneration === undefined
    || typeof raw.followReplacement !== "boolean"
  ) return undefined;
  return {
    actorPrincipalId,
    actorBindingEpoch,
    actorBindingGeneration,
    target: raw.target,
    followReplacement: raw.followReplacement,
  };
}

function snapshotSupervisorLifecycleTarget(value: unknown): LifecycleTarget | undefined {
  const candidate = snapshotOwnDataRecord(
    value,
    new Set(["kind", "workerId", "workerGeneration", "bossRunId", "role"]),
  );
  if (candidate === undefined) return undefined;
  if (candidate.kind === "worker") {
    if (!hasExactSnapshotFields(candidate, ["kind", "workerId", "workerGeneration"])) return undefined;
    const workerId = supervisorString(candidate.workerId, "$.target.workerId");
    const workerGeneration = supervisionWorkerGenerationValue(candidate.workerGeneration);
    return workerId === undefined || workerGeneration === undefined
      ? undefined
      : { kind: "worker", workerId, workerGeneration };
  }
  if (candidate.kind === "role") {
    if (!hasExactSnapshotFields(candidate, ["kind", "bossRunId", "role"])) return undefined;
    const bossRunId = supervisorString(candidate.bossRunId, "$.target.bossRunId");
    const role = typeof candidate.role === "string" && SUPERVISED_ROLES.includes(candidate.role as SupervisedRole)
      ? candidate.role as SupervisedRole
      : undefined;
    return bossRunId === undefined || role === undefined
      ? undefined
      : { kind: "role", bossRunId, role };
  }
  return undefined;
}

export function authorizeSupervisorSubscription(
  state: SupervisorAclState,
  request: SupervisorAuthorizationRequest,
): SupervisorAuthorizationDecision {
  const requested = snapshotSupervisorAuthorizationRequest(request);
  if (requested === undefined) return { allowed: false, code: "UNKNOWN_SUBSCRIBER" };
  const requestedTarget = snapshotSupervisorLifecycleTarget(requested.target);
  if (requestedTarget === undefined) return { allowed: false, code: "UNKNOWN_TARGET" };

  const maps = authoritativeSupervisorAclMaps(state);
  if (maps.principals === undefined) return { allowed: false, code: "UNKNOWN_SUBSCRIBER" };

  const actor = principalForId(maps.principals, requested.actorPrincipalId);
  if (!actor) return { allowed: false, code: "UNKNOWN_SUBSCRIBER" };
  if (actor.state !== "active") return { allowed: false, code: "REVOKED_SUBSCRIBER" };
  if (actor.bindingEpoch !== requested.actorBindingEpoch || actor.bindingGeneration !== requested.actorBindingGeneration) {
    return { allowed: false, code: "STALE_SUBSCRIBER_BINDING" };
  }
  if (requestedTarget.kind === "role") {
    const roleSelectorAllowed = actor.bossRunId === requestedTarget.bossRunId
      && (
        actor.kind === "controller"
        || (actor.kind === "boss" && requestedTarget.role === "manager")
      );
    if (!roleSelectorAllowed) return { allowed: false, code: "ROLE_SELECTOR_DENIED" };
  }
  const targets = requestedTarget.kind === "worker"
    ? maps.workers === undefined
      ? undefined
      : [workerForId(maps.workers, requestedTarget.workerId)].filter((worker): worker is SupervisionWorker => worker !== undefined)
    : workersForRole(maps, requestedTarget.bossRunId, requestedTarget.role);
  if (targets === undefined || targets.length === 0 || targets.some((target) => !target.active)) {
    return { allowed: false, code: "UNKNOWN_TARGET" };
  }
  if (requestedTarget.kind === "worker" && targets[0].workerGeneration !== requestedTarget.workerGeneration) {
    return { allowed: false, code: "STALE_TARGET_GENERATION" };
  }
  if (targets.some((target) =>
    actor.bossRunId !== target.bossRunId
    && (actor.bossRunId !== undefined || target.bossRunId !== undefined))) {
    return { allowed: false, code: "CROSS_RUN_DENIED" };
  }
  if (requested.followReplacement) {
    const permitted = requestedTarget.kind === "role"
      && ((actor.kind === "boss" && requestedTarget.role === "manager") || actor.kind === "controller")
      && actor.bossRunId === requestedTarget.bossRunId;
    if (!permitted) return { allowed: false, code: "FOLLOW_REPLACEMENT_DENIED" };
  }
  if (maps.currentManagerByRun === undefined && actor.kind !== "boss") {
    return { allowed: false, code: "UNKNOWN_TARGET" };
  }
  if (
    actor.kind === "ordinary_owner"
    && targets.every((target) => actor.ownedWorkerIds?.includes(target.workerId) && target.bossRunId === undefined)
  ) {
    return { allowed: true, reason: "owner_to_worker" };
  }
  if (
    actor.kind === "manager"
    && actor.bossRunId !== undefined
    && isCurrentManagerPrincipal(maps, actor)
    && targets.every((target) =>
      target.bossRunId === actor.bossRunId
      && (target.role === "worker" || target.role === "scout")
      && target.participantId !== undefined
      && actor.assignedParticipantIds?.includes(target.participantId))
  ) return { allowed: true, reason: "manager_to_assignment" };
  const currentManagerParticipantId = actor.bossRunId === undefined
    ? undefined
    : currentManagerPrincipal(maps, actor.bossRunId)?.participantId;
  if (
    actor.kind === "boss"
    && actor.bossRunId !== undefined
    && currentManagerParticipantId !== undefined
    && targets.every((target) =>
      target.role === "manager"
      && target.participantId === currentManagerParticipantId)
  ) return { allowed: true, reason: "boss_to_manager" };
  if (
    actor.kind === "controller"
    && actor.bossRunId !== undefined
    && targets.every((target) =>
      target.bossRunId === actor.bossRunId
      && target.participantId !== undefined)
  ) {
    return { allowed: true, reason: "controller_to_participant" };
  }
  return { allowed: false, code: "SUPERVISION_EDGE_DENIED" };
}

export function aggregateDeliveryIntent(intents: readonly DeliveryIntent[]): DeliveryIntent {
  return effectiveDeliveryIntent(intents);
}

export const validateLifecycleSubscriptionStore = (value: unknown): StoreValidationResult<LifecycleSubscriptionRecord> => {
  if (nodeUtilTypes.isProxy(value)) {
    return {
      ok: false,
      status: "corrupt",
      path: "$",
      message: "$: Proxy values are not supported",
      preserveExisting: true,
      mutationAllowed: false,
    };
  }
  return validateVersionedStoreRecord(value, LIFECYCLE_SUBSCRIPTION_VERSION, parseLifecycleSubscription);
};
export const validateAuthenticatedActivityStore = (value: unknown): StoreValidationResult<AuthenticatedActivityRecord> =>
  validateVersionedStoreRecord(value, ACTIVITY_RECORD_VERSION, parseAuthenticatedActivity);
export const validateActiveOperationLeaseStore = (value: unknown): StoreValidationResult<ActiveOperationLease> =>
  validateVersionedStoreRecord(value, ACTIVE_OPERATION_LEASE_VERSION, parseActiveOperationLease);
export const validateExternalWaitLeaseStore = (value: unknown): StoreValidationResult<ExternalWaitLease> =>
  validateVersionedStoreRecord(value, EXTERNAL_WAIT_LEASE_VERSION, parseExternalWaitLease);
export const validateLifecycleTriggerStore = (value: unknown): StoreValidationResult<LifecycleTriggerRecord> =>
  validateVersionedStoreRecord(value, LIFECYCLE_TRIGGER_VERSION, parseLifecycleTrigger);
export const validateSubscriberRebindMigrationStore = (value: unknown): StoreValidationResult<SubscriberRebindMigrationRecord> =>
  validateVersionedStoreRecord(value, SUBSCRIBER_REBIND_MIGRATION_VERSION, parseSubscriberRebindMigration);
