import { authorize, identityOf, parseReaders, type AccessIdentity, type Principal } from "./auth.js";
import { readStoreMeta, type StoreMeta } from "./db.js";
import { failure, json, methodNotAllowed } from "./errors.js";
import { serverTiming, trace } from "./observe.js";
import { handleGenerations } from "./routes/generations.js";
import { handleLearning } from "./routes/learning.js";
import { handleMemories } from "./routes/memories.js";
import { handleSnapshots } from "./routes/snapshots.js";
import { handleSync } from "./routes/sync.js";
import { handleTombstones } from "./routes/tombstones.js";

export interface Env {
  readonly READERS?: string;
  readonly ACCESS_TEAM_DOMAIN: string;
  readonly ACCESS_AUD: string;
  readonly DB: D1Database;
  readonly BUCKET: R2Bucket;
}

const PROTOCOL = 1;
const READ_METHODS = ["GET", "HEAD"] as const;

export default {
  async fetch(request: Request, env: Env, context: ExecutionContext): Promise<Response> {
    const timing = { d1: 0, r2: 0 };
    const authStarted = performance.now();
    let identity: AccessIdentity | null;
    let principal: Principal | null;
    try {
      identity = await identityOf(context, request, {
        teamDomain: env.ACCESS_TEAM_DOMAIN,
        audience: env.ACCESS_AUD,
      });
      principal = await trace(context, "auth", {}, async () =>
        authorize(env.DB, identity, parseReaders(env.READERS)));
    } catch {
      timing.d1 += performance.now() - authStarted;
      return failure(503, "unavailable", "authentication is unavailable", {
        "Server-Timing": serverTiming(timing),
      });
    }
    if (identity?.service_token_id !== undefined) {
      timing.d1 += performance.now() - authStarted;
    }
    if (principal === null) {
      return failure(403, "forbidden", "an authorized Access identity is required", {
        "Server-Timing": serverTiming(timing),
      });
    }
    const url = new URL(request.url);
    const { pathname } = url;
    if (pathname === "/api/v1/status") {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return methodNotAllowed(READ_METHODS, { "Server-Timing": serverTiming(timing) });
      }
      let store: StoreMeta | null;
      const started = performance.now();
      try {
        store = await trace(context, "status.d1", { count: 1 }, () => readStoreMeta(env.DB));
      } catch {
        timing.d1 += performance.now() - started;
        return failure(503, "unavailable", "store is unavailable", { "Server-Timing": serverTiming(timing) });
      }
      timing.d1 += performance.now() - started;
      if (store === null) {
        return failure(503, "unavailable", "store is not provisioned", {
          "Server-Timing": serverTiming(timing),
        });
      }
      return json(200, {
        protocol: PROTOCOL,
        store_id: store.id,
        principal,
        ready: true,
        counts: {},
      }, request.method === "HEAD", { "Server-Timing": serverTiming(timing) });
    }
    try {
      const sync = await handleSync(request, env, principal, pathname, timing);
      if (sync !== null) return sync;
      const generations = await handleGenerations(request, env, principal, pathname, url, timing);
      if (generations !== null) return generations;
      const snapshots = await handleSnapshots(request, env, principal, pathname, url, timing);
      if (snapshots !== null) return snapshots;
      const tombstones = await handleTombstones(request, env, principal, pathname, url, timing);
      if (tombstones !== null) return tombstones;
      const learning = await handleLearning(request, env, principal, pathname, url, timing);
      if (learning !== null) return learning;
      const memories = await handleMemories(request, env, principal, pathname, url, timing);
      if (memories !== null) return memories;
    } catch {
      return failure(503, "unavailable", "sync is unavailable", { "Server-Timing": serverTiming(timing) });
    }
    return failure(404, "not_found", "route not found", { "Server-Timing": serverTiming(timing) });
  },
} satisfies ExportedHandler<Env>;
