export const POLICY_SEMANTICS_VERSION = 2;

export type PolicyAction = "discover" | "send" | "ask" | "reply" | "inspect_tree" | "delegate_child" | "revoke" | "adopt";
export type PrincipalKind = "local" | "remote";
export type PrincipalState = "active" | "revoked";
export type PrincipalPolicy = "local-public" | "remote-tree";

export interface PolicyPrincipal {
  id: string;
  kind: PrincipalKind;
  state: PrincipalState;
  generation: number;
  policy: PrincipalPolicy;
  parentSessionId?: string;
  rootSessionId: string;
}

export interface PolicyState {
  principals: Record<string, PolicyPrincipal>;
}

export interface AuthorizationContext {
  actorGeneration?: number;
  targetGeneration?: number;
}

export type AuthorizationDenialCode =
  | "UNKNOWN_PRINCIPAL"
  | "REVOKED_PRINCIPAL"
  | "STALE_GENERATION"
  | "POLICY_DENIED";

export type AuthorizationDecision =
  | { allowed: true; reason: "self" | "local-public" | "direct-parent" | "ancestor-chain" | "ancestor-control" }
  | { allowed: false; code: AuthorizationDenialCode };

function activePrincipal(state: PolicyState, id: string): PolicyPrincipal | undefined {
  return state.principals[id];
}

export function isDirectParentPair(left: PolicyPrincipal, right: PolicyPrincipal): boolean {
  return left.parentSessionId === right.id || right.parentSessionId === left.id;
}

export function isAncestor(state: PolicyState, ancestorId: string, descendantId: string): boolean {
  if (ancestorId === descendantId) return false;
  const visited = new Set<string>();
  let current = state.principals[descendantId];
  while (current?.parentSessionId && !visited.has(current.id)) {
    if (current.parentSessionId === ancestorId) return true;
    visited.add(current.id);
    current = state.principals[current.parentSessionId];
  }
  return false;
}

export function authorize(
  state: PolicyState,
  actorId: string,
  action: PolicyAction,
  targetId: string,
  context: AuthorizationContext = {},
): AuthorizationDecision {
  const actor = activePrincipal(state, actorId);
  const target = activePrincipal(state, targetId);
  if (!actor || !target) return { allowed: false, code: "UNKNOWN_PRINCIPAL" };
  if (actor.state !== "active" || target.state !== "active") return { allowed: false, code: "REVOKED_PRINCIPAL" };
  if (
    (context.actorGeneration !== undefined && context.actorGeneration !== actor.generation)
    || (context.targetGeneration !== undefined && context.targetGeneration !== target.generation)
  ) {
    return { allowed: false, code: "STALE_GENERATION" };
  }
  if (actor.id === target.id) return { allowed: true, reason: "self" };
  if (actor.kind === "local" && target.kind === "local") return { allowed: true, reason: "local-public" };
  if (action === "discover" || action === "send" || action === "ask" || action === "reply") {
    if (isDirectParentPair(actor, target)) return { allowed: true, reason: "direct-parent" };
    if (isAncestor(state, actor.id, target.id) || isAncestor(state, target.id, actor.id)) {
      return { allowed: true, reason: "ancestor-chain" };
    }
  }
  if (action === "inspect_tree" || action === "revoke" || action === "adopt") {
    if (isAncestor(state, actor.id, target.id)) return { allowed: true, reason: "ancestor-control" };
  }
  return { allowed: false, code: "POLICY_DENIED" };
}

export interface PolicyTransitionResult {
  state: PolicyState;
  changedPrincipalIds: string[];
}

function cloneState(state: PolicyState): PolicyState {
  return { principals: Object.fromEntries(Object.entries(state.principals).map(([id, principal]) => [id, { ...principal }])) };
}

function subtreeIds(state: PolicyState, rootId: string): string[] {
  const result: string[] = [];
  const queue = [rootId];
  const seen = new Set<string>();
  while (queue.length) {
    const id = queue.shift()!;
    if (seen.has(id) || !state.principals[id]) continue;
    seen.add(id);
    result.push(id);
    for (const principal of Object.values(state.principals)) {
      if (principal.parentSessionId === id) queue.push(principal.id);
    }
  }
  return result;
}

export function revokeSubtree(state: PolicyState, principalId: string): PolicyTransitionResult {
  const next = cloneState(state);
  const changedPrincipalIds = subtreeIds(next, principalId);
  for (const id of changedPrincipalIds) {
    const principal = next.principals[id];
    principal.state = "revoked";
    principal.generation += 1;
  }
  return { state: next, changedPrincipalIds };
}

export function adoptSubtree(
  state: PolicyState,
  principalId: string,
  newParentSessionId: string,
  newRootSessionId: string,
): PolicyTransitionResult {
  if (!state.principals[principalId]) throw new Error(`Unknown principal: ${principalId}`);
  if (!state.principals[newParentSessionId]) throw new Error(`Unknown parent principal: ${newParentSessionId}`);
  if (principalId === newParentSessionId || isAncestor(state, principalId, newParentSessionId)) {
    throw new Error("Adoption would create an ownership cycle");
  }
  const next = cloneState(state);
  const changedPrincipalIds = subtreeIds(next, principalId);
  next.principals[principalId].parentSessionId = newParentSessionId;
  for (const id of changedPrincipalIds) {
    const principal = next.principals[id];
    principal.rootSessionId = newRootSessionId;
    principal.generation += 1;
  }
  return { state: next, changedPrincipalIds };
}
