import {
  canonicalHash,
  canonicalJson,
  ContractValidationError,
  type CanonicalValue,
  assertExactKeys,
  assertRecord,
  readBoolean,
  readEnum,
  readHexDigest,
  readIdentifier,
  readInteger,
  readOptionalBoolean,
  readOptionalInteger,
  readOptionalIdentifier,
  readOptionalString,
  readOptionalTimestamp,
  readString,
  readStringArray,
  readTimestamp,
  validateVersionedStoreRecord,
  bossBindingEpoch as readBossBindingEpoch,
  brokerRevision as readBrokerRevision,
  controllerGeneration as readControllerGeneration,
  participantBindingEpoch as readParticipantBindingEpoch,
  subscriberBindingEpoch as readSubscriberBindingEpoch,
  workerGeneration as readWorkerGeneration,
  transitionVersion as readTransitionVersion,
  brokerGeneration as readBrokerGeneration,
  journalGeneration as readJournalGeneration,
  schedulerGeneration as readSchedulerGeneration,
  recipientTransferGeneration as readRecipientTransferGeneration,
  deliveryClaimGeneration as readDeliveryClaimGeneration,
  triggerGeneration as readTriggerGeneration,
  watchdogGeneration as readWatchdogGeneration,
  type StoreValidationResult,
  type BossBindingEpoch,
  type BrokerRevision,
  type ControllerGeneration,
  type ParticipantBindingEpoch,
  type SubscriberBindingEpoch,
  type WorkerGeneration,
  type TransitionVersion,
  type BrokerGeneration,
  type JournalGeneration,
  type SchedulerGeneration,
  type RecipientTransferGeneration,
  type DeliveryClaimGeneration,
  type TriggerGeneration,
  type WatchdogGeneration,
} from "./canonical.ts";
import { BOSS_POLICY_SEMANTICS_HASH } from "./boss-policy-vectors.ts";
import { FEATURE_ROUTING_SEMANTICS_HASH, FEATURE_ROUTING_VECTOR_SCHEMA_VERSION } from "./feature-routing-vectors.ts";
import {
  FULL_WORKER_STORE_MIGRATION_VECTOR_VERSION,
  FULL_WORKER_STORE_MIGRATION_VECTORS_HASH,
  INTERCOM_BASE_PROTOCOL_VERSION,
  PARTICIPANT_STATE_TRANSITION_VECTOR_SCHEMA_VERSION,
  PARTICIPANT_STATE_TRANSITION_VECTORS_HASH,
  PARTICIPANT_STATE_VECTOR_SCHEMA_VERSION,
  PARTICIPANT_STATE_VECTORS_HASH,
  SUPERVISION_VECTOR_SCHEMA_VERSION,
  SUPERVISION_VECTORS_HASH,
} from "./boss-semantic-binding-constants.ts";

export const BOSS_RUN_FEATURE = "boss-run-v1" as const;
export const BOSS_RUN_FEATURE_VERSION = 1 as const;
export const BOSS_CONTROL_ENVELOPE_VERSION = 1 as const;

/**
 * This corpus is deliberately separate from remote-access-v1 policy vectors.
 * Changing it changes only the negotiated Boss feature hash.
 */
export const BOSS_RUN_FEATURE_SEMANTICS_CORPUS = {
  feature: BOSS_RUN_FEATURE,
  version: BOSS_RUN_FEATURE_VERSION,
  baseProtocolVersion: INTERCOM_BASE_PROTOCOL_VERSION,
  controlEnvelopeVersion: BOSS_CONTROL_ENVELOPE_VERSION,
  bindingAuthority: "broker",
  unknownMetadata: "reject",
  downgradeToLocalPublic: "forbidden",
  participantEpochs: "independent",
  bossBindingEpoch: "independent",
  crossRunCommunication: "deny",
  controllerDeliveryRunIdentity: "embedded_and_top_level_boss_run_id_present_and_equal",
  legacyRemoteAccessSemantics: "unchanged",
  deliveryClaimReleaseProof: "drained_barrier_bound_to_claim_generation_session_epoch_named_pi_opencode_paths_and_not_before_attempt",
  recordReceiptIngress: "persisted_claim_chronology_and_result_invariants",
  initialAuthorityBindPriorEpoch: 0,
  laterAuthorityTransitionPriorEpoch: "positive",
  bossPolicySemanticsVersion: 1,
  bossPolicySemanticsHash: BOSS_POLICY_SEMANTICS_HASH,
  featureRoutingVectorVersion: FEATURE_ROUTING_VECTOR_SCHEMA_VERSION,
  featureRoutingSemanticsHash: FEATURE_ROUTING_SEMANTICS_HASH,
  participantStateVectorSchemaVersion: PARTICIPANT_STATE_VECTOR_SCHEMA_VERSION,
  participantStateVectorsHash: PARTICIPANT_STATE_VECTORS_HASH,
  participantStateTransitionVectorSchemaVersion: PARTICIPANT_STATE_TRANSITION_VECTOR_SCHEMA_VERSION,
  participantStateTransitionVectorsHash: PARTICIPANT_STATE_TRANSITION_VECTORS_HASH,
  supervisionVectorSchemaVersion: SUPERVISION_VECTOR_SCHEMA_VERSION,
  supervisionVectorsHash: SUPERVISION_VECTORS_HASH,
  fullWorkerStoreMigrationVectorVersion: FULL_WORKER_STORE_MIGRATION_VECTOR_VERSION,
  fullWorkerStoreMigrationVectorsHash: FULL_WORKER_STORE_MIGRATION_VECTORS_HASH,
} as const;

export const BOSS_RUN_FEATURE_SEMANTICS_HASH = canonicalHash(
  "agent-intercom-core/boss-run-v1/feature-semantics",
  BOSS_RUN_FEATURE_SEMANTICS_CORPUS,
);

export interface BossRunFeatureContract {
  feature: typeof BOSS_RUN_FEATURE;
  version: typeof BOSS_RUN_FEATURE_VERSION;
  baseProtocolVersion: typeof INTERCOM_BASE_PROTOCOL_VERSION;
  semanticsHash: string;
  controlEnvelopeVersion: typeof BOSS_CONTROL_ENVELOPE_VERSION;
}

export const BOSS_RUN_FEATURE_CONTRACT: BossRunFeatureContract = {
  feature: BOSS_RUN_FEATURE,
  version: BOSS_RUN_FEATURE_VERSION,
  baseProtocolVersion: INTERCOM_BASE_PROTOCOL_VERSION,
  semanticsHash: BOSS_RUN_FEATURE_SEMANTICS_HASH,
  controlEnvelopeVersion: BOSS_CONTROL_ENVELOPE_VERSION,
};

/** Hash of the exact protocol negotiation tuple, distinct from policy semantics. */
export const BOSS_RUN_PROTOCOL_FEATURE_CONTRACT_HASH = canonicalHash(
  "agent-intercom-core/boss-run-v1/protocol-feature-contract",
  BOSS_RUN_FEATURE_CONTRACT,
);

export const BOSS_CAPABILITY_FEATURE_CONTRACT_VERSION = 1 as const;
export const BOSS_CAPABILITY_FEATURE_DIGEST = canonicalHash(
  "agent-intercom-core/boss-run-v1/capability-feature-digest",
  {
    version: BOSS_CAPABILITY_FEATURE_CONTRACT_VERSION,
    canonicalEncodingVersion: 1,
    baseProtocolVersion: INTERCOM_BASE_PROTOCOL_VERSION,
    protocolFeatureContractHash: BOSS_RUN_PROTOCOL_FEATURE_CONTRACT_HASH,
    policySemanticsVersion: 1,
    policySemanticsHash: BOSS_POLICY_SEMANTICS_HASH,
    controlEnvelopeVersion: BOSS_CONTROL_ENVELOPE_VERSION,
    participantStateVectorSchemaVersion: PARTICIPANT_STATE_VECTOR_SCHEMA_VERSION,
    participantStateVectorsHash: PARTICIPANT_STATE_VECTORS_HASH,
    participantStateTransitionVectorSchemaVersion: PARTICIPANT_STATE_TRANSITION_VECTOR_SCHEMA_VERSION,
    participantStateTransitionVectorsHash: PARTICIPANT_STATE_TRANSITION_VECTORS_HASH,
    supervisionVectorSchemaVersion: SUPERVISION_VECTOR_SCHEMA_VERSION,
    supervisionVectorsHash: SUPERVISION_VECTORS_HASH,
    fullWorkerStoreMigrationVectorVersion: FULL_WORKER_STORE_MIGRATION_VECTOR_VERSION,
    fullWorkerStoreMigrationVectorsHash: FULL_WORKER_STORE_MIGRATION_VECTORS_HASH,
  },
);

export function parseBossRunFeatureContract(value: unknown): BossRunFeatureContract {
  assertRecord(value);
  assertExactKeys(value, ["feature", "version", "baseProtocolVersion", "semanticsHash", "controlEnvelopeVersion"]);
  if (value.feature !== BOSS_RUN_FEATURE) throw new ContractValidationError("$.feature", `must be ${BOSS_RUN_FEATURE}`);
  if (value.version !== BOSS_RUN_FEATURE_VERSION) {
    throw new ContractValidationError("$.version", `unsupported Boss feature version: ${String(value.version)}`);
  }
  if (value.baseProtocolVersion !== INTERCOM_BASE_PROTOCOL_VERSION) {
    throw new ContractValidationError(
      "$.baseProtocolVersion",
      `unsupported Boss base protocol version: ${String(value.baseProtocolVersion)}`,
    );
  }
  const semanticsHash = readHexDigest(value.semanticsHash, "$.semanticsHash");
  if (semanticsHash !== BOSS_RUN_FEATURE_SEMANTICS_HASH) {
    throw new ContractValidationError("$.semanticsHash", "does not match the boss-run-v1 semantics corpus");
  }
  if (value.controlEnvelopeVersion !== BOSS_CONTROL_ENVELOPE_VERSION) {
    throw new ContractValidationError(
      "$.controlEnvelopeVersion",
      `unsupported control envelope version: ${String(value.controlEnvelopeVersion)}`,
    );
  }
  return value as unknown as BossRunFeatureContract;
}

export const BOSS_PARTICIPANT_ROLES = ["boss", "manager", "adversary", "scout", "worker", "council"] as const;
export type BossParticipantRole = (typeof BOSS_PARTICIPANT_ROLES)[number];
export const BOSS_COMMUNICATION_PROFILES = BOSS_PARTICIPANT_ROLES;
export type BossCommunicationProfile = BossParticipantRole;

export const BOSS_RUN_AUTHORITY_IDENTITY_VERSION = "boss.run-authority.v1" as const;
export interface BossRunAuthorityIdentity {
  version: typeof BOSS_RUN_AUTHORITY_IDENTITY_VERSION;
  controllerPrincipalId: string;
  bossRunId: string;
  controllerGeneration: ControllerGeneration;
  authorityTransitionRevision: BrokerRevision;
  activeBossSessionId?: string;
  bossBindingEpoch: BossBindingEpoch;
}

export function parseBossRunAuthorityIdentity(value: unknown): BossRunAuthorityIdentity {
  assertRecord(value);
  assertExactKeys(
    value,
    ["version", "controllerPrincipalId", "bossRunId", "controllerGeneration", "authorityTransitionRevision", "bossBindingEpoch"],
    ["activeBossSessionId"],
  );
  assertLiteralVersion(value.version, BOSS_RUN_AUTHORITY_IDENTITY_VERSION, "$.version");
  readString(value.controllerPrincipalId, "$.controllerPrincipalId");
  readString(value.bossRunId, "$.bossRunId");
  readControllerGeneration(value.controllerGeneration, "$.controllerGeneration");
  readBrokerRevision(value.authorityTransitionRevision, "$.authorityTransitionRevision");
  readOptionalString(value.activeBossSessionId, "$.activeBossSessionId");
  readBossBindingEpoch(value.bossBindingEpoch, "$.bossBindingEpoch");
  return value as unknown as BossRunAuthorityIdentity;
}

export const BOSS_PARTICIPANT_BINDING_VERSION = "boss.participant-binding.v1" as const;
export const BOSS_BINDING_STATES = ["active", "revoked", "replaced"] as const;
export type BossBindingState = (typeof BOSS_BINDING_STATES)[number];

export interface BossParticipantBinding {
  version: typeof BOSS_PARTICIPANT_BINDING_VERSION;
  bossRunId: string;
  participantId: string;
  role: BossParticipantRole;
  communicationProfile: BossCommunicationProfile;
  bindingEpoch: ParticipantBindingEpoch;
  sessionId: string;
  brokerGeneration: BrokerGeneration;
  brokerBootInstance: string;
  state: BossBindingState;
  assignedManagerParticipantId?: string;
  authorityTransitionId: string;
}

export function parseBossParticipantBinding(value: unknown): BossParticipantBinding {
  assertRecord(value);
  assertExactKeys(
    value,
    [
      "version",
      "bossRunId",
      "participantId",
      "role",
      "communicationProfile",
      "bindingEpoch",
      "sessionId",
      "brokerGeneration",
      "brokerBootInstance",
      "state",
      "authorityTransitionId",
    ],
    ["assignedManagerParticipantId"],
  );
  assertLiteralVersion(value.version, BOSS_PARTICIPANT_BINDING_VERSION, "$.version");
  readString(value.bossRunId, "$.bossRunId");
  readString(value.participantId, "$.participantId");
  const role = readEnum(value.role, BOSS_PARTICIPANT_ROLES, "$.role");
  const profile = readEnum(value.communicationProfile, BOSS_COMMUNICATION_PROFILES, "$.communicationProfile");
  if (profile !== role) throw new ContractValidationError("$.communicationProfile", "must match the authenticated role");
  readParticipantBindingEpoch(value.bindingEpoch, "$.bindingEpoch");
  readString(value.sessionId, "$.sessionId");
  readBrokerGeneration(value.brokerGeneration, "$.brokerGeneration");
  readString(value.brokerBootInstance, "$.brokerBootInstance");
  readEnum(value.state, BOSS_BINDING_STATES, "$.state");
  const assignedManagerParticipantId = readOptionalString(value.assignedManagerParticipantId, "$.assignedManagerParticipantId");
  if ((role === "worker" || role === "scout") !== (assignedManagerParticipantId !== undefined)) {
    throw new ContractValidationError("$.assignedManagerParticipantId", "is required exactly for Worker and Scout bindings");
  }
  readString(value.authorityTransitionId, "$.authorityTransitionId");
  return value as unknown as BossParticipantBinding;
}

export const BOSS_PARTICIPANT_CREDENTIAL_VERSION = "boss.participant-credential.v1" as const;
export const BOSS_CREDENTIAL_KINDS = ["enrollment", "reconnect"] as const;
export type BossCredentialKind = (typeof BOSS_CREDENTIAL_KINDS)[number];

export interface BossParticipantCredentialEnvelope {
  version: typeof BOSS_PARTICIPANT_CREDENTIAL_VERSION;
  namespace: typeof BOSS_RUN_FEATURE;
  credentialKind: BossCredentialKind;
  credentialId: string;
  credential: string;
  bossRunId: string;
  participantId: string;
  role: BossParticipantRole;
  communicationProfile: BossCommunicationProfile;
  bindingEpoch: ParticipantBindingEpoch;
  issuedAt: string;
  expiresAt: string;
  nonce: string;
}

export function credentialDigest(envelope: BossParticipantCredentialEnvelope): string {
  parseBossParticipantCredentialEnvelope(envelope);
  return canonicalHash("agent-intercom-core/boss-run-v1/participant-credential", envelope);
}

export function parseBossParticipantCredentialEnvelope(value: unknown): BossParticipantCredentialEnvelope {
  assertRecord(value);
  assertExactKeys(value, [
    "version",
    "namespace",
    "credentialKind",
    "credentialId",
    "credential",
    "bossRunId",
    "participantId",
    "role",
    "communicationProfile",
    "bindingEpoch",
    "issuedAt",
    "expiresAt",
    "nonce",
  ]);
  assertLiteralVersion(value.version, BOSS_PARTICIPANT_CREDENTIAL_VERSION, "$.version");
  if (value.namespace !== BOSS_RUN_FEATURE) throw new ContractValidationError("$.namespace", `must be ${BOSS_RUN_FEATURE}`);
  readEnum(value.credentialKind, BOSS_CREDENTIAL_KINDS, "$.credentialKind");
  readString(value.credentialId, "$.credentialId");
  readString(value.credential, "$.credential");
  readString(value.bossRunId, "$.bossRunId");
  readString(value.participantId, "$.participantId");
  const role = readEnum(value.role, BOSS_PARTICIPANT_ROLES, "$.role");
  const profile = readEnum(value.communicationProfile, BOSS_COMMUNICATION_PROFILES, "$.communicationProfile");
  if (profile !== role) throw new ContractValidationError("$.communicationProfile", "must match role");
  readParticipantBindingEpoch(value.bindingEpoch, "$.bindingEpoch");
  const issuedAt = readTimestamp(value.issuedAt, "$.issuedAt");
  const expiresAt = readTimestamp(value.expiresAt, "$.expiresAt");
  if (timestampMillis(expiresAt) <= timestampMillis(issuedAt)) {
    throw new ContractValidationError("$.expiresAt", "must be later than issuedAt");
  }
  readString(value.nonce, "$.nonce");
  return value as unknown as BossParticipantCredentialEnvelope;
}

export const BOSS_CREDENTIAL_DIGEST_RECORD_VERSION = "boss.credential-digest.v1" as const;
export const BOSS_CREDENTIAL_STATES = ["issued", "consumed", "revoked", "expired"] as const;
export type BossCredentialState = (typeof BOSS_CREDENTIAL_STATES)[number];

export interface BossCredentialDigestRecord {
  version: typeof BOSS_CREDENTIAL_DIGEST_RECORD_VERSION;
  namespace: typeof BOSS_RUN_FEATURE;
  credentialKind: BossCredentialKind;
  credentialId: string;
  digest: string;
  bossRunId: string;
  participantId: string;
  role: BossParticipantRole;
  bindingEpoch: ParticipantBindingEpoch;
  nonce: string;
  issuedAt: string;
  expiresAt: string;
  state: BossCredentialState;
  consumedAt?: string;
  revokedAt?: string;
  auditEventId: string;
}

export function parseBossCredentialDigestRecord(value: unknown): BossCredentialDigestRecord {
  assertRecord(value);
  assertExactKeys(
    value,
    [
      "version",
      "namespace",
      "credentialKind",
      "credentialId",
      "digest",
      "bossRunId",
      "participantId",
      "role",
      "bindingEpoch",
      "nonce",
      "issuedAt",
      "expiresAt",
      "state",
      "auditEventId",
    ],
    ["consumedAt", "revokedAt"],
  );
  assertLiteralVersion(value.version, BOSS_CREDENTIAL_DIGEST_RECORD_VERSION, "$.version");
  if (value.namespace !== BOSS_RUN_FEATURE) throw new ContractValidationError("$.namespace", `must be ${BOSS_RUN_FEATURE}`);
  readEnum(value.credentialKind, BOSS_CREDENTIAL_KINDS, "$.credentialKind");
  readString(value.credentialId, "$.credentialId");
  readHexDigest(value.digest, "$.digest");
  readString(value.bossRunId, "$.bossRunId");
  readString(value.participantId, "$.participantId");
  readEnum(value.role, BOSS_PARTICIPANT_ROLES, "$.role");
  readParticipantBindingEpoch(value.bindingEpoch, "$.bindingEpoch");
  readString(value.nonce, "$.nonce");
  const issuedAt = readTimestamp(value.issuedAt, "$.issuedAt");
  const expiresAt = readTimestamp(value.expiresAt, "$.expiresAt");
  if (timestampMillis(expiresAt) <= timestampMillis(issuedAt)) {
    throw new ContractValidationError("$.expiresAt", "must be later than issuedAt");
  }
  const state = readEnum(value.state, BOSS_CREDENTIAL_STATES, "$.state");
  const consumedAt = readOptionalTimestamp(value.consumedAt, "$.consumedAt");
  const revokedAt = readOptionalTimestamp(value.revokedAt, "$.revokedAt");
  readString(value.auditEventId, "$.auditEventId");
  if ((state === "consumed") !== (consumedAt !== undefined)) {
    throw new ContractValidationError("$.consumedAt", "is required exactly when state is consumed");
  }
  if ((state === "revoked") !== (revokedAt !== undefined)) {
    throw new ContractValidationError("$.revokedAt", "is required exactly when state is revoked");
  }
  if (consumedAt !== undefined) {
    if (timestampMillis(consumedAt) < timestampMillis(issuedAt)) {
      throw new ContractValidationError("$.consumedAt", "must not precede issuedAt");
    }
    if (timestampMillis(consumedAt) >= timestampMillis(expiresAt)) {
      throw new ContractValidationError("$.consumedAt", "must be earlier than expiresAt");
    }
  }
  if (revokedAt !== undefined && timestampMillis(revokedAt) < timestampMillis(issuedAt)) {
    throw new ContractValidationError("$.revokedAt", "must not precede issuedAt");
  }
  return value as unknown as BossCredentialDigestRecord;
}

export interface BossCredentialUseContext {
  now: string;
  credentialKind: BossCredentialKind;
  bossRunId: string;
  participantId: string;
  role: BossParticipantRole;
  bindingEpoch: ParticipantBindingEpoch;
  nonce: string;
}

export type BossCredentialDenialCode =
  | "DIGEST_MISMATCH"
  | "NOT_YET_VALID"
  | "EXPIRED"
  | "ALREADY_CONSUMED"
  | "REVOKED"
  | "RUN_SUBSTITUTION"
  | "PARTICIPANT_SUBSTITUTION"
  | "ROLE_SUBSTITUTION"
  | "EPOCH_MISMATCH"
  | "NONCE_MISMATCH"
  | "KIND_MISMATCH"
  | "REGISTRY_MISMATCH";

export type BossCredentialUseDecision =
  | { accepted: true; credentialId: string; auditEventId: string }
  | { accepted: false; code: BossCredentialDenialCode; auditEventId: string };

/** Pure broker-side credential decision. Callers persist consumption and its audit event atomically. */
export function authorizeBossCredentialUse(
  envelopeValue: unknown,
  recordValue: unknown,
  contextValue: unknown,
): BossCredentialUseDecision {
  const envelope = parseBossParticipantCredentialEnvelope(envelopeValue);
  const record = parseBossCredentialDigestRecord(recordValue);
  const context = parseBossCredentialUseContext(contextValue);
  const denied = (code: BossCredentialDenialCode): BossCredentialUseDecision => ({
    accepted: false,
    code,
    auditEventId: record.auditEventId,
  });
  if (record.digest !== credentialDigest(envelope) || record.credentialId !== envelope.credentialId) return denied("DIGEST_MISMATCH");
  if (record.state === "consumed") return denied("ALREADY_CONSUMED");
  if (record.state === "revoked") return denied("REVOKED");
  if (record.state === "expired") return denied("EXPIRED");
  if (record.issuedAt !== envelope.issuedAt || record.expiresAt !== envelope.expiresAt) return denied("REGISTRY_MISMATCH");
  const now = timestampMillis(context.now);
  if (now < timestampMillis(envelope.issuedAt)) return denied("NOT_YET_VALID");
  if (now >= timestampMillis(envelope.expiresAt) || now >= timestampMillis(record.expiresAt)) return denied("EXPIRED");
  if (context.credentialKind !== envelope.credentialKind || record.credentialKind !== envelope.credentialKind) return denied("KIND_MISMATCH");
  if (context.bossRunId !== envelope.bossRunId || record.bossRunId !== envelope.bossRunId) return denied("RUN_SUBSTITUTION");
  if (context.participantId !== envelope.participantId || record.participantId !== envelope.participantId) {
    return denied("PARTICIPANT_SUBSTITUTION");
  }
  if (context.role !== envelope.role || record.role !== envelope.role) return denied("ROLE_SUBSTITUTION");
  if (context.bindingEpoch !== envelope.bindingEpoch || record.bindingEpoch !== envelope.bindingEpoch) return denied("EPOCH_MISMATCH");
  if (context.nonce !== envelope.nonce || record.nonce !== envelope.nonce) return denied("NONCE_MISMATCH");
  return { accepted: true, credentialId: envelope.credentialId, auditEventId: record.auditEventId };
}

export const BOSS_CREDENTIAL_AUDIT_EVENT_VERSION = "boss.credential-audit-event.v1" as const;
export const BOSS_CREDENTIAL_AUDIT_OPERATIONS = ["issue", "consume", "reconnect", "deny", "revoke", "rotate"] as const;
export interface BossCredentialAuditEvent {
  version: typeof BOSS_CREDENTIAL_AUDIT_EVENT_VERSION;
  eventId: string;
  credentialId: string;
  credentialKind: BossCredentialKind;
  bossRunId: string;
  participantId: string;
  presentedBindingEpoch: ParticipantBindingEpoch;
  operation: (typeof BOSS_CREDENTIAL_AUDIT_OPERATIONS)[number];
  outcome: "accepted" | BossCredentialDenialCode;
  nonceDigest: string;
  authorityTransitionId?: string;
  occurredAt: string;
}

export function parseBossCredentialAuditEvent(value: unknown): BossCredentialAuditEvent {
  assertRecord(value);
  assertExactKeys(
    value,
    ["version", "eventId", "credentialId", "credentialKind", "bossRunId", "participantId", "presentedBindingEpoch", "operation", "outcome", "nonceDigest", "occurredAt"],
    ["authorityTransitionId"],
  );
  assertLiteralVersion(value.version, BOSS_CREDENTIAL_AUDIT_EVENT_VERSION, "$.version");
  const operation = readEnum(value.operation, BOSS_CREDENTIAL_AUDIT_OPERATIONS, "$.operation");
  const outcome = readEnum(value.outcome, [
    "accepted", "DIGEST_MISMATCH", "NOT_YET_VALID", "EXPIRED", "ALREADY_CONSUMED", "REVOKED", "RUN_SUBSTITUTION",
    "PARTICIPANT_SUBSTITUTION", "ROLE_SUBSTITUTION", "EPOCH_MISMATCH", "NONCE_MISMATCH", "KIND_MISMATCH", "REGISTRY_MISMATCH",
  ] as const, "$.outcome");
  if ((operation === "deny") !== (outcome !== "accepted")) {
    throw new ContractValidationError("$.outcome", "deny requires a denial code and all other audit operations require accepted");
  }
  const authorityTransitionId = readOptionalString(value.authorityTransitionId, "$.authorityTransitionId");
  if ((operation === "revoke" || operation === "rotate") && authorityTransitionId === undefined) {
    throw new ContractValidationError("$.authorityTransitionId", "is required for revocation and rotation");
  }
  return {
    version: BOSS_CREDENTIAL_AUDIT_EVENT_VERSION,
    eventId: readString(value.eventId, "$.eventId"),
    credentialId: readString(value.credentialId, "$.credentialId"),
    credentialKind: readEnum(value.credentialKind, BOSS_CREDENTIAL_KINDS, "$.credentialKind"),
    bossRunId: readString(value.bossRunId, "$.bossRunId"),
    participantId: readString(value.participantId, "$.participantId"),
    presentedBindingEpoch: readParticipantBindingEpoch(value.presentedBindingEpoch, "$.presentedBindingEpoch"),
    operation,
    outcome,
    nonceDigest: readHexDigest(value.nonceDigest, "$.nonceDigest"),
    ...(authorityTransitionId === undefined ? {} : { authorityTransitionId }),
    occurredAt: readTimestamp(value.occurredAt, "$.occurredAt"),
  };
}

export const AUTHORITY_TRANSITION_VERSION = "boss.authority-transition.v1" as const;
export const AUTHORITY_EVENT_VERSION = "boss.authority-event.v1" as const;
export const AUTHORITY_REQUEST_VERSION = "boss.authority-request.v1" as const;
export const AUTHORITY_TRANSITION_OPERATIONS = [
  "bind_boss",
  "rebind_boss",
  "revoke_boss",
  "bind_participant",
  "rebind_participant",
  "revoke_participant",
  "replace_participant",
  "replace_manager",
  "rebind_subscriber",
  "controller_takeover",
  "rotate_credential",
] as const;
export type AuthorityTransitionOperation = (typeof AUTHORITY_TRANSITION_OPERATIONS)[number];
export const AUTHORITY_TRANSITION_STATES = ["prepared", "committed", "aborted"] as const;
export type AuthorityTransitionState = (typeof AUTHORITY_TRANSITION_STATES)[number];
export const AUTHORITY_REQUEST_OPERATIONS = ["prepare", "commit", "abort", "query"] as const;
export type AuthorityRequestOperation = (typeof AUTHORITY_REQUEST_OPERATIONS)[number];

export interface AuthorityTransitionEpochs {
  controllerGeneration?: ControllerGeneration;
  bossBindingEpoch?: BossBindingEpoch;
  participantBindingEpoch?: ParticipantBindingEpoch;
  subscriberBindingEpoch?: SubscriberBindingEpoch;
}

export interface AuthorityTransitionTarget {
  bossRunId?: string;
  participantId?: string;
  replacementParticipantId?: string;
  controllerPrincipalId?: string;
  credentialId?: string;
  subscriberPrincipalId?: string;
}

export interface AuthorityTransitionRecord {
  version: typeof AUTHORITY_TRANSITION_VERSION;
  authorityTransitionId: string;
  expectedBrokerRevision: BrokerRevision;
  brokerRevision: BrokerRevision;
  operation: AuthorityTransitionOperation;
  target: AuthorityTransitionTarget;
  prior: AuthorityTransitionEpochs;
  proposed: AuthorityTransitionEpochs;
  idempotencyKey: string;
  state: AuthorityTransitionState;
  prepareToken: string;
  preparedAt: string;
  committedAt?: string;
  abortedAt?: string;
  abortReason?: string;
}

export function parseAuthorityTransitionRecord(value: unknown): AuthorityTransitionRecord {
  assertRecord(value);
  assertExactKeys(
    value,
    [
      "version",
      "authorityTransitionId",
      "expectedBrokerRevision",
      "brokerRevision",
      "operation",
      "target",
      "prior",
      "proposed",
      "idempotencyKey",
      "state",
      "prepareToken",
      "preparedAt",
    ],
    ["committedAt", "abortedAt", "abortReason"],
  );
  assertLiteralVersion(value.version, AUTHORITY_TRANSITION_VERSION, "$.version");
  readString(value.authorityTransitionId, "$.authorityTransitionId");
  const expectedRevision = readBrokerRevision(value.expectedBrokerRevision, "$.expectedBrokerRevision");
  const brokerRevision = readBrokerRevision(value.brokerRevision, "$.brokerRevision");
  if (brokerRevision <= expectedRevision) {
    throw new ContractValidationError("$.brokerRevision", "must be later than expectedBrokerRevision after durable prepare");
  }
  const operation = readEnum(value.operation, AUTHORITY_TRANSITION_OPERATIONS, "$.operation");
  const target = parseAuthorityTransitionTarget(value.target, "$.target");
  const prior = parseAuthorityTransitionEpochs(value.prior, "$.prior", operation === "bind_boss" || operation === "bind_participant" ? 0 : 1);
  const proposed = parseAuthorityTransitionEpochs(value.proposed, "$.proposed", 1);
  validateAuthorityEpochChange(operation, target, prior, proposed);
  readString(value.idempotencyKey, "$.idempotencyKey");
  const state = readEnum(value.state, AUTHORITY_TRANSITION_STATES, "$.state");
  readString(value.prepareToken, "$.prepareToken");
  readTimestamp(value.preparedAt, "$.preparedAt");
  const committedAt = readOptionalTimestamp(value.committedAt, "$.committedAt");
  const abortedAt = readOptionalTimestamp(value.abortedAt, "$.abortedAt");
  const abortReason = readOptionalString(value.abortReason, "$.abortReason");
  if (state === "committed") {
    if (committedAt === undefined) throw new ContractValidationError("$.committedAt", "is required for a committed transition");
    if (abortedAt !== undefined || abortReason !== undefined) throw new ContractValidationError("$", "committed transition cannot be aborted");
  } else if (state === "aborted") {
    if (abortedAt === undefined || abortReason === undefined) {
      throw new ContractValidationError("$", "aborted transition requires abortedAt and abortReason");
    }
    if (committedAt !== undefined) throw new ContractValidationError("$", "aborted transition cannot have commit fields");
  } else if (committedAt !== undefined || abortedAt !== undefined || abortReason !== undefined) {
    throw new ContractValidationError("$", "prepared transition cannot have terminal fields");
  }
  const preparedMillis = timestampMillis(value.preparedAt as string);
  if (committedAt !== undefined && timestampMillis(committedAt) < preparedMillis) {
    throw new ContractValidationError("$.committedAt", "must not precede preparedAt");
  }
  if (abortedAt !== undefined && timestampMillis(abortedAt) < preparedMillis) {
    throw new ContractValidationError("$.abortedAt", "must not precede preparedAt");
  }
  return value as unknown as AuthorityTransitionRecord;
}

export interface AuthorityTransitionEvent {
  version: typeof AUTHORITY_EVENT_VERSION;
  eventId: string;
  bossRunId?: string;
  authorityTransitionId: string;
  brokerRevision: BrokerRevision;
  operation: AuthorityTransitionOperation;
  state: "committed";
  target: AuthorityTransitionTarget;
  prior: AuthorityTransitionEpochs;
  resulting: AuthorityTransitionEpochs;
  occurredAt: string;
}

export function parseAuthorityTransitionEvent(value: unknown): AuthorityTransitionEvent {
  assertRecord(value);
  assertExactKeys(value, [
    "version",
    "eventId",
    "authorityTransitionId",
    "brokerRevision",
    "operation",
    "state",
    "target",
    "prior",
    "resulting",
    "occurredAt",
  ], ["bossRunId"]);
  assertLiteralVersion(value.version, AUTHORITY_EVENT_VERSION, "$.version");
  readString(value.eventId, "$.eventId");
  const bossRunId = readOptionalString(value.bossRunId, "$.bossRunId");
  readString(value.authorityTransitionId, "$.authorityTransitionId");
  readBrokerRevision(value.brokerRevision, "$.brokerRevision");
  const operation = readEnum(value.operation, AUTHORITY_TRANSITION_OPERATIONS, "$.operation");
  if (value.state !== "committed") throw new ContractValidationError("$.state", "authority events are emitted only for committed transitions");
  const target = parseAuthorityTransitionTarget(value.target, "$.target");
  if (target.bossRunId !== bossRunId) throw new ContractValidationError("$.target.bossRunId", "must match bossRunId");
  const prior = parseAuthorityTransitionEpochs(value.prior, "$.prior", operation === "bind_boss" || operation === "bind_participant" ? 0 : 1);
  const resulting = parseAuthorityTransitionEpochs(value.resulting, "$.resulting", 1);
  validateAuthorityEpochChange(operation, target, prior, resulting);
  readTimestamp(value.occurredAt, "$.occurredAt");
  return value as unknown as AuthorityTransitionEvent;
}

export type AuthorityTransitionRequest = {
  version: typeof AUTHORITY_REQUEST_VERSION;
  operation: AuthorityRequestOperation;
  requestId: string;
  idempotencyKey: string;
  authorityTransitionId: string;
  expectedBrokerRevision: BrokerRevision;
  payload:
    | {
      requestedOperation: AuthorityTransitionOperation;
      target: AuthorityTransitionTarget;
      prior: AuthorityTransitionEpochs;
    }
    | { prepareToken: string }
    | { prepareToken: string; reason: string }
    | Record<string, never>;
};

/** Authority-socket request contract; broker responses are the persisted record returned at its authoritative revision. */
export function parseAuthorityTransitionRequest(value: unknown): AuthorityTransitionRequest {
  assertRecord(value);
  assertExactKeys(value, [
    "version",
    "operation",
    "requestId",
    "idempotencyKey",
    "authorityTransitionId",
    "expectedBrokerRevision",
    "payload",
  ]);
  assertLiteralVersion(value.version, AUTHORITY_REQUEST_VERSION, "$.version");
  const operation = readEnum(value.operation, AUTHORITY_REQUEST_OPERATIONS, "$.operation");
  readString(value.requestId, "$.requestId");
  readString(value.idempotencyKey, "$.idempotencyKey");
  readString(value.authorityTransitionId, "$.authorityTransitionId");
  readBrokerRevision(value.expectedBrokerRevision, "$.expectedBrokerRevision");
  assertRecord(value.payload, "$.payload");
  if (operation === "prepare") {
    assertExactKeys(value.payload, ["requestedOperation", "target", "prior"], [], "$.payload");
    const requestedOperation = readEnum(value.payload.requestedOperation, AUTHORITY_TRANSITION_OPERATIONS, "$.payload.requestedOperation");
    const target = parseAuthorityTransitionTarget(value.payload.target, "$.payload.target");
    const prior = parseAuthorityTransitionEpochs(
      value.payload.prior,
      "$.payload.prior",
      requestedOperation === "bind_boss" || requestedOperation === "bind_participant" ? 0 : 1,
    );
    validateAuthorityPriorEpoch(requestedOperation, prior, "$.payload.prior");
    validateAuthorityTarget(requestedOperation, target, "$.payload.target");
  } else if (operation === "commit") {
    assertExactKeys(value.payload, ["prepareToken"], [], "$.payload");
    readString(value.payload.prepareToken, "$.payload.prepareToken");
  } else if (operation === "abort") {
    assertExactKeys(value.payload, ["prepareToken", "reason"], [], "$.payload");
    readString(value.payload.prepareToken, "$.payload.prepareToken");
    readString(value.payload.reason, "$.payload.reason");
  } else {
    assertExactKeys(value.payload, [], [], "$.payload");
  }
  return value as unknown as AuthorityTransitionRequest;
}

export const BOSS_CONTROL_TYPES = [
  "boss.assignment.created",
  "boss.assignment.accepted",
  "boss.assignment.checkpoint",
  "boss.assignment.submitted",
  "boss.assignment.rejected",
  "boss.assignment.cancelled",
  "boss.staffing.requested",
  "boss.staffing.resolved",
  "boss.review.requested",
  "boss.review.submitted",
  "boss.council.requested",
  "boss.council.submitted",
  "boss.proof.submitted",
  "boss.worker.health",
  "boss.worker.blocked",
  "boss.worker.failed",
  "boss.worker.notice",
  "boss.worker.notice_delivery_failed",
  "boss.decision.required",
] as const;
export type BossControlType = (typeof BOSS_CONTROL_TYPES)[number];

export interface BossControlEnvelope<TPayload extends CanonicalValue = CanonicalValue> {
  type: BossControlType;
  version: typeof BOSS_CONTROL_ENVELOPE_VERSION;
  messageId: string;
  bossRunId: string;
  participantId: string;
  bindingEpoch: ParticipantBindingEpoch;
  causationId?: string;
  replyTo?: string;
  idempotencyKey: string;
  payload: TPayload;
}

export function parseBossControlEnvelope(value: unknown): BossControlEnvelope {
  assertRecord(value);
  assertExactKeys(
    value,
    ["type", "version", "messageId", "bossRunId", "participantId", "bindingEpoch", "idempotencyKey", "payload"],
    ["causationId", "replyTo"],
  );
  readEnum(value.type, BOSS_CONTROL_TYPES, "$.type");
  if (value.version !== BOSS_CONTROL_ENVELOPE_VERSION) {
    throw new ContractValidationError("$.version", `unsupported Boss control envelope version: ${String(value.version)}`);
  }
  readString(value.messageId, "$.messageId");
  readString(value.bossRunId, "$.bossRunId");
  readString(value.participantId, "$.participantId");
  readParticipantBindingEpoch(value.bindingEpoch, "$.bindingEpoch");
  readOptionalString(value.causationId, "$.causationId");
  readOptionalString(value.replyTo, "$.replyTo");
  readString(value.idempotencyKey, "$.idempotencyKey");
  assertWireValue(value.payload, "$.payload");
  return value as unknown as BossControlEnvelope;
}

export const LIFECYCLE_NOTICE_VERSION = "orc.lifecycle-notice.v1" as const;
export const DELIVERY_GROUP_VERSION = "orc.delivery-group.v1" as const;
export const DELIVERY_CLAIM_VERSION = "orc.delivery-claim.v1" as const;
export const NOTICE_RECIPIENT_INGRESS_VERSION = "orc.notice-recipient-ingress.v1" as const;
export const TARGET_LEDGER_RESULT_VERSION = "orc.target-ledger-result.v1" as const;
export const DELIVERY_INTENTS = ["wake", "follow_up", "status_only"] as const;
export type DeliveryIntent = (typeof DELIVERY_INTENTS)[number];
export const RECIPIENT_CONTEXTS = ["pi", "opencode", "headless_cli"] as const;
export type RecipientContext = (typeof RECIPIENT_CONTEXTS)[number];
export const DELIVERY_CLAIM_STATES = ["reserved", "inserting", "inserted", "delivered", "blocked", "released"] as const;
export type DeliveryClaimState = (typeof DELIVERY_CLAIM_STATES)[number];
export const NOTICE_DELIVERY_CLAIM_STATES = ["reserved", "inserting", "inserted", "delivered", "blocked"] as const;
export type NoticeDeliveryClaimState = (typeof NOTICE_DELIVERY_CLAIM_STATES)[number];
export const DELIVERY_MODES = ["lifecycle_message", "correlated_result"] as const;
export type DeliveryMode = (typeof DELIVERY_MODES)[number];
export const DELIVERY_GROUP_MEMBERSHIP_STATES = ["assembling", "sealed"] as const;
export const DELIVERY_GROUP_STATES = ["pending", "reserved", "inserting", "inserted", "delivered", "blocked", "migrated"] as const;
export type DeliveryGroupState = (typeof DELIVERY_GROUP_STATES)[number];

function assertResultCorrelation(
  mode: DeliveryMode,
  modeField: "deliveryMode" | "ingressMode",
  resultMessageId: string | undefined,
  coalescedByResult: boolean | undefined,
  path = "$",
): void {
  const fieldPath = (field: string): string => path === "$" ? `$.${field}` : `${path}.${field}`;
  if (coalescedByResult === true && resultMessageId === undefined) {
    throw new ContractValidationError(fieldPath("coalescedByResult"), "requires resultMessageId");
  }
  if (coalescedByResult === true && mode !== "correlated_result") {
    throw new ContractValidationError(fieldPath("coalescedByResult"), `is valid only with correlated_result ${modeField}`);
  }
  if (mode === "correlated_result" && resultMessageId === undefined) {
    throw new ContractValidationError(fieldPath(modeField), "correlated_result requires resultMessageId");
  }
  if (mode === "lifecycle_message" && resultMessageId !== undefined) {
    throw new ContractValidationError(fieldPath("resultMessageId"), `is forbidden with lifecycle_message ${modeField}`);
  }
}

export interface LifecycleNoticeLogicalKey {
  workerId: string;
  workerGeneration: WorkerGeneration;
  transitionId: string;
  transitionVersion: TransitionVersion;
  kind: string;
  assignmentId?: string;
  watchdogGeneration?: WatchdogGeneration;
  subscriptionId?: string;
  subscriptionTriggerGeneration?: TriggerGeneration;
}

export function lifecycleNoticeId(key: LifecycleNoticeLogicalKey): string {
  parseLifecycleNoticeLogicalKey(key);
  return canonicalHash("orc-notice-v1", key);
}

export interface LifecycleNotice {
  version: typeof LIFECYCLE_NOTICE_VERSION;
  noticeId: string;
  deliveryGroupId: string;
  deliveryGroupMembershipRevision: number;
  requestedDeliveryIntent?: DeliveryIntent;
  sourceEventId: string;
  transitionId: string;
  transitionVersion: TransitionVersion;
  bossRunId?: string;
  workerId: string;
  workerIncarnationId: string;
  assignmentId?: string;
  turnId?: string;
  watchdogGeneration?: WatchdogGeneration;
  subscriptionId?: string;
  subscriptionTriggerGeneration?: TriggerGeneration;
  causationId?: string;
  resultMessageId?: string;
  recipientSessionId?: string;
  recipientTargetSessionId?: string;
  recipientPrincipalId?: string;
  recipientBindingEpoch?: number;
  workerGeneration: WorkerGeneration;
  kind: string;
  severity: string;
  observedState: string;
  reason: string;
  createdAt: string;
  deliveryAttemptedAt?: string;
  deliveryClaimId?: string;
  deliveryClaimGeneration?: DeliveryClaimGeneration;
  deliveryClaimExpiresAt?: string;
  deliveryClaimState?: NoticeDeliveryClaimState;
  recipientContext: RecipientContext;
  deliveredAt?: string;
  deliveryMode?: DeliveryMode;
  deliveryReceiptId?: string;
  coalescedByResult?: boolean;
  acknowledgedAt?: string;
}

export function parseLifecycleNotice(value: unknown): LifecycleNotice {
  assertRecord(value);
  assertExactKeys(
    value,
    [
      "version",
      "noticeId",
      "deliveryGroupId",
      "deliveryGroupMembershipRevision",
      "sourceEventId",
      "transitionId",
      "transitionVersion",
      "workerId",
      "workerIncarnationId",
      "workerGeneration",
      "kind",
      "severity",
      "observedState",
      "reason",
      "createdAt",
      "recipientContext",
    ],
    [
      "requestedDeliveryIntent",
      "bossRunId",
      "assignmentId",
      "turnId",
      "watchdogGeneration",
      "subscriptionId",
      "subscriptionTriggerGeneration",
      "causationId",
      "resultMessageId",
      "recipientSessionId",
      "recipientTargetSessionId",
      "recipientPrincipalId",
      "recipientBindingEpoch",
      "deliveryAttemptedAt",
      "deliveryClaimId",
      "deliveryClaimGeneration",
      "deliveryClaimExpiresAt",
      "deliveryClaimState",
      "deliveredAt",
      "deliveryMode",
      "deliveryReceiptId",
      "coalescedByResult",
      "acknowledgedAt",
    ],
  );
  assertLiteralVersion(value.version, LIFECYCLE_NOTICE_VERSION, "$.version");
  const noticeId = readString(value.noticeId, "$.noticeId");
  readString(value.deliveryGroupId, "$.deliveryGroupId");
  readInteger(value.deliveryGroupMembershipRevision, "$.deliveryGroupMembershipRevision", 1);
  if (value.requestedDeliveryIntent !== undefined) readEnum(value.requestedDeliveryIntent, DELIVERY_INTENTS, "$.requestedDeliveryIntent");
  readString(value.sourceEventId, "$.sourceEventId");
  readString(value.transitionId, "$.transitionId");
  const transitionVersion = readTransitionVersion(value.transitionVersion, "$.transitionVersion");
  readOptionalString(value.bossRunId, "$.bossRunId");
  readString(value.workerId, "$.workerId");
  readString(value.workerIncarnationId, "$.workerIncarnationId");
  const assignmentId = readOptionalString(value.assignmentId, "$.assignmentId");
  readOptionalString(value.turnId, "$.turnId");
  const watchdogGeneration = value.watchdogGeneration === undefined ? undefined : readWatchdogGeneration(value.watchdogGeneration, "$.watchdogGeneration");
  const subscriptionId = readOptionalString(value.subscriptionId, "$.subscriptionId");
  const subscriptionTriggerGeneration = value.subscriptionTriggerGeneration === undefined
    ? undefined
    : readTriggerGeneration(value.subscriptionTriggerGeneration, "$.subscriptionTriggerGeneration", 1);
  readOptionalString(value.causationId, "$.causationId");
  const resultMessageId = readOptionalString(value.resultMessageId, "$.resultMessageId");
  readOptionalString(value.recipientSessionId, "$.recipientSessionId");
  readOptionalString(value.recipientTargetSessionId, "$.recipientTargetSessionId");
  readOptionalString(value.recipientPrincipalId, "$.recipientPrincipalId");
  readOptionalInteger(value.recipientBindingEpoch, "$.recipientBindingEpoch", 1);
  const workerGeneration = readWorkerGeneration(value.workerGeneration, "$.workerGeneration");
  const kind = readString(value.kind, "$.kind");
  readString(value.severity, "$.severity");
  readString(value.observedState, "$.observedState");
  readString(value.reason, "$.reason");
  const createdAt = readTimestamp(value.createdAt, "$.createdAt");
  const deliveryAttemptedAt = readOptionalTimestamp(value.deliveryAttemptedAt, "$.deliveryAttemptedAt");
  const claimId = readOptionalString(value.deliveryClaimId, "$.deliveryClaimId");
  const claimGeneration = value.deliveryClaimGeneration === undefined ? undefined : readDeliveryClaimGeneration(value.deliveryClaimGeneration, "$.deliveryClaimGeneration");
  const claimExpiresAt = readOptionalTimestamp(value.deliveryClaimExpiresAt, "$.deliveryClaimExpiresAt");
  const claimState = value.deliveryClaimState === undefined
    ? undefined
    : readEnum(value.deliveryClaimState, NOTICE_DELIVERY_CLAIM_STATES, "$.deliveryClaimState");
  const claimFields = [claimId, claimGeneration, claimExpiresAt, claimState].filter((entry) => entry !== undefined).length;
  if (claimFields !== 0 && claimFields !== 4) throw new ContractValidationError("$", "delivery claim fields must be present together");
  readEnum(value.recipientContext, RECIPIENT_CONTEXTS, "$.recipientContext");
  const deliveredAt = readOptionalTimestamp(value.deliveredAt, "$.deliveredAt");
  const deliveryMode = value.deliveryMode === undefined ? undefined : readEnum(value.deliveryMode, DELIVERY_MODES, "$.deliveryMode");
  const receiptId = readOptionalString(value.deliveryReceiptId, "$.deliveryReceiptId");
  const coalescedByResult = readOptionalBoolean(value.coalescedByResult, "$.coalescedByResult");
  const acknowledgedAt = readOptionalTimestamp(value.acknowledgedAt, "$.acknowledgedAt");
  if ([deliveredAt, deliveryMode, receiptId].filter((entry) => entry !== undefined).length % 3 !== 0) {
    throw new ContractValidationError("$", "deliveredAt, deliveryMode, and deliveryReceiptId must be present together");
  }
  const hasDeliveredTuple = deliveredAt !== undefined;
  const hasAttempt = deliveryAttemptedAt !== undefined;
  if ((claimState === "delivered") !== hasDeliveredTuple) {
    throw new ContractValidationError("$.deliveryClaimState", "must be delivered exactly when the delivery receipt tuple is present");
  }
  if (claimState === undefined && hasAttempt) {
    throw new ContractValidationError("$.deliveryAttemptedAt", "requires delivery claim fields");
  }
  if (claimState === "reserved" && hasAttempt) {
    throw new ContractValidationError("$.deliveryAttemptedAt", "is not valid while the delivery claim is reserved");
  }
  if ((claimState === "inserting" || claimState === "inserted" || claimState === "delivered") && !hasAttempt) {
    throw new ContractValidationError("$.deliveryAttemptedAt", "is required once delivery claim insertion starts");
  }
  if (deliveryAttemptedAt !== undefined && Date.parse(deliveryAttemptedAt) < Date.parse(createdAt)) {
    throw new ContractValidationError("$.deliveryAttemptedAt", "must not precede createdAt");
  }
  if (deliveryAttemptedAt !== undefined && claimExpiresAt !== undefined && Date.parse(deliveryAttemptedAt) >= Date.parse(claimExpiresAt)) {
    throw new ContractValidationError("$.deliveryAttemptedAt", "must occur before claim expiry");
  }
  if (deliveredAt !== undefined && deliveryAttemptedAt !== undefined && Date.parse(deliveredAt) < Date.parse(deliveryAttemptedAt)) {
    throw new ContractValidationError("$.deliveredAt", "must not precede deliveryAttemptedAt");
  }
  if (acknowledgedAt !== undefined && Date.parse(acknowledgedAt) < Date.parse(deliveredAt ?? createdAt)) {
    throw new ContractValidationError("$.acknowledgedAt", "must not precede delivery or creation");
  }
  if (coalescedByResult !== undefined && claimState !== "delivered") {
    throw new ContractValidationError("$.coalescedByResult", "is valid only for delivered notices");
  }
  if (resultMessageId !== undefined && !hasDeliveredTuple) {
    throw new ContractValidationError("$.resultMessageId", "is valid only with a delivered claim and delivery receipt tuple");
  }
  if (deliveryMode !== undefined) assertResultCorrelation(deliveryMode, "deliveryMode", resultMessageId, coalescedByResult);
  const expectedNoticeId = lifecycleNoticeId({
    workerId: value.workerId as string,
    workerGeneration,
    transitionId: value.transitionId as string,
    transitionVersion,
    kind,
    ...(assignmentId === undefined ? {} : { assignmentId }),
    ...(watchdogGeneration === undefined ? {} : { watchdogGeneration }),
    ...(subscriptionId === undefined ? {} : { subscriptionId }),
    ...(subscriptionTriggerGeneration === undefined ? {} : { subscriptionTriggerGeneration }),
  });
  if (noticeId !== expectedNoticeId) throw new ContractValidationError("$.noticeId", "does not match the lifecycle logical key");
  return value as unknown as LifecycleNotice;
}

export type SourceAuthorityId =
  | { kind: "worker_store"; workerStoreId: string; journalGeneration: JournalGeneration }
  | { kind: "controller"; bossRunId: string; controllerGeneration: ControllerGeneration }
  | { kind: "orc_scheduler"; ownerUid: number; schedulerGeneration: SchedulerGeneration };

export interface DeliveryEquivalenceKey {
  recipientPrincipalId: string;
  recipientBindingEpoch: number;
  sourceAuthorityId: SourceAuthorityId;
  sourceEventId: string;
  bossRunId?: string;
  workerId: string;
  workerGeneration: WorkerGeneration;
  transitionId: string;
  transitionVersion: TransitionVersion;
  assignmentId?: string;
  turnId?: string;
  watchdogGeneration?: WatchdogGeneration;
}

export function deliveryGroupId(key: DeliveryEquivalenceKey): string {
  parseDeliveryEquivalenceKey(key);
  return canonicalHash("orc-delivery-group-v1", key);
}

export function effectiveDeliveryIntent(intents: readonly DeliveryIntent[]): DeliveryIntent {
  const entries = readDenseOwnDataArray(intents, "intents");
  const validated = entries.map((intent, index) => readEnum(intent, DELIVERY_INTENTS, `intents[${index}]`));
  if (validated.includes("wake")) return "wake";
  if (validated.includes("follow_up")) return "follow_up";
  return "status_only";
}

export const DELIVERY_GROUP_ASSEMBLY_VERSION = "orc.delivery-group-assembly.v1" as const;
export interface DeliveryGroupAssemblyMember {
  noticeId: string;
  requestedDeliveryIntent: DeliveryIntent;
}
export interface DeliveryGroupAssemblyInput {
  version: typeof DELIVERY_GROUP_ASSEMBLY_VERSION;
  equivalenceKey: DeliveryEquivalenceKey;
  subscriptionRegistryRevision: number;
  membershipRevision: number;
  primaryNoticeId: string;
  members: DeliveryGroupAssemblyMember[];
  recipientTransferGeneration: RecipientTransferGeneration;
}

export function mintDeliveryGroupAssemblyMember(value: unknown): DeliveryGroupAssemblyMember {
  assertRecord(value);
  assertExactKeys(value, ["kind", "noticeId"], ["requestedDeliveryIntent"]);
  const kind = readEnum(value.kind, ["built_in", "subscription"] as const, "$.kind");
  const requestedDeliveryIntent = value.requestedDeliveryIntent === undefined
    ? kind === "built_in" ? "wake" : undefined
    : readEnum(value.requestedDeliveryIntent, DELIVERY_INTENTS, "$.requestedDeliveryIntent");
  if (requestedDeliveryIntent === undefined) {
    throw new ContractValidationError("$.requestedDeliveryIntent", "subscription members must declare an intent before assembly");
  }
  return { noticeId: readString(value.noticeId, "$.noticeId"), requestedDeliveryIntent };
}

export function parseDeliveryGroupAssemblyInput(value: unknown): DeliveryGroupAssemblyInput {
  assertRecord(value);
  assertExactKeys(value, ["version", "equivalenceKey", "subscriptionRegistryRevision", "membershipRevision", "primaryNoticeId", "members", "recipientTransferGeneration"]);
  assertLiteralVersion(value.version, DELIVERY_GROUP_ASSEMBLY_VERSION, "$.version");
  const equivalenceKey = parseDeliveryEquivalenceKey(value.equivalenceKey, "$.equivalenceKey");
  const memberValues = readDenseOwnDataArray(value.members, "$.members");
  if (memberValues.length === 0) throw new ContractValidationError("$.members", "must be a non-empty array");
  const members = memberValues.map((member, index): DeliveryGroupAssemblyMember => {
    const path = `$.members[${index}]`;
    assertRecord(member, path);
    assertExactKeys(member, ["noticeId", "requestedDeliveryIntent"], [], path);
    return {
      noticeId: readString(member.noticeId, `${path}.noticeId`),
      requestedDeliveryIntent: readEnum(member.requestedDeliveryIntent, DELIVERY_INTENTS, `${path}.requestedDeliveryIntent`),
    };
  });
  if (new Set(members.map((member) => member.noticeId)).size !== members.length) {
    throw new ContractValidationError("$.members", "notice IDs must be unique");
  }
  const primaryNoticeId = readString(value.primaryNoticeId, "$.primaryNoticeId");
  if (!members.some((member) => member.noticeId === primaryNoticeId)) {
    throw new ContractValidationError("$.primaryNoticeId", "must identify an assembly member");
  }
  return {
    version: DELIVERY_GROUP_ASSEMBLY_VERSION,
    equivalenceKey,
    subscriptionRegistryRevision: readInteger(value.subscriptionRegistryRevision, "$.subscriptionRegistryRevision"),
    membershipRevision: readInteger(value.membershipRevision, "$.membershipRevision", 1),
    primaryNoticeId,
    members,
    recipientTransferGeneration: readRecipientTransferGeneration(value.recipientTransferGeneration, "$.recipientTransferGeneration"),
  };
}

export function assembleDeliveryGroup(value: unknown): DeliveryGroupRecord {
  const input = parseDeliveryGroupAssemblyInput(value);
  const members = [...input.members].sort((left, right) => left.noticeId < right.noticeId ? -1 : left.noticeId > right.noticeId ? 1 : 0);
  const requestedIntents = members.map((member) => member.requestedDeliveryIntent);
  return {
    version: DELIVERY_GROUP_VERSION,
    deliveryGroupId: deliveryGroupId(input.equivalenceKey),
    equivalenceKey: input.equivalenceKey,
    subscriptionRegistryRevision: input.subscriptionRegistryRevision,
    membershipRevision: input.membershipRevision,
    membershipState: "sealed",
    primaryNoticeId: input.primaryNoticeId,
    memberNoticeIds: members.map((member) => member.noticeId),
    requestedIntents,
    effectiveDeliveryIntent: effectiveDeliveryIntent(requestedIntents),
    recipientTransferGeneration: input.recipientTransferGeneration,
    state: "pending",
  };
}

export interface DeliveryGroupRecord {
  version: typeof DELIVERY_GROUP_VERSION;
  deliveryGroupId: string;
  equivalenceKey: DeliveryEquivalenceKey;
  subscriptionRegistryRevision: number;
  membershipRevision: number;
  membershipState: (typeof DELIVERY_GROUP_MEMBERSHIP_STATES)[number];
  primaryNoticeId: string;
  memberNoticeIds: string[];
  requestedIntents: DeliveryIntent[];
  effectiveDeliveryIntent: DeliveryIntent;
  operativeActivationConsumedAt?: string;
  recipientTransferGeneration: RecipientTransferGeneration;
  supersedesDeliveryGroupId?: string;
  successorDeliveryGroupId?: string;
  authorityTransitionId?: string;
  state: DeliveryGroupState;
}

export function parseDeliveryGroupRecord(value: unknown): DeliveryGroupRecord {
  assertRecord(value);
  assertExactKeys(
    value,
    [
      "version",
      "deliveryGroupId",
      "equivalenceKey",
      "subscriptionRegistryRevision",
      "membershipRevision",
      "membershipState",
      "primaryNoticeId",
      "memberNoticeIds",
      "requestedIntents",
      "effectiveDeliveryIntent",
      "recipientTransferGeneration",
      "state",
    ],
    ["operativeActivationConsumedAt", "supersedesDeliveryGroupId", "successorDeliveryGroupId", "authorityTransitionId"],
  );
  assertLiteralVersion(value.version, DELIVERY_GROUP_VERSION, "$.version");
  const groupId = readString(value.deliveryGroupId, "$.deliveryGroupId");
  const key = parseDeliveryEquivalenceKey(value.equivalenceKey, "$.equivalenceKey");
  if (groupId !== deliveryGroupId(key)) throw new ContractValidationError("$.deliveryGroupId", "does not match equivalenceKey");
  readInteger(value.subscriptionRegistryRevision, "$.subscriptionRegistryRevision");
  readInteger(value.membershipRevision, "$.membershipRevision", 1);
  const membershipState = readEnum(value.membershipState, DELIVERY_GROUP_MEMBERSHIP_STATES, "$.membershipState");
  const primaryNoticeId = readString(value.primaryNoticeId, "$.primaryNoticeId");
  const memberNoticeIds = readUniqueStrings(value.memberNoticeIds, "$.memberNoticeIds");
  if (!memberNoticeIds.includes(primaryNoticeId)) throw new ContractValidationError("$.primaryNoticeId", "must be a memberNoticeId");
  const intents = readEnumArray(value.requestedIntents, DELIVERY_INTENTS, "$.requestedIntents");
  if (intents.length !== memberNoticeIds.length) {
    throw new ContractValidationError("$.requestedIntents", "must contain one intent for each member notice");
  }
  const aggregate = readEnum(value.effectiveDeliveryIntent, DELIVERY_INTENTS, "$.effectiveDeliveryIntent");
  if (aggregate !== effectiveDeliveryIntent(intents)) {
    throw new ContractValidationError("$.effectiveDeliveryIntent", "does not equal the monotonic wake > follow_up > status_only aggregate");
  }
  const operativeActivationConsumedAt = readOptionalTimestamp(value.operativeActivationConsumedAt, "$.operativeActivationConsumedAt");
  readRecipientTransferGeneration(value.recipientTransferGeneration, "$.recipientTransferGeneration");
  const supersedes = readOptionalString(value.supersedesDeliveryGroupId, "$.supersedesDeliveryGroupId");
  const successor = readOptionalString(value.successorDeliveryGroupId, "$.successorDeliveryGroupId");
  const authorityTransitionId = readOptionalString(value.authorityTransitionId, "$.authorityTransitionId");
  const state = readEnum(value.state, DELIVERY_GROUP_STATES, "$.state");
  if (membershipState === "assembling" && state !== "pending") {
    throw new ContractValidationError("$.state", "an assembling group must remain pending");
  }
  if (state !== "pending" && membershipState !== "sealed") {
    throw new ContractValidationError("$.membershipState", "must be sealed before reservation or any later state");
  }
  if ((aggregate === "status_only" || (state !== "inserted" && state !== "delivered")) && operativeActivationConsumedAt !== undefined) {
    throw new ContractValidationError("$.operativeActivationConsumedAt", "requires a receipted non-status operative insertion");
  }
  if (state === "migrated") {
    if (membershipState !== "sealed" || successor === undefined || authorityTransitionId === undefined || supersedes !== undefined) {
      throw new ContractValidationError("$", "a migrated old group requires sealed membership, successor, and authority transition only");
    }
  } else if (successor !== undefined) {
    throw new ContractValidationError("$.successorDeliveryGroupId", "is valid only for a migrated old group");
  }
  if (supersedes !== undefined && authorityTransitionId === undefined) {
    throw new ContractValidationError("$.authorityTransitionId", "is required for a successor group");
  }
  if (authorityTransitionId !== undefined && supersedes === undefined && state !== "migrated") {
    throw new ContractValidationError("$.authorityTransitionId", "requires a migrated or successor group");
  }
  if (supersedes === groupId || successor === groupId) throw new ContractValidationError("$", "a group cannot supersede itself");
  return value as unknown as DeliveryGroupRecord;
}

export interface DeliveryClaimRecord {
  version: typeof DELIVERY_CLAIM_VERSION;
  deliveryClaimId: string;
  deliveryGroupId: string;
  membershipRevision: number;
  effectiveDeliveryIntent: DeliveryIntent;
  primaryNoticeId: string;
  memberNoticeIds: string[];
  claimGeneration: DeliveryClaimGeneration;
  expiresAt: string;
  recipientContext: Exclude<RecipientContext, "headless_cli">;
  recipientSessionId: string;
  recipientTargetSessionId?: string;
  recipientPrincipalId: string;
  recipientBindingEpoch: number;
  recipientTransferGeneration: RecipientTransferGeneration;
  workerId: string;
  workerGeneration: WorkerGeneration;
  transitionId: string;
  transitionVersion: TransitionVersion;
  assignmentId?: string;
  turnId?: string;
  watchdogGeneration?: WatchdogGeneration;
  ingressMode: DeliveryMode;
  state: DeliveryClaimState;
  deliveryAttemptedAt?: string;
  targetLedgerEntryId?: string;
  insertedAt?: string;
  deliveredAt?: string;
  deliveryReceiptId?: string;
  resultMessageId?: string;
  coalescedByResult?: boolean;
  blockedReason?: string;
  releaseProof?: DeliveryClaimReleaseProof;
  releasedAt?: string;
}

export interface DeliveryClaimReleaseProof {
  deliveryClaimId: string;
  claimGeneration: DeliveryClaimGeneration;
  recipientSessionId: string;
  recipientTargetSessionId?: string;
  recipientBindingEpoch: number;
  barrierId: string;
  noSessionEntry: true;
  noAdapterQueue: true;
  noInflightInvocation: true;
  noPiFollowUp: true;
  noOpenCodePendingPrompt: true;
  establishedAt: string;
}

export function parseDeliveryClaimRecord(value: unknown): DeliveryClaimRecord {
  assertRecord(value);
  assertExactKeys(
    value,
    [
      "version",
      "deliveryClaimId",
      "deliveryGroupId",
      "membershipRevision",
      "effectiveDeliveryIntent",
      "primaryNoticeId",
      "memberNoticeIds",
      "claimGeneration",
      "expiresAt",
      "recipientContext",
      "recipientSessionId",
      "recipientPrincipalId",
      "recipientBindingEpoch",
      "recipientTransferGeneration",
      "workerId",
      "workerGeneration",
      "transitionId",
      "transitionVersion",
      "ingressMode",
      "state",
    ],
    [
      "recipientTargetSessionId",
      "assignmentId",
      "turnId",
      "watchdogGeneration",
      "deliveryAttemptedAt",
      "targetLedgerEntryId",
      "insertedAt",
      "deliveredAt",
      "deliveryReceiptId",
      "resultMessageId",
      "coalescedByResult",
      "blockedReason",
      "releaseProof",
      "releasedAt",
    ],
  );
  assertLiteralVersion(value.version, DELIVERY_CLAIM_VERSION, "$.version");
  readString(value.deliveryClaimId, "$.deliveryClaimId");
  readString(value.deliveryGroupId, "$.deliveryGroupId");
  readInteger(value.membershipRevision, "$.membershipRevision", 1);
  readEnum(value.effectiveDeliveryIntent, DELIVERY_INTENTS, "$.effectiveDeliveryIntent");
  const primaryNoticeId = readString(value.primaryNoticeId, "$.primaryNoticeId");
  const memberNoticeIds = readUniqueStrings(value.memberNoticeIds, "$.memberNoticeIds");
  if (!memberNoticeIds.includes(primaryNoticeId)) throw new ContractValidationError("$.primaryNoticeId", "must be a memberNoticeId");
  readDeliveryClaimGeneration(value.claimGeneration, "$.claimGeneration");
  const expiresAt = readTimestamp(value.expiresAt, "$.expiresAt");
  readEnum(value.recipientContext, ["pi", "opencode"] as const, "$.recipientContext");
  readString(value.recipientSessionId, "$.recipientSessionId");
  readOptionalString(value.recipientTargetSessionId, "$.recipientTargetSessionId");
  readString(value.recipientPrincipalId, "$.recipientPrincipalId");
  readInteger(value.recipientBindingEpoch, "$.recipientBindingEpoch", 1);
  readRecipientTransferGeneration(value.recipientTransferGeneration, "$.recipientTransferGeneration");
  readString(value.workerId, "$.workerId");
  readWorkerGeneration(value.workerGeneration, "$.workerGeneration");
  readString(value.transitionId, "$.transitionId");
  readTransitionVersion(value.transitionVersion, "$.transitionVersion");
  readOptionalString(value.assignmentId, "$.assignmentId");
  readOptionalString(value.turnId, "$.turnId");
  if (value.watchdogGeneration !== undefined) readWatchdogGeneration(value.watchdogGeneration, "$.watchdogGeneration");
  const ingressMode = readEnum(value.ingressMode, DELIVERY_MODES, "$.ingressMode");
  const state = readEnum(value.state, DELIVERY_CLAIM_STATES, "$.state");
  const deliveryAttemptedAt = readOptionalTimestamp(value.deliveryAttemptedAt, "$.deliveryAttemptedAt");
  const targetLedgerEntryId = readOptionalString(value.targetLedgerEntryId, "$.targetLedgerEntryId");
  const insertedAt = readOptionalTimestamp(value.insertedAt, "$.insertedAt");
  const deliveredAt = readOptionalTimestamp(value.deliveredAt, "$.deliveredAt");
  const receipt = readOptionalString(value.deliveryReceiptId, "$.deliveryReceiptId");
  const resultMessageId = readOptionalString(value.resultMessageId, "$.resultMessageId");
  const coalescedByResult = readOptionalBoolean(value.coalescedByResult, "$.coalescedByResult");
  const blockedReason = readOptionalString(value.blockedReason, "$.blockedReason");
  const releaseProof = value.releaseProof === undefined ? undefined : parseDeliveryClaimReleaseProof(value.releaseProof);
  const releasedAt = readOptionalTimestamp(value.releasedAt, "$.releasedAt");
  const hasAttempt = deliveryAttemptedAt !== undefined;
  const hasInsertion = targetLedgerEntryId !== undefined || insertedAt !== undefined;
  if (hasInsertion && (targetLedgerEntryId === undefined || insertedAt === undefined || !hasAttempt)) {
    throw new ContractValidationError("$", "target ledger and insertion timestamp require deliveryAttemptedAt and must be present together");
  }
  if (state === "reserved" && (hasAttempt || hasInsertion)) {
    throw new ContractValidationError("$", "reserved claims cannot contain attempt, ledger, or insertion evidence");
  }
  if (state === "inserting" && (!hasAttempt || hasInsertion)) {
    throw new ContractValidationError("$", "inserting claims require only deliveryAttemptedAt");
  }
  if ((state === "inserted" || state === "delivered") && !hasInsertion) {
    throw new ContractValidationError("$", "inserted/delivered claims require attempted, ledger, and insertion evidence");
  }
  if (state === "delivered" && (deliveredAt === undefined || receipt === undefined)) {
    throw new ContractValidationError("$", "delivered claims require deliveredAt and deliveryReceiptId");
  }
  if (state !== "delivered" && (deliveredAt !== undefined || receipt !== undefined)) {
    throw new ContractValidationError("$", "delivery receipt fields are valid only when state is delivered");
  }
  if (state === "blocked" && blockedReason === undefined) throw new ContractValidationError("$.blockedReason", "is required while blocked");
  if (state === "released" && (releasedAt === undefined || releaseProof === undefined)) {
    throw new ContractValidationError("$", "released claims require releasedAt and a drained-barrier releaseProof");
  }
  if (state !== "blocked" && blockedReason !== undefined) throw new ContractValidationError("$.blockedReason", "is only valid while blocked");
  if (state !== "released" && releasedAt !== undefined) throw new ContractValidationError("$.releasedAt", "is only valid when released");
  if (state !== "released" && releaseProof !== undefined) throw new ContractValidationError("$.releaseProof", "is only valid when released");
  if ((state === "blocked" || state === "released") && (hasInsertion || deliveredAt !== undefined || receipt !== undefined)) {
    throw new ContractValidationError("$", "blocked/released claims cannot contain proved insertion or receipt evidence");
  }
  if (releaseProof !== undefined) {
    if (releaseProof.deliveryClaimId !== value.deliveryClaimId) {
      throw new ContractValidationError("$.releaseProof.deliveryClaimId", "must match deliveryClaimId");
    }
    if (releaseProof.claimGeneration !== value.claimGeneration) {
      throw new ContractValidationError("$.releaseProof.claimGeneration", "must match claimGeneration");
    }
    if (releaseProof.recipientSessionId !== value.recipientSessionId) {
      throw new ContractValidationError("$.releaseProof.recipientSessionId", "must match recipientSessionId");
    }
    if (releaseProof.recipientTargetSessionId !== value.recipientTargetSessionId) {
      throw new ContractValidationError("$.releaseProof.recipientTargetSessionId", "must match recipientTargetSessionId exactly");
    }
    if (releaseProof.recipientBindingEpoch !== value.recipientBindingEpoch) {
      throw new ContractValidationError("$.releaseProof.recipientBindingEpoch", "must match recipientBindingEpoch");
    }
    if (releasedAt !== undefined && Date.parse(releasedAt) < Date.parse(releaseProof.establishedAt)) {
      throw new ContractValidationError("$.releasedAt", "must not precede the drained barrier");
    }
    if (deliveryAttemptedAt !== undefined && Date.parse(releaseProof.establishedAt) < Date.parse(deliveryAttemptedAt)) {
      throw new ContractValidationError("$.releaseProof.establishedAt", "must not precede deliveryAttemptedAt");
    }
  }
  if (resultMessageId !== undefined && state !== "delivered") {
    throw new ContractValidationError("$.resultMessageId", "is valid only after delivery");
  }
  if (coalescedByResult !== undefined && state !== "delivered") {
    throw new ContractValidationError("$.coalescedByResult", "is valid only after delivery");
  }
  if (state === "delivered") assertResultCorrelation(ingressMode, "ingressMode", resultMessageId, coalescedByResult);
  if (deliveryAttemptedAt !== undefined && Date.parse(deliveryAttemptedAt) >= Date.parse(expiresAt)) {
    throw new ContractValidationError("$.deliveryAttemptedAt", "must occur before claim expiry");
  }
  if (insertedAt !== undefined && deliveryAttemptedAt !== undefined && Date.parse(insertedAt) < Date.parse(deliveryAttemptedAt)) {
    throw new ContractValidationError("$.insertedAt", "must not precede deliveryAttemptedAt");
  }
  if (deliveredAt !== undefined && insertedAt !== undefined && Date.parse(deliveredAt) < Date.parse(insertedAt)) {
    throw new ContractValidationError("$.deliveredAt", "must not precede insertedAt");
  }
  return value as unknown as DeliveryClaimRecord;
}

export const NOTICE_RECIPIENT_INGRESS_OPERATIONS = [
  "reserve_delivery",
  "lookup_target_ledger",
  "insert_or_attach",
  "record_receipt",
  "prove_target_drained",
  "acknowledge",
] as const;
export type NoticeRecipientIngressOperation = (typeof NOTICE_RECIPIENT_INGRESS_OPERATIONS)[number];

export type NoticeRecipientIngressEnvelope = {
  version: typeof NOTICE_RECIPIENT_INGRESS_VERSION;
  operation: NoticeRecipientIngressOperation;
  requestId: string;
  idempotencyKey: string;
  payload: CanonicalValue;
};

export function parseNoticeRecipientIngressEnvelope(value: unknown): NoticeRecipientIngressEnvelope {
  assertRecord(value);
  assertExactKeys(value, ["version", "operation", "requestId", "idempotencyKey", "payload"]);
  assertLiteralVersion(value.version, NOTICE_RECIPIENT_INGRESS_VERSION, "$.version");
  const operation = readEnum(value.operation, NOTICE_RECIPIENT_INGRESS_OPERATIONS, "$.operation");
  readString(value.requestId, "$.requestId");
  readString(value.idempotencyKey, "$.idempotencyKey");
  parseIngressPayload(operation, value.payload);
  return value as unknown as NoticeRecipientIngressEnvelope;
}

export const TARGET_LEDGER_STATES = ["absent", "inserting", "inserted", "ambiguous"] as const;
export interface TargetLedgerLookupResult {
  version: typeof TARGET_LEDGER_RESULT_VERSION;
  deliveryClaimId: string;
  claimGeneration: DeliveryClaimGeneration;
  state: (typeof TARGET_LEDGER_STATES)[number];
  checkedAt: string;
  targetLedgerEntryId?: string;
  insertedAt?: string;
}

export function parseTargetLedgerLookupResult(value: unknown): TargetLedgerLookupResult {
  assertRecord(value);
  assertExactKeys(value, ["version", "deliveryClaimId", "claimGeneration", "state", "checkedAt"], ["targetLedgerEntryId", "insertedAt"]);
  assertLiteralVersion(value.version, TARGET_LEDGER_RESULT_VERSION, "$.version");
  readString(value.deliveryClaimId, "$.deliveryClaimId");
  readDeliveryClaimGeneration(value.claimGeneration, "$.claimGeneration");
  const state = readEnum(value.state, TARGET_LEDGER_STATES, "$.state");
  const checkedAt = readTimestamp(value.checkedAt, "$.checkedAt");
  const ledgerId = readOptionalString(value.targetLedgerEntryId, "$.targetLedgerEntryId");
  const insertedAt = readOptionalTimestamp(value.insertedAt, "$.insertedAt");
  if (state === "inserted" && (ledgerId === undefined || insertedAt === undefined)) {
    throw new ContractValidationError("$", "ledger evidence is required when state is inserted");
  }
  if (state !== "inserted" && (ledgerId !== undefined || insertedAt !== undefined)) {
    throw new ContractValidationError("$", "ledger evidence is valid only when state is inserted");
  }
  if (insertedAt !== undefined && Date.parse(checkedAt) < Date.parse(insertedAt)) {
    throw new ContractValidationError("$.checkedAt", "must not precede insertedAt");
  }
  return value as unknown as TargetLedgerLookupResult;
}

export const validateBossParticipantBindingStore = (value: unknown): StoreValidationResult<BossParticipantBinding> =>
  validateVersionedStoreRecord(value, BOSS_PARTICIPANT_BINDING_VERSION, parseBossParticipantBinding);
export const validateBossCredentialDigestStore = (value: unknown): StoreValidationResult<BossCredentialDigestRecord> =>
  validateVersionedStoreRecord(value, BOSS_CREDENTIAL_DIGEST_RECORD_VERSION, parseBossCredentialDigestRecord);
export const validateAuthorityTransitionStore = (value: unknown): StoreValidationResult<AuthorityTransitionRecord> =>
  validateVersionedStoreRecord(value, AUTHORITY_TRANSITION_VERSION, parseAuthorityTransitionRecord);
export const validateAuthorityEventStore = (value: unknown): StoreValidationResult<AuthorityTransitionEvent> =>
  validateVersionedStoreRecord(value, AUTHORITY_EVENT_VERSION, parseAuthorityTransitionEvent);
export const validateLifecycleNoticeStore = (value: unknown): StoreValidationResult<LifecycleNotice> =>
  validateVersionedStoreRecord(value, LIFECYCLE_NOTICE_VERSION, parseLifecycleNotice);
export const validateDeliveryGroupStore = (value: unknown): StoreValidationResult<DeliveryGroupRecord> =>
  validateVersionedStoreRecord(value, DELIVERY_GROUP_VERSION, parseDeliveryGroupRecord);
export const validateDeliveryClaimStore = (value: unknown): StoreValidationResult<DeliveryClaimRecord> =>
  validateVersionedStoreRecord(value, DELIVERY_CLAIM_VERSION, parseDeliveryClaimRecord);
export const validateTargetLedgerStore = (value: unknown): StoreValidationResult<TargetLedgerLookupResult> =>
  validateVersionedStoreRecord(value, TARGET_LEDGER_RESULT_VERSION, parseTargetLedgerLookupResult);

function parseLifecycleNoticeLogicalKey(value: unknown, path = "$"): LifecycleNoticeLogicalKey {
  assertRecord(value, path);
  assertExactKeys(
    value,
    ["workerId", "workerGeneration", "transitionId", "transitionVersion", "kind"],
    ["assignmentId", "watchdogGeneration", "subscriptionId", "subscriptionTriggerGeneration"],
    path,
  );
  readIdentifier(value.workerId, `${path}.workerId`);
  readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`);
  readIdentifier(value.transitionId, `${path}.transitionId`);
  readTransitionVersion(value.transitionVersion, `${path}.transitionVersion`);
  readIdentifier(value.kind, `${path}.kind`);
  readOptionalIdentifier(value.assignmentId, `${path}.assignmentId`);
  if (value.watchdogGeneration !== undefined) readWatchdogGeneration(value.watchdogGeneration, `${path}.watchdogGeneration`);
  const subscriptionId = readOptionalIdentifier(value.subscriptionId, `${path}.subscriptionId`);
  const triggerGeneration = value.subscriptionTriggerGeneration === undefined
    ? undefined
    : readTriggerGeneration(value.subscriptionTriggerGeneration, `${path}.subscriptionTriggerGeneration`, 1);
  if ((subscriptionId === undefined) !== (triggerGeneration === undefined)) {
    throw new ContractValidationError(path, "subscriptionId and subscriptionTriggerGeneration must be present together");
  }
  return value as unknown as LifecycleNoticeLogicalKey;
}

export function parseDeliveryEquivalenceKey(value: unknown, path = "$"): DeliveryEquivalenceKey {
  assertRecord(value, path);
  assertExactKeys(
    value,
    [
      "recipientPrincipalId",
      "recipientBindingEpoch",
      "sourceAuthorityId",
      "sourceEventId",
      "workerId",
      "workerGeneration",
      "transitionId",
      "transitionVersion",
    ],
    ["bossRunId", "assignmentId", "turnId", "watchdogGeneration"],
    path,
  );
  readIdentifier(value.recipientPrincipalId, `${path}.recipientPrincipalId`);
  readInteger(value.recipientBindingEpoch, `${path}.recipientBindingEpoch`, 1);
  const sourceAuthorityId = parseSourceAuthorityId(value.sourceAuthorityId, `${path}.sourceAuthorityId`);
  readIdentifier(value.sourceEventId, `${path}.sourceEventId`);
  const bossRunId = readOptionalIdentifier(value.bossRunId, `${path}.bossRunId`);
  if (sourceAuthorityId.kind === "controller") {
    if (bossRunId === undefined) {
      throw new ContractValidationError(`${path}.bossRunId`, "is required for a controller source authority");
    }
    if (sourceAuthorityId.bossRunId !== bossRunId) {
      throw new ContractValidationError(
        `${path}.sourceAuthorityId.bossRunId`,
        "must exactly match bossRunId for a controller source authority",
      );
    }
  }
  readIdentifier(value.workerId, `${path}.workerId`);
  readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`);
  readIdentifier(value.transitionId, `${path}.transitionId`);
  readTransitionVersion(value.transitionVersion, `${path}.transitionVersion`);
  readOptionalIdentifier(value.assignmentId, `${path}.assignmentId`);
  readOptionalIdentifier(value.turnId, `${path}.turnId`);
  if (value.watchdogGeneration !== undefined) readWatchdogGeneration(value.watchdogGeneration, `${path}.watchdogGeneration`);
  return value as unknown as DeliveryEquivalenceKey;
}

function parseSourceAuthorityId(value: unknown, path: string): SourceAuthorityId {
  assertRecord(value, path);
  const kind = readEnum(value.kind, ["worker_store", "controller", "orc_scheduler"] as const, `${path}.kind`);
  if (kind === "worker_store") {
    assertExactKeys(value, ["kind", "workerStoreId", "journalGeneration"], [], path);
    return {
      kind,
      workerStoreId: readIdentifier(value.workerStoreId, `${path}.workerStoreId`),
      journalGeneration: readJournalGeneration(value.journalGeneration, `${path}.journalGeneration`),
    };
  }
  if (kind === "controller") {
    assertExactKeys(value, ["kind", "bossRunId", "controllerGeneration"], [], path);
    return {
      kind,
      bossRunId: readIdentifier(value.bossRunId, `${path}.bossRunId`),
      controllerGeneration: readControllerGeneration(value.controllerGeneration, `${path}.controllerGeneration`),
    };
  }
  assertExactKeys(value, ["kind", "ownerUid", "schedulerGeneration"], [], path);
  return {
    kind,
    ownerUid: readInteger(value.ownerUid, `${path}.ownerUid`),
    schedulerGeneration: readSchedulerGeneration(value.schedulerGeneration, `${path}.schedulerGeneration`),
  };
}

function parseIngressPayload(operation: NoticeRecipientIngressOperation, value: unknown): void {
  assertRecord(value, "$.payload");
  const path = "$.payload";
  if (operation === "reserve_delivery") {
    assertExactKeys(value, [
      "deliveryGroupId",
      "membershipRevision",
      "effectiveDeliveryIntent",
      "primaryNoticeId",
      "memberNoticeIds",
      "recipientContext",
      "recipientSessionId",
      "recipientPrincipalId",
      "recipientBindingEpoch",
      "recipientTransferGeneration",
      "workerGeneration",
      "requestedAt",
    ], ["recipientTargetSessionId"], path);
    readString(value.deliveryGroupId, `${path}.deliveryGroupId`);
    readInteger(value.membershipRevision, `${path}.membershipRevision`, 1);
    readEnum(value.effectiveDeliveryIntent, DELIVERY_INTENTS, `${path}.effectiveDeliveryIntent`);
    validatePrimaryAndMembers(value.primaryNoticeId, value.memberNoticeIds, path);
    readEnum(value.recipientContext, ["pi", "opencode"] as const, `${path}.recipientContext`);
    readString(value.recipientSessionId, `${path}.recipientSessionId`);
    readOptionalString(value.recipientTargetSessionId, `${path}.recipientTargetSessionId`);
    readString(value.recipientPrincipalId, `${path}.recipientPrincipalId`);
    readInteger(value.recipientBindingEpoch, `${path}.recipientBindingEpoch`, 1);
    readRecipientTransferGeneration(value.recipientTransferGeneration, `${path}.recipientTransferGeneration`);
    readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`);
    readTimestamp(value.requestedAt, `${path}.requestedAt`);
    return;
  }
  if (operation === "lookup_target_ledger") {
    assertExactKeys(value, ["deliveryClaimId", "claimGeneration", "recipientContext", "recipientSessionId", "checkedAt"], ["recipientTargetSessionId"], path);
    readClaimIdentity(value, path);
    readEnum(value.recipientContext, ["pi", "opencode"] as const, `${path}.recipientContext`);
    readString(value.recipientSessionId, `${path}.recipientSessionId`);
    readOptionalString(value.recipientTargetSessionId, `${path}.recipientTargetSessionId`);
    readTimestamp(value.checkedAt, `${path}.checkedAt`);
    return;
  }
  if (operation === "insert_or_attach") {
    assertExactKeys(value, [
      "deliveryClaimId",
      "claimGeneration",
      "deliveryGroupId",
      "membershipRevision",
      "effectiveDeliveryIntent",
      "primaryNoticeId",
      "memberNoticeIds",
      "transitionIds",
      "recipientPrincipalId",
      "recipientBindingEpoch",
      "workerGeneration",
      "ingressMode",
      "requestedAt",
    ], ["resultMessageId"], path);
    readClaimIdentity(value, path);
    readString(value.deliveryGroupId, `${path}.deliveryGroupId`);
    readInteger(value.membershipRevision, `${path}.membershipRevision`, 1);
    readEnum(value.effectiveDeliveryIntent, DELIVERY_INTENTS, `${path}.effectiveDeliveryIntent`);
    validatePrimaryAndMembers(value.primaryNoticeId, value.memberNoticeIds, path);
    readUniqueStrings(value.transitionIds, `${path}.transitionIds`);
    readString(value.recipientPrincipalId, `${path}.recipientPrincipalId`);
    readInteger(value.recipientBindingEpoch, `${path}.recipientBindingEpoch`, 1);
    readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`);
    const ingressMode = readEnum(value.ingressMode, DELIVERY_MODES, `${path}.ingressMode`);
    const resultMessageId = readOptionalString(value.resultMessageId, `${path}.resultMessageId`);
    assertResultCorrelation(ingressMode, "ingressMode", resultMessageId, undefined, path);
    readTimestamp(value.requestedAt, `${path}.requestedAt`);
    return;
  }
  if (operation === "record_receipt") {
    assertExactKeys(value, [
      "deliveryClaimId",
      "claimGeneration",
      "deliveryGroupId",
      "membershipRevision",
      "recipientPrincipalId",
      "recipientBindingEpoch",
      "workerGeneration",
      "deliveryReceiptId",
      "targetLedgerEntryId",
      "deliveryMode",
      "insertedAt",
      "deliveredAt",
    ], ["resultMessageId", "coalescedByResult"], path);
    readClaimIdentity(value, path);
    readString(value.deliveryGroupId, `${path}.deliveryGroupId`);
    readInteger(value.membershipRevision, `${path}.membershipRevision`, 1);
    readString(value.recipientPrincipalId, `${path}.recipientPrincipalId`);
    readInteger(value.recipientBindingEpoch, `${path}.recipientBindingEpoch`, 1);
    readWorkerGeneration(value.workerGeneration, `${path}.workerGeneration`);
    readString(value.deliveryReceiptId, `${path}.deliveryReceiptId`);
    readString(value.targetLedgerEntryId, `${path}.targetLedgerEntryId`);
    const deliveryMode = readEnum(value.deliveryMode, DELIVERY_MODES, `${path}.deliveryMode`);
    const insertedAt = readTimestamp(value.insertedAt, `${path}.insertedAt`);
    const deliveredAt = readTimestamp(value.deliveredAt, `${path}.deliveredAt`);
    const resultMessageId = readOptionalString(value.resultMessageId, `${path}.resultMessageId`);
    const coalescedByResult = readOptionalBoolean(value.coalescedByResult, `${path}.coalescedByResult`);
    if (Date.parse(deliveredAt) < Date.parse(insertedAt)) {
      throw new ContractValidationError(`${path}.deliveredAt`, "must not precede insertedAt");
    }
    assertResultCorrelation(deliveryMode, "deliveryMode", resultMessageId, coalescedByResult, path);
    return;
  }
  if (operation === "prove_target_drained") {
    assertExactKeys(value, [
      "deliveryClaimId",
      "claimGeneration",
      "recipientSessionId",
      "recipientBindingEpoch",
      "barrierId",
      "noSessionEntry",
      "noAdapterQueue",
      "noInflightInvocation",
      "noPiFollowUp",
      "noOpenCodePendingPrompt",
      "establishedAt",
    ], ["recipientTargetSessionId"], path);
    readClaimIdentity(value, path);
    readString(value.recipientSessionId, `${path}.recipientSessionId`);
    readOptionalString(value.recipientTargetSessionId, `${path}.recipientTargetSessionId`);
    readInteger(value.recipientBindingEpoch, `${path}.recipientBindingEpoch`, 1);
    readString(value.barrierId, `${path}.barrierId`);
    for (const key of ["noSessionEntry", "noAdapterQueue", "noInflightInvocation", "noPiFollowUp", "noOpenCodePendingPrompt"] as const) {
      if (!readBoolean(value[key], `${path}.${key}`)) throw new ContractValidationError(`${path}.${key}`, "must be true to prove absence");
    }
    readTimestamp(value.establishedAt, `${path}.establishedAt`);
    return;
  }
  assertExactKeys(value, ["deliveryGroupId", "noticeIds", "recipientPrincipalId", "acknowledgedAt"], ["recipientBindingEpoch"], path);
  readString(value.deliveryGroupId, `${path}.deliveryGroupId`);
  readUniqueStrings(value.noticeIds, `${path}.noticeIds`);
  readString(value.recipientPrincipalId, `${path}.recipientPrincipalId`);
  readOptionalInteger(value.recipientBindingEpoch, `${path}.recipientBindingEpoch`, 1);
  readTimestamp(value.acknowledgedAt, `${path}.acknowledgedAt`);
}

function parseDeliveryClaimReleaseProof(value: unknown): DeliveryClaimReleaseProof {
  const path = "$.releaseProof";
  assertRecord(value, path);
  assertExactKeys(value, [
    "deliveryClaimId",
    "claimGeneration",
    "recipientSessionId",
    "recipientBindingEpoch",
    "barrierId",
    "noSessionEntry",
    "noAdapterQueue",
    "noInflightInvocation",
    "noPiFollowUp",
    "noOpenCodePendingPrompt",
    "establishedAt",
  ], ["recipientTargetSessionId"], path);
  readClaimIdentity(value, path);
  readString(value.recipientSessionId, `${path}.recipientSessionId`);
  readOptionalString(value.recipientTargetSessionId, `${path}.recipientTargetSessionId`);
  readInteger(value.recipientBindingEpoch, `${path}.recipientBindingEpoch`, 1);
  readString(value.barrierId, `${path}.barrierId`);
  for (const key of ["noSessionEntry", "noAdapterQueue", "noInflightInvocation", "noPiFollowUp", "noOpenCodePendingPrompt"] as const) {
    if (!readBoolean(value[key], `${path}.${key}`)) {
      throw new ContractValidationError(`${path}.${key}`, "must be true to prove absence");
    }
  }
  readTimestamp(value.establishedAt, `${path}.establishedAt`);
  return value as unknown as DeliveryClaimReleaseProof;
}

function parseAuthorityTransitionTarget(value: unknown, path: string): AuthorityTransitionTarget {
  assertRecord(value, path);
  assertExactKeys(
    value,
    [],
    ["bossRunId", "participantId", "replacementParticipantId", "controllerPrincipalId", "credentialId", "subscriberPrincipalId"],
    path,
  );
  readOptionalString(value.bossRunId, `${path}.bossRunId`);
  readOptionalString(value.participantId, `${path}.participantId`);
  readOptionalString(value.replacementParticipantId, `${path}.replacementParticipantId`);
  readOptionalString(value.controllerPrincipalId, `${path}.controllerPrincipalId`);
  readOptionalString(value.credentialId, `${path}.credentialId`);
  readOptionalString(value.subscriberPrincipalId, `${path}.subscriberPrincipalId`);
  return value as unknown as AuthorityTransitionTarget;
}

function parseBossCredentialUseContext(value: unknown): BossCredentialUseContext {
  assertRecord(value);
  assertExactKeys(value, ["now", "credentialKind", "bossRunId", "participantId", "role", "bindingEpoch", "nonce"]);
  readTimestamp(value.now, "$.now");
  readEnum(value.credentialKind, BOSS_CREDENTIAL_KINDS, "$.credentialKind");
  readString(value.bossRunId, "$.bossRunId");
  readString(value.participantId, "$.participantId");
  readEnum(value.role, BOSS_PARTICIPANT_ROLES, "$.role");
  readParticipantBindingEpoch(value.bindingEpoch, "$.bindingEpoch");
  readString(value.nonce, "$.nonce");
  return value as unknown as BossCredentialUseContext;
}

function parseAuthorityTransitionEpochs(value: unknown, path: string, minimum: 0 | 1): AuthorityTransitionEpochs {
  assertRecord(value, path);
  assertExactKeys(value, [], ["controllerGeneration", "bossBindingEpoch", "participantBindingEpoch", "subscriberBindingEpoch"], path);
  const controller = value.controllerGeneration === undefined ? undefined : readControllerGeneration(value.controllerGeneration, `${path}.controllerGeneration`, minimum);
  const boss = value.bossBindingEpoch === undefined ? undefined : readBossBindingEpoch(value.bossBindingEpoch, `${path}.bossBindingEpoch`, minimum);
  const participant = value.participantBindingEpoch === undefined ? undefined : readParticipantBindingEpoch(value.participantBindingEpoch, `${path}.participantBindingEpoch`, minimum);
  const subscriber = value.subscriberBindingEpoch === undefined ? undefined : readSubscriberBindingEpoch(value.subscriberBindingEpoch, `${path}.subscriberBindingEpoch`, minimum);
  if (controller === undefined && boss === undefined && participant === undefined && subscriber === undefined) {
    throw new ContractValidationError(path, "must contain at least one generation or epoch");
  }
  return value as unknown as AuthorityTransitionEpochs;
}

function validateAuthorityEpochChange(
  operation: AuthorityTransitionOperation,
  target: AuthorityTransitionTarget,
  prior: AuthorityTransitionEpochs,
  proposed: AuthorityTransitionEpochs,
): void {
  const required = authorityEpochField(operation);
  validateAuthorityPriorEpoch(operation, prior, "$.prior");
  if (prior[required] === undefined || proposed[required] === undefined || proposed[required]! <= prior[required]!) {
    throw new ContractValidationError(`$.proposed.${required}`, `must monotonically increase ${required}`);
  }
  validateAuthorityTarget(operation, target);
  for (const field of ["controllerGeneration", "bossBindingEpoch", "participantBindingEpoch", "subscriberBindingEpoch"] as const) {
    const before = prior[field];
    const after = proposed[field];
    if ((before === undefined) !== (after === undefined)) {
      throw new ContractValidationError(`$.proposed.${field}`, "must be paired with the prior value");
    }
    if (field !== required && before !== undefined && after !== before) {
      throw new ContractValidationError(`$.proposed.${field}`, "unaffected authority dimensions must remain unchanged");
    }
  }
}

function validateAuthorityPriorEpoch(
  operation: AuthorityTransitionOperation,
  prior: AuthorityTransitionEpochs,
  path: string,
): void {
  const required = authorityEpochField(operation);
  const priorEpoch = prior[required];
  if (priorEpoch === undefined) throw new ContractValidationError(`${path}.${required}`, `is required for ${operation}`);
  if ((operation === "bind_boss" || operation === "bind_participant") && priorEpoch !== 0) {
    throw new ContractValidationError(`${path}.${required}`, `must be exactly 0 for initial ${operation}`);
  }
  if (operation !== "bind_boss" && operation !== "bind_participant" && priorEpoch < 1) {
    throw new ContractValidationError(`${path}.${required}`, `must be positive for ${operation}`);
  }
}

function authorityEpochField(operation: AuthorityTransitionOperation): keyof AuthorityTransitionEpochs {
  if (operation === "controller_takeover") return "controllerGeneration";
  if (operation === "bind_boss" || operation === "rebind_boss" || operation === "revoke_boss") return "bossBindingEpoch";
  if (operation === "rebind_subscriber") return "subscriberBindingEpoch";
  return "participantBindingEpoch";
}

function validateAuthorityTarget(operation: AuthorityTransitionOperation, target: AuthorityTransitionTarget, path = "$.target"): void {
  if (operation !== "rebind_subscriber" && target.bossRunId === undefined) {
    throw new ContractValidationError(`${path}.bossRunId`, `is required for ${operation}`);
  }
  if (authorityEpochField(operation) === "participantBindingEpoch" && target.participantId === undefined) {
    throw new ContractValidationError(`${path}.participantId`, `is required for ${operation}`);
  }
  if (operation === "replace_participant" || operation === "replace_manager") {
    if (target.replacementParticipantId === undefined) {
      throw new ContractValidationError(`${path}.replacementParticipantId`, `is required for ${operation}`);
    }
  }
  if (operation === "controller_takeover" && target.controllerPrincipalId === undefined) {
    throw new ContractValidationError(`${path}.controllerPrincipalId`, "is required for controller_takeover");
  }
  if (operation === "rotate_credential" && target.credentialId === undefined) {
    throw new ContractValidationError(`${path}.credentialId`, "is required for rotate_credential");
  }
  if (operation === "rebind_subscriber" && target.subscriberPrincipalId === undefined) {
    throw new ContractValidationError(`${path}.subscriberPrincipalId`, "is required for rebind_subscriber");
  }
  const allowedByOperation: Record<AuthorityTransitionOperation, readonly (keyof AuthorityTransitionTarget)[]> = {
    bind_boss: [],
    rebind_boss: [],
    revoke_boss: [],
    bind_participant: ["participantId"],
    rebind_participant: ["participantId"],
    revoke_participant: ["participantId"],
    replace_participant: ["participantId", "replacementParticipantId"],
    replace_manager: ["participantId", "replacementParticipantId"],
    rebind_subscriber: ["bossRunId", "subscriberPrincipalId"],
    controller_takeover: ["controllerPrincipalId"],
    rotate_credential: ["participantId", "credentialId"],
  };
  const allowed = new Set<keyof AuthorityTransitionTarget>(["bossRunId", ...allowedByOperation[operation]]);
  for (const key of ["participantId", "replacementParticipantId", "controllerPrincipalId", "credentialId", "subscriberPrincipalId"] as const) {
    if (target[key] !== undefined && !allowed.has(key)) {
      throw new ContractValidationError(`${path}.${key}`, `is not valid for ${operation}`);
    }
  }
}

function timestampMillis(value: string): number {
  return Date.parse(value);
}

function assertLiteralVersion(value: unknown, expected: string, path: string): void {
  if (value !== expected) throw new ContractValidationError(path, `unsupported version: ${String(value)}; expected ${expected}`);
}

function assertWireValue(value: unknown, path: string): asserts value is CanonicalValue {
  canonicalJson(value);
  rejectUndefined(value, path);
}

function rejectUndefined(value: unknown, path: string): void {
  if (Array.isArray(value)) {
    value.forEach((entry, index) => rejectUndefined(entry, `${path}[${index}]`));
    return;
  }
  if (typeof value === "object" && value !== null) {
    for (const [key, entry] of Object.entries(value)) {
      if (entry === undefined) throw new ContractValidationError(`${path}.${key}`, "undefined is not valid on the wire");
      rejectUndefined(entry, `${path}.${key}`);
    }
  }
}

function readDenseOwnDataArray(value: unknown, path: string): unknown[] {
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

  const entries: unknown[] = [];
  for (let index = 0; index < length; index += 1) entries.push(descriptors.get(index)!.value);
  return entries;
}

function readEnumArray<const T extends readonly string[]>(value: unknown, allowed: T, path: string): T[number][] {
  const entries = readDenseOwnDataArray(value, path);
  if (entries.length === 0) throw new ContractValidationError(path, "must be a non-empty array");
  return entries.map((entry, index) => readEnum(entry, allowed, `${path}[${index}]`));
}

function readUniqueStrings(value: unknown, path: string): string[] {
  const entries = readStringArray(value, path);
  if (entries.length === 0) throw new ContractValidationError(path, "must not be empty");
  if (new Set(entries).size !== entries.length) throw new ContractValidationError(path, "must not contain duplicates");
  return entries;
}

function validatePrimaryAndMembers(primaryValue: unknown, membersValue: unknown, path: string): void {
  const primary = readString(primaryValue, `${path}.primaryNoticeId`);
  const members = readUniqueStrings(membersValue, `${path}.memberNoticeIds`);
  if (!members.includes(primary)) throw new ContractValidationError(`${path}.primaryNoticeId`, "must be a memberNoticeId");
}

function readClaimIdentity(value: Record<string, unknown>, path: string): void {
  readString(value.deliveryClaimId, `${path}.deliveryClaimId`);
  readDeliveryClaimGeneration(value.claimGeneration, `${path}.claimGeneration`);
}
