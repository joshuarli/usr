import type {
  ActiveOperationLease,
  AuthenticatedActivityRecord,
  ExternalWaitLease,
  InactivityEdgeKey,
  LifecycleSubscriptionRecord,
  DeliveryGroupMigrationLink,
  LifecycleTriggerRecord,
  SubscriberRebindMigrationRecord,
  RebindMigrationLinkEvidence,
  SupervisorAclState,
  SupervisorAuthorizationDecision,
  SupervisorAuthorizationRequest,
} from "./supervision.ts";
import { rebindMigrationEvidenceDigest } from "./supervision.ts";
import {
  DELIVERY_CLAIM_VERSION,
  DELIVERY_GROUP_VERSION,
  deliveryGroupId,
  type DeliveryClaimRecord,
  type DeliveryEquivalenceKey,
  type DeliveryGroupRecord,
} from "./boss-wire.ts";
import {
  controllerGeneration,
  deliveryClaimGeneration,
  participantBindingEpoch,
  recipientTransferGeneration,
  subscriberBindingEpoch,
  subscriberBindingGeneration,
  transitionVersion,
  triggerGeneration,
  workerGeneration,
} from "./canonical.ts";
import {
  SUPERVISION_VECTOR_SCHEMA_VERSION,
  SUPERVISION_VECTORS_HASH,
} from "./boss-semantic-binding-constants.ts";

export {
  SUPERVISION_VECTOR_SCHEMA_VERSION,
  SUPERVISION_VECTORS_HASH,
};

export const SUPERVISION_VECTOR_HASH_DOMAIN = "agent-intercom-core/orc-supervision-v1" as const;

const CREATED_AT = "2026-07-28T12:00:00.000Z";

export const MANAGER_WORKER_SUBSCRIPTION_VECTOR: LifecycleSubscriptionRecord = {
  version: "orc.lifecycle-subscription.v1",
  subscriptionId: "subscription-manager-worker-60s",
  subscriberPrincipalId: "manager-a",
  subscriberBindingEpoch: subscriberBindingEpoch(4),
  subscriberBindingGeneration: subscriberBindingGeneration(2),
  lastSubscriberAuthorityTransitionId: "authority-transition-manager-bind-4",
  bossRunId: "boss-run-a",
  target: { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) },
  followReplacement: false,
  predicates: [{ kind: "state_changed" }, { kind: "failed" }, { kind: "stopped" }, { kind: "inactive_for" }],
  inactivityMode: "smart",
  inactiveAfterMs: 60_000,
  activityBasis: "meaningful",
  cooldownMs: 0,
  expiresAt: "2026-07-29T12:00:00.000Z",
  delivery: "wake",
  state: "armed",
  triggerGeneration: triggerGeneration(0),
  lastActivityAt: CREATED_AT,
  dueAt: "2026-07-28T12:01:00.000Z",
  createdAt: CREATED_AT,
  updatedAt: CREATED_AT,
};

export const BOSS_MANAGER_SUBSCRIPTION_VECTOR: LifecycleSubscriptionRecord = {
  version: "orc.lifecycle-subscription.v1",
  subscriptionId: "subscription-boss-manager-10m",
  subscriberPrincipalId: "boss-a",
  subscriberBindingEpoch: subscriberBindingEpoch(3),
  subscriberBindingGeneration: subscriberBindingGeneration(5),
  lastSubscriberAuthorityTransitionId: "authority-transition-boss-bind-3",
  bossRunId: "boss-run-a",
  target: { kind: "role", bossRunId: "boss-run-a", role: "manager" },
  followReplacement: true,
  predicates: [{ kind: "failed" }, { kind: "stopped" }, { kind: "inactive_for" }],
  inactivityMode: "smart",
  inactiveAfterMs: 600_000,
  activityBasis: "meaningful",
  cooldownMs: 0,
  maxFires: 8,
  delivery: "follow_up",
  state: "armed",
  triggerGeneration: triggerGeneration(0),
  lastActivityAt: CREATED_AT,
  dueAt: "2026-07-28T12:10:00.000Z",
  createdAt: CREATED_AT,
  updatedAt: CREATED_AT,
};

/** Persisted scheduler states that must fail closed at the subscription/store boundary. */
export const LIFECYCLE_SUBSCRIPTION_SCHEDULER_NEGATIVE_VECTORS: readonly { name: string; value: unknown }[] = [
  {
    name: "dueAt cannot precede lastActivityAt plus inactiveAfterMs",
    value: {
      ...MANAGER_WORKER_SUBSCRIPTION_VECTOR,
      dueAt: "2026-07-28T12:00:59.999Z",
    },
  },
  {
    name: "scheduler timestamp addition cannot overflow the safe integer range",
    value: {
      ...MANAGER_WORKER_SUBSCRIPTION_VECTOR,
      inactiveAfterMs: Number.MAX_SAFE_INTEGER,
      dueAt: "9999-12-31T23:59:59.999Z",
    },
  },
  {
    name: "scheduler relation rejects a noncanonical dueAt timestamp",
    value: {
      ...MANAGER_WORKER_SUBSCRIPTION_VECTOR,
      dueAt: "2026-07-28T12:01:00Z",
    },
  },
  {
    name: "triggerGeneration cannot exceed maxFires",
    value: {
      ...BOSS_MANAGER_SUBSCRIPTION_VECTOR,
      triggerGeneration: triggerGeneration(9),
    },
  },
] as const;

export const AUTHENTICATED_ACTIVITY_VECTOR: AuthenticatedActivityRecord = {
  version: "orc.activity-record.v1",
  activityId: "activity-worker-a-tool-1",
  workerId: "worker-a",
  workerGeneration: workerGeneration(7),
  sourceEventId: "worker-event-tool-progress-1",
  participantId: "worker-participant-a",
  bindingEpoch: participantBindingEpoch(6),
  kind: "meaningful",
  activityType: "tool",
  occurredAt: "2026-07-28T12:00:10.000Z",
};

export const ACTIVE_OPERATION_LEASE_VECTOR: ActiveOperationLease = {
  version: "orc.active-operation-lease.v1",
  leaseId: "operation-lease-1",
  workerId: "worker-a",
  workerGeneration: workerGeneration(7),
  invocationId: "terminal-invocation-1",
  processId: 4242,
  cgroupIdentity: "user.slice/orc-worker-a.scope#invocation-1",
  startedAt: "2026-07-28T12:00:10.000Z",
  renewBy: "2026-07-28T12:01:10.000Z",
  maxUntil: "2026-07-28T12:20:00.000Z",
  hardWorkerLeaseExpiresAt: "2026-07-28T12:30:00.000Z",
  maxRuntimeAt: "2026-07-28T13:00:00.000Z",
  state: "active",
};

export const EXTERNAL_WAIT_LEASE_VECTOR: ExternalWaitLease = {
  version: "orc.external-wait-lease.v1",
  leaseId: "external-wait-lease-1",
  workerId: "worker-a",
  workerGeneration: workerGeneration(7),
  sourceKind: "process",
  sourceRefHash: "f8f4c22c86b62fe57ee20f13ca34a981a4a2ed13878efef167a047687d1f5334",
  processIdentity: "pidfd:4243:starttime:123456",
  startedAt: "2026-07-28T12:00:10.000Z",
  renewBy: "2026-07-28T12:10:00.000Z",
  maxUntil: "2026-07-28T13:30:00.000Z",
  expectedWakeAt: "2026-07-28T13:00:00.000Z",
  hardWorkerLeaseExpiresAt: "2026-07-28T14:00:00.000Z",
  maxRuntimeAt: "2026-07-28T15:00:00.000Z",
  state: "active",
};

export const LIFECYCLE_TRIGGER_VECTOR: LifecycleTriggerRecord = {
  version: "orc.lifecycle-trigger.v1",
  triggerId: "trigger-subscription-manager-worker-1",
  subscriptionId: MANAGER_WORKER_SUBSCRIPTION_VECTOR.subscriptionId,
  triggerGeneration: triggerGeneration(1),
  targetWorkerId: "worker-a",
  targetWorkerGeneration: workerGeneration(7),
  predicateEdge: "inactive_for:smart:meaningful:60000:2026-07-28T12:01:00.000Z",
  sourceEventId: "inactivity-event-worker-a-epoch-1",
  transitionId: "0db9f264c21905c17728172782dbcc7e79dc1fbf8aa4d3e6aae1b1233daec1a3",
  subscriberBindingEpoch: subscriberBindingEpoch(4),
  subscriberBindingGeneration: subscriberBindingGeneration(2),
  deliveryGroupId: "delivery-group-old-epoch-4",
  deliveryGroupMembershipRevision: 11,
  noticeId: "notice-subscription-trigger-1",
  recipientTransferGeneration: recipientTransferGeneration(0),
  createdAt: "2026-07-28T12:01:00.000Z",
};

export const INACTIVITY_EDGE_VECTORS: readonly InactivityEdgeKey[] = [
  {
    workerId: "worker-a",
    workerGeneration: workerGeneration(7),
    inactivityEpochId: "inactive-epoch-1",
    inactivityMode: "smart",
    activityBasis: "meaningful",
    inactiveAfterMs: 60_000,
    dueAt: "2026-07-28T12:01:00.000Z",
  },
  {
    workerId: "worker-a",
    workerGeneration: workerGeneration(7),
    inactivityEpochId: "inactive-epoch-1",
    inactivityMode: "smart",
    activityBasis: "meaningful",
    inactiveAfterMs: 600_000,
    dueAt: "2026-07-28T12:10:00.000Z",
  },
] as const;

function rebindEquivalence(sourceEventId: string, recipientBindingEpoch: number): DeliveryEquivalenceKey {
  return {
    recipientPrincipalId: "manager-a",
    recipientBindingEpoch,
    sourceAuthorityId: { kind: "controller", bossRunId: "boss-run-a", controllerGeneration: controllerGeneration(2) },
    sourceEventId,
    bossRunId: "boss-run-a",
    workerId: "worker-a",
    workerGeneration: workerGeneration(7),
    transitionId: `transition-${sourceEventId}`,
    transitionVersion: transitionVersion(1),
  };
}

const migratedOldKey = rebindEquivalence("event-pending", 4);
const migratedNewKey = rebindEquivalence("event-pending", 5);
const insertedOldKey = rebindEquivalence("event-inserted", 4);
const deliveredOldKey = rebindEquivalence("event-delivered", 4);
const blockedOldKey: DeliveryEquivalenceKey = {
  ...rebindEquivalence("event-blocked", 3),
  recipientPrincipalId: "boss-a",
};

function rebindOldGroup(
  equivalenceKey: DeliveryEquivalenceKey,
  state: DeliveryGroupRecord["state"],
  transferGeneration: number,
): DeliveryGroupRecord {
  const noticeId = `notice-${equivalenceKey.sourceEventId}`;
  return {
    version: DELIVERY_GROUP_VERSION,
    deliveryGroupId: deliveryGroupId(equivalenceKey),
    equivalenceKey,
    subscriptionRegistryRevision: 12,
    membershipRevision: 1,
    membershipState: "sealed",
    primaryNoticeId: noticeId,
    memberNoticeIds: [noticeId],
    requestedIntents: ["wake"],
    effectiveDeliveryIntent: "wake",
    recipientTransferGeneration: recipientTransferGeneration(transferGeneration),
    state,
  };
}

function rebindClaim(
  group: DeliveryGroupRecord,
  state: "inserting" | "delivered",
  times: { attemptedAt: string; insertedAt?: string; deliveredAt?: string },
): DeliveryClaimRecord {
  return {
    version: DELIVERY_CLAIM_VERSION,
    deliveryClaimId: `claim-${group.equivalenceKey.sourceEventId}`,
    deliveryGroupId: group.deliveryGroupId,
    membershipRevision: group.membershipRevision,
    effectiveDeliveryIntent: group.effectiveDeliveryIntent,
    primaryNoticeId: group.primaryNoticeId,
    memberNoticeIds: group.memberNoticeIds,
    claimGeneration: deliveryClaimGeneration(1),
    expiresAt: "2026-07-28T12:30:00.000Z",
    recipientContext: "pi",
    recipientSessionId: `session-${group.equivalenceKey.recipientPrincipalId}`,
    recipientPrincipalId: group.equivalenceKey.recipientPrincipalId,
    recipientBindingEpoch: group.equivalenceKey.recipientBindingEpoch,
    recipientTransferGeneration: group.recipientTransferGeneration,
    workerId: group.equivalenceKey.workerId,
    workerGeneration: group.equivalenceKey.workerGeneration,
    transitionId: group.equivalenceKey.transitionId,
    transitionVersion: group.equivalenceKey.transitionVersion,
    ingressMode: "lifecycle_message",
    state,
    deliveryAttemptedAt: times.attemptedAt,
    ...(state === "delivered" ? {
      targetLedgerEntryId: `ledger-${group.equivalenceKey.sourceEventId}`,
      insertedAt: times.insertedAt!,
      deliveredAt: times.deliveredAt!,
      deliveryReceiptId: `receipt-${group.equivalenceKey.sourceEventId}`,
    } : {}),
  };
}

function authenticatedRebindEvidence(
  evidence: Omit<RebindMigrationLinkEvidence, "evidenceDigest">,
): RebindMigrationLinkEvidence {
  return { ...evidence, evidenceDigest: rebindMigrationEvidenceDigest(evidence) };
}

const migratedOldGroup = rebindOldGroup(migratedOldKey, "pending", 0);
const deliveredOldGroup = rebindOldGroup(insertedOldKey, "delivered", 0);
const acknowledgedOldGroup = rebindOldGroup(deliveredOldKey, "delivered", 1);
const ambiguousOldGroup = rebindOldGroup(blockedOldKey, "inserting", 2);
const deliveredOldClaim = rebindClaim(deliveredOldGroup, "delivered", {
  attemptedAt: "2026-07-28T12:04:50.000Z",
  insertedAt: "2026-07-28T12:04:51.000Z",
  deliveredAt: "2026-07-28T12:04:52.000Z",
});
const ambiguousOldClaim = rebindClaim(ambiguousOldGroup, "inserting", {
  attemptedAt: "2026-07-28T12:05:50.000Z",
});

export const COMMITTED_REBIND_MIGRATION_VECTOR: SubscriberRebindMigrationRecord = {
  version: "orc.subscriber-rebind-migration.v1",
  authorityTransitionId: "authority-transition-subscriber-rebind-5",
  subscriptionId: MANAGER_WORKER_SUBSCRIPTION_VECTOR.subscriptionId,
  stableSubscriberPrincipalId: "manager-a",
  oldSubscriberBindingEpoch: subscriberBindingEpoch(4),
  newSubscriberBindingEpoch: subscriberBindingEpoch(5),
  oldSubscriberBindingGeneration: subscriberBindingGeneration(2),
  newSubscriberBindingGeneration: subscriberBindingGeneration(3),
  reauthorized: true,
  resultingSubscriptionState: "armed",
  deliveryGroups: [
    {
      oldDeliveryGroupId: deliveryGroupId(migratedOldKey),
      oldEquivalenceKey: migratedOldKey,
      successorDeliveryGroupId: deliveryGroupId(migratedNewKey),
      successorEquivalenceKey: migratedNewKey,
      disposition: "migrated",
      previousRecipientTransferGeneration: recipientTransferGeneration(0),
      recipientTransferGeneration: recipientTransferGeneration(1),
      evidence: authenticatedRebindEvidence({
        authorityPrincipalId: "manager-a",
        authoritySessionId: "session-manager-a-epoch-4",
        authenticatedAt: "2026-07-28T12:04:59.000Z",
        oldGroup: migratedOldGroup,
        currentClaim: { status: "unclaimed", observedAt: "2026-07-28T12:04:56.000Z" },
        targetLedger: {
          deliveryGroupId: migratedOldGroup.deliveryGroupId,
          membershipRevision: migratedOldGroup.membershipRevision,
          recipientPrincipalId: "manager-a",
          recipientBindingEpoch: subscriberBindingEpoch(4),
          recipientTransferGeneration: recipientTransferGeneration(0),
          state: "absent",
          checkedAt: "2026-07-28T12:04:57.000Z",
        },
        drainBarrier: {
          deliveryGroupId: migratedOldGroup.deliveryGroupId,
          membershipRevision: migratedOldGroup.membershipRevision,
          recipientPrincipalId: "manager-a",
          recipientBindingEpoch: subscriberBindingEpoch(4),
          recipientTransferGeneration: recipientTransferGeneration(0),
          barrierId: "barrier-event-pending",
          noSessionEntry: true,
          noAdapterQueue: true,
          noInflightInvocation: true,
          operativePathsDrained: true,
          establishedAt: "2026-07-28T12:04:58.000Z",
        },
      }),
    },
    {
      oldDeliveryGroupId: deliveryGroupId(insertedOldKey),
      oldEquivalenceKey: insertedOldKey,
      disposition: "delivered_old_epoch",
      previousRecipientTransferGeneration: recipientTransferGeneration(0),
      recipientTransferGeneration: recipientTransferGeneration(0),
      evidence: authenticatedRebindEvidence({
        authorityPrincipalId: "manager-a",
        authoritySessionId: "session-manager-a-epoch-4",
        authenticatedAt: "2026-07-28T12:04:59.000Z",
        oldGroup: deliveredOldGroup,
        currentClaim: { status: "claimed", observedAt: "2026-07-28T12:04:53.000Z", claim: deliveredOldClaim },
        targetLedger: {
          deliveryGroupId: deliveredOldGroup.deliveryGroupId,
          membershipRevision: deliveredOldGroup.membershipRevision,
          recipientPrincipalId: "manager-a",
          recipientBindingEpoch: subscriberBindingEpoch(4),
          recipientTransferGeneration: recipientTransferGeneration(0),
          state: "inserted",
          checkedAt: "2026-07-28T12:04:53.000Z",
          targetLedgerEntryId: deliveredOldClaim.targetLedgerEntryId!,
          insertedAt: deliveredOldClaim.insertedAt!,
        },
        receipt: {
          deliveryClaimId: deliveredOldClaim.deliveryClaimId,
          claimGeneration: deliveredOldClaim.claimGeneration,
          deliveryGroupId: deliveredOldGroup.deliveryGroupId,
          membershipRevision: deliveredOldGroup.membershipRevision,
          recipientPrincipalId: "manager-a",
          recipientBindingEpoch: subscriberBindingEpoch(4),
          recipientTransferGeneration: recipientTransferGeneration(0),
          deliveryReceiptId: deliveredOldClaim.deliveryReceiptId!,
          targetLedgerEntryId: deliveredOldClaim.targetLedgerEntryId!,
          insertedAt: deliveredOldClaim.insertedAt!,
          deliveredAt: deliveredOldClaim.deliveredAt!,
        },
      }),
    },
    {
      oldDeliveryGroupId: deliveryGroupId(deliveredOldKey),
      oldEquivalenceKey: deliveredOldKey,
      disposition: "not_replayed",
      previousRecipientTransferGeneration: recipientTransferGeneration(1),
      recipientTransferGeneration: recipientTransferGeneration(1),
      evidence: authenticatedRebindEvidence({
        authorityPrincipalId: "manager-a",
        authoritySessionId: "session-manager-a-epoch-4",
        authenticatedAt: "2026-07-28T12:04:59.000Z",
        oldGroup: acknowledgedOldGroup,
        currentClaim: { status: "unclaimed", observedAt: "2026-07-28T12:04:56.000Z" },
        targetLedger: {
          deliveryGroupId: acknowledgedOldGroup.deliveryGroupId,
          membershipRevision: acknowledgedOldGroup.membershipRevision,
          recipientPrincipalId: "manager-a",
          recipientBindingEpoch: subscriberBindingEpoch(4),
          recipientTransferGeneration: recipientTransferGeneration(1),
          state: "inserted",
          checkedAt: "2026-07-28T12:04:57.000Z",
          targetLedgerEntryId: "ledger-event-delivered",
          insertedAt: "2026-07-28T12:04:50.000Z",
        },
        acknowledgment: {
          deliveryGroupId: acknowledgedOldGroup.deliveryGroupId,
          noticeIds: acknowledgedOldGroup.memberNoticeIds,
          recipientPrincipalId: "manager-a",
          recipientBindingEpoch: subscriberBindingEpoch(4),
          acknowledgedAt: "2026-07-28T12:04:58.000Z",
        },
      }),
    },
  ],
  state: "committed",
  createdAt: "2026-07-28T12:05:00.000Z",
  committedAt: "2026-07-28T12:05:01.000Z",
};

export const BLOCKED_REBIND_MIGRATION_VECTOR: SubscriberRebindMigrationRecord = {
  version: "orc.subscriber-rebind-migration.v1",
  authorityTransitionId: "authority-transition-subscriber-rebind-blocked",
  subscriptionId: BOSS_MANAGER_SUBSCRIPTION_VECTOR.subscriptionId,
  stableSubscriberPrincipalId: "boss-a",
  oldSubscriberBindingEpoch: subscriberBindingEpoch(3),
  newSubscriberBindingEpoch: subscriberBindingEpoch(4),
  oldSubscriberBindingGeneration: subscriberBindingGeneration(5),
  newSubscriberBindingGeneration: subscriberBindingGeneration(6),
  reauthorized: true,
  resultingSubscriptionState: "suspended",
  deliveryGroups: [{
    oldDeliveryGroupId: deliveryGroupId(blockedOldKey),
    oldEquivalenceKey: blockedOldKey,
    disposition: "blocked_ambiguous",
    previousRecipientTransferGeneration: recipientTransferGeneration(2),
    recipientTransferGeneration: recipientTransferGeneration(2),
    evidence: authenticatedRebindEvidence({
      authorityPrincipalId: "boss-a",
      authoritySessionId: "session-boss-a-epoch-3",
      authenticatedAt: "2026-07-28T12:05:59.000Z",
      oldGroup: ambiguousOldGroup,
      currentClaim: { status: "claimed", observedAt: "2026-07-28T12:05:51.000Z", claim: ambiguousOldClaim },
      targetLedger: {
        deliveryGroupId: ambiguousOldGroup.deliveryGroupId,
        membershipRevision: ambiguousOldGroup.membershipRevision,
        recipientPrincipalId: "boss-a",
        recipientBindingEpoch: subscriberBindingEpoch(3),
        recipientTransferGeneration: recipientTransferGeneration(2),
        state: "ambiguous",
        checkedAt: "2026-07-28T12:05:52.000Z",
      },
    }),
  }],
  state: "blocked",
  createdAt: "2026-07-28T12:06:00.000Z",
};

function replaceRebindEvidence(
  link: DeliveryGroupMigrationLink,
  changes: Partial<Omit<RebindMigrationLinkEvidence, "evidenceDigest">>,
): DeliveryGroupMigrationLink {
  const { evidenceDigest: _discarded, ...base } = link.evidence;
  return { ...link, evidence: authenticatedRebindEvidence({ ...base, ...changes }) };
}

const migratedLink = COMMITTED_REBIND_MIGRATION_VECTOR.deliveryGroups[0];
const deliveredLink = COMMITTED_REBIND_MIGRATION_VECTOR.deliveryGroups[1];
const notReplayedLink = COMMITTED_REBIND_MIGRATION_VECTOR.deliveryGroups[2];
const claimedPendingGroup = rebindClaim(migratedOldGroup, "inserting", {
  attemptedAt: "2026-07-28T12:04:55.000Z",
});
const { acknowledgment: _acknowledgment, ...notReplayedWithoutAck } = (() => {
  const { evidenceDigest: _digest, ...evidence } = notReplayedLink.evidence;
  return evidence;
})();

/** Fail-closed cases from the authoritative subscriber-rebind review. */
export const REBIND_MIGRATION_NEGATIVE_VECTORS: readonly { name: string; value: unknown }[] = [
  {
    name: "claimed old group cannot migrate even with absent ledger and a drained barrier",
    value: {
      ...COMMITTED_REBIND_MIGRATION_VECTOR,
      deliveryGroups: [replaceRebindEvidence(migratedLink, {
        currentClaim: { status: "claimed", observedAt: "2026-07-28T12:04:56.000Z", claim: claimedPendingGroup },
      })],
    },
  },
  {
    name: "ambiguous authenticated ledger cannot be classified as migrated",
    value: {
      ...COMMITTED_REBIND_MIGRATION_VECTOR,
      deliveryGroups: [replaceRebindEvidence(migratedLink, {
        targetLedger: { ...migratedLink.evidence.targetLedger, state: "ambiguous" },
      })],
    },
  },
  {
    name: "partial target drain is not absence proof",
    value: {
      ...COMMITTED_REBIND_MIGRATION_VECTOR,
      deliveryGroups: [{
        ...migratedLink,
        evidence: {
          ...migratedLink.evidence,
          drainBarrier: { ...migratedLink.evidence.drainBarrier!, noAdapterQueue: false },
        },
      }],
    },
  },
  {
    name: "delivered-old disposition rejects a receipt from another delivery",
    value: {
      ...COMMITTED_REBIND_MIGRATION_VECTOR,
      deliveryGroups: [replaceRebindEvidence(deliveredLink, {
        receipt: { ...deliveredLink.evidence.receipt!, deliveryReceiptId: "receipt-substitution" },
      })],
    },
  },
  {
    name: "not-replayed disposition rejects a delivered-looking group without receipt or acknowledgment",
    value: {
      ...COMMITTED_REBIND_MIGRATION_VECTOR,
      deliveryGroups: [{
        ...notReplayedLink,
        evidence: authenticatedRebindEvidence(notReplayedWithoutAck),
      }],
    },
  },
  {
    name: "cross-group old-state evidence cannot satisfy a migration link",
    value: {
      ...COMMITTED_REBIND_MIGRATION_VECTOR,
      deliveryGroups: [replaceRebindEvidence(migratedLink, { oldGroup: acknowledgedOldGroup })],
    },
  },
  {
    name: "evidence substitution without a new authenticated digest is rejected",
    value: {
      ...COMMITTED_REBIND_MIGRATION_VECTOR,
      deliveryGroups: [{
        ...migratedLink,
        evidence: { ...migratedLink.evidence, authoritySessionId: "substituted-session" },
      }],
    },
  },
  {
    name: "ambiguous old group cannot be committed",
    value: {
      ...BLOCKED_REBIND_MIGRATION_VECTOR,
      state: "committed",
      committedAt: "2026-07-28T12:06:01.000Z",
    },
  },
] as const;

export const SUPERVISOR_ACL_STATE: SupervisorAclState = {
  principals: {
    "owner-local": {
      principalId: "owner-local",
      kind: "ordinary_owner",
      state: "active",
      bindingEpoch: subscriberBindingEpoch(2),
      bindingGeneration: subscriberBindingGeneration(3),
      ownedWorkerIds: ["local-worker-a"],
    },
    "owner-revoked": {
      principalId: "owner-revoked",
      kind: "ordinary_owner",
      state: "revoked",
      bindingEpoch: subscriberBindingEpoch(1),
      bindingGeneration: subscriberBindingGeneration(1),
      ownedWorkerIds: ["local-worker-a"],
    },
    "boss-a": {
      principalId: "boss-a",
      kind: "boss",
      state: "active",
      bindingEpoch: subscriberBindingEpoch(3),
      bindingGeneration: subscriberBindingGeneration(5),
      bossRunId: "boss-run-a",
    },
    "manager-a": {
      principalId: "manager-a",
      participantId: "manager-participant-a",
      kind: "manager",
      state: "active",
      bindingEpoch: subscriberBindingEpoch(4),
      bindingGeneration: subscriberBindingGeneration(2),
      bossRunId: "boss-run-a",
      assignedParticipantIds: ["worker-participant-a", "scout-participant-a"],
    },
    "manager-a-superseded": {
      principalId: "manager-a-superseded",
      participantId: "old-manager-a",
      kind: "manager",
      state: "active",
      bindingEpoch: subscriberBindingEpoch(3),
      bindingGeneration: subscriberBindingGeneration(1),
      bossRunId: "boss-run-a",
      assignedParticipantIds: ["worker-participant-a", "scout-participant-a"],
    },
    "controller-a": {
      principalId: "controller-a",
      kind: "controller",
      state: "active",
      bindingEpoch: subscriberBindingEpoch(8),
      bindingGeneration: subscriberBindingGeneration(1),
      bossRunId: "boss-run-a",
    },
    "worker-principal-a": {
      principalId: "worker-principal-a",
      kind: "worker",
      state: "active",
      bindingEpoch: subscriberBindingEpoch(2),
      bindingGeneration: subscriberBindingGeneration(1),
      bossRunId: "boss-run-a",
    },
    "boss-b": {
      principalId: "boss-b",
      kind: "boss",
      state: "active",
      bindingEpoch: subscriberBindingEpoch(1),
      bindingGeneration: subscriberBindingGeneration(1),
      bossRunId: "boss-run-b",
    },
  },
  workers: {
    "local-worker-a": { workerId: "local-worker-a", workerGeneration: workerGeneration(3), active: true },
    "local-worker-b": { workerId: "local-worker-b", workerGeneration: workerGeneration(1), active: true },
    "boss-worker-a": {
      workerId: "boss-worker-a",
      workerGeneration: workerGeneration(1),
      participantId: "boss-a",
      role: "boss",
      bossRunId: "boss-run-a",
      active: true,
    },
    "manager-worker-a": {
      workerId: "manager-worker-a",
      workerGeneration: workerGeneration(5),
      participantId: "manager-participant-a",
      role: "manager",
      bossRunId: "boss-run-a",
      active: true,
    },
    "old-manager-worker-a": {
      workerId: "old-manager-worker-a",
      workerGeneration: workerGeneration(2),
      participantId: "old-manager-a",
      role: "manager",
      bossRunId: "boss-run-a",
      active: true,
    },
    "worker-a": {
      workerId: "worker-a",
      workerGeneration: workerGeneration(7),
      participantId: "worker-participant-a",
      role: "worker",
      bossRunId: "boss-run-a",
      active: true,
    },
    "worker-a-2": {
      workerId: "worker-a-2",
      workerGeneration: workerGeneration(2),
      participantId: "worker-participant-a-2",
      role: "worker",
      bossRunId: "boss-run-a",
      active: true,
    },
    "scout-a": {
      workerId: "scout-a",
      workerGeneration: workerGeneration(3),
      participantId: "scout-participant-a",
      role: "scout",
      bossRunId: "boss-run-a",
      active: true,
    },
    "scout-a-2": {
      workerId: "scout-a-2",
      workerGeneration: workerGeneration(2),
      participantId: "scout-participant-a-2",
      role: "scout",
      bossRunId: "boss-run-a",
      active: true,
    },
    "unregistered-worker-a": {
      workerId: "unregistered-worker-a",
      workerGeneration: workerGeneration(1),
      participantId: "unregistered-worker-participant-a",
      role: "worker",
      bossRunId: "boss-run-a",
      active: true,
    },
    "unregistered-process-a": {
      workerId: "unregistered-process-a",
      workerGeneration: workerGeneration(1),
      role: "adversary",
      bossRunId: "boss-run-a",
      active: true,
    },
    "manager-worker-b": {
      workerId: "manager-worker-b",
      workerGeneration: workerGeneration(1),
      participantId: "manager-b",
      role: "manager",
      bossRunId: "boss-run-b",
      active: true,
    },
    "worker-b": {
      workerId: "worker-b",
      workerGeneration: workerGeneration(1),
      participantId: "worker-participant-b",
      role: "worker",
      bossRunId: "boss-run-b",
      active: true,
    },
  },
  currentManagerByRun: {
    "boss-run-a": "manager-a",
    "boss-run-b": "manager-b",
  },
};

export interface SupervisorAclVector {
  name: string;
  request: SupervisorAuthorizationRequest;
  expected: SupervisorAuthorizationDecision;
}

function request(
  actorPrincipalId: string,
  actorBindingEpoch: number,
  actorBindingGeneration: number,
  target: SupervisorAuthorizationRequest["target"],
  followReplacement = false,
): SupervisorAuthorizationRequest {
  return {
    actorPrincipalId,
    actorBindingEpoch: subscriberBindingEpoch(actorBindingEpoch),
    actorBindingGeneration: subscriberBindingGeneration(actorBindingGeneration),
    target,
    followReplacement,
  };
}

export const SUPERVISOR_ACL_VECTORS: readonly SupervisorAclVector[] = [
  {
    name: "ordinary owner may supervise its ordinary owned worker",
    request: request("owner-local", 2, 3, { kind: "worker", workerId: "local-worker-a", workerGeneration: workerGeneration(3) }),
    expected: { allowed: true, reason: "owner_to_worker" },
  },
  {
    name: "Manager may supervise an assigned Worker in the same Boss run",
    request: request("manager-a", 4, 2, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }),
    expected: { allowed: true, reason: "manager_to_assignment" },
  },
  {
    name: "Manager may supervise an assigned Scout in the same Boss run",
    request: request("manager-a", 4, 2, { kind: "worker", workerId: "scout-a", workerGeneration: workerGeneration(3) }),
    expected: { allowed: true, reason: "manager_to_assignment" },
  },
  {
    name: "superseded Manager cannot use stale assignments in the same Boss run",
    request: request("manager-a-superseded", 3, 1, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }),
    expected: { allowed: false, code: "SUPERVISION_EDGE_DENIED" },
  },
  {
    name: "Boss may follow the current Manager role",
    request: request("boss-a", 3, 5, { kind: "role", bossRunId: "boss-run-a", role: "manager" }, true),
    expected: { allowed: true, reason: "boss_to_manager" },
  },
  {
    name: "Controller may supervise an authenticated participant in its run",
    request: request("controller-a", 8, 1, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }),
    expected: { allowed: true, reason: "controller_to_participant" },
  },
  {
    name: "Controller may supervise the Boss role in its run",
    request: request("controller-a", 8, 1, { kind: "role", bossRunId: "boss-run-a", role: "boss" }),
    expected: { allowed: true, reason: "controller_to_participant" },
  },
  {
    name: "Controller may follow the current Manager role in its run",
    request: request("controller-a", 8, 1, { kind: "role", bossRunId: "boss-run-a", role: "manager" }, true),
    expected: { allowed: true, reason: "controller_to_participant" },
  },
  {
    name: "Controller may supervise every active Worker in its run",
    request: request("controller-a", 8, 1, { kind: "role", bossRunId: "boss-run-a", role: "worker" }),
    expected: { allowed: true, reason: "controller_to_participant" },
  },
  {
    name: "Controller may supervise every active Scout in its run",
    request: request("controller-a", 8, 1, { kind: "role", bossRunId: "boss-run-a", role: "scout" }),
    expected: { allowed: true, reason: "controller_to_participant" },
  },
  {
    name: "unknown subscriber is denied without discovery",
    request: request("missing", 1, 1, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }),
    expected: { allowed: false, code: "UNKNOWN_SUBSCRIBER" },
  },
  {
    name: "revoked subscriber is denied",
    request: request("owner-revoked", 1, 1, { kind: "worker", workerId: "local-worker-a", workerGeneration: workerGeneration(3) }),
    expected: { allowed: false, code: "REVOKED_SUBSCRIBER" },
  },
  {
    name: "stale subscriber epoch is fenced",
    request: request("manager-a", 3, 2, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }),
    expected: { allowed: false, code: "STALE_SUBSCRIBER_BINDING" },
  },
  {
    name: "stale subscriber binding generation is fenced",
    request: request("manager-a", 4, 1, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }),
    expected: { allowed: false, code: "STALE_SUBSCRIBER_BINDING" },
  },
  {
    name: "unknown target is denied without hidden discovery",
    request: request("manager-a", 4, 2, { kind: "worker", workerId: "hidden-worker", workerGeneration: workerGeneration(1) }),
    expected: { allowed: false, code: "UNKNOWN_TARGET" },
  },
  {
    name: "stale exact target generation is fenced",
    request: request("manager-a", 4, 2, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(6) }),
    expected: { allowed: false, code: "STALE_TARGET_GENERATION" },
  },
  {
    name: "Boss cross-run Manager supervision is denied",
    request: request("boss-a", 3, 5, { kind: "worker", workerId: "manager-worker-b", workerGeneration: workerGeneration(1) }),
    expected: { allowed: false, code: "CROSS_RUN_DENIED" },
  },
  {
    name: "Manager cannot self-authorize a role selector",
    request: request("manager-a", 4, 2, { kind: "role", bossRunId: "boss-run-a", role: "worker" }),
    expected: { allowed: false, code: "ROLE_SELECTOR_DENIED" },
  },
  {
    name: "Boss cannot authorize a non-Manager role selector",
    request: request("boss-a", 3, 5, { kind: "role", bossRunId: "boss-run-a", role: "boss" }),
    expected: { allowed: false, code: "ROLE_SELECTOR_DENIED" },
  },
  {
    name: "exact Worker selector cannot follow replacement",
    request: request("manager-a", 4, 2, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }, true),
    expected: { allowed: false, code: "FOLLOW_REPLACEMENT_DENIED" },
  },
  {
    name: "Worker to Worker supervision is denied",
    request: request("worker-principal-a", 2, 1, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }),
    expected: { allowed: false, code: "SUPERVISION_EDGE_DENIED" },
  },
  {
    name: "Manager to unrelated Worker supervision is denied",
    request: request("manager-a", 4, 2, { kind: "worker", workerId: "unregistered-worker-a", workerGeneration: workerGeneration(1) }),
    expected: { allowed: false, code: "SUPERVISION_EDGE_DENIED" },
  },
  {
    name: "Boss cannot supervise a replaced old Manager",
    request: request("boss-a", 3, 5, { kind: "worker", workerId: "old-manager-worker-a", workerGeneration: workerGeneration(2) }),
    expected: { allowed: false, code: "SUPERVISION_EDGE_DENIED" },
  },
  {
    name: "ordinary ownership cannot cross into a Boss run",
    request: request("owner-local", 2, 3, { kind: "worker", workerId: "worker-a", workerGeneration: workerGeneration(7) }),
    expected: { allowed: false, code: "CROSS_RUN_DENIED" },
  },
  {
    name: "Controller cannot treat a non-participant process as a run participant",
    request: request("controller-a", 8, 1, { kind: "worker", workerId: "unregistered-process-a", workerGeneration: workerGeneration(1) }),
    expected: { allowed: false, code: "SUPERVISION_EDGE_DENIED" },
  },
  {
    name: "Controller role selector rejects a participantless active target",
    request: request("controller-a", 8, 1, { kind: "role", bossRunId: "boss-run-a", role: "adversary" }),
    expected: { allowed: false, code: "SUPERVISION_EDGE_DENIED" },
  },
] as const;

export function stateForSupervisorAclVector(): SupervisorAclState {
  return structuredClone(SUPERVISOR_ACL_STATE);
}

export const SUPERVISION_VECTOR_CORPUS = {
  version: SUPERVISION_VECTOR_SCHEMA_VERSION,
  subscriptions: [MANAGER_WORKER_SUBSCRIPTION_VECTOR, BOSS_MANAGER_SUBSCRIPTION_VECTOR],
  subscriptionSchedulerNegativeVectors: LIFECYCLE_SUBSCRIPTION_SCHEDULER_NEGATIVE_VECTORS,
  activity: AUTHENTICATED_ACTIVITY_VECTOR,
  operationLease: ACTIVE_OPERATION_LEASE_VECTOR,
  externalWaitLease: EXTERNAL_WAIT_LEASE_VECTOR,
  trigger: LIFECYCLE_TRIGGER_VECTOR,
  inactivityEdges: INACTIVITY_EDGE_VECTORS,
  rebindMigrations: [COMMITTED_REBIND_MIGRATION_VECTOR, BLOCKED_REBIND_MIGRATION_VECTOR],
  aclState: SUPERVISOR_ACL_STATE,
  aclVectors: SUPERVISOR_ACL_VECTORS,
} as const;
