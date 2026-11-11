import {
  assertExactKeys,
  assertRecord,
  ContractValidationError,
  participantBindingEpoch,
  readBoolean,
  readEnum,
  readHexDigest,
  readIdentifier,
  readInteger,
  readString,
  type ParticipantBindingEpoch,
} from "./canonical.ts";
import {
  authorize,
  isAncestor,
  isDirectParentPair,
  type AuthorizationContext,
  type AuthorizationDecision,
  type PolicyAction,
  type PolicyState,
} from "./policy.ts";
import {
  authorizeBossPolicy,
  BOSS_CONTROL_KINDS,
  BOSS_POLICY_ACTIONS,
  parseBossPolicyPrincipal,
  type BossAuthorizationContext,
  type BossAuthorizationDecision,
  type BossPolicyPrincipal,
  type BossPolicyAction,
  type BossPolicyState,
} from "./boss-policy.ts";
import { BOSS_POLICY_SEMANTICS_HASH } from "./boss-policy-vectors.ts";
import {
  BOSS_CAPABILITY_FEATURE_DIGEST,
  BOSS_RUN_FEATURE_CONTRACT,
  parseBossRunFeatureContract,
  type BossRunFeatureContract,
} from "./boss-wire.ts";

export const LEGACY_POLICY_ACTIONS: readonly PolicyAction[] = [
  "discover", "send", "ask", "reply", "inspect_tree", "delegate_child", "revoke", "adopt",
] as const;
export type FeatureRegistrationState = "active" | "credential_only" | "unbound" | "revoked" | "replaced" | "ended";

export interface OrdinaryFeatureRegistration {
  principalId: string;
  principalClass: "ordinary";
  state: "active" | "revoked" | "ended";
}
export interface BossFeatureRegistration {
  principalId: string;
  principalClass: "boss-bound";
  state: FeatureRegistrationState;
  bossRunId: string;
  participantId: string;
  bindingEpoch: ParticipantBindingEpoch;
  featureContract: BossRunFeatureContract;
  policySemanticsHash: string;
  capabilityDigest: string;
  brokerIdentityVerified: boolean;
}
export type FeatureRegistration = OrdinaryFeatureRegistration | BossFeatureRegistration;

export interface FeatureAwarePolicyState {
  legacy: PolicyState;
  boss: BossPolicyState;
  registrations: Record<string, FeatureRegistration>;
}
export interface FeatureAwareAuthorizationRequest {
  actorId: string;
  targetId: string;
  action: PolicyAction | BossPolicyAction;
  legacyContext?: AuthorizationContext;
  bossContext?: BossAuthorizationContext;
}
export type FeatureAwareAuthorizationDecision =
  | AuthorizationDecision
  | BossAuthorizationDecision
  | {
      allowed: false;
      code:
        | "UNKNOWN_REGISTRATION"
        | "FEATURE_CLASS_DENIED"
        | "BINDING_INACTIVE"
        | "FEATURE_ATTESTATION_DENIED"
        | "ACTION_NAMESPACE_DENIED"
        | "CONTEXT_NAMESPACE_DENIED";
    };

const FEATURE_REGISTRATION_STATES = ["active", "credential_only", "unbound", "revoked", "replaced", "ended"] as const;
const ORDINARY_REGISTRATION_STATES = ["active", "revoked", "ended"] as const;

/** Exact parser for the broker's authoritative, principal-class-discriminated registration. */
export function parseFeatureRegistration(value: unknown, path = "$"): FeatureRegistration {
  assertRecord(value, path);
  const principalClass = readEnum(value.principalClass, ["ordinary", "boss-bound"] as const, `${path}.principalClass`);
  if (principalClass === "ordinary") {
    assertExactKeys(value, ["principalId", "principalClass", "state"], [], path);
    return {
      principalId: readIdentifier(value.principalId, `${path}.principalId`),
      principalClass,
      state: readEnum(value.state, ORDINARY_REGISTRATION_STATES, `${path}.state`),
    };
  }
  assertExactKeys(value, [
    "principalId",
    "principalClass",
    "state",
    "bossRunId",
    "participantId",
    "bindingEpoch",
    "featureContract",
    "policySemanticsHash",
    "capabilityDigest",
    "brokerIdentityVerified",
  ], [], path);
  return {
    principalId: readIdentifier(value.principalId, `${path}.principalId`),
    principalClass,
    state: readEnum(value.state, FEATURE_REGISTRATION_STATES, `${path}.state`),
    bossRunId: readIdentifier(value.bossRunId, `${path}.bossRunId`),
    participantId: readIdentifier(value.participantId, `${path}.participantId`),
    bindingEpoch: participantBindingEpoch(value.bindingEpoch, `${path}.bindingEpoch`),
    featureContract: parseBossRunFeatureContract(value.featureContract),
    policySemanticsHash: readHexDigest(value.policySemanticsHash, `${path}.policySemanticsHash`),
    capabilityDigest: readHexDigest(value.capabilityDigest, `${path}.capabilityDigest`),
    brokerIdentityVerified: readBoolean(value.brokerIdentityVerified, `${path}.brokerIdentityVerified`),
  };
}

function parseLegacyAuthorizationContext(value: unknown, path: string): AuthorizationContext {
  assertRecord(value, path);
  assertExactKeys(value, [], ["actorGeneration", "targetGeneration"], path);
  const actorGeneration = value.actorGeneration === undefined
    ? undefined
    : readInteger(value.actorGeneration, `${path}.actorGeneration`, 1);
  const targetGeneration = value.targetGeneration === undefined
    ? undefined
    : readInteger(value.targetGeneration, `${path}.targetGeneration`, 1);
  return {
    ...(actorGeneration === undefined ? {} : { actorGeneration }),
    ...(targetGeneration === undefined ? {} : { targetGeneration }),
  };
}

function parseBossAuthorizationContext(value: unknown, path: string): BossAuthorizationContext {
  assertRecord(value, path);
  assertExactKeys(value, [], ["actorBindingEpoch", "targetBindingEpoch", "controlKind", "correlated"], path);
  const actorBindingEpoch = value.actorBindingEpoch === undefined
    ? undefined
    : participantBindingEpoch(value.actorBindingEpoch, `${path}.actorBindingEpoch`);
  const targetBindingEpoch = value.targetBindingEpoch === undefined
    ? undefined
    : participantBindingEpoch(value.targetBindingEpoch, `${path}.targetBindingEpoch`);
  const controlKind = value.controlKind === undefined
    ? undefined
    : readEnum(value.controlKind, BOSS_CONTROL_KINDS, `${path}.controlKind`);
  const correlated = value.correlated === undefined
    ? undefined
    : readBoolean(value.correlated, `${path}.correlated`);
  return {
    ...(actorBindingEpoch === undefined ? {} : { actorBindingEpoch }),
    ...(targetBindingEpoch === undefined ? {} : { targetBindingEpoch }),
    ...(controlKind === undefined ? {} : { controlKind }),
    ...(correlated === undefined ? {} : { correlated }),
  };
}

/** Exact parser for routing requests; feature-class selection remains exclusively registration-derived. */
export function parseFeatureAwareAuthorizationRequest(value: unknown): FeatureAwareAuthorizationRequest {
  assertRecord(value);
  assertExactKeys(value, ["actorId", "targetId", "action"], ["legacyContext", "bossContext"]);
  const legacyContext = value.legacyContext === undefined
    ? undefined
    : parseLegacyAuthorizationContext(value.legacyContext, "$.legacyContext");
  const bossContext = value.bossContext === undefined
    ? undefined
    : parseBossAuthorizationContext(value.bossContext, "$.bossContext");
  return {
    actorId: readIdentifier(value.actorId, "$.actorId"),
    targetId: readIdentifier(value.targetId, "$.targetId"),
    // Namespace membership is deliberately authorized only after the
    // authoritative registration class has selected the policy kernel.
    action: readString(value.action, "$.action") as PolicyAction | BossPolicyAction,
    ...(legacyContext === undefined ? {} : { legacyContext }),
    ...(bossContext === undefined ? {} : { bossContext }),
  };
}

function registrationIsActive(registration: FeatureRegistration): boolean {
  return registration.state === "active";
}

function bossRegistrationAttested(registration: BossFeatureRegistration): boolean {
  return registration.featureContract.semanticsHash === BOSS_RUN_FEATURE_CONTRACT.semanticsHash
    && registration.policySemanticsHash === BOSS_POLICY_SEMANTICS_HASH
    && registration.capabilityDigest === BOSS_CAPABILITY_FEATURE_DIGEST
    && registration.brokerIdentityVerified;
}

type RegistrationLookup =
  | { status: "missing" }
  | { status: "invalid" }
  | { status: "valid"; registration: FeatureRegistration };

function registrationPath(principalId: string): string {
  return `$.registrations[${JSON.stringify(principalId)}]`;
}

type OwnEnumerableDataDescriptor = PropertyDescriptor & { value: unknown };

function ownEnumerableDataDescriptor(value: object, key: PropertyKey): OwnEnumerableDataDescriptor | undefined {
  const descriptor = Object.getOwnPropertyDescriptor(value, key);
  return descriptor !== undefined && descriptor.enumerable && Object.hasOwn(descriptor, "value")
    ? descriptor as OwnEnumerableDataDescriptor
    : undefined;
}

/**
 * Snapshot a plain string-key record from descriptors only. This is the
 * additive boundary's container check: values are copied without reading a
 * property through the source object, and entry semantics are deferred until
 * the selected actor/target is known.
 */
function projectPlainDataRecord(value: unknown, allowCustomPrototype = false): Record<string, unknown> | undefined {
  const prototype = typeof value === "object" && value !== null
    ? Object.getPrototypeOf(value)
    : undefined;
  if (
    typeof value !== "object"
    || value === null
    || Array.isArray(value)
    || (!allowCustomPrototype && prototype !== Object.prototype)
  ) return undefined;

  const projected = Object.create(Object.prototype) as Record<string, unknown>;
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string") return undefined;
    const descriptor = ownEnumerableDataDescriptor(value, key);
    if (descriptor === undefined) return undefined;
    Object.defineProperty(projected, key, {
      configurable: true,
      enumerable: true,
      value: descriptor.value,
      writable: true,
    });
  }
  return projected;
}

function projectedValue(record: Record<string, unknown>, key: string): unknown {
  return Object.getOwnPropertyDescriptor(record, key)!.value;
}

function hasExactKeys(record: Record<string, unknown>, required: readonly string[]): boolean {
  const keys = Reflect.ownKeys(record);
  return keys.length === required.length
    && required.every((key) => Object.hasOwn(record, key));
}

function projectPolicyStateContainer(value: unknown): PolicyState | undefined {
  const container = projectPlainDataRecord(value);
  if (container === undefined || !hasExactKeys(container, ["principals"])) return undefined;
  const principals = projectPlainDataRecord(projectedValue(container, "principals"), true);
  if (principals === undefined) return undefined;
  return { principals: principals as PolicyState["principals"] };
}

function projectBossPolicyStateContainer(value: unknown): BossPolicyState | undefined {
  const container = projectPlainDataRecord(value);
  if (container === undefined || !hasExactKeys(container, ["principals"])) return undefined;
  const principals = projectPlainDataRecord(projectedValue(container, "principals"), true);
  if (principals === undefined) return undefined;
  return { principals: principals as BossPolicyState["principals"] };
}

/**
 * Validate and project the complete additive state before any routing lookup.
 * Every source property is inspected through an own descriptor; no source
 * accessor is invoked. Registration and principal records remain opaque here
 * so selected-entry semantics retain their existing denial ordering.
 */
function projectFeatureAwarePolicyState(value: unknown): FeatureAwarePolicyState | undefined {
  try {
    const state = projectPlainDataRecord(value);
    if (state === undefined || !hasExactKeys(state, ["registrations", "legacy", "boss"])) return undefined;

    const registrations = projectPlainDataRecord(projectedValue(state, "registrations"));
    const legacy = projectPolicyStateContainer(projectedValue(state, "legacy"));
    const boss = projectBossPolicyStateContainer(projectedValue(state, "boss"));
    if (registrations === undefined || legacy === undefined || boss === undefined) return undefined;
    return {
      registrations: registrations as FeatureAwarePolicyState["registrations"],
      legacy,
      boss,
    };
  } catch {
    return undefined;
  }
}

function authoritativeRegistration(state: FeatureAwarePolicyState, principalId: string): RegistrationLookup {
  const entry = Object.getOwnPropertyDescriptor(state.registrations, principalId);
  if (entry === undefined) return { status: "missing" };
  if (!entry.enumerable || !Object.hasOwn(entry, "value")) return { status: "invalid" };
  try {
    const registration = parseFeatureRegistration(entry.value, registrationPath(principalId));
    if (registration.principalId !== principalId) return { status: "invalid" };
    return { status: "valid", registration };
  } catch (error) {
    if (error instanceof ContractValidationError) return { status: "invalid" };
    throw error;
  }
}

function exactOrdinaryRegistration(
  state: FeatureAwarePolicyState,
  principalId: string,
): OrdinaryFeatureRegistration {
  const lookup = authoritativeRegistration(state, principalId);
  if (lookup.status !== "valid") {
    throw new ContractValidationError(registrationPath(principalId), "must be an authoritative exact registration");
  }
  if (lookup.registration.principalClass !== "ordinary") {
    throw new ContractValidationError(registrationPath(principalId), "Boss-bound principals must never cross the frozen legacy authorization boundary");
  }
  if (lookup.registration.state !== "active") {
    throw new ContractValidationError(`${registrationPath(principalId)}.state`, "must be active at the legacy authorization boundary");
  }
  return lookup.registration;
}

function activeOrdinaryPolicyBinding(
  state: FeatureAwarePolicyState,
  principalId: string,
  registration: OrdinaryFeatureRegistration,
): boolean {
  const principal = ownLegacyPolicyPrincipal(state.legacy.principals, principalId);
  if (principal === undefined) return false;
  return registration.state === "active" && principal.id === principalId && principal.state === registration.state;
}

const LEGACY_PRINCIPAL_REQUIRED_KEYS = [
  "id",
  "kind",
  "state",
  "generation",
  "policy",
  "rootSessionId",
] as const;
const LEGACY_PRINCIPAL_OPTIONAL_KEYS = ["parentSessionId"] as const;
const LEGACY_PRINCIPAL_KEYS = new Set<string>([
  ...LEGACY_PRINCIPAL_REQUIRED_KEYS,
  ...LEGACY_PRINCIPAL_OPTIONAL_KEYS,
]);

/**
 * Snapshot a legacy principal exclusively from own enumerable data
 * descriptors. Descriptor values can be copied without evaluating an
 * attacker-controlled accessor before the frozen policy kernel runs.
 */
function exactOwnLegacyPrincipal(value: unknown): PolicyState["principals"][string] | undefined {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return undefined;

  const descriptors = new Map<string, PropertyDescriptor>();
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string" || !LEGACY_PRINCIPAL_KEYS.has(key)) return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (
      descriptor === undefined
      || !descriptor.enumerable
      || !Object.hasOwn(descriptor, "value")
    ) return undefined;
    descriptors.set(key, descriptor);
  }
  for (const key of LEGACY_PRINCIPAL_REQUIRED_KEYS) {
    if (!descriptors.has(key)) return undefined;
  }

  const valueOf = (key: string): unknown => descriptors.get(key)!.value;
  const parentSessionId = descriptors.get("parentSessionId")?.value;
  return {
    id: valueOf("id") as PolicyState["principals"][string]["id"],
    kind: valueOf("kind") as PolicyState["principals"][string]["kind"],
    state: valueOf("state") as PolicyState["principals"][string]["state"],
    generation: valueOf("generation") as PolicyState["principals"][string]["generation"],
    policy: valueOf("policy") as PolicyState["principals"][string]["policy"],
    ...(parentSessionId === undefined
      ? {}
      : { parentSessionId: parentSessionId as PolicyState["principals"][string]["parentSessionId"] }),
    rootSessionId: valueOf("rootSessionId") as PolicyState["principals"][string]["rootSessionId"],
  };
}

function ownLegacyPolicyPrincipal(
  principals: PolicyState["principals"],
  principalId: string,
): PolicyState["principals"][string] | undefined {
  const entry = Object.getOwnPropertyDescriptor(principals, principalId);
  if (
    entry === undefined
    || !entry.enumerable
    || !Object.hasOwn(entry, "value")
  ) return undefined;
  return exactOwnLegacyPrincipal(entry.value);
}

/**
 * Snapshot only own legacy map entries whose record identity is bound to the
 * map key. A null prototype prevents the frozen ancestor walker from
 * resolving a missing intermediary through the source map's prototype.
 */
function ownLegacyPolicyProjection(state: PolicyState): PolicyState {
  const principals = Object.create(null) as PolicyState["principals"];
  for (const principalId of Object.keys(state.principals)) {
    const principal = ownLegacyPolicyPrincipal(state.principals, principalId);
    if (principal === undefined || principal.id !== principalId) continue;
    principals[principalId] = principal;
  }
  return { principals };
}

function activeBossPolicyBinding(
  state: FeatureAwarePolicyState,
  principalId: string,
  registration: BossFeatureRegistration,
): BossPolicyPrincipal | undefined {
  const entry = Object.getOwnPropertyDescriptor(state.boss.principals, principalId);
  if (
    entry === undefined
    || !entry.enumerable
    || !Object.hasOwn(entry, "value")
  ) return undefined;
  let principal: BossPolicyPrincipal;
  try {
    principal = parseBossPolicyPrincipal(entry.value);
  } catch (error) {
    if (error instanceof ContractValidationError) return undefined;
    throw error;
  }
  if (
    registration.state !== "active"
    || principal.principalClass !== "boss-private"
    || principal.state !== registration.state
    || principal.principalId !== principalId
    || registration.bossRunId !== principal.bossRunId
    || registration.participantId !== principal.participantId
    || registration.bindingEpoch !== principal.bindingEpoch
  ) return undefined;
  return principal;
}

/** Guarded compatibility boundary: calling frozen legacy authorization for a Boss registration is a programmer error. */
export function authorizeLegacyBoundary(
  state: FeatureAwarePolicyState,
  actorId: string,
  action: PolicyAction,
  targetId: string,
  context: AuthorizationContext = {},
): AuthorizationDecision {
  const parsedContext = parseLegacyAuthorizationContext(context, "$.legacyContext");
  if (!(LEGACY_POLICY_ACTIONS as readonly string[]).includes(action)) {
    throw new ContractValidationError("$.action", "must be a frozen legacy policy action");
  }
  const projectedState = projectFeatureAwarePolicyState(state);
  if (projectedState === undefined) {
    throw new ContractValidationError("$.state", "must be an exact additive feature-policy state");
  }
  const actorRegistration = exactOrdinaryRegistration(projectedState, actorId);
  const targetRegistration = exactOrdinaryRegistration(projectedState, targetId);
  if (
    !activeOrdinaryPolicyBinding(projectedState, actorId, actorRegistration)
    || !activeOrdinaryPolicyBinding(projectedState, targetId, targetRegistration)
  ) {
    throw new ContractValidationError("$.legacy.principals", "must contain active principals bound to their registration map keys");
  }
  const legacy = ownLegacyPolicyProjection(projectedState.legacy);
  const decision = authorize(legacy, actorId, action, targetId, parsedContext);
  if (!decision.allowed || decision.reason !== "local-public") return decision;

  const actor = legacy.principals[actorId];
  const target = legacy.principals[targetId];
  if (actor.policy === "local-public" && target.policy === "local-public") return decision;

  // The frozen semantics-v2 kernel shortcuts on local kind alone. The live
  // feature-aware boundary hardens that predicate while retaining every
  // remote-tree relationship decision and the byte-identical legacy corpus.
  if (action === "discover" || action === "send" || action === "ask" || action === "reply") {
    if (isDirectParentPair(actor, target)) return { allowed: true, reason: "direct-parent" };
    if (isAncestor(legacy, actor.id, target.id) || isAncestor(legacy, target.id, actor.id)) {
      return { allowed: true, reason: "ancestor-chain" };
    }
  }
  if (action === "inspect_tree" || action === "revoke" || action === "adopt") {
    if (isAncestor(legacy, actor.id, target.id)) return { allowed: true, reason: "ancestor-control" };
  }
  return { allowed: false, code: "POLICY_DENIED" };
}

/** Derives routing only from authoritative registrations; request metadata cannot select or downgrade the policy namespace. */
export function authorizeFeatureAware(
  state: FeatureAwarePolicyState,
  requestValue: unknown,
): FeatureAwareAuthorizationDecision {
  const request = parseFeatureAwareAuthorizationRequest(requestValue);
  const projectedState = projectFeatureAwarePolicyState(state);
  if (projectedState === undefined) return { allowed: false, code: "FEATURE_ATTESTATION_DENIED" };
  const actorLookup = authoritativeRegistration(projectedState, request.actorId);
  const targetLookup = authoritativeRegistration(projectedState, request.targetId);
  if (actorLookup.status === "missing" || targetLookup.status === "missing") {
    return { allowed: false, code: "UNKNOWN_REGISTRATION" };
  }
  if (actorLookup.status === "invalid" || targetLookup.status === "invalid") {
    return { allowed: false, code: "FEATURE_ATTESTATION_DENIED" };
  }
  const actorRegistration = actorLookup.registration;
  const targetRegistration = targetLookup.registration;
  if (!registrationIsActive(actorRegistration) || !registrationIsActive(targetRegistration)) {
    return { allowed: false, code: "BINDING_INACTIVE" };
  }
  if (actorRegistration.principalClass !== targetRegistration.principalClass) {
    return { allowed: false, code: "FEATURE_CLASS_DENIED" };
  }
  if (actorRegistration.principalClass === "ordinary" && targetRegistration.principalClass === "ordinary") {
    if (request.bossContext !== undefined) return { allowed: false, code: "CONTEXT_NAMESPACE_DENIED" };
    if (!(LEGACY_POLICY_ACTIONS as readonly string[]).includes(request.action)) {
      return { allowed: false, code: "ACTION_NAMESPACE_DENIED" };
    }
    if (
      !activeOrdinaryPolicyBinding(projectedState, request.actorId, actorRegistration)
      || !activeOrdinaryPolicyBinding(projectedState, request.targetId, targetRegistration)
    ) return { allowed: false, code: "FEATURE_ATTESTATION_DENIED" };
    return authorizeLegacyBoundary(projectedState, request.actorId, request.action as PolicyAction, request.targetId, request.legacyContext);
  }
  const actorBoss = actorRegistration as BossFeatureRegistration;
  const targetBoss = targetRegistration as BossFeatureRegistration;
  if (!bossRegistrationAttested(actorBoss) || !bossRegistrationAttested(targetBoss)) {
    return { allowed: false, code: "FEATURE_ATTESTATION_DENIED" };
  }
  const actorPrincipal = activeBossPolicyBinding(projectedState, request.actorId, actorBoss);
  const targetPrincipal = activeBossPolicyBinding(projectedState, request.targetId, targetBoss);
  if (!actorPrincipal || !targetPrincipal) return { allowed: false, code: "FEATURE_ATTESTATION_DENIED" };
  if (request.legacyContext !== undefined) return { allowed: false, code: "CONTEXT_NAMESPACE_DENIED" };
  if (!(BOSS_POLICY_ACTIONS as readonly string[]).includes(request.action)) {
    return { allowed: false, code: "ACTION_NAMESPACE_DENIED" };
  }
  if (
    (request.bossContext?.actorBindingEpoch !== undefined && request.bossContext.actorBindingEpoch !== actorBoss.bindingEpoch)
    || (request.bossContext?.targetBindingEpoch !== undefined && request.bossContext.targetBindingEpoch !== targetBoss.bindingEpoch)
  ) return { allowed: false, code: "FEATURE_ATTESTATION_DENIED" };
  return authorizeBossPolicy(
    projectedState.boss,
    request.actorId,
    request.action as BossPolicyAction,
    request.targetId,
    {
      ...request.bossContext,
      actorBindingEpoch: actorBoss.bindingEpoch,
      targetBindingEpoch: targetBoss.bindingEpoch,
    },
  );
}
