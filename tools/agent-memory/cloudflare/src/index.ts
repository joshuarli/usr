import { authorize, identityOf, parseReaders } from "./auth";
import { readStoreMeta, type StoreMeta } from "./db";
import { failure, json, methodNotAllowed } from "./errors";
import { serverTiming, trace } from "./observe";

export interface Env {
  readonly READERS?: string;
  readonly DB: D1Database;
  readonly BUCKET: R2Bucket;
}

const PROTOCOL = 1;
const READ_METHODS = ["GET", "HEAD"] as const;

export default {
  async fetch(request: Request, env: Env, context: ExecutionContext): Promise<Response> {
    const timing = { d1: 0, r2: 0 };
    const principal = await trace(context, "auth", {}, async () =>
      authorize(await identityOf(context), parseReaders(env.READERS)));
    if (principal === null) {
      return failure(403, "forbidden", "an authorized Access identity is required", {
        "Server-Timing": serverTiming(timing),
      });
    }
    const { pathname } = new URL(request.url);
    if (pathname === "/api/v1/status") {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return methodNotAllowed(READ_METHODS, { "Server-Timing": serverTiming(timing) });
      }
      let store: StoreMeta | null;
      const started = performance.now();
      try {
        store = await trace(context, "status.d1", { count: 1 }, () => readStoreMeta(env.DB));
      } catch {
        timing.d1 = performance.now() - started;
        return failure(503, "unavailable", "store is unavailable", { "Server-Timing": serverTiming(timing) });
      }
      timing.d1 = performance.now() - started;
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
    return failure(404, "not_found", "route not found", { "Server-Timing": serverTiming(timing) });
  },
} satisfies ExportedHandler<Env>;
