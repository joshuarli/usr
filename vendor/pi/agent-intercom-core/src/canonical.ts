import { createHash } from "node:crypto";

export type CanonicalPrimitive = boolean | null | number | string;
export type CanonicalValue = CanonicalPrimitive | readonly CanonicalValue[] | { readonly [key: string]: CanonicalValue };
export const CANONICAL_ENCODING_VERSION = 1 as const;
export const CANONICAL_HASH_FRAME = "agent-intercom-canonical-frame-v1" as const;
/** Strings are encoded exactly as supplied; NFC/NFD normalization is intentionally not performed. */
export const CANONICAL_UNICODE_NORMALIZATION = "none" as const;

export class ContractValidationError extends Error {
  readonly path: string;

  constructor(path: string, message: string) {
    super(`${path}: ${message}`);
    this.name = "ContractValidationError";
    this.path = path;
  }
}

function ownEnumerableDataKeys(value: object, path: string): string[] {
  const keys: string[] = [];
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string") {
      throw new ContractValidationError(path, "symbol properties are not supported");
    }
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor === undefined || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) {
      throw new ContractValidationError(`${path}.${key}`, "must be an enumerable data property");
    }
    keys.push(key);
  }
  return keys;
}

function ownDenseArrayDataValues(value: unknown, path: string): unknown[] {
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
  for (let index = 0; index < length; index += 1) {
    result.push(descriptors.get(index)!.value);
  }
  return result;
}

function normalized(value: unknown, path: string, objectMember: boolean): CanonicalValue | undefined {
  if (value === undefined) {
    throw new ContractValidationError(path, "undefined is not a canonical value");
  }
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "string") {
    assertWellFormedUnicode(value, path);
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new ContractValidationError(path, "number must be a safe integer and must not be negative zero");
    }
    return value;
  }
  if (Array.isArray(value)) {
    const entries = ownDenseArrayDataValues(value, path);
    const result: CanonicalValue[] = [];
    for (let index = 0; index < entries.length; index += 1) {
      const item = normalized(entries[index], `${path}[${index}]`, false);
      if (item === undefined) throw new ContractValidationError(`${path}[${index}]`, "undefined is not a canonical value");
      result.push(item);
    }
    return result;
  }
  if (typeof value !== "object" || Object.getPrototypeOf(value) !== Object.prototype) {
    throw new ContractValidationError(path, "value must be a JSON primitive, array, or plain object");
  }
  const enumerableKeys = ownEnumerableDataKeys(value, path);
  const result: Record<string, CanonicalValue> = Object.create(null) as Record<string, CanonicalValue>;
  for (const key of enumerableKeys.sort()) {
    assertWellFormedUnicode(key, `${path}.[key]`);
    const item = normalized((value as Record<string, unknown>)[key], `${path}.${key}`, true);
    if (item === undefined) throw new ContractValidationError(`${path}.${key}`, "undefined is not a canonical value");
    result[key] = item;
  }
  return result;
}

function assertWellFormedUnicode(value: string, path: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) throw new ContractValidationError(path, "string contains an unpaired high surrogate");
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      throw new ContractValidationError(path, "string contains an unpaired low surrogate");
    }
  }
}

/** Canonical JSON sorts object keys recursively and rejects undefined and every non-JSON value. */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(normalized(value, "$", false));
}

/** Injective length-prefixed framing for the domain and canonical payload bytes. */
export function canonicalFrame(domain: string, value: unknown): Uint8Array {
  if (!/^[\x21-\x7e]+$/.test(domain)) {
    throw new ContractValidationError("domain", "must be non-empty printable ASCII without whitespace");
  }
  const encoder = new TextEncoder();
  const domainBytes = encoder.encode(domain);
  const payloadBytes = encoder.encode(canonicalJson(value));
  const header = encoder.encode(`${CANONICAL_HASH_FRAME}:${domainBytes.byteLength}:`);
  const separator = encoder.encode(`:${payloadBytes.byteLength}:`);
  const frame = new Uint8Array(header.byteLength + domainBytes.byteLength + separator.byteLength + payloadBytes.byteLength);
  frame.set(header, 0);
  frame.set(domainBytes, header.byteLength);
  frame.set(separator, header.byteLength + domainBytes.byteLength);
  frame.set(payloadBytes, header.byteLength + domainBytes.byteLength + separator.byteLength);
  return frame;
}

/** Domain-separated SHA-256 over UTF-8 canonical JSON. */
export function canonicalHash(domain: string, value: unknown): string {
  return createHash("sha256").update(canonicalFrame(domain, value)).digest("hex");
}

export type StringEnum<T extends readonly string[]> = T[number];

declare const MONOTONIC_COUNTER_BRAND: unique symbol;
export type MonotonicCounter<Kind extends string> = number & { readonly [MONOTONIC_COUNTER_BRAND]: Kind };
export type BossBindingEpoch = MonotonicCounter<"boss_binding_epoch">;
export type ParticipantBindingEpoch = MonotonicCounter<"participant_binding_epoch">;
export type SubscriberBindingEpoch = MonotonicCounter<"subscriber_binding_epoch">;
export type SubscriberBindingGeneration = MonotonicCounter<"subscriber_binding_generation">;
export type ControllerGeneration = MonotonicCounter<"controller_generation">;
export type BrokerRevision = MonotonicCounter<"broker_revision">;
export type WorkerGeneration = MonotonicCounter<"worker_generation">;
export type TransitionVersion = MonotonicCounter<"transition_version">;
export type BrokerGeneration = MonotonicCounter<"broker_generation">;
export type JournalGeneration = MonotonicCounter<"journal_generation">;
export type SchedulerGeneration = MonotonicCounter<"scheduler_generation">;
export type RecipientTransferGeneration = MonotonicCounter<"recipient_transfer_generation">;
export type DeliveryClaimGeneration = MonotonicCounter<"delivery_claim_generation">;
export type TriggerGeneration = MonotonicCounter<"trigger_generation">;
export type WatchdogGeneration = MonotonicCounter<"watchdog_generation">;

export function readMonotonicCounter<Kind extends string>(value: unknown, path: string, _kind: Kind, minimum = 1): MonotonicCounter<Kind> {
  return readInteger(value, path, minimum) as MonotonicCounter<Kind>;
}

export const bossBindingEpoch = (value: unknown, path = "bossBindingEpoch", minimum = 1) => readMonotonicCounter(value, path, "boss_binding_epoch", minimum);
export const participantBindingEpoch = (value: unknown, path = "bindingEpoch", minimum = 1) => readMonotonicCounter(value, path, "participant_binding_epoch", minimum);
export const subscriberBindingEpoch = (value: unknown, path = "subscriberBindingEpoch", minimum = 1) => readMonotonicCounter(value, path, "subscriber_binding_epoch", minimum);
export const subscriberBindingGeneration = (value: unknown, path = "subscriberBindingGeneration", minimum = 1) => readMonotonicCounter(value, path, "subscriber_binding_generation", minimum);
export const controllerGeneration = (value: unknown, path = "controllerGeneration", minimum = 1) => readMonotonicCounter(value, path, "controller_generation", minimum);
export const brokerRevision = (value: unknown, path = "brokerRevision", minimum = 0) => readMonotonicCounter(value, path, "broker_revision", minimum);
export const workerGeneration = (value: unknown, path = "workerGeneration") => readMonotonicCounter(value, path, "worker_generation");
export const transitionVersion = (value: unknown, path = "transitionVersion") => readMonotonicCounter(value, path, "transition_version");
export const brokerGeneration = (value: unknown, path = "brokerGeneration") => readMonotonicCounter(value, path, "broker_generation");
export const journalGeneration = (value: unknown, path = "journalGeneration") => readMonotonicCounter(value, path, "journal_generation");
export const schedulerGeneration = (value: unknown, path = "schedulerGeneration") => readMonotonicCounter(value, path, "scheduler_generation");
export const recipientTransferGeneration = (value: unknown, path = "recipientTransferGeneration", minimum = 0) => readMonotonicCounter(value, path, "recipient_transfer_generation", minimum);
export const deliveryClaimGeneration = (value: unknown, path = "claimGeneration") => readMonotonicCounter(value, path, "delivery_claim_generation");
export const triggerGeneration = (value: unknown, path = "triggerGeneration", minimum = 0) => readMonotonicCounter(value, path, "trigger_generation", minimum);
export const watchdogGeneration = (value: unknown, path = "watchdogGeneration") => readMonotonicCounter(value, path, "watchdog_generation");

export function assertRecord(value: unknown, path = "$" ): asserts value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) {
    throw new ContractValidationError(path, "must be a plain object");
  }
  ownEnumerableDataKeys(value, path);
}

export function assertExactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = [],
  path = "$",
): void {
  const permitted = new Set([...required, ...optional]);
  for (const key of required) {
    if (!Object.hasOwn(value, key)) throw new ContractValidationError(`${path}.${key}`, "is required");
  }
  for (const key of ownEnumerableDataKeys(value, path)) {
    if (!permitted.has(key)) throw new ContractValidationError(`${path}.${key}`, "is not supported");
  }
}

export function readString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) throw new ContractValidationError(path, "must be a non-empty string");
  assertWellFormedUnicode(value, path);
  return value;
}

export function readIdentifier(value: unknown, path: string): string {
  const identifier = readString(value, path);
  if (/[\x00-\x20\x7f]/.test(identifier)) {
    throw new ContractValidationError(path, "identifier must not contain ASCII whitespace or control characters");
  }
  return identifier;
}

export function readOptionalIdentifier(value: unknown, path: string): string | undefined {
  return value === undefined ? undefined : readIdentifier(value, path);
}

export function readOptionalString(value: unknown, path: string): string | undefined {
  return value === undefined ? undefined : readString(value, path);
}

export function readInteger(value: unknown, path: string, minimum = 0): number {
  if (!Number.isSafeInteger(value) || Object.is(value, -0) || (value as number) < minimum) {
    throw new ContractValidationError(path, `must be a safe integer >= ${minimum}`);
  }
  return value as number;
}

export function readOptionalInteger(value: unknown, path: string, minimum = 0): number | undefined {
  return value === undefined ? undefined : readInteger(value, path, minimum);
}

export function readBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") throw new ContractValidationError(path, "must be a boolean");
  return value;
}

export function readOptionalBoolean(value: unknown, path: string): boolean | undefined {
  return value === undefined ? undefined : readBoolean(value, path);
}

export function readEnum<const T extends readonly string[]>(value: unknown, allowed: T, path: string): T[number] {
  if (typeof value !== "string" || !allowed.includes(value)) {
    throw new ContractValidationError(path, `must be one of: ${allowed.join(", ")}`);
  }
  return value as T[number];
}

export function readStringArray(value: unknown, path: string): string[] {
  return ownDenseArrayDataValues(value, path).map((entry, index) => readString(entry, `${path}[${index}]`));
}

export function readTimestamp(value: unknown, path: string): string {
  const timestamp = readString(value, path);
  const parsed = Date.parse(timestamp);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(timestamp) || Number.isNaN(parsed) || new Date(parsed).toISOString() !== timestamp) {
    throw new ContractValidationError(path, "must be a canonical UTC ISO-8601 timestamp");
  }
  return timestamp;
}

export function readOptionalTimestamp(value: unknown, path: string): string | undefined {
  return value === undefined ? undefined : readTimestamp(value, path);
}

export function readHexDigest(value: unknown, path: string): string {
  const digest = readString(value, path);
  if (!/^[a-f0-9]{64}$/.test(digest)) throw new ContractValidationError(path, "must be a lowercase SHA-256 digest");
  return digest;
}

export type StoreValidationFailureReason =
  | "corrupt"
  | "unsupported_newer_version"
  | "unsupported_older_version"
  | "foreign_version";

export type StoreValidationResult<T> =
  | { ok: true; status: "valid"; value: T }
  | {
      ok: false;
      status: StoreValidationFailureReason;
      observedVersion?: unknown;
      path?: string;
      message: string;
      preserveExisting: true;
      mutationAllowed: false;
    };

function versionFamily(value: string): { family: string; revision: number } | undefined {
  const match = /^(.*\.v)(\d+)$/.exec(value);
  return match ? { family: match[1], revision: Number(match[2]) } : undefined;
}

/** Nonthrowing store gate. Failures never synthesize defaults and always require preserving the source. */
export function validateVersionedStoreRecord<T>(
  value: unknown,
  expectedVersion: string | number,
  parser: (input: unknown) => T,
): StoreValidationResult<T> {
  const failure = (
    status: StoreValidationFailureReason,
    message: string,
    observedVersion?: unknown,
    path?: string,
  ): StoreValidationResult<T> => ({
    ok: false,
    status,
    ...(observedVersion === undefined ? {} : { observedVersion }),
    ...(path === undefined ? {} : { path }),
    message,
    preserveExisting: true,
    mutationAllowed: false,
  });
  try {
    assertRecord(value);
  } catch (error) {
    if (error instanceof ContractValidationError) return failure("corrupt", error.message, undefined, error.path);
    return failure("corrupt", error instanceof Error ? error.message : "unknown validation failure", undefined, "$");
  }

  const versionDescriptor = Object.getOwnPropertyDescriptor(value, "version");
  if (versionDescriptor === undefined) {
    return failure("corrupt", "store version is required", undefined, "$.version");
  }
  if (!versionDescriptor.enumerable || !Object.hasOwn(versionDescriptor, "value")) {
    return failure("corrupt", "store version must be an enumerable data property", undefined, "$.version");
  }
  const observedVersion = versionDescriptor.value;
  if (observedVersion === undefined) {
    return failure("corrupt", "store version is required", undefined, "$.version");
  }
  if (observedVersion !== expectedVersion) {
    if (typeof observedVersion === "number" && typeof expectedVersion === "number" && Number.isSafeInteger(observedVersion)) {
      return failure(
        observedVersion > expectedVersion ? "unsupported_newer_version" : "unsupported_older_version",
        `unsupported store version ${observedVersion}; expected ${expectedVersion}`,
        observedVersion,
        "$.version",
      );
    }
    if (typeof observedVersion === "string" && typeof expectedVersion === "string") {
      const observed = versionFamily(observedVersion);
      const expected = versionFamily(expectedVersion);
      if (observed && expected && observed.family === expected.family) {
        return failure(
          observed.revision > expected.revision ? "unsupported_newer_version" : "unsupported_older_version",
          `unsupported store version ${observedVersion}; expected ${expectedVersion}`,
          observedVersion,
          "$.version",
        );
      }
      return failure("foreign_version", `foreign store version ${observedVersion}`, observedVersion, "$.version");
    }
    return failure("foreign_version", "store version uses an incompatible representation", observedVersion, "$.version");
  }
  try {
    return { ok: true, status: "valid", value: parser(value) };
  } catch (error) {
    if (error instanceof ContractValidationError) return failure("corrupt", error.message, observedVersion, error.path);
    return failure("corrupt", error instanceof Error ? error.message : "unknown validation failure", observedVersion);
  }
}
