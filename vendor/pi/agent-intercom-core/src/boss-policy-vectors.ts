import { canonicalHash, participantBindingEpoch } from "./canonical.ts";
import {
  type BossAuthorizationContext,
  type BossControlKind,
  type BossPolicyAction,
  type BossPrivatePrincipal,
  type BossPolicyPrincipal,
  type BossPolicyState,
  BOSS_POLICY_PRINCIPAL_VERSION,
  BOSS_POLICY_ROLES,
  type BossPolicyRole,
} from "./boss-policy.ts";

export const BOSS_POLICY_VECTOR_SCHEMA_VERSION = 1 as const;

function privatePrincipal(
  participantId: string,
  role: Exclude<BossPolicyPrincipal, { principalClass: "legacy-local-public" }>["role"],
  extra: Partial<Exclude<BossPolicyPrincipal, { principalClass: "legacy-local-public" }>> = {},
): BossPolicyPrincipal {
  return {
    version: BOSS_POLICY_PRINCIPAL_VERSION,
    principalId: participantId,
    principalClass: "boss-private",
    state: "active",
    bossRunId: "run-a",
    participantId,
    role,
    bindingEpoch: participantBindingEpoch(1),
    ...(role === "manager" ? { assignedParticipantIds: ["scout", "worker"] } : {}),
    ...(role === "scout" || role === "worker" ? { assignedManagerParticipantId: "manager" } : {}),
    ...(role === "council" ? { requestingPrincipalId: "boss" } : {}),
    ...extra,
  } as BossPolicyPrincipal;
}

const principals: BossPolicyPrincipal[] = [
  privatePrincipal("boss", "boss"),
  privatePrincipal("manager", "manager"),
  privatePrincipal("adversary", "adversary"),
  privatePrincipal("scout", "scout"),
  privatePrincipal("worker", "worker"),
  privatePrincipal("worker-two", "worker", { assignedManagerParticipantId: "manager", bindingEpoch: participantBindingEpoch(2) }),
  privatePrincipal("council", "council"),
  privatePrincipal("controller", "controller"),
  privatePrincipal("cross-run", "boss", { bossRunId: "run-b" }),
  { version: BOSS_POLICY_PRINCIPAL_VERSION, principalId: "local-a", principalClass: "legacy-local-public", state: "active" },
  { version: BOSS_POLICY_PRINCIPAL_VERSION, principalId: "local-b", principalClass: "legacy-local-public", state: "active" },
];

export interface BossPolicyVector {
  name: string;
  actorId: string;
  action: BossPolicyAction;
  targetId: string;
  context?: BossAuthorizationContext;
  expectedAllowed: boolean;
  expectedReasonOrCode: string;
  principalOverride?: BossPolicyPrincipal;
  additionalPrincipals?: readonly BossPolicyPrincipal[];
}

const epoch = { actorBindingEpoch: participantBindingEpoch(1), targetBindingEpoch: participantBindingEpoch(1) } as const;

const principalForRole: Record<BossPolicyRole, string> = {
  boss: "boss",
  manager: "manager",
  adversary: "adversary",
  scout: "scout",
  worker: "worker",
  council: "council",
  controller: "controller",
};

function genericRoleEdgeAllowed(actor: BossPolicyRole, target: BossPolicyRole): boolean {
  if (actor === target) return true;
  if (actor === "controller") return true;
  const pair = new Set([actor, target]);
  if (pair.has("boss") && pair.has("manager")) return true;
  if (pair.has("boss") && pair.has("adversary")) return true;
  if (pair.has("manager") && pair.has("adversary")) return true;
  if (pair.has("manager") && (pair.has("worker") || pair.has("scout"))) return true;
  if (pair.has("controller") && (pair.has("boss") || pair.has("manager") || pair.has("adversary"))) return true;
  return false;
}

/** Exhaustive generic-communication/discovery role table; typed Controller/Council edges are covered separately below. */
export const BOSS_ROLE_EDGE_VECTORS: readonly BossPolicyVector[] = BOSS_POLICY_ROLES.flatMap((actorRole) =>
  BOSS_POLICY_ROLES.map((targetRole): BossPolicyVector => {
    const expectedAllowed = genericRoleEdgeAllowed(actorRole, targetRole);
    return {
      name: `exhaustive role edge ${actorRole} -> ${targetRole}`,
      actorId: principalForRole[actorRole],
      action: "discover",
      targetId: principalForRole[targetRole],
      context: epoch,
      expectedAllowed,
      expectedReasonOrCode: expectedAllowed ? (actorRole === targetRole ? "self" : "communication-profile") : "POLICY_DENIED",
    };
  }),
);

/*
 * This expectation table intentionally does not consume the policy matrix.
 * It is an independent, frozen oracle for the exhaustive control corpus.
 */
const EXPECTED_BOSS_POLICY_ROLES = [
  "boss", "manager", "adversary", "scout", "worker", "council", "controller",
] as const satisfies readonly BossPolicyRole[];
const EXPECTED_BOSS_CONTROL_KINDS = [
  "assignment_request", "assignment_response", "health", "staffing", "review_request",
  "review_result", "proof", "lifecycle", "decision",
] as const satisfies readonly BossControlKind[];

type ExpectedDirectionalControlKindMatrix = {
  readonly [ActorRole in BossPolicyRole]: Readonly<Partial<Record<BossPolicyRole, readonly BossControlKind[]>>>;
};

const EXPECTED_DIRECTIONAL_CONTROL_KIND_MATRIX = {
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
} as const satisfies ExpectedDirectionalControlKindMatrix;

function expectedPrivatePrincipal(role: BossPolicyRole): BossPrivatePrincipal {
  const principal = principals.find((candidate) =>
    candidate.principalClass === "boss-private"
    && candidate.principalId === principalForRole[role]
    && candidate.role === role
  );
  if (principal === undefined || principal.principalClass !== "boss-private") {
    throw new Error(`missing exhaustive fixture for ${role}`);
  }
  return principal;
}

function expectedAssignedEdge(actor: BossPrivatePrincipal, target: BossPrivatePrincipal): boolean {
  if (actor.role === "manager" && (target.role === "worker" || target.role === "scout")) {
    return actor.assignedParticipantIds?.includes(target.participantId) === true
      && target.assignedManagerParticipantId === actor.participantId;
  }
  if (target.role === "manager" && (actor.role === "worker" || actor.role === "scout")) {
    return target.assignedParticipantIds?.includes(actor.participantId) === true
      && actor.assignedManagerParticipantId === target.participantId;
  }
  return true;
}

function expectedRequesterEdge(actor: BossPrivatePrincipal, target: BossPrivatePrincipal): boolean {
  if (target.role === "council") return target.requestingPrincipalId === actor.principalId;
  if (actor.role === "council") return actor.requestingPrincipalId === target.principalId;
  return true;
}

function expectedDirectionalControl(
  actor: BossPrivatePrincipal,
  target: BossPrivatePrincipal,
  kind: BossControlKind,
): boolean {
  const targetKinds = EXPECTED_DIRECTIONAL_CONTROL_KIND_MATRIX[actor.role] as Readonly<Partial<Record<BossPolicyRole, readonly BossControlKind[]>>>;
  return targetKinds[target.role]?.includes(kind) === true
    && expectedAssignedEdge(actor, target)
    && expectedRequesterEdge(actor, target);
}

export interface BossControlEdgeVector extends BossPolicyVector {
  actorRole: BossPolicyRole;
  targetRole: BossPolicyRole;
  context: BossAuthorizationContext & { controlKind: BossControlKind; correlated: true };
}

/** Every ordered role pair (both directions) crossed with every Boss v1 control kind. */
export const BOSS_CONTROL_EDGE_VECTORS: readonly BossControlEdgeVector[] = EXPECTED_BOSS_POLICY_ROLES.flatMap((actorRole) =>
  EXPECTED_BOSS_POLICY_ROLES.flatMap((targetRole) =>
    EXPECTED_BOSS_CONTROL_KINDS.map((controlKind): BossControlEdgeVector => {
      const expectedAllowed = expectedDirectionalControl(
        expectedPrivatePrincipal(actorRole),
        expectedPrivatePrincipal(targetRole),
        controlKind,
      );
      return {
        name: `exhaustive control edge ${actorRole} -> ${targetRole}: ${controlKind}`,
        actorId: principalForRole[actorRole],
        actorRole,
        action: "control",
        targetId: principalForRole[targetRole],
        targetRole,
        context: { ...epoch, correlated: true, controlKind },
        expectedAllowed,
        expectedReasonOrCode: expectedAllowed ? "structured-control" : "CONTROL_KIND_DENIED",
      };
    }),
  ),
);

export const BOSS_POLICY_VECTORS: readonly BossPolicyVector[] = [
  ...BOSS_ROLE_EDGE_VECTORS,
  ...BOSS_CONTROL_EDGE_VECTORS,
  { name: "Boss reaches Manager", actorId: "boss", action: "send", targetId: "manager", context: epoch, expectedAllowed: true, expectedReasonOrCode: "communication-profile" },
  { name: "Manager reaches Boss", actorId: "manager", action: "reply", targetId: "boss", context: epoch, expectedAllowed: true, expectedReasonOrCode: "communication-profile" },
  { name: "Boss reaches Adversary", actorId: "boss", action: "ask", targetId: "adversary", context: epoch, expectedAllowed: true, expectedReasonOrCode: "communication-profile" },
  { name: "Manager reaches Adversary", actorId: "manager", action: "send", targetId: "adversary", context: epoch, expectedAllowed: true, expectedReasonOrCode: "communication-profile" },
  { name: "Manager reaches assigned Scout", actorId: "manager", action: "discover", targetId: "scout", context: epoch, expectedAllowed: true, expectedReasonOrCode: "communication-profile" },
  { name: "assigned Worker reaches Manager", actorId: "worker", action: "send", targetId: "manager", context: epoch, expectedAllowed: true, expectedReasonOrCode: "communication-profile" },
  { name: "Worker to Worker send denied", actorId: "worker", action: "send", targetId: "worker-two", context: { actorBindingEpoch: participantBindingEpoch(1), targetBindingEpoch: participantBindingEpoch(2) }, expectedAllowed: false, expectedReasonOrCode: "POLICY_DENIED" },
  { name: "Worker to Worker discover denied", actorId: "worker", action: "discover", targetId: "worker-two", context: { actorBindingEpoch: participantBindingEpoch(1), targetBindingEpoch: participantBindingEpoch(2) }, expectedAllowed: false, expectedReasonOrCode: "POLICY_DENIED" },
  { name: "Worker peer reverse send denied", actorId: "worker-two", action: "send", targetId: "worker", context: { actorBindingEpoch: participantBindingEpoch(2), targetBindingEpoch: participantBindingEpoch(1) }, expectedAllowed: false, expectedReasonOrCode: "POLICY_DENIED" },
  { name: "Worker peer reverse discover denied", actorId: "worker-two", action: "discover", targetId: "worker", context: { actorBindingEpoch: participantBindingEpoch(2), targetBindingEpoch: participantBindingEpoch(1) }, expectedAllowed: false, expectedReasonOrCode: "POLICY_DENIED" },
  { name: "known target cross Boss run denied before otherwise allowed Manager to Boss edge", actorId: "manager", action: "send", targetId: "cross-run", context: epoch, expectedAllowed: false, expectedReasonOrCode: "CROSS_RUN_DENIED" },
  { name: "stale actor epoch denied", actorId: "worker", action: "send", targetId: "manager", context: { actorBindingEpoch: participantBindingEpoch(2), targetBindingEpoch: participantBindingEpoch(1) }, expectedAllowed: false, expectedReasonOrCode: "STALE_BINDING_EPOCH" },
  { name: "stale target epoch denied", actorId: "manager", action: "send", targetId: "worker-two", context: epoch, expectedAllowed: false, expectedReasonOrCode: "STALE_BINDING_EPOCH" },
  { name: "replaced participant denied", actorId: "worker", action: "send", targetId: "manager", context: epoch, expectedAllowed: false, expectedReasonOrCode: "REVOKED_OR_REPLACED_PRINCIPAL", principalOverride: privatePrincipal("worker", "worker", { state: "replaced" }) },
  { name: "legacy local sessions remain public", actorId: "local-a", action: "send", targetId: "local-b", expectedAllowed: true, expectedReasonOrCode: "legacy-local-public" },
  { name: "Boss private to legacy denied", actorId: "boss", action: "discover", targetId: "local-a", expectedAllowed: false, expectedReasonOrCode: "BOSS_LEGACY_ISOLATION" },
  { name: "Boss private send to legacy denied", actorId: "boss", action: "send", targetId: "local-a", expectedAllowed: false, expectedReasonOrCode: "BOSS_LEGACY_ISOLATION" },
  { name: "legacy to Boss private denied", actorId: "local-a", action: "send", targetId: "boss", expectedAllowed: false, expectedReasonOrCode: "BOSS_LEGACY_ISOLATION" },
  { name: "legacy discovery of Boss private denied", actorId: "local-a", action: "discover", targetId: "boss", expectedAllowed: false, expectedReasonOrCode: "BOSS_LEGACY_ISOLATION" },
  { name: "Worker typed assignment response to Controller allowed", actorId: "worker", action: "control", targetId: "controller", context: { ...epoch, correlated: true, controlKind: "assignment_response" }, expectedAllowed: true, expectedReasonOrCode: "structured-control" },
  { name: "Worker arbitrary control to Controller denied", actorId: "worker", action: "control", targetId: "controller", context: { ...epoch, correlated: true, controlKind: "decision" }, expectedAllowed: false, expectedReasonOrCode: "CONTROL_KIND_DENIED" },
  { name: "uncorrelated control denied", actorId: "manager", action: "control", targetId: "worker", context: epoch, expectedAllowed: false, expectedReasonOrCode: "CONTROL_REQUIRES_CORRELATION" },
  { name: "Council review to requesting Boss allowed", actorId: "council", action: "control", targetId: "boss", context: { ...epoch, correlated: true, controlKind: "review_result" }, expectedAllowed: true, expectedReasonOrCode: "structured-control" },
  { name: "Manager assignment request requires reciprocal Worker binding", actorId: "manager", action: "control", targetId: "worker", context: { ...epoch, correlated: true, controlKind: "assignment_request" }, expectedAllowed: false, expectedReasonOrCode: "CONTROL_KIND_DENIED", principalOverride: privatePrincipal("worker", "worker", { assignedManagerParticipantId: "other-manager" }) },
  { name: "Worker assignment response requires reciprocal Manager binding", actorId: "worker", action: "control", targetId: "manager", context: { ...epoch, correlated: true, controlKind: "assignment_response" }, expectedAllowed: false, expectedReasonOrCode: "CONTROL_KIND_DENIED", principalOverride: privatePrincipal("manager", "manager", { assignedParticipantIds: ["scout"] }) },
  { name: "Boss Council request denied after requester changes", actorId: "boss", action: "control", targetId: "council", context: { ...epoch, correlated: true, controlKind: "review_request" }, expectedAllowed: false, expectedReasonOrCode: "CONTROL_KIND_DENIED", principalOverride: privatePrincipal("council", "council", { requestingPrincipalId: "controller" }) },
  { name: "Council result denied to former requester", actorId: "council", action: "control", targetId: "boss", context: { ...epoch, correlated: true, controlKind: "review_result" }, expectedAllowed: false, expectedReasonOrCode: "CONTROL_KIND_DENIED", principalOverride: privatePrincipal("council", "council", { requestingPrincipalId: "controller" }) },
  { name: "Controller Council request allowed for matching requester", actorId: "controller", action: "control", targetId: "council", context: { ...epoch, correlated: true, controlKind: "review_request" }, expectedAllowed: true, expectedReasonOrCode: "structured-control", principalOverride: privatePrincipal("council", "council", { requestingPrincipalId: "controller" }) },
  { name: "Council result allowed to matching Controller requester", actorId: "council", action: "control", targetId: "controller", context: { ...epoch, correlated: true, controlKind: "review_result" }, expectedAllowed: true, expectedReasonOrCode: "structured-control", principalOverride: privatePrincipal("council", "council", { requestingPrincipalId: "controller" }) },
  { name: "ambiguous active Worker identity cannot use its Manager communication binding", actorId: "worker", action: "send", targetId: "manager", context: epoch, expectedAllowed: false, expectedReasonOrCode: "AMBIGUOUS_PARTICIPANT_IDENTITY", additionalPrincipals: [privatePrincipal("worker", "worker", { principalId: "worker-duplicate" })] },
  { name: "Manager cannot control an ambiguous active Scout identity by assignment", actorId: "manager", action: "control", targetId: "scout", context: { ...epoch, correlated: true, controlKind: "assignment_request" }, expectedAllowed: false, expectedReasonOrCode: "AMBIGUOUS_PARTICIPANT_IDENTITY", additionalPrincipals: [privatePrincipal("scout", "scout", { principalId: "scout-duplicate" })] },
  { name: "Worker cannot control an ambiguous active Manager identity by assignment", actorId: "worker", action: "control", targetId: "manager", context: { ...epoch, correlated: true, controlKind: "assignment_response" }, expectedAllowed: false, expectedReasonOrCode: "AMBIGUOUS_PARTICIPANT_IDENTITY", additionalPrincipals: [privatePrincipal("manager", "manager", { principalId: "manager-duplicate" })] },
  { name: "ambiguous active Controller identity cannot use broad discovery", actorId: "controller", action: "discover", targetId: "council", context: epoch, expectedAllowed: false, expectedReasonOrCode: "AMBIGUOUS_PARTICIPANT_IDENTITY", additionalPrincipals: [privatePrincipal("controller", "controller", { principalId: "controller-duplicate" })] },
] as const;

export function bossPolicyStateForVector(vector: BossPolicyVector): BossPolicyState {
  const entries = principals.map((principal) => structuredClone(principal));
  if (vector.principalOverride) {
    const index = entries.findIndex((principal) => principal.principalId === vector.principalOverride?.principalId);
    entries[index] = structuredClone(vector.principalOverride);
  }
  for (const principal of vector.additionalPrincipals ?? []) entries.push(structuredClone(principal));
  return { principals: Object.fromEntries(entries.map((principal) => [principal.principalId, principal])) };
}

export const BOSS_POLICY_SEMANTICS_HASH = canonicalHash("agent-intercom-core/boss-run-v1/policy-vectors", {
  version: BOSS_POLICY_VECTOR_SCHEMA_VERSION,
  vectors: BOSS_POLICY_VECTORS,
});
