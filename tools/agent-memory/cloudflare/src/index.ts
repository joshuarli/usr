import { authorize, identityOf, parseReaders } from "./auth";
import { readStoreMeta, type StoreMeta } from "./db";
import { failure, json, methodNotAllowed } from "./errors";

export interface Env {
  readonly READERS?: string;
  readonly DB: D1Database;
  readonly BUCKET: R2Bucket;
}

const PROTOCOL = 1;
const READ_METHODS = ["GET", "HEAD"] as const;

export default {
  async fetch(request: Request, env: Env, context: ExecutionContext): Promise<Response> {
    const principal = authorize(await identityOf(context), parseReaders(env.READERS));
    if (principal === null) {
      return failure(403, "forbidden", "an authorized Access identity is required");
    }
    const { pathname } = new URL(request.url);
    if (pathname === "/api/v1/status") {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return methodNotAllowed(READ_METHODS);
      }
      let store: StoreMeta | null;
      try {
        store = await readStoreMeta(env.DB);
      } catch {
        return failure(503, "unavailable", "store is unavailable");
      }
      if (store === null) {
        return failure(503, "unavailable", "store is not provisioned");
      }
      return json(200, {
        protocol: PROTOCOL,
        store_id: store.id,
        principal,
        ready: true,
        counts: {},
      }, request.method === "HEAD");
    }
    return failure(404, "not_found", "route not found");
  },
} satisfies ExportedHandler<Env>;
