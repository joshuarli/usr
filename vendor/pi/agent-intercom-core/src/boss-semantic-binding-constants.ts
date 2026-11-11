/**
 * Leaf-only constants cryptographically committed by the Boss negotiation
 * contract. Keep this module free of imports so vector corpora may re-export
 * the reviewed bindings without introducing runtime initialization cycles.
 */
export const INTERCOM_BASE_PROTOCOL_VERSION = 3 as const;

export const PARTICIPANT_STATE_VECTOR_SCHEMA_VERSION = 1 as const;
export const PARTICIPANT_STATE_VECTORS_HASH =
  "0da19269f0c2befd9b22b8d146d6bd30450f3f0d64598148fd9317f36a5fc920" as const;

export const PARTICIPANT_STATE_TRANSITION_VECTOR_SCHEMA_VERSION = 1 as const;
export const PARTICIPANT_STATE_TRANSITION_VECTORS_HASH =
  "143fb362364d0742df565e8a02f778a493007e799c429cec8468f38e6520c86a" as const;

export const SUPERVISION_VECTOR_SCHEMA_VERSION = 1 as const;
export const SUPERVISION_VECTORS_HASH =
  "6795156a761aa7fa404c06657e7ca3438a99b1a7e4d2919308379a5448e14b33" as const;

export const FULL_WORKER_STORE_MIGRATION_VECTOR_VERSION = 2 as const;
export const FULL_WORKER_STORE_MIGRATION_VECTORS_HASH =
  "dfc3680c3b085a0a7a53266abe309d5710a181b7831d2582998dd38e76dca2bf" as const;
