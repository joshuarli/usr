import type { Principal } from "../auth.js";
import { json, methodNotAllowed } from "../errors.js";
import { serverTiming } from "../observe.js";
import {
  StaleLearningRevision,
  applyLearningDelta,
  decodeLearningDelta,
  readLearningState,
  type LearningState,
} from "../learning.js";
import { PROTOCOL, decodeOrigin } from "../protocol.js";
import type { Env } from "../index.js";
import {
  boundOrigin,
  readJson,
  refuse,
  versionOrError,
  type SyncTiming,
} from "./shared.js";

const STATE_PATH = "/api/v1/sync/learning/state";
const DELTAS_PATH = "/api/v1/sync/learning/deltas";

function stateJson(origin: string, state: LearningState): Record<string, unknown> {
  return {
    protocol: PROTOCOL,
    origin,
    revision: state.revision,
    epoch: state.epoch,
    digest: state.digest,
    records: state.records,
  };
}

function stale(origin: string, state: LearningState, timing: SyncTiming): Response {
  return json(409, {
    error: { code: "stale_revision", message: "base revision is stale" },
    state: stateJson(origin, state),
  }, false, { "Server-Timing": serverTiming(timing) });
}

async function state(
  request: Request,
  env: Env,
  principal: Principal,
  url: URL,
  timing: SyncTiming,
): Promise<Response> {
  if (request.method !== "GET") return methodNotAllowed(["GET"], { "Server-Timing": serverTiming(timing) });
  const origin = decodeOrigin(url.searchParams.get("origin"));
  if (origin === null) return refuse(400, "invalid_request", "origin is required", timing);
  const mismatch = boundOrigin(principal, origin, timing);
  if (mismatch !== null) return mismatch;
  const started = performance.now();
  let answer: LearningState;
  try {
    answer = await readLearningState(env.DB, origin);
  } finally {
    timing.d1 += performance.now() - started;
  }
  return json(200, stateJson(origin, answer), false, { "Server-Timing": serverTiming(timing) });
}

async function deltas(
  request: Request,
  env: Env,
  principal: Principal,
  timing: SyncTiming,
): Promise<Response> {
  if (request.method !== "POST") return methodNotAllowed(["POST"], { "Server-Timing": serverTiming(timing) });
  const body = await readJson(request, timing);
  if (!body.ok) return body.response;
  const version = versionOrError(body.value, timing);
  if (version !== null) return version;
  const delta = decodeLearningDelta(body.value);
  if (delta === null) return refuse(400, "invalid_request", "invalid learning delta", timing);
  const mismatch = boundOrigin(principal, delta.origin, timing);
  if (mismatch !== null) return mismatch;
  const started = performance.now();
  try {
    const current = await readLearningState(env.DB, delta.origin);
    const applied = await applyLearningDelta(env.DB, delta, current);
    return json(200, {
      protocol: PROTOCOL,
      origin: delta.origin,
      revision: applied.state.revision,
      epoch: applied.state.epoch,
      digest: applied.state.digest,
      records: applied.state.records,
      applied: applied.applied,
      deleted: applied.deleted,
      replayed: applied.replayed,
    }, false, { "Server-Timing": serverTiming(timing) });
  } catch (error) {
    if (error instanceof StaleLearningRevision || String(error).includes("stale_revision")) {
      const current = await readLearningState(env.DB, delta.origin);
      return stale(delta.origin, current, timing);
    }
    throw error;
  } finally {
    timing.d1 += performance.now() - started;
  }
}

export async function handleLearning(
  request: Request,
  env: Env,
  principal: Principal,
  pathname: string,
  url: URL,
  timing: SyncTiming,
): Promise<Response | null> {
  if (pathname !== STATE_PATH && pathname !== DELTAS_PATH) return null;
  if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
  if (pathname === STATE_PATH) return await state(request, env, principal, url, timing);
  return await deltas(request, env, principal, timing);
}
