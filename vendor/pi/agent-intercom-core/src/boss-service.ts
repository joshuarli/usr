import { createPublicKey, KeyObject, verify as verifySignature } from "node:crypto";
import { posix as posixPath } from "node:path";
import { types as nodeUtilTypes } from "node:util";
import {
  assertExactKeys,
  assertRecord,
  brokerGeneration,
  brokerRevision,
  canonicalFrame,
  canonicalHash,
  canonicalJson,
  ContractValidationError,
  readEnum,
  readHexDigest,
  readInteger,
  readString,
  readStringArray,
  readTimestamp,
  participantBindingEpoch,
  subscriberBindingEpoch,
  subscriberBindingGeneration,
  validateVersionedStoreRecord,
  type StoreValidationResult,
} from "./canonical.ts";
import {
  BOSS_CONTROL_ENVELOPE_VERSION,
  BOSS_RUN_FEATURE,
  BOSS_RUN_FEATURE_SEMANTICS_HASH,
  BOSS_RUN_FEATURE_VERSION,
  BOSS_CAPABILITY_FEATURE_DIGEST,
  BOSS_RUN_PROTOCOL_FEATURE_CONTRACT_HASH,
  parseBossParticipantBinding,
  type BossParticipantBinding,
} from "./boss-wire.ts";
import type {
  BrokerGeneration,
  BrokerRevision,
  ParticipantBindingEpoch,
  SubscriberBindingEpoch,
  SubscriberBindingGeneration,
} from "./canonical.ts";
import { parseBossPolicyPrincipal, type BossPolicyState, type BossPrivatePrincipal, type BossPolicyRole } from "./boss-policy.ts";
import { parseParticipantState, type ParticipantState } from "./boss-participant-state.ts";
import {
  parseLifecycleSubscription,
  parseLifecycleTarget,
  type LifecycleSubscriptionRecord,
  type LifecycleTarget,
} from "./supervision.ts";
import { INTERCOM_BASE_PROTOCOL_VERSION } from "./boss-semantic-binding-constants.ts";

export { INTERCOM_BASE_PROTOCOL_VERSION };
export const BROKER_FEATURE_ATTESTATION_VERSION = "intercom.broker-feature.v1" as const;
export const BROKER_IDENTITY_RECORD_VERSION = "intercom.broker-identity.v1" as const;
export const BROKER_PROVIDER_ATTESTATION_VERSION = "intercom.broker-provider-attestation.v1" as const;
export const BROKER_PEER_EXPECTATION_VERSION = "intercom.broker-peer-expectation.v1" as const;
export const LEGACY_ADMIN_MIGRATION_VERSION = "intercom.legacy-admin-migration.v1" as const;
export const BROKER_JOURNAL_RECOVERY_VERSION = "intercom.broker-journal-recovery.v1" as const;
export const BOSS_RESTRICTED_CLIENT_REQUEST_VERSION = "boss.restricted-client-request.v1" as const;
export const BOSS_RESTRICTED_CLIENT_RESULT_VERSION = "boss.restricted-client-result.v1" as const;
export const BROKER_FEATURE_SET_HASH_DOMAIN = "agent-intercom-core/broker-feature-set/v1" as const;
export const BROKER_IDENTITY_SIGNATURE_DOMAIN = "agent-intercom-core/broker-identity/v1" as const;
export const BROKER_PROVIDER_ATTESTATION_SIGNATURE_DOMAIN = "agent-intercom-core/broker-provider-attestation/v1" as const;
export const BROKER_PROTECTED_PROVIDER_ROOT = "/usr/lib/agent-intercom/providers/" as const;

export interface BrokerFeatureAttestation {
  version: typeof BROKER_FEATURE_ATTESTATION_VERSION;
  feature: string;
  featureVersion: number;
  semanticsHash: string;
  controlEnvelopeVersion?: number;
  capabilityDigest?: string;
  optional?: true;
}

export function parseBrokerFeatureAttestation(value: unknown): BrokerFeatureAttestation {
  assertRecord(value);
  assertExactKeys(value, ["version", "feature", "featureVersion", "semanticsHash"], ["controlEnvelopeVersion", "capabilityDigest", "optional"]);
  if (value.version !== BROKER_FEATURE_ATTESTATION_VERSION) {
    throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  }
  const feature = readString(value.feature, "$.feature");
  const featureVersion = readInteger(value.featureVersion, "$.featureVersion", 1);
  const semanticsHash = readHexDigest(value.semanticsHash, "$.semanticsHash");
  const controlEnvelopeVersion = value.controlEnvelopeVersion === undefined
    ? undefined
    : readInteger(value.controlEnvelopeVersion, "$.controlEnvelopeVersion", 1);
  const capabilityDigest = value.capabilityDigest === undefined ? undefined : readHexDigest(value.capabilityDigest, "$.capabilityDigest");
  if (value.optional !== undefined && value.optional !== true) throw new ContractValidationError("$.optional", "must be true when present");
  const optional = value.optional === true ? true : undefined;
  if (feature === BOSS_RUN_FEATURE) {
    if (optional !== undefined) throw new ContractValidationError("$.optional", "the required Boss feature cannot be optional");
    if (
      featureVersion !== BOSS_RUN_FEATURE_VERSION
      || semanticsHash !== BOSS_RUN_FEATURE_SEMANTICS_HASH
      || controlEnvelopeVersion !== BOSS_CONTROL_ENVELOPE_VERSION
      || capabilityDigest !== BOSS_CAPABILITY_FEATURE_DIGEST
    ) throw new ContractValidationError("$.feature", "invalid boss-run-v1 feature attestation");
  }
  return {
    version: BROKER_FEATURE_ATTESTATION_VERSION,
    feature,
    featureVersion,
    semanticsHash,
    ...(controlEnvelopeVersion === undefined ? {} : { controlEnvelopeVersion }),
    ...(capabilityDigest === undefined ? {} : { capabilityDigest }),
    ...(optional === undefined ? {} : { optional }),
  };
}

export interface BrokerCapabilityAdvertisement {
  baseProtocolVersion: number;
  features: BrokerFeatureAttestation[];
  protocolFeatureContractHash?: string;
  featureSetHash?: string;
  controlEnvelopeVersion?: number;
  capabilityDigest?: string;
}

export type BrokerCapabilityAdvertisementDenialCode = "UNKNOWN_FEATURE" | "DUPLICATE_FEATURE" | "FEATURE_DIVERGENCE";

export class BrokerCapabilityAdvertisementError extends ContractValidationError {
  readonly code: BrokerCapabilityAdvertisementDenialCode;

  constructor(path: string, message: string, code: BrokerCapabilityAdvertisementDenialCode) {
    super(path, message);
    this.name = "BrokerCapabilityAdvertisementError";
    this.code = code;
  }
}

function sortedFeatures(features: readonly BrokerFeatureAttestation[]): BrokerFeatureAttestation[] {
  return [...features].sort((left, right) => left.feature < right.feature ? -1 : left.feature > right.feature ? 1 : 0);
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

/**
 * Validates an untrusted object entirely through own-property descriptors and
 * returns a fresh plain-object projection. No property value is obtained via
 * [[Get]], so accessors are rejected without being invoked.
 */
function projectExactOwnEnumerableDataRecord(
  value: unknown,
  required: readonly string[],
  optional: readonly string[] = [],
  path = "$",
): Record<string, unknown> {
  assertRecord(value, path);
  assertExactKeys(value, required, optional, path);
  const projected: Record<string, unknown> = {};
  for (const key of [...required, ...optional]) {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor !== undefined) {
      Object.defineProperty(projected, key, {
        configurable: true,
        enumerable: true,
        value: descriptor.value,
        writable: true,
      });
    }
  }
  return projected;
}

function projectOwnEnumerableDataRecord(value: unknown, path: string): Record<string, unknown> {
  assertRecord(value, path);
  const projected: Record<string, unknown> = {};
  for (const key of Reflect.ownKeys(value)) {
    const descriptor = Object.getOwnPropertyDescriptor(value, key)!;
    Object.defineProperty(projected, key, {
      configurable: true,
      enumerable: true,
      value: descriptor.value,
      writable: true,
    });
  }
  return projected;
}

export function brokerFeatureSetHash(featuresValue: unknown): string {
  if (!Array.isArray(featuresValue)) throw new ContractValidationError("$.features", "must be an array");
  const features = parseBrokerFeatureSet(featuresValue, "$.features");
  return canonicalHash(BROKER_FEATURE_SET_HASH_DOMAIN, sortedFeatures(features));
}

function parseBrokerFeatureSet(value: readonly unknown[], path: string): BrokerFeatureAttestation[] {
  let entries: unknown[];
  try {
    entries = ownDenseArrayDataValues(value, path);
  } catch (error) {
    throw new BrokerCapabilityAdvertisementError(path, error instanceof Error ? error.message : "invalid feature array", "FEATURE_DIVERGENCE");
  }
  const parsed: BrokerFeatureAttestation[] = [];
  const names = new Set<string>();
  for (let index = 0; index < entries.length; index += 1) {
    const entryPath = `${path}[${index}]`;
    const entry = entries[index];
    try {
      assertRecord(entry, entryPath);
    } catch (error) {
      throw new BrokerCapabilityAdvertisementError(entryPath, error instanceof Error ? error.message : "invalid feature", "FEATURE_DIVERGENCE");
    }
    const name = typeof entry.feature === "string" ? entry.feature : undefined;
    if (name === undefined || name.length === 0) {
      throw new BrokerCapabilityAdvertisementError(`${entryPath}.feature`, "must be a non-empty string", "FEATURE_DIVERGENCE");
    }
    if (names.has(name)) {
      throw new BrokerCapabilityAdvertisementError(`${entryPath}.feature`, `duplicate feature ${name}`, "DUPLICATE_FEATURE");
    }
    names.add(name);
    if (name !== BOSS_RUN_FEATURE && entry.optional !== true) {
      throw new BrokerCapabilityAdvertisementError(`${entryPath}.feature`, `unsupported feature ${name}`, "UNKNOWN_FEATURE");
    }
    try {
      parsed.push(parseBrokerFeatureAttestation(entry));
    } catch (error) {
      throw new BrokerCapabilityAdvertisementError(entryPath, error instanceof Error ? error.message : "invalid feature", "FEATURE_DIVERGENCE");
    }
  }
  return parsed;
}

/** Strictly parses the envelope and every advertised feature before any client-specific negotiation. */
export function parseBrokerCapabilityAdvertisement(value: unknown): BrokerCapabilityAdvertisement {
  try {
    assertRecord(value);
    assertExactKeys(
      value,
      ["baseProtocolVersion", "features"],
      ["protocolFeatureContractHash", "featureSetHash", "controlEnvelopeVersion", "capabilityDigest"],
    );
  } catch (error) {
    throw new BrokerCapabilityAdvertisementError("$", error instanceof Error ? error.message : "invalid advertisement", "FEATURE_DIVERGENCE");
  }
  if (!Array.isArray(value.features)) {
    throw new BrokerCapabilityAdvertisementError("$.features", "must be an array", "FEATURE_DIVERGENCE");
  }
  const baseProtocolVersion = readInteger(value.baseProtocolVersion, "$.baseProtocolVersion", 1);
  const features = parseBrokerFeatureSet(value.features, "$.features");
  const hasBossFeature = features.some((feature) => feature.feature === BOSS_RUN_FEATURE);
  if (hasBossFeature && baseProtocolVersion !== INTERCOM_BASE_PROTOCOL_VERSION) {
    throw new BrokerCapabilityAdvertisementError(
      "$.baseProtocolVersion",
      `Boss advertisements require base protocol version ${INTERCOM_BASE_PROTOCOL_VERSION}`,
      "FEATURE_DIVERGENCE",
    );
  }
  const metadata = [
    value.protocolFeatureContractHash,
    value.featureSetHash,
    value.controlEnvelopeVersion,
    value.capabilityDigest,
  ];
  if (hasBossFeature && metadata.some((entry) => entry === undefined)) {
    throw new BrokerCapabilityAdvertisementError("$", "Boss advertisements require the complete protocol/feature/envelope/capability binding", "FEATURE_DIVERGENCE");
  }
  if (features.length > 0 && value.featureSetHash === undefined) {
    throw new BrokerCapabilityAdvertisementError("$.featureSetHash", "is required whenever features are advertised", "FEATURE_DIVERGENCE");
  }
  const protocolFeatureContractHash = value.protocolFeatureContractHash === undefined
    ? undefined
    : readHexDigest(value.protocolFeatureContractHash, "$.protocolFeatureContractHash");
  const featureSetHash = value.featureSetHash === undefined ? undefined : readHexDigest(value.featureSetHash, "$.featureSetHash");
  const controlEnvelopeVersion = value.controlEnvelopeVersion === undefined
    ? undefined
    : readInteger(value.controlEnvelopeVersion, "$.controlEnvelopeVersion", 1);
  const capabilityDigest = value.capabilityDigest === undefined ? undefined : readHexDigest(value.capabilityDigest, "$.capabilityDigest");
  if (featureSetHash !== undefined && featureSetHash !== brokerFeatureSetHash(features)) {
    throw new BrokerCapabilityAdvertisementError("$.featureSetHash", "does not hash the complete advertised feature set", "FEATURE_DIVERGENCE");
  }
  if (hasBossFeature && (
    protocolFeatureContractHash !== BOSS_RUN_PROTOCOL_FEATURE_CONTRACT_HASH
    || controlEnvelopeVersion !== BOSS_CONTROL_ENVELOPE_VERSION
    || capabilityDigest !== BOSS_CAPABILITY_FEATURE_DIGEST
  )) {
    throw new BrokerCapabilityAdvertisementError("$", "advertised Boss binding metadata diverges from the canonical contract", "FEATURE_DIVERGENCE");
  }
  return {
    baseProtocolVersion,
    features,
    ...(protocolFeatureContractHash === undefined ? {} : { protocolFeatureContractHash }),
    ...(featureSetHash === undefined ? {} : { featureSetHash }),
    ...(controlEnvelopeVersion === undefined ? {} : { controlEnvelopeVersion }),
    ...(capabilityDigest === undefined ? {} : { capabilityDigest }),
  };
}

export type BrokerCompatibilityRequest =
  | { clientKind: "ordinary"; supportedBaseProtocolVersions: number[] }
  | {
      clientKind: "boss";
      supportedBaseProtocolVersions: number[];
      requiredFeature: typeof BOSS_RUN_FEATURE;
      expectedProtectedOwnerUid: number;
      identityVerification: BrokerIdentityVerificationContext;
      peerExpectation: BrokerPeerExpectation;
      observedPeer: ObservedBrokerPeer;
    };

function parseSupportedBaseProtocolVersions(value: unknown, path: string): number[] {
  const entries = ownDenseArrayDataValues(value, path);
  if (entries.length === 0) throw new ContractValidationError(path, "must be a non-empty array");
  const versions = entries.map((entry, index) => readInteger(entry, `${path}[${index}]`, 1));
  if (new Set(versions).size !== versions.length) throw new ContractValidationError(path, "must not contain duplicates");
  return versions;
}

function parseBrokerPublicKeyTrustStore(value: unknown, path: string): BrokerPublicKeyTrustStore {
  const projected = projectOwnEnumerableDataRecord(value, path);
  for (const [keyId, publicKey] of Object.entries(projected)) {
    readString(keyId, `${path}.[keyId]`);
    if (typeof publicKey === "string") {
      readString(publicKey, `${path}.${keyId}`);
      try {
        if (createPublicKey(publicKey).type !== "public") throw new Error("not public");
      } catch {
        throw new ContractValidationError(`${path}.${keyId}`, "must resolve to a public key");
      }
    } else if (!(publicKey instanceof KeyObject) || publicKey.type !== "public") {
      throw new ContractValidationError(`${path}.${keyId}`, "must be a public KeyObject or encoded public key");
    }
  }
  return projected as BrokerPublicKeyTrustStore;
}

function parseBrokerIdentityVerificationContext(
  value: unknown,
  requireProviderAttestation = true,
  parseProviderAttestation = true,
): BrokerIdentityVerificationContext {
  const path = "$.identityVerification";
  const projected = projectExactOwnEnumerableDataRecord(value, [
    "expectedProviderPackage",
    "expectedProviderVersion",
    "expectedProviderDigest",
    "expectedProviderArtifactRoot",
    "expectedProviderArtifactOwnerUid",
    "expectedProviderArtifactOwnerGid",
    "expectedProviderArtifactMode",
    "expectedOwnerUid",
    "expectedBrokerServiceUid",
    "expectedBootInstance",
    "minimumBrokerGeneration",
    "expectedPublicEndpoint",
    "expectedAuthorityEndpoint",
    "trustedIdentityKeys",
    "trustedProviderKeys",
  ], ["providerAttestation"], path);
  if (requireProviderAttestation && projected.providerAttestation === undefined) {
    throw new ContractValidationError(`${path}.providerAttestation`, "is required");
  }
  const providerAttestation = projected.providerAttestation === undefined
    ? undefined
    : parseProviderAttestation
      ? parseBrokerProviderAttestation(projected.providerAttestation)
      : projected.providerAttestation;
  return {
    expectedProviderPackage: readString(projected.expectedProviderPackage, `${path}.expectedProviderPackage`),
    expectedProviderVersion: readString(projected.expectedProviderVersion, `${path}.expectedProviderVersion`),
    expectedProviderDigest: readHexDigest(projected.expectedProviderDigest, `${path}.expectedProviderDigest`),
    expectedProviderArtifactRoot: readString(projected.expectedProviderArtifactRoot, `${path}.expectedProviderArtifactRoot`),
    expectedProviderArtifactOwnerUid: readInteger(projected.expectedProviderArtifactOwnerUid, `${path}.expectedProviderArtifactOwnerUid`),
    expectedProviderArtifactOwnerGid: readInteger(projected.expectedProviderArtifactOwnerGid, `${path}.expectedProviderArtifactOwnerGid`),
    expectedProviderArtifactMode: readString(projected.expectedProviderArtifactMode, `${path}.expectedProviderArtifactMode`),
    expectedOwnerUid: readInteger(projected.expectedOwnerUid, `${path}.expectedOwnerUid`),
    expectedBrokerServiceUid: readInteger(projected.expectedBrokerServiceUid, `${path}.expectedBrokerServiceUid`),
    expectedBootInstance: readString(projected.expectedBootInstance, `${path}.expectedBootInstance`),
    minimumBrokerGeneration: brokerGeneration(projected.minimumBrokerGeneration, `${path}.minimumBrokerGeneration`),
    expectedPublicEndpoint: readString(projected.expectedPublicEndpoint, `${path}.expectedPublicEndpoint`),
    expectedAuthorityEndpoint: readString(projected.expectedAuthorityEndpoint, `${path}.expectedAuthorityEndpoint`),
    trustedIdentityKeys: parseBrokerPublicKeyTrustStore(projected.trustedIdentityKeys, `${path}.trustedIdentityKeys`),
    trustedProviderKeys: parseBrokerPublicKeyTrustStore(projected.trustedProviderKeys, `${path}.trustedProviderKeys`),
    ...(providerAttestation === undefined ? {} : { providerAttestation }),
  };
}

/** Parses the complete request before compatibility evaluation may branch on its discriminator. */
export function parseBrokerCompatibilityRequest(value: unknown): BrokerCompatibilityRequest {
  assertRecord(value);
  const clientKind = readEnum(value.clientKind, ["ordinary", "boss"] as const, "$.clientKind");
  if (clientKind === "ordinary") {
    assertExactKeys(value, ["clientKind", "supportedBaseProtocolVersions"]);
    return {
      clientKind,
      supportedBaseProtocolVersions: parseSupportedBaseProtocolVersions(value.supportedBaseProtocolVersions, "$.supportedBaseProtocolVersions"),
    };
  }
  assertExactKeys(value, [
    "clientKind",
    "supportedBaseProtocolVersions",
    "requiredFeature",
    "expectedProtectedOwnerUid",
    "identityVerification",
    "peerExpectation",
    "observedPeer",
  ]);
  const supportedBaseProtocolVersions = parseSupportedBaseProtocolVersions(
    value.supportedBaseProtocolVersions,
    "$.supportedBaseProtocolVersions",
  );
  if (!supportedBaseProtocolVersions.includes(INTERCOM_BASE_PROTOCOL_VERSION)) {
    throw new ContractValidationError(
      "$.supportedBaseProtocolVersions",
      `Boss clients must support base protocol version ${INTERCOM_BASE_PROTOCOL_VERSION}`,
    );
  }
  if (value.requiredFeature !== BOSS_RUN_FEATURE) {
    throw new ContractValidationError("$.requiredFeature", `must be exactly ${BOSS_RUN_FEATURE}`);
  }
  const expectedProtectedOwnerUid = readInteger(value.expectedProtectedOwnerUid, "$.expectedProtectedOwnerUid");
  const identityVerification = parseBrokerIdentityVerificationContext(value.identityVerification);
  const peerExpectation = parseBrokerPeerExpectation(value.peerExpectation);
  const observedPeer = parseObservedBrokerPeer(value.observedPeer);
  if (
    identityVerification.expectedOwnerUid !== expectedProtectedOwnerUid
    || peerExpectation.ownerUid !== expectedProtectedOwnerUid
  ) throw new ContractValidationError("$.expectedProtectedOwnerUid", "must match the nested identity and peer owner bindings");
  if (peerExpectation.expectedBrokerServiceUid !== identityVerification.expectedBrokerServiceUid) {
    throw new ContractValidationError("$.peerExpectation.expectedBrokerServiceUid", "must match the protected identity verification context");
  }
  return {
    clientKind,
    supportedBaseProtocolVersions,
    requiredFeature: BOSS_RUN_FEATURE,
    expectedProtectedOwnerUid,
    identityVerification,
    peerExpectation,
    observedPeer,
  };
}

export type BrokerCompatibilityDecision =
  | { compatible: true; mode: "ordinary" | "boss" }
  | {
      compatible: false;
      code:
        | "BASE_PROTOCOL_UNSUPPORTED"
        | "INVALID_COMPATIBILITY_REQUEST"
        | "BOSS_FEATURE_REQUIRED"
        | BrokerCapabilityAdvertisementDenialCode
        | "PROTECTED_IDENTITY_REQUIRED"
        | "IDENTITY_UNSIGNED"
        | "IDENTITY_KEY_UNKNOWN"
        | "IDENTITY_SIGNATURE_INVALID"
        | "IDENTITY_RECORD_INVALID"
        | "PROVIDER_ATTESTATION_REQUIRED"
        | "PROVIDER_ATTESTATION_UNSIGNED"
        | "PROVIDER_KEY_UNKNOWN"
        | "PROVIDER_SIGNATURE_INVALID"
        | "PROVIDER_MISMATCH"
        | "PROVIDER_ARTIFACT_MISMATCH"
        | "OWNER_UID_MISMATCH"
        | "PROTECTED_SERVICE_MISMATCH"
        | "STALE_BOOT_INSTANCE"
        | "REGRESSED_BROKER_GENERATION"
        | "ENDPOINT_MISMATCH"
        | "PEER_CREDENTIALS_MISSING"
        | "PEER_MISMATCH";
    };

export function evaluateBrokerCompatibility(
  requestValue: unknown,
  advertisement: BrokerCapabilityAdvertisement,
  identity?: BrokerIdentityRecord,
): BrokerCompatibilityDecision {
  let request: BrokerCompatibilityRequest;
  try {
    request = parseBrokerCompatibilityRequest(requestValue);
  } catch {
    return { compatible: false, code: "INVALID_COMPATIBILITY_REQUEST" };
  }
  let parsedAdvertisement: BrokerCapabilityAdvertisement;
  try {
    parsedAdvertisement = parseBrokerCapabilityAdvertisement(advertisement);
  } catch (error) {
    if (error instanceof BrokerCapabilityAdvertisementError) return { compatible: false, code: error.code };
    return { compatible: false, code: "FEATURE_DIVERGENCE" };
  }
  if (!request.supportedBaseProtocolVersions.includes(parsedAdvertisement.baseProtocolVersion)) {
    return { compatible: false, code: "BASE_PROTOCOL_UNSUPPORTED" };
  }
  if (request.clientKind === "ordinary") return { compatible: true, mode: "ordinary" };
  if (!parsedAdvertisement.features.some((feature) => feature.feature === BOSS_RUN_FEATURE)) {
    return { compatible: false, code: "BOSS_FEATURE_REQUIRED" };
  }
  if (!identity) return { compatible: false, code: "PROTECTED_IDENTITY_REQUIRED" };
  let parsedIdentity: BrokerIdentityRecord;
  try {
    parsedIdentity = parseBrokerIdentityRecord(identity);
  } catch (error) {
    if (error instanceof BrokerCapabilityAdvertisementError) return { compatible: false, code: error.code };
    if (missingSignatureFields(identity, "identityKeyId")) return { compatible: false, code: "IDENTITY_UNSIGNED" };
    if (error instanceof ContractValidationError && (error.path.includes("Endpoint") || error.path.includes("endpoint"))) {
      if (error.message.includes("enumerable data property")) {
        return { compatible: false, code: "IDENTITY_RECORD_INVALID" };
      }
      return { compatible: false, code: "ENDPOINT_MISMATCH" };
    }
    return { compatible: false, code: "IDENTITY_RECORD_INVALID" };
  }
  if (parsedIdentity.ownerUid !== request.expectedProtectedOwnerUid) return { compatible: false, code: "OWNER_UID_MISMATCH" };
  if (
    parsedIdentity.baseProtocolVersion !== parsedAdvertisement.baseProtocolVersion
    || parsedIdentity.protocolFeatureContractHash !== parsedAdvertisement.protocolFeatureContractHash
    || parsedIdentity.featureSetHash !== parsedAdvertisement.featureSetHash
    || parsedIdentity.controlEnvelopeVersion !== parsedAdvertisement.controlEnvelopeVersion
    || parsedIdentity.capabilityDigest !== parsedAdvertisement.capabilityDigest
    || canonicalJson(sortedFeatures(parsedIdentity.features)) !== canonicalJson(sortedFeatures(parsedAdvertisement.features))
  ) return { compatible: false, code: "FEATURE_DIVERGENCE" };
  if (request.identityVerification.expectedOwnerUid !== request.expectedProtectedOwnerUid) {
    return { compatible: false, code: "OWNER_UID_MISMATCH" };
  }
  const identityDecision = verifyProtectedBrokerIdentity(parsedIdentity, request.identityVerification);
  if (!identityDecision.accepted) return { compatible: false, code: identityDecision.code };
  let peerExpectation: BrokerPeerExpectation;
  try {
    peerExpectation = parseBrokerPeerExpectation(request.peerExpectation);
  } catch {
    return { compatible: false, code: "PEER_MISMATCH" };
  }
  if (request.observedPeer.kernelPeerCredentialsPresent !== true) return { compatible: false, code: "PEER_CREDENTIALS_MISSING" };
  let peerDecision: BrokerPeerDecision;
  try {
    peerDecision = authorizeBrokerPeer(peerExpectation, request.observedPeer);
  } catch {
    return { compatible: false, code: "PEER_MISMATCH" };
  }
  if (
    peerExpectation.ownerUid !== request.expectedProtectedOwnerUid
    || peerExpectation.expectedBrokerServiceUid !== parsedIdentity.protectedServiceUid
    || peerExpectation.expectedBrokerProcessId !== parsedIdentity.processId
    || !peerDecision.allowed
  ) return { compatible: false, code: peerDecision.allowed ? "PEER_MISMATCH" : peerDecision.code === "KERNEL_PEER_CREDENTIALS_REQUIRED" ? "PEER_CREDENTIALS_MISSING" : "PEER_MISMATCH" };
  return { compatible: true, mode: "boss" };
}

export interface BrokerProviderAttestation {
  version: typeof BROKER_PROVIDER_ATTESTATION_VERSION;
  providerPackage: string;
  providerVersion: string;
  providerDigest: string;
  artifactPath: string;
  artifactOwnerUid: number;
  artifactOwnerGid: number;
  artifactMode: string;
  userWritable: false;
  attestedAt: string;
  attestationKeyId: string;
  signature: string;
}

export type BrokerPublicKey = KeyObject | string;
export type BrokerPublicKeyTrustStore = Readonly<Record<string, BrokerPublicKey | undefined>>;

function resolveTrustedPublicKey(trustStore: BrokerPublicKeyTrustStore, keyId: string): BrokerPublicKey | undefined {
  if (typeof trustStore !== "object" || trustStore === null) return undefined;
  const descriptor = Object.getOwnPropertyDescriptor(trustStore, keyId);
  return descriptor !== undefined && descriptor.enumerable && Object.hasOwn(descriptor, "value")
    ? descriptor.value as BrokerPublicKey | undefined
    : undefined;
}

function missingSignatureFields(
  value: unknown,
  keyIdField: "attestationKeyId" | "identityKeyId",
): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return true;
  try {
    const projected = projectOwnEnumerableDataRecord(value, "$");
    return typeof projected[keyIdField] !== "string"
      || projected[keyIdField].length === 0
      || typeof projected.signature !== "string"
      || projected.signature.length === 0;
  } catch {
    return false;
  }
}

function signingPayload(value: unknown, signatureField: "signature"): Record<string, unknown> {
  assertRecord(value);
  const payload: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(value)) {
    if (key !== signatureField) payload[key] = entry;
  }
  return payload;
}

function canonicalSignatureBytes(domain: string, value: unknown): Uint8Array {
  return canonicalFrame(domain, signingPayload(value, "signature"));
}

function hasCanonicalEd25519Signature(value: string): boolean {
  try {
    const bytes = Buffer.from(value, "base64");
    return bytes.byteLength === 64 && bytes.toString("base64") === value;
  } catch {
    return false;
  }
}

function verifyCanonicalEd25519Signature(domain: string, value: unknown, signature: string, publicKey: BrokerPublicKey): boolean {
  if (!hasCanonicalEd25519Signature(signature)) return false;
  try {
    const key = typeof publicKey === "string" ? createPublicKey(publicKey) : publicKey;
    return verifySignature(null, canonicalSignatureBytes(domain, value), key, Buffer.from(signature, "base64"));
  } catch {
    return false;
  }
}

export function brokerProviderAttestationSigningBytes(value: unknown): Uint8Array {
  return canonicalSignatureBytes(BROKER_PROVIDER_ATTESTATION_SIGNATURE_DOMAIN, value);
}

export function parseBrokerProviderAttestation(value: unknown): BrokerProviderAttestation {
  assertRecord(value);
  assertExactKeys(value, ["version", "providerPackage", "providerVersion", "providerDigest", "artifactPath", "artifactOwnerUid", "artifactOwnerGid", "artifactMode", "userWritable", "attestedAt", "attestationKeyId", "signature"]);
  if (value.version !== BROKER_PROVIDER_ATTESTATION_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  if (value.userWritable !== false) throw new ContractValidationError("$.userWritable", "must be false for a protected provider artifact");
  const artifactPath = readString(value.artifactPath, "$.artifactPath");
  if (
    !artifactPath.startsWith(BROKER_PROTECTED_PROVIDER_ROOT)
    || artifactPath.length === BROKER_PROTECTED_PROVIDER_ROOT.length
    || artifactPath.slice(BROKER_PROTECTED_PROVIDER_ROOT.length).split("/").includes("..")
  ) throw new ContractValidationError("$.artifactPath", `must be beneath ${BROKER_PROTECTED_PROVIDER_ROOT}`);
  const artifactOwnerUid = readInteger(value.artifactOwnerUid, "$.artifactOwnerUid");
  const artifactOwnerGid = readInteger(value.artifactOwnerGid, "$.artifactOwnerGid");
  if (artifactOwnerUid !== 0 || artifactOwnerGid !== 0) throw new ContractValidationError("$.artifactOwnerUid", "protected provider artifacts must be owned by root:root");
  const artifactMode = readString(value.artifactMode, "$.artifactMode");
  if (!/^0[0-7]{3}$/.test(artifactMode) || (Number.parseInt(artifactMode, 8) & 0o022) !== 0) {
    throw new ContractValidationError("$.artifactMode", "must be a canonical four-digit mode with no group/other write permission");
  }
  return {
    version: BROKER_PROVIDER_ATTESTATION_VERSION,
    providerPackage: readString(value.providerPackage, "$.providerPackage"),
    providerVersion: readString(value.providerVersion, "$.providerVersion"),
    providerDigest: readHexDigest(value.providerDigest, "$.providerDigest"),
    artifactPath,
    artifactOwnerUid,
    artifactOwnerGid,
    artifactMode,
    userWritable: false,
    attestedAt: readTimestamp(value.attestedAt, "$.attestedAt"),
    attestationKeyId: readString(value.attestationKeyId, "$.attestationKeyId"),
    signature: readString(value.signature, "$.signature"),
  };
}

export interface BrokerProviderVerificationContext {
  expectedProviderPackage: string;
  expectedProviderVersion: string;
  expectedProviderDigest: string;
  expectedArtifactRoot: string;
  expectedArtifactOwnerUid: number;
  expectedArtifactOwnerGid: number;
  expectedArtifactMode: string;
  trustedProviderKeys: BrokerPublicKeyTrustStore;
}

function parseBrokerProviderVerificationContext(value: unknown): BrokerProviderVerificationContext {
  const path = "$.verificationContext";
  const projected = projectExactOwnEnumerableDataRecord(value, [
    "expectedProviderPackage",
    "expectedProviderVersion",
    "expectedProviderDigest",
    "expectedArtifactRoot",
    "expectedArtifactOwnerUid",
    "expectedArtifactOwnerGid",
    "expectedArtifactMode",
    "trustedProviderKeys",
  ], [], path);
  return {
    expectedProviderPackage: readString(projected.expectedProviderPackage, `${path}.expectedProviderPackage`),
    expectedProviderVersion: readString(projected.expectedProviderVersion, `${path}.expectedProviderVersion`),
    expectedProviderDigest: readHexDigest(projected.expectedProviderDigest, `${path}.expectedProviderDigest`),
    expectedArtifactRoot: readString(projected.expectedArtifactRoot, `${path}.expectedArtifactRoot`),
    expectedArtifactOwnerUid: readInteger(projected.expectedArtifactOwnerUid, `${path}.expectedArtifactOwnerUid`),
    expectedArtifactOwnerGid: readInteger(projected.expectedArtifactOwnerGid, `${path}.expectedArtifactOwnerGid`),
    expectedArtifactMode: readString(projected.expectedArtifactMode, `${path}.expectedArtifactMode`),
    trustedProviderKeys: parseBrokerPublicKeyTrustStore(projected.trustedProviderKeys, `${path}.trustedProviderKeys`),
  };
}

export type BrokerProviderVerificationDecision =
  | { accepted: true }
  | {
      accepted: false;
      code: "PROVIDER_ATTESTATION_UNSIGNED" | "PROVIDER_KEY_UNKNOWN" | "PROVIDER_SIGNATURE_INVALID" | "PROVIDER_MISMATCH" | "PROVIDER_ARTIFACT_MISMATCH";
    };

export function verifyBrokerProviderAttestation(
  attestationValue: unknown,
  contextValue: BrokerProviderVerificationContext,
): BrokerProviderVerificationDecision {
  let attestation: BrokerProviderAttestation;
  try {
    attestation = parseBrokerProviderAttestation(attestationValue);
  } catch {
    return { accepted: false, code: missingSignatureFields(attestationValue, "attestationKeyId")
      ? "PROVIDER_ATTESTATION_UNSIGNED"
      : "PROVIDER_SIGNATURE_INVALID" };
  }
  let context: BrokerProviderVerificationContext;
  try {
    context = parseBrokerProviderVerificationContext(contextValue);
  } catch (error) {
    return { accepted: false, code: error instanceof ContractValidationError && error.path.includes("trustedProviderKeys")
      ? "PROVIDER_KEY_UNKNOWN"
      : "PROVIDER_SIGNATURE_INVALID" };
  }
  const publicKey = resolveTrustedPublicKey(context.trustedProviderKeys, attestation.attestationKeyId);
  if (publicKey === undefined) return { accepted: false, code: "PROVIDER_KEY_UNKNOWN" };
  if (!verifyCanonicalEd25519Signature(BROKER_PROVIDER_ATTESTATION_SIGNATURE_DOMAIN, attestation, attestation.signature, publicKey)) {
    return { accepted: false, code: "PROVIDER_SIGNATURE_INVALID" };
  }
  if (
    attestation.providerPackage !== context.expectedProviderPackage
    || attestation.providerVersion !== context.expectedProviderVersion
    || attestation.providerDigest !== context.expectedProviderDigest
  ) return { accepted: false, code: "PROVIDER_MISMATCH" };
  if (
    context.expectedArtifactRoot !== BROKER_PROTECTED_PROVIDER_ROOT
    || context.expectedArtifactOwnerUid !== 0
    || context.expectedArtifactOwnerGid !== 0
    || !/^0[0-7]{3}$/.test(context.expectedArtifactMode)
    || (Number.parseInt(context.expectedArtifactMode, 8) & 0o022) !== 0
    || !attestation.artifactPath.startsWith(context.expectedArtifactRoot)
    || attestation.artifactOwnerUid !== context.expectedArtifactOwnerUid
    || attestation.artifactOwnerGid !== context.expectedArtifactOwnerGid
    || attestation.artifactMode !== context.expectedArtifactMode
  ) return { accepted: false, code: "PROVIDER_ARTIFACT_MISMATCH" };
  return { accepted: true };
}

export interface BrokerIdentityRecord {
  version: typeof BROKER_IDENTITY_RECORD_VERSION;
  owningProviderPackage: string;
  providerDigest: string;
  providerVersion: string;
  baseProtocolVersion: number;
  features: BrokerFeatureAttestation[];
  protocolFeatureContractHash: string;
  featureSetHash: string;
  controlEnvelopeVersion: number;
  capabilityDigest: string;
  protectedServiceUid: number;
  ownerUid: number;
  bootInstance: string;
  processId: number;
  brokerGeneration: BrokerGeneration;
  publicEndpoint: string;
  authorityEndpoint: string;
  identityKeyId: string;
  signature: string;
}

export function parseBrokerIdentityRecord(value: unknown): BrokerIdentityRecord {
  assertRecord(value);
  assertExactKeys(value, ["version", "owningProviderPackage", "providerDigest", "providerVersion", "baseProtocolVersion", "features", "protocolFeatureContractHash", "featureSetHash", "controlEnvelopeVersion", "capabilityDigest", "protectedServiceUid", "ownerUid", "bootInstance", "processId", "brokerGeneration", "publicEndpoint", "authorityEndpoint", "identityKeyId", "signature"]);
  if (value.version !== BROKER_IDENTITY_RECORD_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  if (!Array.isArray(value.features)) throw new ContractValidationError("$.features", "must be an array");
  const features = parseBrokerFeatureSet(value.features, "$.features");
  const ownerUid = readInteger(value.ownerUid, "$.ownerUid");
  const baseProtocolVersion = readInteger(value.baseProtocolVersion, "$.baseProtocolVersion", 1);
  if (baseProtocolVersion !== INTERCOM_BASE_PROTOCOL_VERSION) {
    throw new ContractValidationError(
      "$.baseProtocolVersion",
      `protected Boss broker identities require base protocol version ${INTERCOM_BASE_PROTOCOL_VERSION}`,
    );
  }
  const publicEndpoint = readString(value.publicEndpoint, "$.publicEndpoint");
  const authorityEndpoint = readString(value.authorityEndpoint, "$.authorityEndpoint");
  if (!publicEndpoint.startsWith("/") || !authorityEndpoint.startsWith("/")) throw new ContractValidationError("$.publicEndpoint", "broker endpoints must be absolute");
  if (publicEndpoint === authorityEndpoint) throw new ContractValidationError("$.authorityEndpoint", "must be distinct from publicEndpoint");
  const protocolFeatureContractHash = readHexDigest(value.protocolFeatureContractHash, "$.protocolFeatureContractHash");
  const featureSetHash = readHexDigest(value.featureSetHash, "$.featureSetHash");
  const controlEnvelopeVersion = readInteger(value.controlEnvelopeVersion, "$.controlEnvelopeVersion", 1);
  const capabilityDigest = readHexDigest(value.capabilityDigest, "$.capabilityDigest");
  if (featureSetHash !== brokerFeatureSetHash(features)) {
    throw new ContractValidationError("$.featureSetHash", "does not hash the complete identity feature set");
  }
  if (!features.some((feature) => feature.feature === BOSS_RUN_FEATURE)) {
    throw new ContractValidationError("$.features", `protected broker identity must carry ${BOSS_RUN_FEATURE}`);
  }
  if (protocolFeatureContractHash !== BOSS_RUN_PROTOCOL_FEATURE_CONTRACT_HASH) {
    throw new ContractValidationError("$.protocolFeatureContractHash", "diverges from the canonical Boss protocol feature contract");
  }
  if (controlEnvelopeVersion !== BOSS_CONTROL_ENVELOPE_VERSION) {
    throw new ContractValidationError("$.controlEnvelopeVersion", "diverges from the canonical Boss control envelope version");
  }
  if (capabilityDigest !== BOSS_CAPABILITY_FEATURE_DIGEST) {
    throw new ContractValidationError("$.capabilityDigest", "diverges from the canonical Boss capability contract");
  }
  return {
    version: BROKER_IDENTITY_RECORD_VERSION,
    owningProviderPackage: readString(value.owningProviderPackage, "$.owningProviderPackage"),
    providerDigest: readHexDigest(value.providerDigest, "$.providerDigest"),
    providerVersion: readString(value.providerVersion, "$.providerVersion"),
    baseProtocolVersion,
    features,
    protocolFeatureContractHash,
    featureSetHash,
    controlEnvelopeVersion,
    capabilityDigest,
    protectedServiceUid: readInteger(value.protectedServiceUid, "$.protectedServiceUid"),
    ownerUid,
    bootInstance: readString(value.bootInstance, "$.bootInstance"),
    processId: readInteger(value.processId, "$.processId", 1),
    brokerGeneration: brokerGeneration(value.brokerGeneration, "$.brokerGeneration"),
    publicEndpoint,
    authorityEndpoint,
    identityKeyId: readString(value.identityKeyId, "$.identityKeyId"),
    signature: readString(value.signature, "$.signature"),
  };
}

export function brokerIdentitySigningBytes(value: unknown): Uint8Array {
  return canonicalSignatureBytes(BROKER_IDENTITY_SIGNATURE_DOMAIN, value);
}

export interface BrokerPeerExpectation {
  version: typeof BROKER_PEER_EXPECTATION_VERSION;
  endpointClass: "public" | "authority";
  ownerUid: number;
  expectedBrokerServiceUid: number;
  expectedBrokerProcessId: number;
  expectedClientUid: number;
  expectedControllerUid?: number;
  requiresKernelPeerCredentials: true;
  requiresServiceCapability: boolean;
}

export function parseBrokerPeerExpectation(value: unknown): BrokerPeerExpectation {
  assertRecord(value);
  assertExactKeys(value, ["version", "endpointClass", "ownerUid", "expectedBrokerServiceUid", "expectedBrokerProcessId", "expectedClientUid", "requiresKernelPeerCredentials", "requiresServiceCapability"], ["expectedControllerUid"]);
  if (value.version !== BROKER_PEER_EXPECTATION_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  const endpointClass = readEnum(value.endpointClass, ["public", "authority"] as const, "$.endpointClass");
  if (value.requiresKernelPeerCredentials !== true) throw new ContractValidationError("$.requiresKernelPeerCredentials", "must be true");
  if (typeof value.requiresServiceCapability !== "boolean") throw new ContractValidationError("$.requiresServiceCapability", "must be boolean");
  if ((endpointClass === "authority") !== value.requiresServiceCapability) {
    throw new ContractValidationError("$.requiresServiceCapability", "is required exactly for the authority endpoint");
  }
  const ownerUid = readInteger(value.ownerUid, "$.ownerUid");
  const expectedBrokerServiceUid = readInteger(value.expectedBrokerServiceUid, "$.expectedBrokerServiceUid");
  const expectedBrokerProcessId = readInteger(value.expectedBrokerProcessId, "$.expectedBrokerProcessId", 1);
  const expectedClientUid = readInteger(value.expectedClientUid, "$.expectedClientUid");
  const expectedControllerUid = value.expectedControllerUid === undefined
    ? undefined
    : readInteger(value.expectedControllerUid, "$.expectedControllerUid");
  if (expectedBrokerServiceUid === ownerUid) throw new ContractValidationError("$.expectedBrokerServiceUid", "protected broker service uid must be distinct from owner uid");
  if (endpointClass === "public" && (expectedClientUid !== ownerUid || expectedControllerUid !== undefined)) {
    throw new ContractValidationError("$.expectedClientUid", "public endpoint requires the owner uid and forbids Controller identity");
  }
  if (endpointClass === "authority" && (
    expectedControllerUid === undefined
    || expectedClientUid !== expectedControllerUid
    || expectedControllerUid === ownerUid
    || expectedControllerUid === expectedBrokerServiceUid
  )) throw new ContractValidationError("$.expectedControllerUid", "authority endpoint requires a distinct Controller uid");
  return {
    version: BROKER_PEER_EXPECTATION_VERSION,
    endpointClass,
    ownerUid,
    expectedBrokerServiceUid,
    expectedBrokerProcessId,
    expectedClientUid,
    ...(expectedControllerUid === undefined ? {} : { expectedControllerUid }),
    requiresKernelPeerCredentials: true,
    requiresServiceCapability: value.requiresServiceCapability,
  };
}

export interface ObservedBrokerPeer {
  kernelPeerCredentialsPresent: boolean;
  endpointClass: "public" | "authority";
  brokerServiceUid: number;
  brokerProcessId: number;
  clientUid: number;
  serviceCapabilityPresented: boolean;
}

export function parseObservedBrokerPeer(value: unknown): ObservedBrokerPeer {
  assertRecord(value);
  assertExactKeys(value, ["kernelPeerCredentialsPresent", "endpointClass", "brokerServiceUid", "brokerProcessId", "clientUid", "serviceCapabilityPresented"]);
  if (typeof value.kernelPeerCredentialsPresent !== "boolean") throw new ContractValidationError("$.kernelPeerCredentialsPresent", "must be boolean");
  if (typeof value.serviceCapabilityPresented !== "boolean") throw new ContractValidationError("$.serviceCapabilityPresented", "must be boolean");
  return {
    kernelPeerCredentialsPresent: value.kernelPeerCredentialsPresent,
    endpointClass: readEnum(value.endpointClass, ["public", "authority"] as const, "$.endpointClass"),
    brokerServiceUid: readInteger(value.brokerServiceUid, "$.brokerServiceUid"),
    brokerProcessId: readInteger(value.brokerProcessId, "$.brokerProcessId", 1),
    clientUid: readInteger(value.clientUid, "$.clientUid"),
    serviceCapabilityPresented: value.serviceCapabilityPresented,
  };
}

export type BrokerPeerDecision =
  | { allowed: true }
  | { allowed: false; code: "KERNEL_PEER_CREDENTIALS_REQUIRED" | "ENDPOINT_CLASS_MISMATCH" | "BROKER_UID_MISMATCH" | "BROKER_PID_MISMATCH" | "CLIENT_UID_MISMATCH" | "SERVICE_CAPABILITY_REQUIRED" | "UNEXPECTED_SERVICE_CAPABILITY" };

export function authorizeBrokerPeer(expectationValue: unknown, observedValue: unknown): BrokerPeerDecision {
  const expectation = parseBrokerPeerExpectation(expectationValue);
  let observed: ObservedBrokerPeer;
  try {
    observed = parseObservedBrokerPeer(observedValue);
  } catch {
    return { allowed: false, code: "KERNEL_PEER_CREDENTIALS_REQUIRED" };
  }
  if (!observed.kernelPeerCredentialsPresent) return { allowed: false, code: "KERNEL_PEER_CREDENTIALS_REQUIRED" };
  if (observed.endpointClass !== expectation.endpointClass) return { allowed: false, code: "ENDPOINT_CLASS_MISMATCH" };
  if (observed.brokerServiceUid !== expectation.expectedBrokerServiceUid) return { allowed: false, code: "BROKER_UID_MISMATCH" };
  if (observed.brokerProcessId !== expectation.expectedBrokerProcessId) return { allowed: false, code: "BROKER_PID_MISMATCH" };
  if (observed.clientUid !== expectation.expectedClientUid) return { allowed: false, code: "CLIENT_UID_MISMATCH" };
  if (expectation.requiresServiceCapability && !observed.serviceCapabilityPresented) {
    return { allowed: false, code: "SERVICE_CAPABILITY_REQUIRED" };
  }
  if (!expectation.requiresServiceCapability && observed.serviceCapabilityPresented) {
    return { allowed: false, code: "UNEXPECTED_SERVICE_CAPABILITY" };
  }
  return { allowed: true };
}

export interface BrokerIdentityVerificationContext {
  expectedProviderPackage: string;
  expectedProviderVersion: string;
  expectedProviderDigest: string;
  expectedProviderArtifactRoot: string;
  expectedProviderArtifactOwnerUid: number;
  expectedProviderArtifactOwnerGid: number;
  expectedProviderArtifactMode: string;
  expectedOwnerUid: number;
  expectedBrokerServiceUid: number;
  expectedBootInstance: string;
  minimumBrokerGeneration: BrokerGeneration;
  expectedPublicEndpoint: string;
  expectedAuthorityEndpoint: string;
  trustedIdentityKeys: BrokerPublicKeyTrustStore;
  trustedProviderKeys: BrokerPublicKeyTrustStore;
  providerAttestation?: unknown;
}

export type BrokerIdentityVerificationDecision =
  | { accepted: true }
  | {
      accepted: false;
      code:
        | "IDENTITY_UNSIGNED"
        | "IDENTITY_KEY_UNKNOWN"
        | "IDENTITY_SIGNATURE_INVALID"
        | "IDENTITY_RECORD_INVALID"
        | "PROVIDER_ATTESTATION_REQUIRED"
        | "PROVIDER_ATTESTATION_UNSIGNED"
        | "PROVIDER_KEY_UNKNOWN"
        | "PROVIDER_SIGNATURE_INVALID"
        | "PROVIDER_MISMATCH"
        | "PROVIDER_ARTIFACT_MISMATCH"
        | "OWNER_UID_MISMATCH"
        | "PROTECTED_SERVICE_MISMATCH"
        | "STALE_BOOT_INSTANCE"
        | "REGRESSED_BROKER_GENERATION"
        | "ENDPOINT_MISMATCH";
    };

export function verifyProtectedBrokerIdentity(
  identityValue: unknown,
  contextValue: BrokerIdentityVerificationContext,
): BrokerIdentityVerificationDecision {
  let identity: BrokerIdentityRecord;
  try {
    identity = parseBrokerIdentityRecord(identityValue);
  } catch {
    return { accepted: false, code: missingSignatureFields(identityValue, "identityKeyId")
      ? "IDENTITY_UNSIGNED"
      : "IDENTITY_RECORD_INVALID" };
  }
  let context: BrokerIdentityVerificationContext;
  try {
    context = parseBrokerIdentityVerificationContext(contextValue, false, false);
  } catch (error) {
    if (error instanceof ContractValidationError && error.path.includes("trustedIdentityKeys")) {
      return { accepted: false, code: "IDENTITY_KEY_UNKNOWN" };
    }
    if (error instanceof ContractValidationError && error.path.includes("trustedProviderKeys")) {
      return { accepted: false, code: "PROVIDER_KEY_UNKNOWN" };
    }
    return { accepted: false, code: "IDENTITY_RECORD_INVALID" };
  }
  const identityPublicKey = resolveTrustedPublicKey(context.trustedIdentityKeys, identity.identityKeyId);
  if (identityPublicKey === undefined) return { accepted: false, code: "IDENTITY_KEY_UNKNOWN" };
  if (!verifyCanonicalEd25519Signature(BROKER_IDENTITY_SIGNATURE_DOMAIN, identity, identity.signature, identityPublicKey)) {
    return { accepted: false, code: "IDENTITY_SIGNATURE_INVALID" };
  }
  if (context.providerAttestation === undefined) return { accepted: false, code: "PROVIDER_ATTESTATION_REQUIRED" };
  const providerDecision = verifyBrokerProviderAttestation(context.providerAttestation, {
    expectedProviderPackage: context.expectedProviderPackage,
    expectedProviderVersion: context.expectedProviderVersion,
    expectedProviderDigest: context.expectedProviderDigest,
    expectedArtifactRoot: context.expectedProviderArtifactRoot,
    expectedArtifactOwnerUid: context.expectedProviderArtifactOwnerUid,
    expectedArtifactOwnerGid: context.expectedProviderArtifactOwnerGid,
    expectedArtifactMode: context.expectedProviderArtifactMode,
    trustedProviderKeys: context.trustedProviderKeys,
  });
  if (!providerDecision.accepted) return providerDecision;
  if (
    identity.owningProviderPackage !== context.expectedProviderPackage
    || identity.providerVersion !== context.expectedProviderVersion
    || identity.providerDigest !== context.expectedProviderDigest
  ) {
    return { accepted: false, code: "PROVIDER_MISMATCH" };
  }
  if (identity.ownerUid !== context.expectedOwnerUid) return { accepted: false, code: "OWNER_UID_MISMATCH" };
  if (identity.protectedServiceUid === identity.ownerUid || identity.protectedServiceUid !== context.expectedBrokerServiceUid) {
    return { accepted: false, code: "PROTECTED_SERVICE_MISMATCH" };
  }
  if (identity.bootInstance !== context.expectedBootInstance) {
    return { accepted: false, code: "STALE_BOOT_INSTANCE" };
  }
  if (identity.brokerGeneration < context.minimumBrokerGeneration) return { accepted: false, code: "REGRESSED_BROKER_GENERATION" };
  const protectedEndpointRoot = `/run/agent-intercom/${context.expectedOwnerUid}`;
  if (
    context.expectedPublicEndpoint !== `${protectedEndpointRoot}/public.sock`
    || context.expectedAuthorityEndpoint !== `${protectedEndpointRoot}/authority.sock`
    || identity.publicEndpoint !== context.expectedPublicEndpoint
    || identity.authorityEndpoint !== context.expectedAuthorityEndpoint
  ) {
    return { accepted: false, code: "ENDPOINT_MISMATCH" };
  }
  return { accepted: true };
}

export interface LegacyAdminMigrationRecord {
  version: typeof LEGACY_ADMIN_MIGRATION_VERSION;
  ownerUid: number;
  legacyAdminDigest: string;
  remoteAccessRegistrationsImported: number;
  remoteAccessSemanticsVersion: 2;
  legacyAdminState: "revoked_and_removed";
  compatibilityProxyMode: "ordinary_data_only";
  bossFeatureAdvertisedByProxy: false;
  protectedRegistryPath: string;
  migratedAt: string;
  auditEventId: string;
}

export function parseLegacyAdminMigrationRecord(value: unknown): LegacyAdminMigrationRecord {
  assertRecord(value);
  assertExactKeys(value, ["version", "ownerUid", "legacyAdminDigest", "remoteAccessRegistrationsImported", "remoteAccessSemanticsVersion", "legacyAdminState", "compatibilityProxyMode", "bossFeatureAdvertisedByProxy", "protectedRegistryPath", "migratedAt", "auditEventId"]);
  if (value.version !== LEGACY_ADMIN_MIGRATION_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  if (value.remoteAccessSemanticsVersion !== 2) throw new ContractValidationError("$.remoteAccessSemanticsVersion", "must preserve remote-access-v1 semantics v2");
  if (value.legacyAdminState !== "revoked_and_removed" || value.compatibilityProxyMode !== "ordinary_data_only" || value.bossFeatureAdvertisedByProxy !== false) {
    throw new ContractValidationError("$", "legacy proxy must be ordinary-only and the old admin credential must be revoked and removed");
  }
  const ownerUid = readInteger(value.ownerUid, "$.ownerUid");
  const protectedRegistryPath = readString(value.protectedRegistryPath, "$.protectedRegistryPath");
  const protectedOwnerRoot = `/var/lib/agent-intercom/brokers/${ownerUid}`;
  const relativeRegistryPath = posixPath.relative(protectedOwnerRoot, protectedRegistryPath);
  if (
    !posixPath.isAbsolute(protectedRegistryPath)
    || protectedRegistryPath !== posixPath.normalize(protectedRegistryPath)
    || protectedRegistryPath.includes("\\")
    || protectedRegistryPath.includes("\0")
    || protectedRegistryPath.endsWith("/")
    || relativeRegistryPath.length === 0
    || relativeRegistryPath === ".."
    || relativeRegistryPath.startsWith("../")
    || posixPath.isAbsolute(relativeRegistryPath)
    || !protectedRegistryPath.startsWith(`${protectedOwnerRoot}/`)
  ) {
    throw new ContractValidationError("$.protectedRegistryPath", "must be a canonical path strictly contained under the exact protected per-owner broker state root");
  }
  return {
    version: LEGACY_ADMIN_MIGRATION_VERSION,
    ownerUid,
    legacyAdminDigest: readHexDigest(value.legacyAdminDigest, "$.legacyAdminDigest"),
    remoteAccessRegistrationsImported: readInteger(value.remoteAccessRegistrationsImported, "$.remoteAccessRegistrationsImported"),
    remoteAccessSemanticsVersion: 2,
    legacyAdminState: "revoked_and_removed",
    compatibilityProxyMode: "ordinary_data_only",
    bossFeatureAdvertisedByProxy: false,
    protectedRegistryPath,
    migratedAt: readTimestamp(value.migratedAt, "$.migratedAt"),
    auditEventId: readString(value.auditEventId, "$.auditEventId"),
  };
}

export interface BrokerJournalRecoveryRecord {
  version: typeof BROKER_JOURNAL_RECOVERY_VERSION;
  providerDigest: string;
  bootInstance: string;
  brokerGeneration: BrokerGeneration;
  committedBrokerRevision: BrokerRevision;
  recoveredAuthorityTransitionIds: string[];
  state: "reconciled" | "quarantined";
  reason?: string;
  recoveredAt: string;
}

export function parseBrokerJournalRecoveryRecord(value: unknown): BrokerJournalRecoveryRecord {
  assertRecord(value);
  assertExactKeys(value, ["version", "providerDigest", "bootInstance", "brokerGeneration", "committedBrokerRevision", "recoveredAuthorityTransitionIds", "state", "recoveredAt"], ["reason"]);
  if (value.version !== BROKER_JOURNAL_RECOVERY_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  const recoveredAuthorityTransitionIds = readStringArray(value.recoveredAuthorityTransitionIds, "$.recoveredAuthorityTransitionIds");
  if (new Set(recoveredAuthorityTransitionIds).size !== recoveredAuthorityTransitionIds.length) {
    throw new ContractValidationError("$.recoveredAuthorityTransitionIds", "must not contain duplicates");
  }
  const state = readEnum(value.state, ["reconciled", "quarantined"] as const, "$.state");
  const reason = value.reason === undefined ? undefined : readString(value.reason, "$.reason");
  if ((state === "quarantined") !== (reason !== undefined)) {
    throw new ContractValidationError("$.reason", "is required exactly for quarantined recovery");
  }
  return {
    version: BROKER_JOURNAL_RECOVERY_VERSION,
    providerDigest: readHexDigest(value.providerDigest, "$.providerDigest"),
    bootInstance: readString(value.bootInstance, "$.bootInstance"),
    brokerGeneration: brokerGeneration(value.brokerGeneration, "$.brokerGeneration"),
    committedBrokerRevision: brokerRevision(value.committedBrokerRevision, "$.committedBrokerRevision"),
    recoveredAuthorityTransitionIds,
    state,
    ...(reason === undefined ? {} : { reason }),
    recoveredAt: readTimestamp(value.recoveredAt, "$.recoveredAt"),
  };
}

export const BOSS_MANAGER_OPERATIONS = [
  "manager_get_status", "manager_request_staff", "manager_create_assignment", "manager_cancel_assignment",
  "manager_create_subscription", "manager_list_subscriptions", "manager_cancel_subscription", "manager_submit_checkpoint",
  "manager_report_blocker", "manager_submit_proof", "manager_request_adversary_review", "manager_request_council",
] as const;
export type BossManagerOperation = (typeof BOSS_MANAGER_OPERATIONS)[number];
export const BOSS_PARTICIPANT_OPERATIONS = [
  "participant_accept_assignment", "participant_reject_assignment", "participant_submit_checkpoint",
  "participant_submit_assignment", "participant_report_blocker", "participant_report_health",
] as const;
export type BossParticipantOperation = (typeof BOSS_PARTICIPANT_OPERATIONS)[number];
export const BOSS_REVIEWER_OPERATIONS = [
  "reviewer_get_proof", "reviewer_submit_review", "reviewer_submit_proof", "reviewer_get_objection_status", "reviewer_report_health",
] as const;
export type BossReviewerOperation = (typeof BOSS_REVIEWER_OPERATIONS)[number];

export type BossRestrictedClient = "boss_manager" | "boss_participant" | "boss_reviewer";
export type BossRestrictedOperation = BossManagerOperation | BossParticipantOperation | BossReviewerOperation;

export interface BossCheckpointPayload {
  assignmentId: string;
  checkpointId: string;
  summary: string;
  occurredAt: string;
}

export interface BossHealthPayload {
  state: ParticipantState;
  severity: "info" | "warning" | "error" | "critical";
  observedAt: string;
}

export interface BossRestrictedRequestPayloadByOperation {
  manager_get_status: Record<string, never>;
  manager_request_staff: { role: "scout" | "worker"; count: number };
  manager_create_assignment: { assignmentId: string; participantId: string; objective: string };
  manager_cancel_assignment: { assignmentId: string; reason: string };
  manager_create_subscription: LifecycleSubscriptionRecord;
  manager_list_subscriptions: Record<string, never>;
  manager_cancel_subscription: { subscriptionId: string };
  manager_submit_checkpoint: BossCheckpointPayload;
  manager_report_blocker: { blockerId: string; reason: string };
  manager_submit_proof: { proofId: string; digest: string };
  manager_request_adversary_review: { proofId: string };
  manager_request_council: { question: string };
  participant_accept_assignment: { assignmentId: string };
  participant_reject_assignment: { assignmentId: string; reason: string };
  participant_submit_checkpoint: BossCheckpointPayload;
  participant_submit_assignment: { assignmentId: string; resultDigest: string };
  participant_report_blocker: { assignmentId: string; reason: string };
  participant_report_health: BossHealthPayload;
  reviewer_get_proof: { proofId: string };
  reviewer_submit_review: { reviewId: string; proofId: string; decision: "approved" | "changes_requested" | "rejected"; reason: string };
  reviewer_submit_proof: { proofId: string; digest: string };
  reviewer_get_objection_status: { reviewId: string };
  reviewer_report_health: BossHealthPayload;
}

export interface BossRestrictedResultPayloadByOperation {
  manager_get_status: { status: string };
  manager_request_staff: { staffRequestId: string };
  manager_create_assignment: { assignmentId: string };
  manager_cancel_assignment: { assignmentId: string };
  manager_create_subscription: { subscriptionId: string };
  manager_list_subscriptions: { subscriptionIds: string[] };
  manager_cancel_subscription: { subscriptionId: string };
  manager_submit_checkpoint: { assignmentId: string; checkpointId: string; recordedAt: string };
  manager_report_blocker: { blockerId: string };
  manager_submit_proof: { proofId: string };
  manager_request_adversary_review: { reviewId: string };
  manager_request_council: Record<string, never>;
  participant_accept_assignment: { assignmentId: string };
  participant_reject_assignment: { assignmentId: string };
  participant_submit_checkpoint: { assignmentId: string; checkpointId: string; recordedAt: string };
  participant_submit_assignment: { assignmentId: string };
  participant_report_blocker: { blockerId: string };
  participant_report_health: { healthEventId: string };
  reviewer_get_proof: { proofId: string; digest: string };
  reviewer_submit_review: { reviewId: string };
  reviewer_submit_proof: { proofId: string };
  reviewer_get_objection_status: { reviewId: string; status: string };
  reviewer_report_health: { healthEventId: string };
}

interface RestrictedRequestBase {
  version: typeof BOSS_RESTRICTED_CLIENT_REQUEST_VERSION;
  bossRunId: string;
  bindingEpoch: ParticipantBindingEpoch;
  requestId: string;
  idempotencyKey: string;
}

type ManagerRequestFor<Operation extends BossManagerOperation> = RestrictedRequestBase & {
  client: "boss_manager";
  managerParticipantId: string;
  operation: Operation;
  payload: BossRestrictedRequestPayloadByOperation[Operation];
};
type ParticipantRequestFor<Operation extends BossParticipantOperation> = RestrictedRequestBase & {
  client: "boss_participant";
  participantId: string;
  operation: Operation;
  payload: BossRestrictedRequestPayloadByOperation[Operation];
};
type ReviewerRequestFor<Operation extends BossReviewerOperation> = RestrictedRequestBase & {
  client: "boss_reviewer";
  participantId: string;
  operation: Operation;
  payload: BossRestrictedRequestPayloadByOperation[Operation];
};
export type BossManagerRequest = { [Operation in BossManagerOperation]: ManagerRequestFor<Operation> }[BossManagerOperation];
export type BossParticipantRequest = { [Operation in BossParticipantOperation]: ParticipantRequestFor<Operation> }[BossParticipantOperation];
export type BossReviewerRequest = { [Operation in BossReviewerOperation]: ReviewerRequestFor<Operation> }[BossReviewerOperation];
export type BossRestrictedClientRequest = BossManagerRequest | BossParticipantRequest | BossReviewerRequest;

type PayloadFieldRule = "string" | "hexDigest" | "integer" | "stringArray" | "timestamp" | "participantState" | readonly string[];

function parseExactPayload(value: unknown, rules: Readonly<Record<string, PayloadFieldRule>>, path = "$.payload"): Record<string, unknown> {
  assertRecord(value, path);
  const keys = Object.keys(rules);
  assertExactKeys(value, keys, [], path);
  const parsed: Record<string, unknown> = {};
  for (const key of keys) {
    const rule = rules[key];
    const fieldPath = `${path}.${key}`;
    if (rule === "string") parsed[key] = readString(value[key], fieldPath);
    else if (rule === "hexDigest") parsed[key] = readHexDigest(value[key], fieldPath);
    else if (rule === "integer") parsed[key] = readInteger(value[key], fieldPath, 1);
    else if (rule === "stringArray") parsed[key] = readStringArray(value[key], fieldPath);
    else if (rule === "timestamp") parsed[key] = readTimestamp(value[key], fieldPath);
    else if (rule === "participantState") parsed[key] = parseParticipantState(value[key], fieldPath);
    else parsed[key] = readEnum(value[key], rule, fieldPath);
  }
  return parsed;
}

function parseLifecycleSubscriptionCreation(value: unknown): LifecycleSubscriptionRecord {
  const subscription = parseLifecycleSubscription(value);
  if (subscription.state !== "armed") {
    throw new ContractValidationError("$.payload.state", "must be armed on creation");
  }
  if (Number(subscription.triggerGeneration) !== 0) {
    throw new ContractValidationError("$.payload.triggerGeneration", "must be zero on creation");
  }
  if (subscription.createdAt !== subscription.updatedAt) {
    throw new ContractValidationError("$.payload.updatedAt", "must equal createdAt on creation");
  }
  for (const field of ["lastActivityAt", "dueAt", "lastSourceEventId"] as const) {
    if (subscription[field] !== undefined) {
      throw new ContractValidationError(`$.payload.${field}`, "must be absent on creation");
    }
  }
  return subscription;
}

function parseRestrictedRequestPayload(operation: BossRestrictedOperation, value: unknown): BossRestrictedRequestPayloadByOperation[BossRestrictedOperation] {
  let parsed: Record<string, unknown>;
  switch (operation) {
    case "manager_get_status":
    case "manager_list_subscriptions":
      parsed = parseExactPayload(value, {});
      break;
    case "manager_request_staff":
      parsed = parseExactPayload(value, { role: ["scout", "worker"], count: "integer" });
      break;
    case "manager_create_assignment":
      parsed = parseExactPayload(value, { assignmentId: "string", participantId: "string", objective: "string" });
      break;
    case "manager_cancel_assignment":
    case "participant_reject_assignment":
      parsed = parseExactPayload(value, { assignmentId: "string", reason: "string" });
      break;
    case "manager_create_subscription":
      parsed = parseLifecycleSubscriptionCreation(value) as unknown as Record<string, unknown>;
      break;
    case "manager_cancel_subscription":
      parsed = parseExactPayload(value, { subscriptionId: "string" });
      break;
    case "manager_submit_checkpoint":
    case "participant_submit_checkpoint":
      parsed = parseExactPayload(value, { assignmentId: "string", checkpointId: "string", summary: "string", occurredAt: "timestamp" });
      break;
    case "manager_report_blocker":
      parsed = parseExactPayload(value, { blockerId: "string", reason: "string" });
      break;
    case "manager_submit_proof":
    case "reviewer_submit_proof":
      parsed = parseExactPayload(value, { proofId: "string", digest: "hexDigest" });
      break;
    case "manager_request_adversary_review":
    case "reviewer_get_proof":
      parsed = parseExactPayload(value, { proofId: "string" });
      break;
    case "manager_request_council":
      parsed = parseExactPayload(value, { question: "string" });
      break;
    case "participant_accept_assignment":
      parsed = parseExactPayload(value, { assignmentId: "string" });
      break;
    case "participant_submit_assignment":
      parsed = parseExactPayload(value, { assignmentId: "string", resultDigest: "hexDigest" });
      break;
    case "participant_report_blocker":
      parsed = parseExactPayload(value, { assignmentId: "string", reason: "string" });
      break;
    case "participant_report_health":
    case "reviewer_report_health":
      parsed = parseExactPayload(value, { state: "participantState", severity: ["info", "warning", "error", "critical"], observedAt: "timestamp" });
      break;
    case "reviewer_submit_review":
      parsed = parseExactPayload(value, { reviewId: "string", proofId: "string", decision: ["approved", "changes_requested", "rejected"], reason: "string" });
      break;
    case "reviewer_get_objection_status":
      parsed = parseExactPayload(value, { reviewId: "string" });
      break;
  }
  return parsed as unknown as BossRestrictedRequestPayloadByOperation[BossRestrictedOperation];
}

function readClientOperation(client: BossRestrictedClient, operationValue: unknown, path: string): BossRestrictedOperation {
  if (client === "boss_manager") return readEnum(operationValue, BOSS_MANAGER_OPERATIONS, path);
  if (client === "boss_participant") return readEnum(operationValue, BOSS_PARTICIPANT_OPERATIONS, path);
  return readEnum(operationValue, BOSS_REVIEWER_OPERATIONS, path);
}

export function parseBossRestrictedClientRequest(value: unknown): BossRestrictedClientRequest {
  assertRecord(value);
  const client = readEnum(value.client, ["boss_manager", "boss_participant", "boss_reviewer"] as const, "$.client");
  const participantField = client === "boss_manager" ? "managerParticipantId" : "participantId";
  assertExactKeys(value, ["version", "client", "bossRunId", participantField, "bindingEpoch", "requestId", "idempotencyKey", "operation", "payload"]);
  if (value.version !== BOSS_RESTRICTED_CLIENT_REQUEST_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  const operation = readClientOperation(client, value.operation, "$.operation");
  const payload = parseRestrictedRequestPayload(operation, value.payload);
  const base = {
    version: BOSS_RESTRICTED_CLIENT_REQUEST_VERSION,
    client,
    bossRunId: readString(value.bossRunId, "$.bossRunId"),
    bindingEpoch: participantBindingEpoch(value.bindingEpoch, "$.bindingEpoch"),
    requestId: readString(value.requestId, "$.requestId"),
    idempotencyKey: readString(value.idempotencyKey, "$.idempotencyKey"),
    operation,
    payload,
  };
  return (client === "boss_manager"
    ? { ...base, client, managerParticipantId: readString(value.managerParticipantId, "$.managerParticipantId") }
    : { ...base, client, participantId: readString(value.participantId, "$.participantId") }) as BossRestrictedClientRequest;
}

function restrictedParticipantId(request: BossRestrictedClientRequest): string {
  return request.client === "boss_manager" ? request.managerParticipantId : request.participantId;
}

export const BOSS_RESTRICTED_AUTHORIZATION_DENIAL_CODES = [
  "UNKNOWN_PRINCIPAL",
  "PRINCIPAL_NOT_ACTIVE",
  "BINDING_NOT_ACTIVE",
  "POLICY_BINDING_MISMATCH",
  "UNAUTHORIZED_ROLE",
  "PARTICIPANT_MISMATCH",
  "STALE_BINDING_EPOCH",
  "CROSS_RUN_REPLAY",
  "MISSING_AUTHORIZATION_EVIDENCE",
  "PAYLOAD_AUTHORIZATION_MISMATCH",
  "REQUEST_ID_CONFLICT",
  "IDEMPOTENCY_CONFLICT",
] as const;
export type BossRestrictedAuthorizationDenialCode = (typeof BOSS_RESTRICTED_AUTHORIZATION_DENIAL_CODES)[number];

export interface BossRestrictedClientIdempotencyRecord {
  scope: string;
  bossRunId: string;
  client: BossRestrictedClient;
  participantId: string;
  bindingEpoch: ParticipantBindingEpoch;
  operation: BossRestrictedOperation;
  requestId: string;
  idempotencyKey: string;
  requestDigest: string;
}

/** Controller-owned assignment identity used only for pure payload authorization. */
export interface BossRestrictedAssignmentAuthorizationRecord {
  bossRunId: string;
  assignmentId: string;
  managerParticipantId: string;
  participantId: string;
}

/** Controller-owned proof ownership and reviewer correlation. */
export interface BossRestrictedProofAuthorizationRecord {
  bossRunId: string;
  proofId: string;
  ownerParticipantId: string;
  reviewerParticipantIds: string[];
}

/** Controller-owned review identity and lifecycle used for submission and objection-status authorization. */
export interface BossRestrictedReviewAuthorizationRecord {
  bossRunId: string;
  reviewId: string;
  proofId: string;
  requesterParticipantId: string;
  reviewerParticipantId: string;
  state: "pending" | "submitted" | "cancelled";
}

/**
 * Controller/Orc authorization for one exact lifecycle target at the current
 * subscriber binding. targetParticipantIds binds Worker IDs and role selectors
 * back to the Manager's authoritative participant assignments.
 */
export interface BossRestrictedSupervisionAuthorizationRecord {
  bossRunId: string;
  subscriberPrincipalId: string;
  subscriberParticipantId: string;
  subscriberBindingEpoch: SubscriberBindingEpoch;
  subscriberBindingGeneration: SubscriberBindingGeneration;
  target: LifecycleTarget;
  targetParticipantIds: string[];
}

export interface BossRestrictedClientAuthorizationContext {
  policy: BossPolicyState;
  principalId: string;
  currentBinding: BossParticipantBinding;
  assignments?: readonly BossRestrictedAssignmentAuthorizationRecord[];
  proofs?: readonly BossRestrictedProofAuthorizationRecord[];
  reviews?: readonly BossRestrictedReviewAuthorizationRecord[];
  supervision?: readonly BossRestrictedSupervisionAuthorizationRecord[];
  subscriptions?: readonly LifecycleSubscriptionRecord[];
  idempotencyRecords?: readonly BossRestrictedClientIdempotencyRecord[];
}

function parseBossRestrictedClientAuthorizationContext(
  value: unknown,
): BossRestrictedClientAuthorizationContext {
  const projected = projectExactOwnEnumerableDataRecord(value, [
    "policy",
    "principalId",
    "currentBinding",
  ], [
    "assignments",
    "proofs",
    "reviews",
    "supervision",
    "subscriptions",
    "idempotencyRecords",
  ], "$.authorizationContext");
  return {
    policy: projected.policy as BossPolicyState,
    principalId: readString(projected.principalId, "$.authorizationContext.principalId"),
    currentBinding: projected.currentBinding as BossParticipantBinding,
    ...(projected.assignments === undefined
      ? {}
      : { assignments: projected.assignments as readonly BossRestrictedAssignmentAuthorizationRecord[] }),
    ...(projected.proofs === undefined
      ? {}
      : { proofs: projected.proofs as readonly BossRestrictedProofAuthorizationRecord[] }),
    ...(projected.reviews === undefined
      ? {}
      : { reviews: projected.reviews as readonly BossRestrictedReviewAuthorizationRecord[] }),
    ...(projected.supervision === undefined
      ? {}
      : { supervision: projected.supervision as readonly BossRestrictedSupervisionAuthorizationRecord[] }),
    ...(projected.subscriptions === undefined
      ? {}
      : { subscriptions: projected.subscriptions as readonly LifecycleSubscriptionRecord[] }),
    ...(projected.idempotencyRecords === undefined
      ? {}
      : { idempotencyRecords: projected.idempotencyRecords as readonly BossRestrictedClientIdempotencyRecord[] }),
  };
}

export type BossRestrictedClientAuthorizationDecision =
  | { allowed: true; idempotency: "new" | "replay"; record: BossRestrictedClientIdempotencyRecord }
  | { allowed: false; code: BossRestrictedAuthorizationDenialCode };

type PayloadAuthorizationDenial = "MISSING_AUTHORIZATION_EVIDENCE" | "PAYLOAD_AUTHORIZATION_MISMATCH";

function parseAssignmentAuthorizationRecord(value: unknown, path: string): BossRestrictedAssignmentAuthorizationRecord {
  assertRecord(value, path);
  assertExactKeys(value, ["bossRunId", "assignmentId", "managerParticipantId", "participantId"], [], path);
  return {
    bossRunId: readString(value.bossRunId, `${path}.bossRunId`),
    assignmentId: readString(value.assignmentId, `${path}.assignmentId`),
    managerParticipantId: readString(value.managerParticipantId, `${path}.managerParticipantId`),
    participantId: readString(value.participantId, `${path}.participantId`),
  };
}

function parseProofAuthorizationRecord(value: unknown, path: string): BossRestrictedProofAuthorizationRecord {
  assertRecord(value, path);
  assertExactKeys(value, ["bossRunId", "proofId", "ownerParticipantId", "reviewerParticipantIds"], [], path);
  const reviewerParticipantIds = readStringArray(value.reviewerParticipantIds, `${path}.reviewerParticipantIds`);
  if (new Set(reviewerParticipantIds).size !== reviewerParticipantIds.length) {
    throw new ContractValidationError(`${path}.reviewerParticipantIds`, "must not contain duplicates");
  }
  return {
    bossRunId: readString(value.bossRunId, `${path}.bossRunId`),
    proofId: readString(value.proofId, `${path}.proofId`),
    ownerParticipantId: readString(value.ownerParticipantId, `${path}.ownerParticipantId`),
    reviewerParticipantIds,
  };
}

function parseReviewAuthorizationRecord(value: unknown, path: string): BossRestrictedReviewAuthorizationRecord {
  assertRecord(value, path);
  assertExactKeys(value, ["bossRunId", "reviewId", "proofId", "requesterParticipantId", "reviewerParticipantId", "state"], [], path);
  return {
    bossRunId: readString(value.bossRunId, `${path}.bossRunId`),
    reviewId: readString(value.reviewId, `${path}.reviewId`),
    proofId: readString(value.proofId, `${path}.proofId`),
    requesterParticipantId: readString(value.requesterParticipantId, `${path}.requesterParticipantId`),
    reviewerParticipantId: readString(value.reviewerParticipantId, `${path}.reviewerParticipantId`),
    state: readEnum(value.state, ["pending", "submitted", "cancelled"] as const, `${path}.state`),
  };
}

function parseSupervisionAuthorizationRecord(value: unknown, path: string): BossRestrictedSupervisionAuthorizationRecord {
  assertRecord(value, path);
  assertExactKeys(value, [
    "bossRunId",
    "subscriberPrincipalId",
    "subscriberParticipantId",
    "subscriberBindingEpoch",
    "subscriberBindingGeneration",
    "target",
    "targetParticipantIds",
  ], [], path);
  const targetParticipantIds = readStringArray(value.targetParticipantIds, `${path}.targetParticipantIds`);
  if (targetParticipantIds.length === 0 || new Set(targetParticipantIds).size !== targetParticipantIds.length) {
    throw new ContractValidationError(`${path}.targetParticipantIds`, "must be non-empty and unique");
  }
  return {
    bossRunId: readString(value.bossRunId, `${path}.bossRunId`),
    subscriberPrincipalId: readString(value.subscriberPrincipalId, `${path}.subscriberPrincipalId`),
    subscriberParticipantId: readString(value.subscriberParticipantId, `${path}.subscriberParticipantId`),
    subscriberBindingEpoch: subscriberBindingEpoch(value.subscriberBindingEpoch, `${path}.subscriberBindingEpoch`),
    subscriberBindingGeneration: subscriberBindingGeneration(value.subscriberBindingGeneration, `${path}.subscriberBindingGeneration`),
    target: parseLifecycleTarget(value.target, `${path}.target`),
    targetParticipantIds,
  };
}

function parseAuthorizationRecordArray<T>(
  value: unknown,
  path: string,
  parse: (entry: unknown, entryPath: string) => T,
): T[] {
  return ownDenseArrayDataValues(value, path).map((entry, index) => parse(entry, `${path}[${index}]`));
}

type OwnEnumerableDataDescriptor = PropertyDescriptor & { value: unknown };

function ownEnumerableDataDescriptor(value: object, key: PropertyKey): OwnEnumerableDataDescriptor | undefined {
  const descriptor = Object.getOwnPropertyDescriptor(value, key);
  return descriptor !== undefined && descriptor.enumerable && Object.hasOwn(descriptor, "value")
    ? descriptor as OwnEnumerableDataDescriptor
    : undefined;
}

function restrictedPolicyPrincipalMap(policy: unknown): Record<string, unknown> | undefined {
  if (typeof policy !== "object" || policy === null || nodeUtilTypes.isProxy(policy)) return undefined;
  try {
    assertRecord(policy, "$.policy");
  } catch {
    return undefined;
  }
  const policyKeys = Reflect.ownKeys(policy);
  if (policyKeys.length !== 1 || policyKeys[0] !== "principals") return undefined;
  const descriptor = ownEnumerableDataDescriptor(policy, "principals");
  if (descriptor === undefined) return undefined;
  if (typeof descriptor.value !== "object" || descriptor.value === null || nodeUtilTypes.isProxy(descriptor.value)) {
    return undefined;
  }
  try {
    assertRecord(descriptor.value, "$.policy.principals");
  } catch {
    return undefined;
  }
  return descriptor.value;
}

function parseActivePolicyPrincipals(context: BossRestrictedClientAuthorizationContext): BossPrivatePrincipal[] | undefined {
  const principalMap = restrictedPolicyPrincipalMap(context.policy);
  if (principalMap === undefined) return undefined;
  const principals: BossPrivatePrincipal[] = [];
  try {
    for (const key of Object.keys(principalMap)) {
      const descriptor = ownEnumerableDataDescriptor(principalMap, key);
      if (descriptor === undefined) return undefined;
      const parsed = parseBossPolicyPrincipal(descriptor.value);
      if (parsed.principalId !== key) return undefined;
      if (parsed.principalClass === "boss-private" && parsed.state === "active") principals.push(parsed);
    }
  } catch {
    return undefined;
  }
  return principals;
}

function assignedTargetPrincipal(
  context: BossRestrictedClientAuthorizationContext,
  manager: BossPrivatePrincipal,
  participantId: string,
): BossPrivatePrincipal | undefined {
  if (manager.role !== "manager" || manager.assignedParticipantIds?.includes(participantId) !== true) return undefined;
  const matches = parseActivePolicyPrincipals(context)?.filter((candidate) => (
    candidate.participantId === participantId
    && candidate.bossRunId === manager.bossRunId
    && (candidate.role === "worker" || candidate.role === "scout")
    && candidate.assignedManagerParticipantId === manager.participantId
  ));
  return matches?.length === 1 ? matches[0] : undefined;
}

function authorizeAssignmentPayload(
  context: BossRestrictedClientAuthorizationContext,
  principal: BossPrivatePrincipal,
  bossRunId: string,
  assignmentId: string,
): PayloadAuthorizationDenial | undefined {
  if (context.assignments === undefined) return "MISSING_AUTHORIZATION_EVIDENCE";
  let assignments: BossRestrictedAssignmentAuthorizationRecord[];
  try {
    assignments = parseAuthorizationRecordArray(context.assignments, "$.assignments", parseAssignmentAuthorizationRecord);
  } catch {
    return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  const matches = assignments.filter((assignment) => assignment.assignmentId === assignmentId);
  if (matches.length === 0) return "MISSING_AUTHORIZATION_EVIDENCE";
  if (matches.length !== 1) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  const assignment = matches[0];
  if (assignment.bossRunId !== bossRunId) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  if (principal.role === "manager") {
    return assignment.managerParticipantId === principal.participantId
      && assignedTargetPrincipal(context, principal, assignment.participantId) !== undefined
      ? undefined
      : "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  return assignment.participantId === principal.participantId
    && assignment.managerParticipantId === principal.assignedManagerParticipantId
    ? undefined
    : "PAYLOAD_AUTHORIZATION_MISMATCH";
}

function sameLifecycleTarget(left: LifecycleTarget, right: LifecycleTarget): boolean {
  return left.kind === "worker" && right.kind === "worker"
    ? left.workerId === right.workerId && left.workerGeneration === right.workerGeneration
    : left.kind === "role" && right.kind === "role"
      ? left.bossRunId === right.bossRunId && left.role === right.role
      : false;
}

function authorizeSupervisionTarget(
  context: BossRestrictedClientAuthorizationContext,
  manager: BossPrivatePrincipal,
  bossRunId: string,
  bindingEpoch: ParticipantBindingEpoch,
  bindingGeneration: SubscriberBindingGeneration,
  target: LifecycleTarget,
): PayloadAuthorizationDenial | undefined {
  if (context.supervision === undefined) return "MISSING_AUTHORIZATION_EVIDENCE";
  let supervision: BossRestrictedSupervisionAuthorizationRecord[];
  try {
    supervision = parseAuthorizationRecordArray(context.supervision, "$.supervision", parseSupervisionAuthorizationRecord);
  } catch {
    return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  const matches = supervision.filter((grant) => (
    grant.bossRunId === bossRunId
    && grant.subscriberPrincipalId === context.principalId
    && grant.subscriberParticipantId === manager.participantId
    && Number(grant.subscriberBindingEpoch) === Number(bindingEpoch)
    && grant.subscriberBindingGeneration === bindingGeneration
    && sameLifecycleTarget(grant.target, target)
  ));
  if (matches.length === 0) return supervision.length === 0
    ? "MISSING_AUTHORIZATION_EVIDENCE"
    : "PAYLOAD_AUTHORIZATION_MISMATCH";
  if (matches.length !== 1) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  const targetParticipantIds = matches[0].targetParticipantIds;
  if (target.kind === "worker" && targetParticipantIds.length !== 1) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  const targetPrincipals = targetParticipantIds.map((participantId) => assignedTargetPrincipal(context, manager, participantId));
  if (targetPrincipals.some((candidate) => candidate === undefined)) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  if (target.kind === "role") {
    if (target.bossRunId !== bossRunId || (target.role !== "worker" && target.role !== "scout")) {
      return "PAYLOAD_AUTHORIZATION_MISMATCH";
    }
    const selected = new Set(targetParticipantIds);
    const assignedRoleParticipants = parseActivePolicyPrincipals(context)?.filter((candidate) => (
      candidate.bossRunId === bossRunId
      && candidate.role === target.role
      && manager.assignedParticipantIds?.includes(candidate.participantId) === true
      && candidate.assignedManagerParticipantId === manager.participantId
    ));
    if (
      assignedRoleParticipants === undefined
      || assignedRoleParticipants.length !== selected.size
      || assignedRoleParticipants.some((candidate) => !selected.has(candidate.participantId))
    ) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  return undefined;
}

function proofAuthorization(
  context: BossRestrictedClientAuthorizationContext,
  proofId: string,
): { proof?: BossRestrictedProofAuthorizationRecord; denial?: PayloadAuthorizationDenial } {
  if (context.proofs === undefined) return { denial: "MISSING_AUTHORIZATION_EVIDENCE" };
  let proofs: BossRestrictedProofAuthorizationRecord[];
  try {
    proofs = parseAuthorizationRecordArray(context.proofs, "$.proofs", parseProofAuthorizationRecord);
  } catch {
    return { denial: "PAYLOAD_AUTHORIZATION_MISMATCH" };
  }
  const matches = proofs.filter((proof) => proof.proofId === proofId);
  if (matches.length === 0) return { denial: "MISSING_AUTHORIZATION_EVIDENCE" };
  if (matches.length !== 1) return { denial: "PAYLOAD_AUTHORIZATION_MISMATCH" };
  return { proof: matches[0] };
}

function authorizeProofPayload(
  context: BossRestrictedClientAuthorizationContext,
  principal: BossPrivatePrincipal,
  bossRunId: string,
  proofId: string,
  mode: "owner" | "reviewer" | "adversary-review",
): PayloadAuthorizationDenial | undefined {
  const result = proofAuthorization(context, proofId);
  if (result.denial !== undefined) return result.denial;
  const proof = result.proof!;
  if (proof.bossRunId !== bossRunId) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  if (mode === "owner") return proof.ownerParticipantId === principal.participantId
    ? undefined
    : "PAYLOAD_AUTHORIZATION_MISMATCH";
  if (mode === "reviewer") return proof.reviewerParticipantIds.includes(principal.participantId)
    ? undefined
    : "PAYLOAD_AUTHORIZATION_MISMATCH";
  if (proof.ownerParticipantId !== principal.participantId) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  const principals = parseActivePolicyPrincipals(context);
  return principals?.some((candidate) => (
    candidate.bossRunId === bossRunId
    && candidate.role === "adversary"
    && proof.reviewerParticipantIds.includes(candidate.participantId)
  )) === true
    ? undefined
    : "PAYLOAD_AUTHORIZATION_MISMATCH";
}

function authorizeReviewPayload(
  context: BossRestrictedClientAuthorizationContext,
  principal: BossPrivatePrincipal,
  bossRunId: string,
  reviewId: string,
  submissionProofId?: string,
): PayloadAuthorizationDenial | undefined {
  if (context.reviews === undefined) return "MISSING_AUTHORIZATION_EVIDENCE";
  let reviews: BossRestrictedReviewAuthorizationRecord[];
  try {
    reviews = parseAuthorizationRecordArray(context.reviews, "$.reviews", parseReviewAuthorizationRecord);
  } catch {
    return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  const matches = reviews.filter((review) => review.reviewId === reviewId);
  if (matches.length === 0) return "MISSING_AUTHORIZATION_EVIDENCE";
  if (matches.length !== 1) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  const review = matches[0];
  if (review.bossRunId !== bossRunId || review.reviewerParticipantId !== principal.participantId) {
    return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  if (submissionProofId !== undefined && (review.state !== "pending" || review.proofId !== submissionProofId)) {
    return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  const proof = proofAuthorization(context, review.proofId);
  return proof.denial !== undefined
    ? proof.denial
    : proof.proof!.bossRunId === bossRunId
      && proof.proof!.ownerParticipantId === review.requesterParticipantId
      && proof.proof!.reviewerParticipantIds.includes(principal.participantId)
      ? undefined
      : "PAYLOAD_AUTHORIZATION_MISMATCH";
}

function authorizeSubscriptionPayload(
  context: BossRestrictedClientAuthorizationContext,
  manager: BossPrivatePrincipal,
  request: BossManagerRequest,
  subscription: LifecycleSubscriptionRecord,
): PayloadAuthorizationDenial | undefined {
  if (
    subscription.subscriberPrincipalId !== context.principalId
    || Number(subscription.subscriberBindingEpoch) !== Number(request.bindingEpoch)
    || subscription.bossRunId !== request.bossRunId
    || subscription.lastSubscriberAuthorityTransitionId !== context.currentBinding.authorityTransitionId
  ) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  return authorizeSupervisionTarget(
    context,
    manager,
    request.bossRunId,
    request.bindingEpoch,
    subscription.subscriberBindingGeneration,
    subscription.target,
  );
}

function authorizeSubscriptionCreation(
  context: BossRestrictedClientAuthorizationContext,
  manager: BossPrivatePrincipal,
  request: BossManagerRequest,
  subscription: LifecycleSubscriptionRecord,
): PayloadAuthorizationDenial | undefined {
  if (context.subscriptions === undefined) return "MISSING_AUTHORIZATION_EVIDENCE";
  let subscriptions: LifecycleSubscriptionRecord[];
  try {
    subscriptions = ownDenseArrayDataValues(context.subscriptions, "$.subscriptions")
      .map((entry) => parseLifecycleSubscription(entry));
  } catch {
    return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  if (subscriptions.some((stored) => stored.subscriptionId === subscription.subscriptionId)) {
    return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  return authorizeSubscriptionPayload(context, manager, request, subscription);
}

function authorizeStoredSubscriptionCancellation(
  context: BossRestrictedClientAuthorizationContext,
  manager: BossPrivatePrincipal,
  request: BossManagerRequest,
  subscriptionId: string,
): PayloadAuthorizationDenial | undefined {
  if (context.subscriptions === undefined) return "MISSING_AUTHORIZATION_EVIDENCE";
  let subscriptions: LifecycleSubscriptionRecord[];
  try {
    subscriptions = ownDenseArrayDataValues(context.subscriptions, "$.subscriptions")
      .map((entry) => parseLifecycleSubscription(entry));
  } catch {
    return "PAYLOAD_AUTHORIZATION_MISMATCH";
  }
  const matches = subscriptions.filter((subscription) => subscription.subscriptionId === subscriptionId);
  if (matches.length === 0) return "MISSING_AUTHORIZATION_EVIDENCE";
  if (matches.length !== 1) return "PAYLOAD_AUTHORIZATION_MISMATCH";
  return authorizeSubscriptionPayload(context, manager, request, matches[0]);
}

function authorizeRestrictedPayload(
  request: BossRestrictedClientRequest,
  context: BossRestrictedClientAuthorizationContext,
  principal: BossPrivatePrincipal,
): PayloadAuthorizationDenial | undefined {
  switch (request.operation) {
    case "manager_create_assignment": {
      const participantId = request.payload.participantId;
      if (assignedTargetPrincipal(context, principal, participantId) === undefined) return "PAYLOAD_AUTHORIZATION_MISMATCH";
      if (context.assignments === undefined) return "MISSING_AUTHORIZATION_EVIDENCE";
      let assignments: BossRestrictedAssignmentAuthorizationRecord[];
      try {
        assignments = parseAuthorizationRecordArray(context.assignments, "$.assignments", parseAssignmentAuthorizationRecord);
      } catch {
        return "PAYLOAD_AUTHORIZATION_MISMATCH";
      }
      if (assignments.some((assignment) => assignment.assignmentId === request.payload.assignmentId)) {
        return "PAYLOAD_AUTHORIZATION_MISMATCH";
      }
      return undefined;
    }
    case "manager_cancel_assignment":
    case "manager_submit_checkpoint":
    case "participant_accept_assignment":
    case "participant_reject_assignment":
    case "participant_submit_checkpoint":
    case "participant_submit_assignment":
    case "participant_report_blocker":
      return authorizeAssignmentPayload(context, principal, request.bossRunId, request.payload.assignmentId);
    case "manager_create_subscription":
      return authorizeSubscriptionCreation(context, principal, request, request.payload);
    case "manager_cancel_subscription":
      return authorizeStoredSubscriptionCancellation(context, principal, request, request.payload.subscriptionId);
    case "manager_submit_proof":
    case "reviewer_submit_proof":
      return authorizeProofPayload(context, principal, request.bossRunId, request.payload.proofId, "owner");
    case "manager_request_adversary_review":
      return authorizeProofPayload(context, principal, request.bossRunId, request.payload.proofId, "adversary-review");
    case "reviewer_get_proof":
      return authorizeProofPayload(context, principal, request.bossRunId, request.payload.proofId, "reviewer");
    case "reviewer_submit_review":
      return authorizeReviewPayload(context, principal, request.bossRunId, request.payload.reviewId, request.payload.proofId);
    case "reviewer_get_objection_status":
      return authorizeReviewPayload(context, principal, request.bossRunId, request.payload.reviewId);
    case "manager_get_status":
    case "manager_request_staff":
    case "manager_list_subscriptions":
    case "manager_report_blocker":
    case "manager_request_council":
    case "participant_report_health":
    case "reviewer_report_health":
      return undefined;
  }
}

function expectedRestrictedRoles(client: BossRestrictedClient): readonly BossPolicyRole[] {
  if (client === "boss_manager") return ["manager"];
  if (client === "boss_reviewer") return ["adversary", "council"];
  return ["worker", "scout"];
}

function restrictedIdempotencyScope(binding: {
  bossRunId: string;
  client: BossRestrictedClient;
  participantId: string;
  bindingEpoch: ParticipantBindingEpoch;
}): string {
  return canonicalHash("agent-intercom-core/boss-restricted-client/idempotency-scope/v1", binding);
}

function parseBossRestrictedClientIdempotencyRecord(
  value: unknown,
  path: string,
): BossRestrictedClientIdempotencyRecord {
  assertRecord(value, path);
  assertExactKeys(value, [
    "scope",
    "bossRunId",
    "client",
    "participantId",
    "bindingEpoch",
    "operation",
    "requestId",
    "idempotencyKey",
    "requestDigest",
  ], [], path);
  const client = readEnum(value.client, ["boss_manager", "boss_participant", "boss_reviewer"] as const, `${path}.client`);
  const record = {
    scope: readHexDigest(value.scope, `${path}.scope`),
    bossRunId: readString(value.bossRunId, `${path}.bossRunId`),
    client,
    participantId: readString(value.participantId, `${path}.participantId`),
    bindingEpoch: participantBindingEpoch(value.bindingEpoch, `${path}.bindingEpoch`),
    operation: readClientOperation(client, value.operation, `${path}.operation`),
    requestId: readString(value.requestId, `${path}.requestId`),
    idempotencyKey: readString(value.idempotencyKey, `${path}.idempotencyKey`),
    requestDigest: readHexDigest(value.requestDigest, `${path}.requestDigest`),
  };
  if (record.scope !== restrictedIdempotencyScope({
    bossRunId: record.bossRunId,
    client: record.client,
    participantId: record.participantId,
    bindingEpoch: record.bindingEpoch,
  })) {
    throw new ContractValidationError(`${path}.scope`, "is not bound to the record identity");
  }
  return record;
}

function parseBossRestrictedClientIdempotencyRecords(value: unknown): BossRestrictedClientIdempotencyRecord[] {
  return ownDenseArrayDataValues(value, "$.idempotencyRecords")
    .map((entry, index) => parseBossRestrictedClientIdempotencyRecord(entry, `$.idempotencyRecords[${index}]`));
}

export function bossRestrictedClientIdempotencyScope(requestValue: unknown): string {
  const request = parseBossRestrictedClientRequest(requestValue);
  return restrictedIdempotencyScope({
    bossRunId: request.bossRunId,
    client: request.client,
    participantId: restrictedParticipantId(request),
    bindingEpoch: request.bindingEpoch,
  });
}

export function createBossRestrictedClientIdempotencyRecord(requestValue: unknown): BossRestrictedClientIdempotencyRecord {
  const request = parseBossRestrictedClientRequest(requestValue);
  return {
    scope: bossRestrictedClientIdempotencyScope(request),
    bossRunId: request.bossRunId,
    client: request.client,
    participantId: restrictedParticipantId(request),
    bindingEpoch: request.bindingEpoch,
    operation: request.operation,
    requestId: request.requestId,
    idempotencyKey: request.idempotencyKey,
    requestDigest: canonicalHash("agent-intercom-core/boss-restricted-client/request/v1", request),
  };
}

export function authorizeBossRestrictedClientRequest(
  requestValue: unknown,
  contextValue: BossRestrictedClientAuthorizationContext,
): BossRestrictedClientAuthorizationDecision {
  const context = parseBossRestrictedClientAuthorizationContext(contextValue);
  const request = parseBossRestrictedClientRequest(requestValue);
  const principalMap = restrictedPolicyPrincipalMap(context.policy);
  if (principalMap === undefined) return { allowed: false, code: "UNKNOWN_PRINCIPAL" };
  const principalDescriptor = ownEnumerableDataDescriptor(principalMap, context.principalId);
  if (principalDescriptor === undefined) return { allowed: false, code: "UNKNOWN_PRINCIPAL" };
  const principalValue = principalDescriptor.value;
  if (
    typeof principalValue !== "object"
    || principalValue === null
  ) return { allowed: false, code: "POLICY_BINDING_MISMATCH" };
  let principal: BossPrivatePrincipal;
  try {
    const parsedPrincipal = parseBossPolicyPrincipal(principalValue);
    if (parsedPrincipal.principalClass !== "boss-private" || parsedPrincipal.state !== "active") {
      return { allowed: false, code: "PRINCIPAL_NOT_ACTIVE" };
    }
    if (parsedPrincipal.principalId !== context.principalId) return { allowed: false, code: "POLICY_BINDING_MISMATCH" };
    principal = parsedPrincipal;
  } catch {
    return { allowed: false, code: "PRINCIPAL_NOT_ACTIVE" };
  }
  let binding: BossParticipantBinding;
  try {
    binding = parseBossParticipantBinding(context.currentBinding);
  } catch {
    return { allowed: false, code: "POLICY_BINDING_MISMATCH" };
  }
  if (binding.state !== "active") return { allowed: false, code: "BINDING_NOT_ACTIVE" };
  if (
    binding.participantId !== principal.participantId
    || binding.bossRunId !== principal.bossRunId
    || binding.role !== principal.role
    || binding.bindingEpoch !== principal.bindingEpoch
  ) return { allowed: false, code: "POLICY_BINDING_MISMATCH" };
  if (!expectedRestrictedRoles(request.client).includes(principal.role)) return { allowed: false, code: "UNAUTHORIZED_ROLE" };
  if (restrictedParticipantId(request) !== principal.participantId) return { allowed: false, code: "PARTICIPANT_MISMATCH" };
  if (request.bindingEpoch !== principal.bindingEpoch || request.bindingEpoch !== binding.bindingEpoch) {
    return { allowed: false, code: "STALE_BINDING_EPOCH" };
  }
  if (request.bossRunId !== principal.bossRunId || request.bossRunId !== binding.bossRunId) {
    return { allowed: false, code: "CROSS_RUN_REPLAY" };
  }
  const parsedContext = { ...context, currentBinding: binding };
  const record = createBossRestrictedClientIdempotencyRecord(request);
  const records = parsedContext.idempotencyRecords === undefined
    ? []
    : parseBossRestrictedClientIdempotencyRecords(parsedContext.idempotencyRecords);
  const requestIdRecords = records.filter((entry) => entry.requestId === request.requestId);
  if (requestIdRecords.some((entry) => (
    entry.bossRunId !== record.bossRunId
    || entry.client !== record.client
    || entry.participantId !== record.participantId
    || entry.bindingEpoch !== record.bindingEpoch
  ))) return { allowed: false, code: "CROSS_RUN_REPLAY" };
  if (requestIdRecords.some((entry) => (
    entry.scope !== record.scope
    || entry.operation !== record.operation
    || entry.idempotencyKey !== record.idempotencyKey
    || entry.requestDigest !== record.requestDigest
  ))) {
    return { allowed: false, code: "REQUEST_ID_CONFLICT" };
  }
  const priorRecords = records.filter((entry) => entry.scope === record.scope && entry.idempotencyKey === record.idempotencyKey);
  if (priorRecords.some((entry) => (
    entry.bossRunId !== record.bossRunId
    || entry.client !== record.client
    || entry.participantId !== record.participantId
    || entry.bindingEpoch !== record.bindingEpoch
    || entry.operation !== record.operation
    || entry.requestId !== record.requestId
    || entry.requestDigest !== record.requestDigest
  ))) {
    return { allowed: false, code: "IDEMPOTENCY_CONFLICT" };
  }
  const prior = priorRecords[0] ?? requestIdRecords[0];
  if (prior !== undefined) return { allowed: true, idempotency: "replay", record: prior };
  const payloadDenial = authorizeRestrictedPayload(request, parsedContext, principal);
  return payloadDenial === undefined
    ? { allowed: true, idempotency: "new", record }
    : { allowed: false, code: payloadDenial };
}

export const RESTRICTED_RESULT_STATUSES = ["ok", "rejected", "feature_not_enabled", "conflict", "unauthorized"] as const;
export type BossRestrictedResultStatus = (typeof RESTRICTED_RESULT_STATUSES)[number];

interface RestrictedResultBinding {
  version: typeof BOSS_RESTRICTED_CLIENT_RESULT_VERSION;
  bossRunId: string;
  bindingEpoch: ParticipantBindingEpoch;
  requestId: string;
  idempotencyKey: string;
}
type RestrictedSuccessResult<Operation extends BossRestrictedOperation> = RestrictedResultBinding & {
  operation: Operation;
  status: "ok";
  payload: BossRestrictedResultPayloadByOperation[Operation];
};
type RestrictedErrorResult<Operation extends BossRestrictedOperation> = RestrictedResultBinding & {
  operation: Operation;
  status: "rejected" | "feature_not_enabled" | "conflict";
  errorCode: string;
};
type RestrictedUnauthorizedResult<Operation extends BossRestrictedOperation> = RestrictedResultBinding & {
  operation: Operation;
  status: "unauthorized";
  denialCode: BossRestrictedAuthorizationDenialCode;
};
type BoundManagerResult<Operation extends BossManagerOperation> = (
  | RestrictedSuccessResult<Operation>
  | RestrictedErrorResult<Operation>
  | RestrictedUnauthorizedResult<Operation>
) & { client: "boss_manager"; managerParticipantId: string };
type BoundParticipantResult<Operation extends BossParticipantOperation> = (
  | RestrictedSuccessResult<Operation>
  | RestrictedErrorResult<Operation>
  | RestrictedUnauthorizedResult<Operation>
) & { client: "boss_participant"; participantId: string };
type BoundReviewerResult<Operation extends BossReviewerOperation> = (
  | RestrictedSuccessResult<Operation>
  | RestrictedErrorResult<Operation>
  | RestrictedUnauthorizedResult<Operation>
) & { client: "boss_reviewer"; participantId: string };
export type BossRestrictedClientResult =
  | { [Operation in BossManagerOperation]: BoundManagerResult<Operation> }[BossManagerOperation]
  | { [Operation in BossParticipantOperation]: BoundParticipantResult<Operation> }[BossParticipantOperation]
  | { [Operation in BossReviewerOperation]: BoundReviewerResult<Operation> }[BossReviewerOperation];

function parseRestrictedResultPayload(operation: BossRestrictedOperation, value: unknown): BossRestrictedResultPayloadByOperation[BossRestrictedOperation] {
  let parsed: Record<string, unknown>;
  switch (operation) {
    case "manager_get_status": parsed = parseExactPayload(value, { status: "string" }); break;
    case "manager_request_staff": parsed = parseExactPayload(value, { staffRequestId: "string" }); break;
    case "manager_create_assignment":
    case "manager_cancel_assignment":
    case "participant_accept_assignment":
    case "participant_reject_assignment":
    case "participant_submit_assignment": parsed = parseExactPayload(value, { assignmentId: "string" }); break;
    case "manager_create_subscription":
    case "manager_cancel_subscription": parsed = parseExactPayload(value, { subscriptionId: "string" }); break;
    case "manager_list_subscriptions": parsed = parseExactPayload(value, { subscriptionIds: "stringArray" }); break;
    case "manager_submit_checkpoint":
    case "participant_submit_checkpoint": parsed = parseExactPayload(value, { assignmentId: "string", checkpointId: "string", recordedAt: "timestamp" }); break;
    case "manager_report_blocker":
    case "participant_report_blocker": parsed = parseExactPayload(value, { blockerId: "string" }); break;
    case "manager_submit_proof":
    case "reviewer_submit_proof": parsed = parseExactPayload(value, { proofId: "string" }); break;
    case "manager_request_adversary_review":
    case "reviewer_submit_review": parsed = parseExactPayload(value, { reviewId: "string" }); break;
    case "manager_request_council": parsed = parseExactPayload(value, {}); break;
    case "participant_report_health":
    case "reviewer_report_health": parsed = parseExactPayload(value, { healthEventId: "string" }); break;
    case "reviewer_get_proof": parsed = parseExactPayload(value, { proofId: "string", digest: "hexDigest" }); break;
    case "reviewer_get_objection_status": parsed = parseExactPayload(value, { reviewId: "string", status: "string" }); break;
  }
  return parsed as unknown as BossRestrictedResultPayloadByOperation[BossRestrictedOperation];
}

export function parseBossRestrictedClientResult(value: unknown, requestValue?: unknown): BossRestrictedClientResult {
  assertRecord(value);
  const client = readEnum(value.client, ["boss_manager", "boss_participant", "boss_reviewer"] as const, "$.client");
  const participantField = client === "boss_manager" ? "managerParticipantId" : "participantId";
  const status = readEnum(value.status, RESTRICTED_RESULT_STATUSES, "$.status");
  const statusField = status === "ok" ? "payload" : status === "unauthorized" ? "denialCode" : "errorCode";
  assertExactKeys(value, ["version", "bossRunId", "client", participantField, "bindingEpoch", "requestId", "idempotencyKey", "operation", "status", statusField]);
  if (value.version !== BOSS_RESTRICTED_CLIENT_RESULT_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${String(value.version)}`);
  const operation = readClientOperation(client, value.operation, "$.operation");
  if (operation === "manager_request_council" && (status !== "feature_not_enabled" || value.errorCode !== "feature_not_enabled")) {
    throw new ContractValidationError("$.status", "Council execution is reserved and must deterministically return feature_not_enabled");
  }
  const base = {
    version: BOSS_RESTRICTED_CLIENT_RESULT_VERSION,
    bossRunId: readString(value.bossRunId, "$.bossRunId"),
    client,
    bindingEpoch: participantBindingEpoch(value.bindingEpoch, "$.bindingEpoch"),
    requestId: readString(value.requestId, "$.requestId"),
    idempotencyKey: readString(value.idempotencyKey, "$.idempotencyKey"),
    operation,
    status,
    ...(client === "boss_manager"
      ? { managerParticipantId: readString(value.managerParticipantId, "$.managerParticipantId") }
      : { participantId: readString(value.participantId, "$.participantId") }),
  };
  const result = (status === "ok"
    ? { ...base, payload: parseRestrictedResultPayload(operation, value.payload) }
    : status === "unauthorized"
      ? { ...base, denialCode: readEnum(value.denialCode, BOSS_RESTRICTED_AUTHORIZATION_DENIAL_CODES, "$.denialCode") }
      : { ...base, errorCode: readString(value.errorCode, "$.errorCode") }) as BossRestrictedClientResult;
  if (requestValue !== undefined) assertBossRestrictedClientResultBinding(result, requestValue);
  return result;
}

function echoedRestrictedSuccessIdentityFields(operation: BossRestrictedOperation): readonly string[] {
  switch (operation) {
    case "manager_create_assignment":
    case "manager_cancel_assignment":
    case "participant_accept_assignment":
    case "participant_reject_assignment":
    case "participant_submit_assignment":
      return ["assignmentId"];
    case "manager_submit_checkpoint":
    case "participant_submit_checkpoint":
      return ["assignmentId", "checkpointId"];
    case "manager_create_subscription":
    case "manager_cancel_subscription":
      return ["subscriptionId"];
    case "manager_report_blocker":
      return ["blockerId"];
    case "manager_submit_proof":
    case "reviewer_get_proof":
    case "reviewer_submit_proof":
      return ["proofId"];
    case "reviewer_submit_review":
    case "reviewer_get_objection_status":
      return ["reviewId"];
    case "manager_get_status":
    case "manager_request_staff":
    case "manager_list_subscriptions":
    case "manager_request_adversary_review":
    case "manager_request_council":
    case "participant_report_blocker":
    case "participant_report_health":
    case "reviewer_report_health":
      return [];
  }
}

export function assertBossRestrictedClientResultBinding(resultValue: unknown, requestValue: unknown): void {
  const result = parseBossRestrictedClientResult(resultValue);
  const request = parseBossRestrictedClientRequest(requestValue);
  const resultParticipant = result.client === "boss_manager" ? result.managerParticipantId : result.participantId;
  if (
    result.bossRunId !== request.bossRunId
    || result.client !== request.client
    || resultParticipant !== restrictedParticipantId(request)
    || result.bindingEpoch !== request.bindingEpoch
    || result.requestId !== request.requestId
    || result.idempotencyKey !== request.idempotencyKey
    || result.operation !== request.operation
  ) throw new ContractValidationError("$", "restricted result is not bound to the originating authenticated request");
  if (result.status === "ok") {
    const resultPayload = result.payload as unknown as Record<string, unknown>;
    const requestPayload = request.payload as unknown as Record<string, unknown>;
    for (const field of echoedRestrictedSuccessIdentityFields(request.operation)) {
      if (resultPayload[field] !== requestPayload[field]) {
        throw new ContractValidationError(`$.payload.${field}`, "does not match the originating request payload");
      }
    }
  }
}

export const validateBrokerProviderAttestationStore = (value: unknown): StoreValidationResult<BrokerProviderAttestation> =>
  validateVersionedStoreRecord(value, BROKER_PROVIDER_ATTESTATION_VERSION, parseBrokerProviderAttestation);
export const validateBrokerIdentityStore = (value: unknown): StoreValidationResult<BrokerIdentityRecord> =>
  validateVersionedStoreRecord(value, BROKER_IDENTITY_RECORD_VERSION, parseBrokerIdentityRecord);
export const validateLegacyAdminMigrationStore = (value: unknown): StoreValidationResult<LegacyAdminMigrationRecord> =>
  validateVersionedStoreRecord(value, LEGACY_ADMIN_MIGRATION_VERSION, parseLegacyAdminMigrationRecord);
export const validateBrokerJournalRecoveryStore = (value: unknown): StoreValidationResult<BrokerJournalRecoveryRecord> =>
  validateVersionedStoreRecord(value, BROKER_JOURNAL_RECOVERY_VERSION, parseBrokerJournalRecoveryRecord);
