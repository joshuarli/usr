import { types as nodeUtilTypes } from "node:util";
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
  participantBindingEpoch,
  type ParticipantBindingEpoch,
} from "./canonical.ts";

export const BOSS_POLICY_SEMANTICS_VERSION = 1 as const;
export const BOSS_POLICY_PRINCIPAL_VERSION = "boss.policy-principal.v1" as const;
export const BOSS_POLICY_ACTIONS = ["discover", "send", "ask", "reply", "control"] as const;
export type BossPolicyAction = (typeof BOSS_POLICY_ACTIONS)[number];
const BOSS_POLICY_ACTION_SET: ReadonlySet<string> = new Set(BOSS_POLICY_ACTIONS);
export const BOSS_POLICY_ROLES = ["boss", "manager", "adversary", "scout", "worker", "council", "controller"] as const;
export type BossPolicyRole = (typeof BOSS_POLICY_ROLES)[number];
export const BOSS_CONTROL_KINDS = [
  "assignment_request",
  "assignment_response",
  "health",
  "staffing",
  "review_request",
  "review_result",
  "proof",
  "lifecycle",
  "decision",
] as const;
export type BossControlKind = (typeof BOSS_CONTROL_KINDS)[number];

export type BossPolicyPrincipal = BossPrivatePrincipal | LegacyLocalPublicPrincipal;

export interface BossPrivatePrincipal {
  version: typeof BOSS_POLICY_PRINCIPAL_VERSION;
  principalId: string;
  principalClass: "boss-private";
  state: "active" | "revoked" | "replaced";
  bossRunId: string;
  participantId: string;
  role: BossPolicyRole;
  bindingEpoch: ParticipantBindingEpoch;
  assignedManagerParticipantId?: string;
  assignedParticipantIds?: string[];
  requestingPrincipalId?: string;
}

export interface LegacyLocalPublicPrincipal {
  version: typeof BOSS_POLICY_PRINCIPAL_VERSION;
  principalId: string;
  principalClass: "legacy-local-public";
  state: "active" | "revoked";
}

export interface BossPolicyState {
  principals: Record<string, BossPolicyPrincipal>;
}

export interface BossAuthorizationContext {
  actorBindingEpoch?: ParticipantBindingEpoch;
  targetBindingEpoch?: ParticipantBindingEpoch;
  controlKind?: BossControlKind;
  correlated?: boolean;
}

export type BossAuthorizationDenialCode =
  | "UNKNOWN_PRINCIPAL"
  | "REVOKED_OR_REPLACED_PRINCIPAL"
  | "STALE_BINDING_EPOCH"
  | "CROSS_RUN_DENIED"
  | "BOSS_LEGACY_ISOLATION"
  | "CONTROL_REQUIRES_CORRELATION"
  | "CONTROL_KIND_DENIED"
  | "AMBIGUOUS_PARTICIPANT_IDENTITY"
  | "POLICY_DENIED";

export type BossAuthorizationDecision =
  | { allowed: true; reason: "legacy-local-public" | "self" | "communication-profile" | "structured-control" }
  | { allowed: false; code: BossAuthorizationDenialCode };

function isBossPolicyAction(value: unknown): value is BossPolicyAction {
  return typeof value === "string" && BOSS_POLICY_ACTION_SET.has(value);
}

function parseBossAuthorizationContext(
  value: unknown,
  action: BossPolicyAction,
): BossAuthorizationContext {
  if (
    typeof value !== "object"
    || value === null
    || nodeUtilTypes.isProxy(value)
    || Array.isArray(value)
    || Object.getPrototypeOf(value) !== Object.prototype
  ) {
    throw new ContractValidationError("$.context", "must be a plain object");
  }

  const permittedKeys = action === "control"
    ? new Set(["actorBindingEpoch", "targetBindingEpoch", "controlKind", "correlated"])
    : new Set(["actorBindingEpoch", "targetBindingEpoch"]);
  const values: Record<string, unknown> = Object.create(null) as Record<string, unknown>;
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string") {
      throw new ContractValidationError("$.context", "symbol properties are not supported");
    }
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor === undefined || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) {
      throw new ContractValidationError(`$.context.${key}`, "must be an enumerable data property");
    }
    if (!permittedKeys.has(key)) {
      throw new ContractValidationError(`$.context.${key}`, "is not supported");
    }
    values[key] = descriptor.value;
  }

  const actorBindingEpoch = values.actorBindingEpoch === undefined
    ? undefined
    : participantBindingEpoch(values.actorBindingEpoch, "$.context.actorBindingEpoch");
  const targetBindingEpoch = values.targetBindingEpoch === undefined
    ? undefined
    : participantBindingEpoch(values.targetBindingEpoch, "$.context.targetBindingEpoch");
  const controlKind = values.controlKind === undefined
    ? undefined
    : readEnum(values.controlKind, BOSS_CONTROL_KINDS, "$.context.controlKind");
  const correlated = values.correlated === undefined
    ? undefined
    : readBoolean(values.correlated, "$.context.correlated");
  return {
    ...(actorBindingEpoch === undefined ? {} : { actorBindingEpoch }),
    ...(targetBindingEpoch === undefined ? {} : { targetBindingEpoch }),
    ...(controlKind === undefined ? {} : { controlKind }),
    ...(correlated === undefined ? {} : { correlated }),
  };
}

export function parseBossPolicyPrincipal(value: unknown): BossPolicyPrincipal {
  assertRecord(value);
  const version = readString(value.version, "$.version");
  if (version !== BOSS_POLICY_PRINCIPAL_VERSION) throw new ContractValidationError("$.version", `unsupported version: ${version}`);
  const principalClass = readEnum(value.principalClass, ["boss-private", "legacy-local-public"] as const, "$.principalClass");
  if (principalClass === "legacy-local-public") {
    assertExactKeys(value, ["version", "principalId", "principalClass", "state"]);
    return {
      version: BOSS_POLICY_PRINCIPAL_VERSION,
      principalId: readString(value.principalId, "$.principalId"),
      principalClass,
      state: readEnum(value.state, ["active", "revoked"] as const, "$.state"),
    };
  }
  assertExactKeys(
    value,
    ["version", "principalId", "principalClass", "state", "bossRunId", "participantId", "role", "bindingEpoch"],
    ["assignedManagerParticipantId", "assignedParticipantIds", "requestingPrincipalId"],
  );
  const role = readEnum(value.role, BOSS_POLICY_ROLES, "$.role");
  const assignedManagerParticipantId = readOptionalString(value.assignedManagerParticipantId, "$.assignedManagerParticipantId");
  const assignedParticipantIds = value.assignedParticipantIds === undefined
    ? undefined
    : readStringArray(value.assignedParticipantIds, "$.assignedParticipantIds");
  const requestingPrincipalId = readOptionalString(value.requestingPrincipalId, "$.requestingPrincipalId");
  if ((role === "worker" || role === "scout") !== (assignedManagerParticipantId !== undefined)) {
    throw new ContractValidationError("$.assignedManagerParticipantId", "is required exactly for Worker and Scout principals");
  }
  if ((role === "manager") !== (assignedParticipantIds !== undefined)) {
    throw new ContractValidationError("$.assignedParticipantIds", "is required exactly for Manager principals");
  }
  if (assignedParticipantIds !== undefined && new Set(assignedParticipantIds).size !== assignedParticipantIds.length) {
    throw new ContractValidationError("$.assignedParticipantIds", "must not contain duplicates");
  }
  if ((role === "council") !== (requestingPrincipalId !== undefined)) {
    throw new ContractValidationError("$.requestingPrincipalId", "is required exactly for Council principals");
  }
  return {
    version: BOSS_POLICY_PRINCIPAL_VERSION,
    principalId: readString(value.principalId, "$.principalId"),
    principalClass,
    state: readEnum(value.state, ["active", "revoked", "replaced"] as const, "$.state"),
    bossRunId: readString(value.bossRunId, "$.bossRunId"),
    participantId: readString(value.participantId, "$.participantId"),
    role,
    bindingEpoch: participantBindingEpoch(value.bindingEpoch, "$.bindingEpoch"),
    ...(assignedManagerParticipantId === undefined ? {} : { assignedManagerParticipantId }),
    ...(assignedParticipantIds === undefined ? {} : { assignedParticipantIds }),
    ...(requestingPrincipalId === undefined ? {} : { requestingPrincipalId }),
  };
}

function areAssigned(actor: BossPrivatePrincipal, target: BossPrivatePrincipal): boolean {
  if (actor.role === "manager" && (target.role === "worker" || target.role === "scout")) {
    return actor.assignedParticipantIds?.includes(target.participantId) === true
      && target.assignedManagerParticipantId === actor.participantId;
  }
  if (target.role === "manager" && (actor.role === "worker" || actor.role === "scout")) {
    return target.assignedParticipantIds?.includes(actor.participantId) === true
      && actor.assignedManagerParticipantId === target.participantId;
  }
  return false;
}

function communicationEdge(actor: BossPrivatePrincipal, target: BossPrivatePrincipal): boolean {
  const roles = new Set([actor.role, target.role]);
  if (roles.has("boss") && roles.has("manager")) return true;
  if (roles.has("boss") && roles.has("adversary")) return true;
  if (roles.has("manager") && roles.has("adversary")) return true;
  if (areAssigned(actor, target)) return true;
  if (actor.role === "council" || target.role === "council") return false;
  if (actor.role === "controller" || target.role === "controller") {
    const other = actor.role === "controller" ? target.role : actor.role;
    return other === "boss" || other === "manager" || other === "adversary";
  }
  return false;
}

type BossDirectionalControlKindMatrix = {
  readonly [ActorRole in BossPolicyRole]: Readonly<Partial<Record<BossPolicyRole, readonly BossControlKind[]>>>;
};

/**
 * Role communication is deliberately broader than structured control. This
 * directional matrix is the complete role-level Boss v1 control allowlist;
 * omitted role pairs and omitted kinds fail closed. Assignment and requester
 * bindings are enforced separately below.
 */
export const BOSS_DIRECTIONAL_CONTROL_KIND_MATRIX = {
  boss: {
    manager: ["lifecycle", "decision"],
    adversary: ["review_request"],
    council: ["review_request"],
    controller: ["lifecycle", "decision"],
  },
  manager: {
    boss: ["health", "staffing", "proof", "lifecycle"],
    adversary: ["review_request"],
    scout: ["assignment_request", "lifecycle"],
    worker: ["assignment_request", "lifecycle"],
    controller: ["assignment_request", "health", "staffing", "review_request", "proof", "lifecycle"],
  },
  adversary: {
    boss: ["health", "review_result", "proof"],
    manager: ["health", "review_result", "proof"],
    controller: ["health", "review_result", "proof"],
  },
  scout: {
    manager: ["assignment_response", "health", "proof"],
    controller: ["assignment_response", "health"],
  },
  worker: {
    manager: ["assignment_response", "health", "proof"],
    controller: ["assignment_response", "health"],
  },
  council: {
    boss: ["health", "review_result"],
    controller: ["health", "review_result"],
  },
  controller: {
    boss: ["health", "proof", "lifecycle", "decision"],
    manager: ["assignment_response", "health", "staffing", "review_result", "lifecycle", "decision"],
    adversary: ["review_request", "lifecycle"],
    scout: ["assignment_request", "lifecycle"],
    worker: ["assignment_request", "lifecycle"],
    council: ["review_request"],
  },
} as const satisfies BossDirectionalControlKindMatrix;

function requesterEdge(actor: BossPrivatePrincipal, target: BossPrivatePrincipal): boolean {
  if (target.role === "council") return target.requestingPrincipalId === actor.principalId;
  if (actor.role === "council") return actor.requestingPrincipalId === target.principalId;
  return true;
}

function structuredControlEdge(
  actor: BossPrivatePrincipal,
  target: BossPrivatePrincipal,
  kind: BossControlKind,
): boolean {
  const targetKinds = BOSS_DIRECTIONAL_CONTROL_KIND_MATRIX[actor.role] as Readonly<Partial<Record<BossPolicyRole, readonly BossControlKind[]>>>;
  const allowedKinds = targetKinds[target.role];
  if (allowedKinds === undefined || !allowedKinds.includes(kind)) return false;
  if (!requesterEdge(actor, target)) return false;
  if (
    (actor.role === "manager" && (target.role === "worker" || target.role === "scout"))
    || (target.role === "manager" && (actor.role === "worker" || actor.role === "scout"))
  ) return areAssigned(actor, target);
  return true;
}

type OwnEnumerableDataDescriptor = PropertyDescriptor & { value: unknown };

function ownEnumerableDataDescriptor(value: object, key: PropertyKey): OwnEnumerableDataDescriptor | undefined {
  const descriptor = Object.getOwnPropertyDescriptor(value, key);
  return descriptor !== undefined && descriptor.enumerable && Object.hasOwn(descriptor, "value")
    ? descriptor as OwnEnumerableDataDescriptor
    : undefined;
}

function authoritativePrincipalMap(state: BossPolicyState): Record<string, unknown> | undefined {
  if (
    typeof state !== "object"
    || state === null
    || nodeUtilTypes.isProxy(state)
    || Array.isArray(state)
    || Object.getPrototypeOf(state) !== Object.prototype
  ) return undefined;

  const stateKeys = Reflect.ownKeys(state);
  if (stateKeys.length !== 1 || stateKeys[0] !== "principals") return undefined;
  const descriptor = ownEnumerableDataDescriptor(state, "principals");
  if (descriptor === undefined) return undefined;

  const principals = descriptor.value;
  if (
    typeof principals !== "object"
    || principals === null
    || nodeUtilTypes.isProxy(principals)
    || Array.isArray(principals)
    || Object.getPrototypeOf(principals) !== Object.prototype
  ) return undefined;

  for (const key of Reflect.ownKeys(principals)) {
    if (typeof key !== "string" || ownEnumerableDataDescriptor(principals, key) === undefined) return undefined;
  }
  return principals as Record<string, unknown>;
}

function authoritativePrincipal(principals: Record<string, unknown>, principalId: string): BossPolicyPrincipal | undefined {
  const entry = ownEnumerableDataDescriptor(principals, principalId);
  if (entry === undefined) return undefined;
  if (typeof entry.value !== "object" || entry.value === null || nodeUtilTypes.isProxy(entry.value)) return undefined;

  const assignedParticipantIds = ownEnumerableDataDescriptor(entry.value, "assignedParticipantIds")?.value;
  if (typeof assignedParticipantIds === "object" && assignedParticipantIds !== null && nodeUtilTypes.isProxy(assignedParticipantIds)) {
    return undefined;
  }
  try {
    const principal = parseBossPolicyPrincipal(entry.value);
    return principal.principalId === principalId ? principal : undefined;
  } catch (error) {
    if (error instanceof ContractValidationError) return undefined;
    throw error;
  }
}

function hasUniqueActiveParticipantIdentity(
  principals: Record<string, unknown>,
  expected: BossPrivatePrincipal,
): boolean {
  let matches = 0;
  for (const principalId of Reflect.ownKeys(principals)) {
    if (typeof principalId !== "string") continue;
    const candidate = authoritativePrincipal(principals, principalId);
    if (
      candidate?.principalClass === "boss-private"
      && candidate.state === "active"
      && candidate.bossRunId === expected.bossRunId
      && candidate.participantId === expected.participantId
    ) {
      matches += 1;
      if (matches > 1) return false;
    }
  }
  return matches === 1;
}

export function authorizeBossPolicy(
  state: BossPolicyState,
  actorId: string,
  action: BossPolicyAction,
  targetId: string,
  context: BossAuthorizationContext = {},
): BossAuthorizationDecision {
  if (!isBossPolicyAction(action)) return { allowed: false, code: "POLICY_DENIED" };
  if (typeof actorId !== "string" || typeof targetId !== "string") {
    return { allowed: false, code: "UNKNOWN_PRINCIPAL" };
  }

  let parsedContext: BossAuthorizationContext;
  try {
    parsedContext = parseBossAuthorizationContext(context, action);
  } catch (error) {
    if (error instanceof ContractValidationError) return { allowed: false, code: "POLICY_DENIED" };
    throw error;
  }
  const principals = authoritativePrincipalMap(state);
  if (principals === undefined) return { allowed: false, code: "UNKNOWN_PRINCIPAL" };
  const actor = authoritativePrincipal(principals, actorId);
  const target = actorId === targetId ? actor : authoritativePrincipal(principals, targetId);
  if (!actor || !target) {
    return { allowed: false, code: "UNKNOWN_PRINCIPAL" };
  }
  if (actor.state !== "active" || target.state !== "active") return { allowed: false, code: "REVOKED_OR_REPLACED_PRINCIPAL" };
  if (actor.principalClass === "legacy-local-public" && target.principalClass === "legacy-local-public") {
    if (action === "control") return { allowed: false, code: "BOSS_LEGACY_ISOLATION" };
    return { allowed: true, reason: "legacy-local-public" };
  }
  if (actor.principalClass !== "boss-private" || target.principalClass !== "boss-private") {
    return { allowed: false, code: "BOSS_LEGACY_ISOLATION" };
  }
  if (parsedContext.actorBindingEpoch !== actor.bindingEpoch || parsedContext.targetBindingEpoch !== target.bindingEpoch) {
    return { allowed: false, code: "STALE_BINDING_EPOCH" };
  }
  if (actor.bossRunId !== target.bossRunId) return { allowed: false, code: "CROSS_RUN_DENIED" };
  if (
    !hasUniqueActiveParticipantIdentity(principals, actor)
    || !hasUniqueActiveParticipantIdentity(principals, target)
  ) {
    return { allowed: false, code: "AMBIGUOUS_PARTICIPANT_IDENTITY" };
  }
  if (action === "control") {
    if (!parsedContext.correlated || parsedContext.controlKind === undefined) return { allowed: false, code: "CONTROL_REQUIRES_CORRELATION" };
    return structuredControlEdge(actor, target, parsedContext.controlKind)
      ? { allowed: true, reason: "structured-control" }
      : { allowed: false, code: "CONTROL_KIND_DENIED" };
  }
  if (actor.principalId === target.principalId) return { allowed: true, reason: "self" };
  if (action === "discover" && actor.role === "controller") {
    return { allowed: true, reason: "communication-profile" };
  }
  return communicationEdge(actor, target)
    ? { allowed: true, reason: "communication-profile" }
    : { allowed: false, code: "POLICY_DENIED" };
}
