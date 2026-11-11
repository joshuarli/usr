import {
  assertExactKeys,
  assertRecord,
  ContractValidationError,
  readInteger,
  readOptionalString,
  readString,
  participantBindingEpoch,
  type ParticipantBindingEpoch,
  workerGeneration,
  type WorkerGeneration,
} from "./canonical.ts";

export const WORKER_IDENTITY_VERSION = "orc.worker-identity.v2" as const;

export type WorkerIdentityV2 = OrdinaryWorkerIdentityV2 | BossWorkerIdentityV2;

export interface OrdinaryWorkerIdentityV2 {
  version: typeof WORKER_IDENTITY_VERSION;
  workerId: string;
  workerIncarnationId: string;
  workerGeneration: WorkerGeneration;
}

export interface BossWorkerIdentityV2 extends OrdinaryWorkerIdentityV2 {
  bossRunId: string;
  participantId: string;
  bindingEpoch: ParticipantBindingEpoch;
}

export function parseWorkerIdentityV2(value: unknown): WorkerIdentityV2 {
  assertRecord(value);
  assertExactKeys(value, ["version", "workerId", "workerIncarnationId", "workerGeneration"], ["bossRunId", "participantId", "bindingEpoch"]);
  if (value.version !== WORKER_IDENTITY_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  const base: OrdinaryWorkerIdentityV2 = {
    version: WORKER_IDENTITY_VERSION,
    workerId: readString(value.workerId, "$.workerId"),
    workerIncarnationId: readString(value.workerIncarnationId, "$.workerIncarnationId"),
    workerGeneration: workerGeneration(value.workerGeneration, "$.workerGeneration"),
  };
  const bossRunId = readOptionalString(value.bossRunId, "$.bossRunId");
  const participantId = readOptionalString(value.participantId, "$.participantId");
  const bindingEpoch = value.bindingEpoch === undefined ? undefined : participantBindingEpoch(value.bindingEpoch, "$.bindingEpoch");
  if ([bossRunId, participantId, bindingEpoch].filter((entry) => entry !== undefined).length === 0) return base;
  if (bossRunId === undefined || participantId === undefined || bindingEpoch === undefined) {
    throw new ContractValidationError("$", "bossRunId, participantId, and bindingEpoch must be present together");
  }
  return { ...base, bossRunId, participantId, bindingEpoch };
}

export interface WorkerIdentityEnvironment {
  AGENT_INTERCOM_WORKER_ID: string;
  AGENT_INTERCOM_WORKER_INCARNATION_ID?: string;
  AGENT_INTERCOM_WORKER_GENERATION: string;
  AGENT_INTERCOM_BOSS_RUN_ID?: string;
  AGENT_INTERCOM_PARTICIPANT_ID?: string;
  AGENT_INTERCOM_BINDING_EPOCH?: string;
  /** Deprecated v1 incarnation name. It is never Boss authority. */
  AGENT_INTERCOM_RUN_ID?: string;
}

function positiveIntegerEnvironment(value: unknown, path: string): number {
  const text = readString(value, path);
  if (!/^[1-9]\d*$/.test(text)) throw new ContractValidationError(path, "must be a positive base-10 integer");
  return readInteger(Number(text), path, 1);
}

const WORKER_IDENTITY_ENVIRONMENT_REQUIRED_KEYS = [
  "AGENT_INTERCOM_WORKER_ID",
  "AGENT_INTERCOM_WORKER_GENERATION",
] as const;

const WORKER_IDENTITY_ENVIRONMENT_OPTIONAL_KEYS = [
  "AGENT_INTERCOM_WORKER_INCARNATION_ID",
  "AGENT_INTERCOM_BOSS_RUN_ID",
  "AGENT_INTERCOM_PARTICIPANT_ID",
  "AGENT_INTERCOM_BINDING_EPOCH",
  "AGENT_INTERCOM_RUN_ID",
] as const;

const WORKER_IDENTITY_ENVIRONMENT_KEYS = new Set<string>([
  ...WORKER_IDENTITY_ENVIRONMENT_REQUIRED_KEYS,
  ...WORKER_IDENTITY_ENVIRONMENT_OPTIONAL_KEYS,
]);

const BOSS_AUTHORITY_ENVIRONMENT_PREFIXES = [
  "AGENT_INTERCOM_BOSS_",
  "AGENT_INTERCOM_PARTICIPANT_",
  "AGENT_INTERCOM_BINDING_",
] as const;

function projectWorkerIdentityEnvironment(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ContractValidationError("$", "must be an environment object");
  }
  const projected: Record<string, unknown> = {};
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string") continue;
    const supported = WORKER_IDENTITY_ENVIRONMENT_KEYS.has(key);
    const bossAuthorityLike = BOSS_AUTHORITY_ENVIRONMENT_PREFIXES.some((prefix) => key.startsWith(prefix));
    if (!supported && !bossAuthorityLike) continue;
    if (!supported) throw new ContractValidationError(`$.${key}`, "is not a supported Boss authority environment field");
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor === undefined || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) {
      throw new ContractValidationError(`$.${key}`, "must be an enumerable data property");
    }
    projected[key] = descriptor.value;
  }
  assertExactKeys(projected, WORKER_IDENTITY_ENVIRONMENT_REQUIRED_KEYS, WORKER_IDENTITY_ENVIRONMENT_OPTIONAL_KEYS);
  return projected;
}

/** Maps process environment into the v2 identity without ever interpreting legacy runId as bossRunId. */
export function workerIdentityFromEnvironment(value: unknown): WorkerIdentityV2 {
  const environment = projectWorkerIdentityEnvironment(value);
  const canonicalIncarnation = readOptionalString(environment.AGENT_INTERCOM_WORKER_INCARNATION_ID, "$.AGENT_INTERCOM_WORKER_INCARNATION_ID");
  const deprecatedIncarnation = readOptionalString(environment.AGENT_INTERCOM_RUN_ID, "$.AGENT_INTERCOM_RUN_ID");
  if (canonicalIncarnation !== undefined && deprecatedIncarnation !== undefined && canonicalIncarnation !== deprecatedIncarnation) {
    throw new ContractValidationError("$.AGENT_INTERCOM_RUN_ID", "must match the canonical worker incarnation during migration");
  }
  const workerIncarnationId = canonicalIncarnation ?? deprecatedIncarnation;
  if (workerIncarnationId === undefined) throw new ContractValidationError("$.AGENT_INTERCOM_WORKER_INCARNATION_ID", "is required when no deprecated incarnation is present");
  const bossRunId = readOptionalString(environment.AGENT_INTERCOM_BOSS_RUN_ID, "$.AGENT_INTERCOM_BOSS_RUN_ID");
  const participantId = readOptionalString(environment.AGENT_INTERCOM_PARTICIPANT_ID, "$.AGENT_INTERCOM_PARTICIPANT_ID");
  const bindingEpoch = environment.AGENT_INTERCOM_BINDING_EPOCH === undefined
    ? undefined
    : positiveIntegerEnvironment(environment.AGENT_INTERCOM_BINDING_EPOCH, "$.AGENT_INTERCOM_BINDING_EPOCH");
  if (deprecatedIncarnation !== undefined && canonicalIncarnation === undefined && bossRunId !== undefined) {
    throw new ContractValidationError("$.AGENT_INTERCOM_RUN_ID", "a deprecated incarnation-only environment cannot establish Boss authority");
  }
  return parseWorkerIdentityV2({
    version: WORKER_IDENTITY_VERSION,
    workerId: readString(environment.AGENT_INTERCOM_WORKER_ID, "$.AGENT_INTERCOM_WORKER_ID"),
    workerIncarnationId,
    workerGeneration: positiveIntegerEnvironment(environment.AGENT_INTERCOM_WORKER_GENERATION, "$.AGENT_INTERCOM_WORKER_GENERATION"),
    ...(bossRunId === undefined ? {} : { bossRunId }),
    ...(participantId === undefined ? {} : { participantId }),
    ...(bindingEpoch === undefined ? {} : { bindingEpoch }),
  });
}

export interface WorkerEventIdentityV2 {
  workerId: string;
  workerIncarnationId: string;
  workerGeneration: WorkerGeneration;
  bossRunId?: string;
  participantId?: string;
  bindingEpoch?: ParticipantBindingEpoch;
}

/** Event identity uses the same namespace split but omits the store-envelope version. */
export function parseWorkerEventIdentityV2(value: unknown): WorkerEventIdentityV2 {
  assertRecord(value);
  assertExactKeys(value, ["workerId", "workerIncarnationId", "workerGeneration"], ["bossRunId", "participantId", "bindingEpoch"]);
  const parsed = parseWorkerIdentityV2({ version: WORKER_IDENTITY_VERSION, ...value });
  const { version: _version, ...event } = parsed;
  return event;
}
